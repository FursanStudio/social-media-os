FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker cache layer optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY *.py .
COPY .env* .

# Expose FastAPI port
EXPOSE 8000

# Start command
CMD ["uvicorn", "echo_api:app", "--host", "0.0.0.0", "--port", "8000"]