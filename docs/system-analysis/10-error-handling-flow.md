# 10. Error Handling Flow

## 10.1 GitHub API Failures

### Failure Modes
1. **Authentication Failure** (HTTP 401): Expired or revoked access token
2. **Authorization Failure** (HTTP 403): Insufficient token scopes or rate limit
3. **Resource Not Found** (HTTP 404): Repository deleted, renamed, or inaccessible
4. **Validation Error** (HTTP 422): Malformed request (e.g., branch protection blocks PR)
5. **Server Error** (HTTP 5xx): GitHub service degradation or outage
6. **Network Timeout**: Request exceeds configured timeout (default 30s)

### Recovery Strategy

```
┌──────────────────────────────────────────────────────────────┐
│                GitHub API Error Handler                      │
│                                                              │
│  HTTP Status → Error Type → Recovery Action                 │
│                                                              │
│  401 ──▶ AuthExpired                                         │
│          │── Try GitHub App installation token (if available)│
│          │── If still failing → notify user: "Re-authenticate"│
│          └── Log: auth_failure {user_id, repo, timestamp}    │
│                                                              │
│  403 ──▶ RateLimited (X-RateLimit-Remaining: 0)             │
│          │── Parse X-RateLimit-Reset header                  │
│          │── Calculate wait_time = reset - now()              │
│          │── Queue operation with delay                       │
│          │── Notify user: "Rate limited, retrying in X min"  │
│          └── Log: rate_limit {endpoint, wait_time}            │
│                                                              │
│  403 ──▶ InsufficientScopes                                  │
│          │── Check token scopes via GET / (user endpoint)    │
│          │── Notify user: "Missing scope: {required_scope}"  │
│          └── Prompt re-authorization with expanded scopes    │
│                                                              │
│  404 ──▶ ResourceNotFound                                    │
│          │── Verify repo still exists via GET /repos         │
│          │── If deleted → mark repo as "disconnected"        │
│          │── If renamed → update full_name in DB             │
│          └── Notify user if repo no longer accessible        │
│                                                              │
│  422 ──▶ ValidationError                                     │
│          │── Parse error response body for details           │
│          │── Branch protection? → Suggest config change      │
│          │── Duplicate PR? → Return existing PR URL          │
│          └── Notify user with GitHub's error message         │
│                                                              │
│  5xx ──▶ ServerError                                         │
│          │── Retry with exponential backoff (3x, max 60s)    │
│          │── Check status.github.com for incidents           │
│          │── After 3 failures → queue for later retry        │
│          └── Log: github_outage {status, endpoint}           │
│                                                              │
│  Timeout ──▶ NetworkError                                    │
│          │── Retry once with shorter timeout (15s)           │
│          │── If still timing out → mark as "degraded"        │
│          └── Check connectivity via health endpoint          │
└──────────────────────────────────────────────────────────────┘
```

### Implementation Pseudocode

```python
async def github_api_call_with_recovery(
    client: GitHubClient,
    method: str,
    endpoint: str,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> Dict:
    """GitHub API call wrapper with comprehensive error recovery."""
    
    for attempt in range(max_retries):
        try:
            response = await client.request(method, endpoint)
            
            # Success
            if response.status_code < 400:
                return response.json()
            
            # Handle specific errors
            if response.status_code == 401:
                # Try token refresh
                new_token = await refresh_github_token(client.user_id)
                if new_token:
                    client.set_token(new_token)
                    continue
                raise GitHubAuthError("Authentication failed. Please re-authenticate.")
            
            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    wait_seconds = max(reset_time - time.time(), 0) + 1
                    logger.warning(f"GitHub rate limited. Waiting {wait_seconds}s")
                    await asyncio.sleep(wait_seconds)
                    continue
                raise GitHubPermissionError("Insufficient permissions.")
            
            if response.status_code == 404:
                raise GitHubNotFoundError(f"Resource not found: {endpoint}")
            
            if response.status_code == 422:
                error_detail = response.json()
                raise GitHubValidationError(error_detail.get("message", "Validation failed"))
            
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise GitHubServerError(f"GitHub server error: {response.status_code}")
        
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
            raise GitHubTimeoutError("Request timed out after retries")
    
    raise GitHubAPIError("Max retries exceeded")
```

