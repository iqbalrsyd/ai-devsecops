import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.services.llm_service import get_llm


DOMAIN_LIBRARY_INDICATORS: dict[str, dict] = {
    "e-commerce": {
        "libraries": [
            # Global
            "stripe", "@stripe/stripe-js", "stripe-node", "braintree", "paypal",
            "paypal-rest-sdk", "square", "adyen", "razorpay", "shopify-api",
            "woocommerce", "magento", "bigcommerce",
            # Indonesia payment processors
            "midtrans-client", "midtrans", "@midtrans/midtrans-node",
            "xendit-node", "xendit", "xendit-node-sdk",
            "doku-node", "doku",
            "midtrans-node",
            "gopay-node", "gopay",
            "ovo-node", "dana-node", "shopeepay-node",
        ],
        "entities": [
            "order", "product", "cart", "payment", "checkout", "invoice",
            "customer", "shipment", "discount", "coupon", "billing",
        ],
        "routes": ["/checkout", "/cart", "/payment", "/products", "/orders", "/shop"],
        "threats": [
            "Stripe/Midtrans/PayPal key hardcoded in source",
            "SQL injection di form checkout",
            "CSRF di payment endpoint",
            "Credit card data exposure di logs",
            "Price/quantity tampering",
        ],
    },
    "blog": {
        "libraries": [
            "marked", "showdown", "sanitize-html", "dompurify", "markdown-it",
            "remark", "rehype", "ghost", "hexo", "jekyll",
        ],
        "entities": [
            "post", "comment", "tag", "category", "author", "article",
            "subscriber", "newsletter",
        ],
        "routes": ["/posts", "/comments", "/blog", "/articles", "/tags", "/archive"],
        "threats": [
            "XSS di rendering komentar",
            "File upload bypass untuk gambar",
            "CSRF di form komentar",
            "Content injection via markdown",
            "Path traversal di static file serving",
        ],
    },
    "iot": {
        "libraries": [
            "mqtt", "amqp", "paho-mqtt", "azure-iot", "aws-iot",
            "google-cloud-iot", "thinger-io", "coap", "modbus",
        ],
        "entities": [
            "device", "sensor", "telemetry", "actuator", "gateway", "firmware",
            "reading", "alert", "threshold",
        ],
        "routes": ["/devices", "/telemetry", "/sensors", "/firmware", "/alerts"],
        "threats": [
            "Device authentication bypass",
            "MQTT tanpa enkripsi",
            "Firmware tampering",
            "Replay attack di telemetry stream",
            "Default credentials di device provisioning",
        ],
    },
}

VALID_DOMAINS = list(DOMAIN_LIBRARY_INDICATORS.keys()) + ["general"]

DOMAIN_CONFIDENCE_THRESHOLD = 0.50

# Minimum raw heuristic score required for the LLM's domain pick to
# be accepted. The raw score is the sum of weighted hits:
#   library 3.0 + entity 2.0 + route 1.5 per matching signal.
# Threshold 3.0 = at least 1 library match (or 1.5 routes, or 1.5
# entities). When the LLM confidently picks a domain but the
# heuristic disagrees (e.g. a healthcare repo has a single
# `PAYMENT_GATEWAY_KEY` constant that the LLM over-weights toward
# e-commerce with score=0), the heuristic veto in
# `domain_detection_node` falls back to "general" so the pipeline
# only emits standard jobs.
MIN_HEURISTIC_SCORE = 3.0


def _extract_library_names(package_files: dict) -> list[str]:
    """Extract library names from common package manifest files.

    Supports manifests at any path depth:
      * package.json (root or any subdir, e.g. client/package.json)
      * requirements.txt / Pipfile (root or subdir)
      * pyproject.toml
      * go.mod
    The basename is matched (case-insensitive) so manifests inside
    service-boundary subdirs (client/, server/, backend/, ...) are
    picked up the same as root-level ones.
    """
    libs: list[str] = []

    for fname, content in (package_files or {}).items():
        if not content:
            continue
        # Compare by basename so client/package.json, server/package.json,
        # and root package.json all match the same handler.
        basename = fname.rsplit("/", 1)[-1].lower()
        try:
            if basename == "package.json":
                data = json.loads(content)
                for section in ("dependencies", "devDependencies", "peerDependencies"):
                    libs.extend((data.get(section) or {}).keys())
            elif basename in ("requirements.txt", "pipfile"):
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    pkg = re.split(r"[<>=!~\[]", line, 1)[0].strip()
                    if pkg:
                        libs.append(pkg.lower())
            elif basename == "pyproject.toml":
                for m in re.finditer(r'"([A-Za-z0-9_.\-]+)"\s*=\s*\[', content):
                    libs.append(m.group(1).lower())
            elif basename == "go.mod":
                for m in re.finditer(r"^\s*([A-Za-z0-9_.\-/]+)\s+v[0-9]", content, re.M):
                    libs.append(m.group(1).lower())
        except Exception:
            continue

    return libs


