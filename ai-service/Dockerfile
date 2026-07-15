FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source AFTER pip install so layer cache invalidates when the
# application code (workflow_generator.py, etc.) changes. We also
# remove any pre-existing __pycache__ to avoid stale .pyc files
# shadowing the freshly copied .py sources.
COPY . .
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120", "--backlog", "128"]