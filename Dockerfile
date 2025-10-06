FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install build-essential and required browser dependencies (Debian trixie-compatible)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgobject-2.0-0 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgio-2.0-0 \
    libexpat1 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} \
    && chmod -R 755 ${PLAYWRIGHT_BROWSERS_PATH}

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the Playwright-managed Chromium browser ahead of time so the
# application can launch it without downloading at runtime.
RUN python -m playwright install chromium

# The explicit dependency installation above should make this step succeed
# or be redundant. The fallback is kept for robustness.
RUN python -m playwright install-deps chromium || \
    (echo "playwright install-deps chromium failed; continuing with manually installed deps" && exit 0)

COPY . .

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