def _extract_entity_names(source_files: list) -> list[str]:
    """Extract candidate model/entity names from source filenames.

    Matches:
    - top-level files (User.py, Product.js)
    - files in models/, entities/, services/, schemas/, domain/, routes/ dirs
    - service directory names (services/patient/, services/appointment/)
    - Dto/Entity/Model/Schema suffix names
    """
    entities: list[str] = []
    entity_patterns = (
        r"^([A-Za-z]+)\.(?:py|java|go|ts|js|rb|php|cs|kt|swift)$",
        r"(?:models?|entities|services|schemas|domain|routes?|controllers?|handlers?|api)/([A-Za-z]+)\.(?:py|java|go|ts|js|rb|php|cs)$",
        r"(?:services|apps|modules|domains?)/([A-Za-z]+)/",  # service dir names
        r"([A-Z][A-Za-z]+(?:Dto|Entity|Model|Schema))",
    )
    for entry in source_files or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or entry.get("name") or "").lower()
        for pat in entity_patterns:
            m = re.search(pat, path)
            if m:
                entities.append(m.group(1).lower())
                break
    return entities


def _extract_route_hints(source_files: list) -> list[str]:
    """Extract candidate route paths from route handler files."""
    routes: list[str] = []
    route_patterns = (
        r'@(?:app|router|bp|Blueprint)\.(?:get|post|put|delete|patch)\(["\']([^"\']+)',
        r'@(?:Get|Post|Put|Delete|Patch)\(["\']([^"\']+)',
        r'router\.(?:get|post|put|delete|patch)\(["\']([^"\']+)',
    )
    for entry in source_files or []:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", "")
        if not content:
            continue
        for pat in route_patterns:
            for m in re.finditer(pat, content):
                routes.append(m.group(1).lower())
    return routes


def _extract_candidate_signals(state: PipelineEngineerState) -> dict:
    """Step 1: deterministic signal extraction."""
    repo_name = (state.get("repository_name") or state.get("repository_full_name", "") or "").lower()
    repo_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name
    repo_description = (state.get("repository_description") or "").lower()

    package_files = state.get("repository_files") or {}
    libraries = _extract_library_names(package_files)

    source_files = state.get("source_files") or []
    entities = _extract_entity_names(source_files)
    routes = _extract_route_hints(source_files)

    # Inject domain keyword tokens from repo name and description so a
    # repository called "ecommerce-..." or with a description that says
    # "vulnerable e-commerce" still scores on the heuristic even when
    # no entity/route pattern matches.
    NAME_DOMAIN_KEYWORDS = {
        "e-commerce", "ecommerce", "ecommerce-", "commerce", "shop", "store",
        # Common e-commerce project names that don't contain the words
        # above but are clearly online-shop clones. "flipkart", "amazon",
        # "tokopedia", "shopee" all use a market-place-style product/cart
        # domain that the e-commerce indicator set already covers.
        "flipkart", "amazon", "tokopedia", "shopee", "bukalapak",
        "lazada", "toko", "toko-online", "olshop", "olshop-",
        "blog", "cms", "forum",
        "iot", "device", "sensor", "telemetry", "mqtt",
    }
    name_desc_blob = f"{repo_name} {repo_description}"
    name_tokens = [
        kw for kw in NAME_DOMAIN_KEYWORDS
        if kw in name_desc_blob
    ]
    for tok in name_tokens:
        base = tok.rstrip("-")
        if base:
            entities.append(base)

    return {
        "repo_name": repo_name,
        "repo_description": repo_description,
        "libraries": libraries,
        "entities": entities,
        "routes": routes,
    }


