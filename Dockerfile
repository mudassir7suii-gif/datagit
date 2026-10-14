FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    DATAGIT_HOST=0.0.0.0 \
    DATAGIT_PORT=8000

EXPOSE 8000

# Default command runs the API gateway
CMD ["uvicorn", "datagit.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