---

## 10.2 Repository Access Failures

### Failure Modes
1. **Repository Deleted**: Repository no longer exists on GitHub
2. **Repository Renamed**: Full name changed; stored reference is stale
3. **Repository Archived**: Repository is read-only; cannot create PRs
4. **Access Revoked**: User's access to a private repo was revoked
5. **Repository Empty**: No commits on the default branch
6. **Clone Failure**: `git clone` fails due to LFS, submodules, or size

### Recovery Strategy

| Failure | Detection | Recovery | User Notification |
|---|---|---|---|
| Repo deleted | GitHub returns 404 on GET /repos | Mark repo as "disconnected" in DB; hide from dashboard | "Repository '{name}' is no longer accessible. It may have been deleted." |
| Repo renamed | GitHub returns 404; GET /users/{owner}/repos shows new name | Update `full_name` in DB automatically | "Repository renamed to '{new_name}'. Updated automatically." |
| Repo archived | `is_archived == true` in repo metadata | Disable workflow generation; show info banner | "Repository is archived. Workflow generation is disabled." |
| Access revoked | GitHub returns 403 on authenticated call | Mark repo as "limited_access"; prompt re-auth | "Access to '{name}' has been revoked. Please re-authenticate." |
| Empty repo | `git clone` succeeds but HEAD is unborn | Show message; use GitHub Tree API for basic file listing | "Repository is empty. Cannot perform full analysis." |
| Clone failure | `git clone` exit code != 0 | Fall back to GitHub Tree API; mark analysis_mode = "api" | "Limited analysis: Using GitHub API (clone unavailable)." |
| Large repo (> 100 MB) | `git clone` exceeds size threshold | Cancel clone; use GitHub Tree API | "Repository too large for full clone. Using API-based analysis." |

---

## 10.3 Rate Limit Handling

### GitHub Rate Limit Model
- **Primary Limit**: 5000 requests per hour per authenticated user
- **Secondary Limit**: Concurrent request throttling (returns 403 with `retry-after`)
- **Search API**: 30 requests per minute

### Rate Limit Monitor

```python
class RateLimitMonitor:
    """Tracks GitHub API rate limit consumption."""
    
    def __init__(self):
        self.remaining = 5000
        self.reset_time = 0
        self.used_this_window = 0
    
    def update_from_response(self, response):
        """Update from GitHub response headers."""
        self.remaining = int(response.headers.get("X-RateLimit-Remaining", self.remaining))
        self.reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
        self.used_this_window = int(response.headers.get("X-RateLimit-Used", 0))
    
    def can_make_request(self, required: int = 1) -> bool:
        """Check if there are enough remaining requests."""
        return self.remaining >= required
    
    def wait_until_reset(self) -> float:
        """Calculate seconds until rate limit reset."""
        return max(self.reset_time - time.time(), 0)
    
    def should_throttle(self, threshold: int = 50) -> bool:
        """Determine if request should be queued to preserve remaining quota."""
        if self.remaining < threshold:
            return True
        return False
```

### Rate Limit Recovery Flow

```
┌────────────────────┐
│ Before API Call    │
│ Check remaining    │
└────────┬───────────┘
         │
         ▼
  ┌─────────────────┐
  │ Remaining > 100?│──Yes──▶ Execute request normally
  └────────┬────────┘
           │ No
           ▼
  ┌─────────────────────┐
  │ Remaining > 10?     │──Yes──▶ Execute with warning log
  └────────┬────────────┘
           │ No
           ▼
  ┌─────────────────────────┐
  │ Queue operation with    │
  │ delay = min(reset_time, │
  │            60 seconds)  │
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────┐
  │ During rate-limited  │
  │ window:              │
  │ - Prioritize         │
  │   critical ops       │
  │ - Cache responses    │
  │ - Use conditional    │
  │   requests (ETag)    │
  │ - Notify user with   │
  │   estimated wait     │
  └──────────────────────┘
```