def _score_domain(detected_libraries: set[str], detected_entities: set[str], detected_routes: set[str]) -> dict[str, float]:
    """Compute per-domain score from signals.

    Scoring weight:
      - library match: 3.0
      - entity match: 2.0
      - route match: 1.5
    Normalized to 0.0-1.0.
    """
    scores: dict[str, float] = {}
    for domain, indicators in DOMAIN_LIBRARY_INDICATORS.items():
        lib_hits = len(detected_libraries & set(indicators["libraries"]))
        ent_hits = len(detected_entities & set(indicators["entities"]))
        route_hits = len(detected_routes & set(indicators["routes"]))

        raw = (lib_hits * 3.0) + (ent_hits * 2.0) + (route_hits * 1.5)
        scores[domain] = raw

    if not scores or max(scores.values()) == 0:
        return {"general": 1.0}

    top = max(scores.values())
    normalized = {d: (s / top if top > 0 else 0.0) for d, s in scores.items()}

    top_domain = max(normalized, key=normalized.get)
    top_score = normalized[top_domain]
    confidence = min(1.0, top_score * 0.85 + 0.15)
    normalized[top_domain] = confidence
    return normalized


def _score_domain_raw(detected_libraries: set[str], detected_entities: set[str], detected_routes: set[str]) -> dict[str, float]:
    """Return the raw (unnormalised) heuristic score per domain.

    The raw score is the sum of weighted hits (library 3.0, entity 2.0,
    route 1.5). Used by the domain detection node to decide whether the
    heuristic has STRONG enough evidence to override a low-confidence
    LLM answer. Requirement 7: do NOT default to "general" if the raw
    score is >= 1.0 (one library, entity, or route hit).
    """
    scores: dict[str, float] = {}
    for domain, indicators in DOMAIN_LIBRARY_INDICATORS.items():
        lib_hits = len(detected_libraries & set(indicators["libraries"]))
        ent_hits = len(detected_entities & set(indicators["entities"]))
        route_hits = len(detected_routes & set(indicators["routes"]))
        scores[domain] = (lib_hits * 3.0) + (ent_hits * 2.0) + (route_hits * 1.5)
    return scores


DOMAIN_DETECTION_PROMPT = """You are classifying the web application domain of a GitHub repository.

The supported domains have been reduced to THREE (skripsi Bab 3, revisi 3-domain & 2-architecture):
- e-commerce   (Information Systems — online shop, payment, catalog)
- blog         (Information Systems — content publishing, comments, markdown)
- iot          (Embedded Systems — devices, telemetry, MQTT, firmware)
- general      (fallback when no clear domain signal)

DO NOT invent other domains. Map the repository into ONE of the four values above.

When domain is "e-commerce", also identify the payment processor (sub_type):
- "stripe"   - Stripe, @stripe/stripe-js, stripe-node
- "midtrans" - midtrans-client, @midtrans/midtrans-node (Indonesia)
- "xendit"   - xendit-node, xendit (Indonesia)
- "doku"     - doku-node (Indonesia)
- "paypal"   - paypal-rest-sdk, paypal
- "braintree" - braintree
- "razorpay" - razorpay (India)
- "adyen"    - adyen
- "square"   - square
- "multi"    - multiple payment processors detected
- "unknown"  - e-commerce but cannot determine processor
- "none"     - not e-commerce

ALSO identify the business features present in the application.
Available features (choose any that match the codebase):
- authentication (login, signup, session, JWT, OAuth)
- catalog (product listing, search, browse)
- shopping_cart (add-to-cart, cart management)
- checkout (checkout flow, order summary)
- payment (payment processing, payment gateway integration)
- order_management (order history, order tracking)
- database (DB models, migrations, ORM usage)
- file_upload (file/image upload, multipart handling)
- mqtt (MQTT pub/sub, paho-mqtt)
- telemetry (sensor data, telemetry stream)
- firmware (firmware update, device flashing)
- device_management (device registration, provisioning)
- blog_posting (post creation, article management)
- comment_system (comments, replies)

Repository name: {repo_name}
Repository description: {repo_description}

Detected libraries (top 50): {libraries}
Detected entity/model names (top 30): {entities}
Detected route hints (top 30): {routes}

Candidate domain scores from deterministic signal matching:
{scores}

Return ONLY valid JSON:
{{
  "domain": "e-commerce|blog|iot|general",
  "sub_type": "stripe|midtrans|xendit|doku|paypal|braintree|razorpay|adyen|square|multi|unknown|none",
  "confidence": 0.0-1.0,
  "evidence": ["evidence 1", "evidence 2", ...],
  "domain_threats": ["threat 1 specific to this domain", ...],
  "features": ["authentication", "checkout", ...]
}}
"""


