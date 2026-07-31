# ---- Stage 1: Build dependencies ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install only what pip needs to resolve packages
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --target /build/deps -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

# Create a non-root user
RUN addgroup --system app && adduser --system --no-create-home --group app

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages

# Copy application code
COPY backend/ backend/
COPY api/ api/

# Ensure Python can import backend as a package
ENV PYTHONPATH=/app

# Expose the FastAPI port
EXPOSE 8000

# Run as non-root
USER app

# Start uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]