### OpenRouter Rate Limit Strategy

```python
class OpenRouterRateLimiter:
    """Manages OpenRouter API rate limits and cost."""
    
    DAILY_TOKEN_BUDGET = 1_000_000    # Configurable per user
    COST_PER_1K_TOKENS = {
        "primary": 0.015,      # $0.015/1K tokens
        "secondary": 0.010,
        "fallback": 0.0005,
        "lightweight": 0.0002,
    }
    
    async def check_budget(self, user_id: str, estimated_tokens: int, model_tier: str) -> bool:
        """Check if user has remaining token budget."""
        daily_used = await redis.get(f"tokens:daily:{user_id}")
        cost_estimate = (estimated_tokens / 1000) * self.COST_PER_1K_TOKENS[model_tier]
        
        if daily_used + estimated_tokens > self.DAILY_TOKEN_BUDGET:
            raise TokenBudgetExceededError(
                f"Daily token budget exceeded. "
                f"Used: {daily_used}, Limit: {self.DAILY_TOKEN_BUDGET}"
            )
        return True
```

---

## 10.4 LLM Failures

### Failure Modes
1. **LLM Timeout**: OpenRouter request exceeds timeout (30s default)
2. **LLM Rate Limit**: OpenRouter rate limits the API key
3. **LLM Returns Invalid JSON**: Malformed structured output
4. **LLM Returns Empty Response**: No content in choices
5. **LLM Returns Truncated Output**: `finish_reason == "length"`
6. **LLM Hallucination**: Output contains factually incorrect information
7. **LLM Content Filter**: Response blocked by safety filters

### Recovery Strategy

| Failure | Retry? | Recovery | Max Attempts |
|---|---|---|---|
| Timeout | Yes | Exponential backoff: 2s, 4s, 8s | 3 |
| Rate limit | Yes | Wait for `Retry-After` header duration | 2 |
| Invalid JSON | Yes | Request self-correction: "Your previous response was not valid JSON. Please fix it." | 2 |
| Empty response | Yes | Retry with reduced temperature (0.1) | 2 |
| Truncated output | Yes | Send continuation prompt: "Please continue from where you left off." | 1 |
| Hallucination | Yes | Cross-validate against deterministic knowledge base; if mismatch, retry with stricter prompt | 1 |
| Content filter | No | Log the blocked prompt; notify user that generation was blocked | 0 |

### LLM Error Handler Implementation

```python
async def llm_call_with_comprehensive_recovery(
    client: OpenRouterClient,
    model_tier: str,
    messages: List[Dict],
    expected_schema: Dict | None = None,
    max_attempts: int = 3
) -> Dict:
    """LLM call with comprehensive error recovery and validation."""
    
    attempt = 0
    model = client.MODELS[model_tier]
    
    while attempt < max_attempts:
        try:
            response = await client.chat_completion(
                model=model,
                messages=messages,
                temperature=0.3 if attempt == 0 else 0.1,
                max_tokens=4096
            )
            
            content = response["choices"][0]["message"]["content"]
            
            # Check for empty response
            if not content or not content.strip():
                raise LLMEmptyResponseError("LLM returned empty response")
            
            # Check for truncated response
            finish_reason = response["choices"][0].get("finish_reason", "")
            if finish_reason == "length":
                if attempt < max_attempts - 1:
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": "Continue your response. Your output was truncated."})
                    attempt += 1
                    continue
            
            # If structured output is expected, parse and validate
            if expected_schema:
                parsed = parse_and_validate_json(content, expected_schema)
                if parsed is None:
                    # Invalid JSON — ask LLM to self-correct
                    if attempt < max_attempts - 1:
                        messages.append({"role": "assistant", "content": content})
                        messages.append({
                            "role": "user",
                            "content": f"Your response was not valid JSON matching the required schema. Please fix it and return ONLY valid JSON. Required schema: {json.dumps(expected_schema)}"
                        })
                        attempt += 1
                        continue
                return parsed
            else:
                return {"content": content}
        
        except (TimeoutError, ConnectionError, httpx.HTTPStatusError) as e:
            if attempt < max_attempts - 1:
                delay = 2.0 * (2 ** attempt)
                await asyncio.sleep(delay)
                
                # Fall back to cheaper model on timeout
                if isinstance(e, TimeoutError) and attempt == 1:
                    model = client.MODELS["fallback"] if model_tier != "lightweight" else model
                
                attempt += 1
                continue
            raise
    
    raise LLMExhaustedError(f"LLM call failed after {max_attempts} attempts")
```