def _build_prompt(signals: dict, scores: dict) -> str:
    return DOMAIN_DETECTION_PROMPT.format(
        repo_name=signals.get("repo_name") or "unknown",
        repo_description=signals.get("repo_description") or "(none)",
        libraries=json.dumps(signals.get("libraries", [])[:50]),
        entities=json.dumps(signals.get("entities", [])[:30]),
        routes=json.dumps(signals.get("routes", [])[:30]),
        scores=json.dumps(scores, indent=2),
    )


def _parse_llm_response(content: str) -> dict:
    from app.agents.llm_response_parser import parse_llm_json_object
    return parse_llm_json_object(content) or {}


def _llm_classify(signals: dict, scores: dict) -> dict:
    try:
        llm = get_llm()
        response = llm.invoke(_build_prompt(signals, scores))
        return _parse_llm_response(response.content)
    except Exception:
        return {}


def _build_evidence_from_signals(
    detected_libraries: set[str],
    detected_entities: set[str],
    detected_routes: set[str],
    domain: str,
) -> list[str]:
    """Build evidence from the deterministic signals.

    Requirement 7: do NOT default to "general" when there is clear
    repository evidence for a domain. The evidence list is shown to
    the reviewer so the classification is auditable, even when the
    LLM is unavailable or returns low confidence.
    """
    if domain == "general" or domain not in DOMAIN_LIBRARY_INDICATORS:
        return []
    indicators = DOMAIN_LIBRARY_INDICATORS[domain]
    evidence: list[str] = []
    lib_hits = detected_libraries & set(indicators["libraries"])
    if lib_hits:
        evidence.append(f"Domain library detected: {sorted(lib_hits)[:3]}")
    ent_hits = detected_entities & set(indicators["entities"])
    if ent_hits:
        evidence.append(f"Domain entity/model detected: {sorted(ent_hits)[:3]}")
    route_hits = detected_routes & set(indicators["routes"])
    if route_hits:
        evidence.append(f"Domain route detected: {sorted(route_hits)[:3]}")
    return evidence


def _heuristic_top_domain(heuristic_scores: dict[str, float]) -> tuple[str, float]:
    """Return (top_domain, raw_score) for a non-empty heuristic map.
    Excludes the `general` fallback key.
    """
    if not heuristic_scores:
        return ("general", 0.0)
    real = {k: v for k, v in heuristic_scores.items() if k != "general"}
    if not real:
        return ("general", 0.0)
    top = max(real, key=real.get)
    return top, real[top]


