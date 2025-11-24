# STAGE 1: Builder (Heavy Lifting)
# We use the official image to get the browser binaries easily
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy as builder

WORKDIR /app

# Install Python dependencies in a virtual environment to make copying easier
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install ONLY Chromium (Saves ~400MB vs installing all browsers)
RUN playwright install chromium

# STAGE 2: Runner (Slim & Fast)
# We use the same base OS (jammy) to ensure library compatibility
FROM python:3.11-slim-jammy

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install ONLY the runtime system dependencies for Chromium
# This list is curated for 'slim' images to run Chromium headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from builder (Contains FastAPI, Playwright lib, etc.)
COPY --from=builder /opt/venv /opt/venv

# Copy the Chromium binary from the official image (Crucial step!)
# The official image stores them in /ms-playwright
COPY --from=builder /ms-playwright /ms-playwright

# Copy YOUR code last (This layer changes most often)
COPY . .

# Use array syntax for CMD to handle signals correctly
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]