---

## 10.5 Invalid Workflow Generation

### Failure Modes
1. **Invalid YAML Syntax**: LLM outputs malformed YAML
2. **Missing Required Fields**: No `on`, `jobs`, or `runs-on` field
3. **Invalid Action References**: Referenced action doesn't exist
4. **Deprecated Action Usage**: Using `@main` instead of pinned version
5. **Security Tool Misconfiguration**: Tool configured for wrong language
6. **Incompatible Steps**: Step commands that fail for the detected tech stack
7. **Oversized Workflow**: Exceeds GitHub's 512 KB file limit

### Recovery Flow

```
┌───────────────────────────────┐
│ Generated Workflow YAML       │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ 1. YAML Syntax Check          │
│    yaml.safe_load()           │
└────────┬──────────┬───────────┘
         │ PASS     │ FAIL
         ▼          ▼
┌────────────┐  ┌──────────────────────────────┐
│ 2. Schema  │  │ Repair: YAML auto-formatter   │
│    Check   │  │ (fix indent, quotes, brackets)│
└──┬─────┬───┘  │ → Re-parse                    │
   │PASS │FAIL  └───────────────┬───────────────┘
   ▼     ▼                      │
   OK  ┌──────────────────────┐ │
       │ 2a. Missing fields?  │◀┘
       │ → Add defaults       │
       │ 2b. Wrong types?     │
       │ → Type coercion      │
       │ 2c. Invalid structure│
       │ → LLM repair         │
       └──────────┬───────────┘
                  │ (re-validate)
                  ▼
   ┌──────────────────────────┐
   │ 3. Security Policy Check │
   └──┬──────┬────────────────┘
      │PASS  │FAIL
      ▼      ▼
      OK  ┌──────────────────────────┐
          │ 3a. Missing security tool│
          │ → Insert job template    │
          │ 3b. Unpinned action      │
          │ → Pin to latest version  │
          │ 3c. Missing permissions  │
          │ → Add permissions block  │
          └──────────┬───────────────┘
                     │ (re-validate)
                     ▼
      ┌──────────────────────────┐
      │ 4. Semantic Check (LLM)  │
      └──┬──────┬────────────────┘
         │PASS  │FAIL
         ▼      ▼
    ┌────────┐ ┌──────────────────────────┐
    │ PASS ✓ │ │ 4. LLM-based repair:     │
    │ PR     │ │ "Fix the logical errors  │
    │ Ready  │ │  in this workflow..."    │
    └────────┘ └──────────┬───────────────┘
                          │ (max 3 iterations)
                          ▼
                   ┌────────────────┐
                   │ Still failing? │
                   └───┬────────┬───┘
                       │No      │Yes
                       ▼        ▼
                    ┌─────┐ ┌──────────────┐
                    │ PASS│ │ Manual Review│
                    └─────┘ │ (user fixes) │
                            └──────────────┘
```

---

## 10.6 YAML Syntax Errors

### Detection & Categorization