def domain_detection_node(state: PipelineEngineerState) -> PipelineEngineerState:
    """Node 7 of K1: detect the webapp domain of the repository.

    Alur (sesuai struktur-v6 §3.5.3 + requirement 7):
      Step 1: deterministic signal extraction (name, description, libraries, entities, routes)
      Step 2: LLM-based classification using signals + heuristic scores
      Step 3: if the LLM is unavailable or returns low confidence, fall
              back to the deterministic heuristic; the repo is classified
              as `general` ONLY when the heuristic finds no clear evidence
              for any specific domain.
    """
    if state.get("errors"):
        print(
            f"[domain_detection] running with prior errors: "
            f"{state['errors'][:2]}"
        )

    signals = _extract_candidate_signals(state)

    detected_libraries = set(l.lower() for l in signals.get("libraries", []))
    detected_entities = set(e.lower() for e in signals.get("entities", []))
    detected_routes = set(r.lower() for r in signals.get("routes", []))

    heuristic_scores = _score_domain(detected_libraries, detected_entities, detected_routes)
    heuristic_raw_scores = _score_domain_raw(
        detected_libraries, detected_entities, detected_routes
    )

    llm_result = _llm_classify(signals, heuristic_scores)
    llm_failed = not llm_result or not llm_result.get("domain")

    domain = (llm_result.get("domain") or "general").lower().strip() if llm_result else "general"
    if domain not in VALID_DOMAINS:
        domain = "general"

    try:
        confidence = float(llm_result.get("confidence", 0.0)) if llm_result else 0.0
    except (TypeError, ValueError):
        confidence = 0.0

    # When the LLM is unavailable, returns a low-confidence answer, or
    # disagrees with the deterministic heuristic, fall back to the
    # heuristic. This is the key fix for requirement 7: do NOT default
    # to "general" if clear evidence exists.
    heuristic_top, heuristic_raw = _heuristic_top_domain(heuristic_raw_scores)
    has_strong_heuristic_evidence = (
        heuristic_top != "general" and heuristic_raw >= 1.0
    )
    if llm_failed or confidence < 0.5:
        if has_strong_heuristic_evidence:
            domain = heuristic_top
            # Convert the raw heuristic score into a confidence value
            # (0-1). The raw score is unnormalised so we cap at 1.0 and
            # use 0.6 as the floor when the heuristic has at least one
            # library/entity/route hit.
            confidence = min(1.0, max(0.55, heuristic_raw * 0.3 + 0.4))
        elif heuristic_top != "general" and heuristic_raw > 0:
            # Heuristic has weak evidence (score < 1.0). Trust it but
            # with lower confidence.
            domain = heuristic_top
            confidence = 0.55
        else:
            domain = "general"
            confidence = 1.0
    elif heuristic_raw_scores:
        # LLM returned a domain (possibly "general" with high confidence).
        # Keep it unless the heuristic strongly disagrees (e.g. LLM said
        # "general" but heuristic found clear e-commerce evidence).
        if domain == "general" and has_strong_heuristic_evidence:
            domain = heuristic_top
            confidence = min(1.0, max(0.55, heuristic_raw * 0.3 + 0.4))
        elif domain != "general" and heuristic_top != domain and heuristic_top != "general":
            # Heuristic disagrees with LLM. Trust the heuristic when it
            # has clear evidence and the LLM confidence is low.
            if confidence < 0.7 and heuristic_raw >= 1.0:
                domain = heuristic_top
                confidence = max(confidence, heuristic_raw * 0.3 + 0.4)
        # Heuristic veto: if the LLM confidently picked a specific
        # domain (e.g. "e-commerce") but the heuristic scored that
        # domain below MIN_HEURISTIC_SCORE, treat the LLM answer as
        # over-fit and fall back to "general". This handles repos
        # that have 1-2 weak signals (e.g. a `PAYMENT_GATEWAY_KEY`
        # constant in a healthcare billing service) where the LLM
        # misclassifies based on a single token. The veto fires
        # whenever the LLM-picked domain has a weak heuristic
        # foundation, regardless of whether the top-heuristic
        # domain happens to match. (Healthcare-micro-vuln: LLM says
        # e-commerce, heuristic e-commerce = 2.0 < 3.0 -> veto
        # fires even though `heuristic_top == domain`.)
        if (
            domain != "general"
            and heuristic_raw_scores.get(domain, 0) < MIN_HEURISTIC_SCORE
        ):
            domain = "general"
            confidence = 0.0

    if domain == "general":
        confidence = 1.0
    elif confidence < DOMAIN_CONFIDENCE_THRESHOLD:
        # Last-resort fallback: confidence is still too low after the
        # heuristic promotion above, so accept it as "general" but only
        # if the heuristic really has no signal.
        if heuristic_top == "general" or heuristic_raw == 0:
            domain = "general"
            confidence = 1.0

    evidence = llm_result.get("evidence") or [] if llm_result else []
    if not evidence:
        evidence = _build_evidence_from_signals(
            detected_libraries, detected_entities, detected_routes, domain
        )

    threats = llm_result.get("domain_threats") or [] if llm_result else []
    if not threats and domain in DOMAIN_LIBRARY_INDICATORS:
        threats = list(DOMAIN_LIBRARY_INDICATORS[domain]["threats"])

    # Sub-type (payment processor for e-commerce, billing model for
    # SaaS, etc.). Only meaningful when domain is e-commerce; for
    # other domains, sub_type is "none".
    sub_type_raw = (llm_result.get("sub_type") or "none") if llm_result else "none"
    sub_type = sub_type_raw.lower().strip() if isinstance(sub_type_raw, str) else "none"
    VALID_SUB_TYPES = {
        "stripe", "midtrans", "xendit", "doku", "paypal", "braintree",
        "razorpay", "adyen", "square", "multi", "unknown", "none",
    }
    if sub_type not in VALID_SUB_TYPES:
        sub_type = "none"
    # Heuristic fallback for sub_type: derive from detected libraries
    if sub_type == "none" and domain == "e-commerce":
        sub_type = _infer_payment_processor(detected_libraries)

    state["detected_domain"] = domain
    state["domain_sub_type"] = sub_type
    state["domain_confidence"] = round(confidence, 2)
    state["domain_evidence"] = list(evidence) if isinstance(evidence, list) else [str(evidence)]
    state["domain_threats"] = list(threats) if isinstance(threats, list) else [str(threats)]

    # Business features (struktur-v8): extract from LLM result with
    # heuristic fallback. Used downstream by security inference to
    # select domain-relevant controls.
    VALID_FEATURES = {
        "authentication", "catalog", "shopping_cart", "checkout", "payment",
        "order_management", "database", "file_upload",
        "mqtt", "telemetry", "firmware", "device_management",
        "blog_posting", "comment_system",
    }
    features_raw = llm_result.get("features") or [] if llm_result else []
    features = [f for f in features_raw if isinstance(f, str) and f in VALID_FEATURES]
    if not features:
        features = _fallback_features(signals, domain)
    state["features"] = sorted(set(features))

    return state


