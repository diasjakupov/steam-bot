# ==========================================
# STAGE 1: Builder (Compiles dependencies)
# ==========================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build tools (needed to compile some Python packages)
# We do NOT need the browser libraries here, just the compiler (gcc).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment to install dependencies
RUN python -m venv /opt/venv
# Enable the venv for the following commands
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
# Install Python deps into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt


# ==========================================
# STAGE 2: Runtime (The final lightweight image)
# ==========================================
FROM python:3.11-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install ONLY the runtime libraries required by Playwright/Chromium.
# REMOVED: build-essential (saves space)
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Copy the Virtual Environment from the Builder stage
COPY --from=builder /opt/venv /opt/venv

# Set up Playwright folder permissions
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} \
    && chmod -R 755 ${PLAYWRIGHT_BROWSERS_PATH}

# Install Chromium (must be done in the final stage so the binary exists here)
RUN python -m playwright install chromium

# Copy your application code
COPY . .

# Default command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]