```python
class YAMLErrorHandler:
    """Handles YAML syntax errors with specific fix strategies."""
    
    ERROR_PATTERNS = {
        r"mapping values are not allowed": {
            "cause": "Indentation error",
            "fix": "apply_yaml_formatter",
            "auto_fixable": True,
        },
        r"found unexpected end of stream": {
            "cause": "Unclosed quote or bracket",
            "fix": "find_and_close_unclosed",
            "auto_fixable": True,
        },
        r"found character.*cannot start any token": {
            "cause": "Tab character used instead of spaces",
            "fix": "replace_tabs_with_spaces",
            "auto_fixable": True,
        },
        r"expected.*but found": {
            "cause": "Wrong YAML structure",
            "fix": "llm_based_repair",
            "auto_fixable": False,  # Requires LLM
        },
        r"duplicated mapping key": {
            "cause": "Duplicate key in mapping",
            "fix": "remove_duplicate_keys",
            "auto_fixable": True,
        },
    }
    
    def diagnose_and_fix(self, yaml_string: str) -> Tuple[str, List[Dict]]:
        """Diagnose YAML errors and apply appropriate fixes."""
        fixes_applied = []
        
        try:
            yaml.safe_load(yaml_string)
            return yaml_string, []  # No errors
        except yaml.YAMLError as e:
            error_msg = str(e)
            line = e.problem_mark.line + 1 if hasattr(e, 'problem_mark') else None
            
            # Match error pattern
            for pattern, strategy in self.ERROR_PATTERNS.items():
                if re.search(pattern, error_msg):
                    if strategy["auto_fixable"]:
                        fixed = self.apply_deterministic_fix(yaml_string, strategy["fix"])
                        fixes_applied.append({
                            "line": line,
                            "error": error_msg[:100],
                            "fix_strategy": strategy["fix"],
                            "auto_applied": True,
                        })
                        return self.diagnose_and_fix(fixed)  # Recursive re-check
                    else:
                        # Requires LLM
                        return yaml_string, [{
                            "line": line,
                            "error": error_msg[:100],
                            "fix_strategy": strategy["fix"],
                            "auto_applied": False,
                            "requires_llm": True,
                        }]
            
            # Unknown error pattern
            return yaml_string, [{
                "line": line,
                "error": error_msg[:200],
                "fix_strategy": "llm_based_repair",
                "auto_applied": False,
                "requires_llm": True,
            }]
```

---

## 10.7 Security Tool Execution Failures

### Failure Modes (in GitHub Actions context)
1. **Tool Not Installed**: Action image not found or incompatible
2. **Tool Configuration Error**: Invalid config file or flags
3. **Tool Timeout**: Scan takes longer than `timeout-minutes`
4. **Tool Out of Memory**: Runner memory insufficient
5. **Tool Rate Limited**: External API rate limit (e.g., CodeQL upload)
6. **Tool Artifact Upload Failed**: SARIF upload to GitHub fails

### Recovery Strategy

| Failure | Detection | Recovery |
|---|---|---|
| Tool not installed | Check conclusion: "failure" + logs contain "command not found" | The workflow hasn't changed; this is a transient GitHub Actions issue. Wait and re-run. |
| Config error | Check conclusion + SARIF validation failure | Analyze error logs; suggest config fix in repair prompt |
| Tool timeout | Check conclusion: "timed_out" | Increase `timeout-minutes` in repair; split large scans |
| OOM | Check conclusion: "failure" + logs contain "Out of memory" | Suggest larger runner (`ubuntu-latest-16-cores`) |
| Rate limited | Check conclusion: "failure" + logs contain "rate limit" | Add retry with delay in workflow; notify user |
| Upload failed | Missing SARIF artifact in artifact list | Retry upload step; log for investigation |

### Post-Execution Recovery