def _fallback_features(signals: dict, domain: str) -> list[str]:
    """Heuristic feature detection from signals (LLM fallback)."""
    features: set[str] = set()
    libs_lower = {lib.lower() for lib in signals.get("libraries", [])}
    entities_lower = {e.lower() for e in signals.get("entities", [])}
    routes_lower = {r.lower() for r in signals.get("routes", [])}

    auth_libs = {"passport", "jsonwebtoken", "jwt", "bcrypt", "auth0", "oauth", "firebase-auth"}
    if libs_lower & auth_libs or any(r in routes_lower for r in ["/login", "/signup", "/auth", "/register"]):
        features.add("authentication")

    if "shopping_cart" in entities_lower or any("cart" in r for r in routes_lower):
        features.add("shopping_cart")
    if any("checkout" in r or "payment" in r for r in routes_lower):
        features.add("checkout")
    if features & {"shopping_cart", "checkout"}:
        features.add("catalog")
    if "checkout" in features:
        features.add("payment")
    if any("order" in r or "/orders" in r for r in routes_lower) or "order" in entities_lower:
        features.add("order_management")

    if libs_lower & {"sequelize", "prisma", "mongoose", "typeorm", "sqlalchemy", "drizzle-orm"}:
        features.add("database")

    if libs_lower & {"multer", "formidable", "busboy", "sharp"} or any("upload" in r for r in routes_lower):
        features.add("file_upload")

    if libs_lower & {"mqtt", "paho-mqtt", "amqp", "coap"}:
        features.add("mqtt")
    if "telemetry" in entities_lower or "sensor" in entities_lower:
        features.add("telemetry")
    if "firmware" in entities_lower:
        features.add("firmware")
    if "device" in entities_lower:
        features.add("device_management")

    if domain == "blog":
        if "post" in entities_lower or "article" in entities_lower:
            features.add("blog_posting")
        if "comment" in entities_lower:
            features.add("comment_system")

    return sorted(features)


# Payment-processor library detection (deterministic, used as fallback
# when LLM doesn't return sub_type or returns "none"/"unknown").
_PAYMENT_PROCESSOR_LIBS: dict[str, tuple[str, ...]] = {
    "stripe": (
        "stripe", "@stripe/stripe-js", "stripe-node", "@stripe/react-stripe-js",
    ),
    "midtrans": (
        "midtrans-client", "midtrans", "@midtrans/midtrans-node",
    ),
    "xendit": (
        "xendit-node", "xendit", "xendit-node-sdk",
    ),
    "doku": (
        "doku-node", "doku",
    ),
    "paypal": (
        "paypal-rest-sdk", "paypal", "@paypal/checkout-server-sdk",
    ),
    "braintree": ("braintree",),
    "razorpay": ("razorpay",),
    "adyen": ("adyen",),
    "square": ("square",),
}


def _infer_payment_processor(detected_libraries: set[str]) -> str:
    """Infer payment processor from library imports (deterministic).

    Returns one of: stripe, midtrans, xendit, doku, paypal, braintree,
    razorpay, adyen, square, multi, unknown.

    Priority order: if MULTIPLE processors detected, return "multi".
    """
    matches: list[str] = []
    libs_lower = {lib.lower() for lib in detected_libraries}
    for processor, libs in _PAYMENT_PROCESSOR_LIBS.items():
        if any(lib in libs_lower for lib in libs):
            matches.append(processor)
    if not matches:
        return "unknown"
    if len(matches) == 1:
        return matches[0]
    return "multi"
