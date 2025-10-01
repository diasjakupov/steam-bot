FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libglib2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxshmfence1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} \
    && chmod -R 755 ${PLAYWRIGHT_BROWSERS_PATH}

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Attempt to install any additional system dependencies Playwright expects. The
# upstream script still references transitional font packages that are no longer
# available on Debian trixie, so we ignore failures after preinstalling the
# required libraries above.
RUN python -m playwright install-deps chromium || \
    (echo "playwright install-deps chromium failed; continuing with manually installed deps" && exit 0)

# Install the Playwright-managed Chromium browser ahead of time so the
# application can launch it without downloading at runtime.
RUN python -m playwright install chromium

COPY . .

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