```python
async def handle_security_tool_failure(run_id: str, failed_jobs: List[Dict]):
    """Handle security tool execution failures after workflow completion."""
    
    for job in failed_jobs:
        # Analyze failure reason from logs
        logs = await fetch_job_logs(run_id, job["id"])
        failure_reason = classify_failure(logs)
        
        if failure_reason == "transient":
            # Auto re-run the job
            await github_client.rerun_job(run_id, job["id"])
            logger.info(f"Auto-rerunning transient failure: {job['name']}")
        
        elif failure_reason == "config_error":
            # Generate fix suggestion
            suggestion = await llm_suggest_config_fix(job["name"], logs)
            # Store for user review
            await store_fix_suggestion(run_id, job["name"], suggestion)
        
        elif failure_reason == "resource_exhaustion":
            # Suggest runner upgrade
            await store_recommendation(
                run_id,
                type="cicd_hardening",
                message=f"Job '{job['name']}' exceeded resources. Consider upgrading to a larger runner."
            )
        
        # Mark finding as partial if only some tools failed
        await update_run_status(run_id, "partially_completed")
```

---

## 10.8 Database Failures

### Failure Modes
1. **Connection Pool Exhaustion**: No available connections
2. **Query Timeout**: Long-running query exceeds statement timeout
3. **Deadlock**: Concurrent transactions conflict
4. **Constraint Violation**: Unique constraint or foreign key violation
5. **Disk Full**: PostgreSQL runs out of storage
6. **Replication Lag**: Read replica is behind primary

### Recovery Strategy

```python
class DatabaseErrorHandler:
    
    @staticmethod
    async def execute_with_recovery(session: AsyncSession, operation: Callable):
        """Execute database operation with comprehensive recovery."""
        
        max_retries = 3
        base_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                result = await operation(session)
                await session.commit()
                return result
            
            except asyncpg.exceptions.TooManyConnectionsError:
                # Connection pool exhausted — wait and retry
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
            
            except asyncpg.exceptions.QueryCanceledError:
                # Query timeout — optimize or split query
                logger.error(f"Query timeout. Attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0)
                    continue
                raise DatabaseTimeoutError("Query exceeded timeout")
            
            except asyncpg.exceptions.DeadlockDetectedError:
                # Deadlock — retry the transaction
                await session.rollback()
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise DatabaseDeadlockError("Transaction deadlock")
            
            except asyncpg.exceptions.UniqueViolationError as e:
                # Duplicate — handle gracefully
                await session.rollback()
                logger.warning(f"Duplicate key violation: {e}")
                return None  # Idempotent operation
            
            except asyncpg.exceptions.ForeignKeyViolationError as e:
                # Referential integrity — log and fail
                await session.rollback()
                logger.error(f"Foreign key violation: {e}")
                raise DatabaseIntegrityError(f"Referenced record does not exist: {e}")
            
            except asyncpg.exceptions.DiskFullError:
                # Critical — alert operations
                await session.rollback()
                await alert_operations("PostgreSQL disk full!")
                raise DatabaseCriticalError("Database disk is full")
        
        raise DatabaseExhaustedError("Max retries exceeded")
```

### Database Health Monitoring

```python
async def health_check_database() -> Dict:
    """Comprehensive database health check."""
    checks = {}
    
    # Connection check
    try:
        await db.execute("SELECT 1")
        checks["connection"] = "healthy"
    except Exception as e:
        checks["connection"] = f"unhealthy: {e}"
    
    # Connection pool status
    pool = db.get_pool()
    checks["pool"] = {
        "size": pool.size,
        "free": pool.freesize,
        "checked_in": pool.size - pool.freesize,
    }
    
    # Replication lag
    if replication_enabled:
        lag = await db.execute("SELECT extract(epoch FROM now() - pg_last_xact_replay_timestamp())")
        checks["replication_lag_seconds"] = lag
    
    # Disk usage
    disk_usage = await db.execute("""
        SELECT pg_database_size(current_database()) / 1024 / 1024 AS size_mb
    """)
    checks["database_size_mb"] = disk_usage
    
    return checks
```

---

## 10.9 Network Failures

### Failure Modes
1. **DNS Resolution Failure**: Cannot resolve GitHub/OpenRouter hostnames
2. **Connection Refused**: Service is down or firewall blocks connection
3. **Connection Reset**: Abrupt connection termination (load balancer timeout)
4. **TLS Handshake Failure**: Certificate expired or mismatch
5. **Slow Network**: High latency or packet loss

