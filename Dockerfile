# ==========================================
# STAGE 1: Builder (Compiles dependencies)
# ==========================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build tools (needed to compile some Python packages)
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
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the Virtual Environment from the Builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy your application code
COPY . .

# Default command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