### Recovery Strategy

```python
class NetworkErrorHandler:
    
    @staticmethod
    async def execute_with_network_recovery(
        operation: Callable,
        service_name: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        """Execute network operation with comprehensive recovery."""
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await operation()
            
            except aiodns.error.DNSError:
                # DNS failure — wait for DNS to recover
                logger.error(f"DNS resolution failed for {service_name}")
                delay = min(base_delay * (3 ** attempt), max_delay)  # Steeper backoff
                await asyncio.sleep(delay)
                last_exception = NetworkDNSError(f"DNS failure for {service_name}")
                continue
            
            except aiohttp.ClientConnectorError as e:
                # Connection refused — service might be starting
                if "Connection refused" in str(e):
                    logger.warning(f"Connection refused for {service_name}. Retrying...")
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    await asyncio.sleep(delay)
                    last_exception = NetworkConnectionRefusedError(f"{service_name} refused connection")
                    continue
                raise
            
            except aiohttp.ClientOSError as e:
                # Connection reset — retry with backoff
                if "Connection reset" in str(e):
                    logger.warning(f"Connection reset by {service_name}. Retrying...")
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    await asyncio.sleep(delay)
                    last_exception = NetworkConnectionResetError(f"{service_name} reset connection")
                    continue
                raise
            
            except ssl.SSLError as e:
                # TLS failure — do NOT retry (security risk)
                logger.critical(f"TLS handshake failed for {service_name}: {e}")
                raise NetworkTLSError(f"TLS validation failed for {service_name}")
            
            except asyncio.TimeoutError:
                # Timeout — retry with longer timeout
                logger.warning(f"Timeout for {service_name}. Attempt {attempt + 1}")
                delay = min(base_delay * (2 ** attempt), max_delay)
                await asyncio.sleep(delay)
                last_exception = NetworkTimeoutError(f"Timeout connecting to {service_name}")
                continue
        
        raise NetworkExhaustedError(
            f"Failed to connect to {service_name} after {max_retries} attempts. "
            f"Last error: {last_exception}"
        )
```

### Circuit Breaker Pattern

```python
class CircuitBreaker:
    """Prevents cascading failures by stopping calls to failing services."""
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, operation: Callable):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = await operation()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info(f"Circuit breaker '{self.name}' CLOSED (recovered)")
            return result
        
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker '{self.name}' OPEN ({self.failure_count} failures)")
            
            raise
```

---

## 10.10 Global Error Recovery Orchestration

### Error Severity Classification

| Severity | Definition | User Impact | Recovery Strategy |
|---|---|---|---|
| **CRITICAL** | System cannot function | Service unavailable | Immediate alert; auto-restart; manual intervention |
| **HIGH** | Core feature broken | Cannot complete current operation | Auto-recovery with retry; notify user on failure |
| **MEDIUM** | Non-critical feature affected | Degraded experience | Graceful degradation; log and continue |
| **LOW** | Cosmetic issue | User unaware | Log only; fix in next release |

### Global Error Handler

```python
async def global_error_handler(request: Request, call_next):
    """FastAPI middleware for global error handling."""
    try:
        response = await call_next(request)
        return response
    except GitHubAuthError as e:
        return JSONResponse(status_code=401, content={"error": "github_auth", "message": str(e)})
    except GitHubRateLimitError as e:
        return JSONResponse(status_code=429, content={"error": "rate_limit", "message": str(e), "retry_after": e.retry_after})
    except LLMExhaustedError as e:
        return JSONResponse(status_code=502, content={"error": "ai_unavailable", "message": "AI service temporarily unavailable"})
    except DatabaseCriticalError as e:
        return JSONResponse(status_code=503, content={"error": "database_unavailable", "message": "Service temporarily unavailable"})
    except CircuitBreakerOpenError as e:
        return JSONResponse(status_code=503, content={"error": "service_unavailable", "message": str(e)})
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return JSONResponse(status_code=500, content={"error": "internal_error", "message": "An unexpected error occurred"})
```
