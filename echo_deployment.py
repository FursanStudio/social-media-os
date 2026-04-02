# ============================================================
# ECHO — Docker + GCP Deployment Files
# Week 4 Day 3 (Docker) + Day 4 (Cloud Run)
# ============================================================
# This file contains ALL deployment configs as comments.
# Copy each section into its own file as instructed below.
# ============================================================


# ─── FILE: Dockerfile ────────────────────────────────────────────────────────
DOCKERFILE = """
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc curl \\
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
"""

# ─── FILE: docker-compose.yml ────────────────────────────────────────────────
DOCKER_COMPOSE = """
version: '3.9'

services:

  # FastAPI backend
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - SERPER_API_KEY=${SERPER_API_KEY}
      - FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
      - X_API_KEY=${X_API_KEY}
      - X_API_SECRET=${X_API_SECRET}
      - X_ACCESS_TOKEN=${X_ACCESS_TOKEN}
      - X_ACCESS_SECRET=${X_ACCESS_SECRET}
      - LINKEDIN_ACCESS_TOKEN=${LINKEDIN_ACCESS_TOKEN}
      - LINKEDIN_PERSON_URN=${LINKEDIN_PERSON_URN}
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - redis
      - qdrant
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  # Redis for pipeline state persistence
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  # Qdrant vector database for brand memory
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  # Daily cron worker — runs content machine every morning at 9am
  worker:
    build: .
    command: python echo_scheduler.py
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - redis
      - qdrant
    restart: unless-stopped

volumes:
  redis_data:
  qdrant_data:
"""

# ─── FILE: cloudbuild.yaml (GCP Cloud Build) ─────────────────────────────────
CLOUDBUILD = """
steps:
  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/echo-api:$COMMIT_SHA'
      - '.'

  # Push to Google Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/echo-api:$COMMIT_SHA'

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'echo-api'
      - '--image=gcr.io/$PROJECT_ID/echo-api:$COMMIT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--memory=1Gi'
      - '--cpu=1'
      - '--max-instances=3'
      - '--set-env-vars=GROQ_API_KEY=$$GROQ_API_KEY'
      - '--update-secrets=GROQ_API_KEY=groq-api-key:latest'

images:
  - 'gcr.io/$PROJECT_ID/echo-api:$COMMIT_SHA'
"""

# ─── FILE: echo_scheduler.py (Cron worker) ───────────────────────────────────
SCHEDULER = """
# echo_scheduler.py — Week 4 Day 4
# Cloud Scheduler cron worker — runs daily at 9:00 AM

import os, time, json, schedule
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BRAND_NAME = os.getenv("BRAND_NAME", "Aoraza")
INDUSTRY   = os.getenv("INDUSTRY",   "dairy")

def daily_job():
    print(f\"\\n{'='*50}\")
    print(f\"🤖 ECHO DAILY RUN — {datetime.now().strftime('%Y-%m-%d %H:%M')}\")
    print(f\"{'='*50}\")
    try:
        from echo_pipeline import run_daily_content_machine
        result = run_daily_content_machine(BRAND_NAME, INDUSTRY)

        if result.get("linkedin_post"):
            from echo_reliability import ApprovalQueue
            queue = ApprovalQueue()
            li = result["linkedin_post"]
            content = f\"{li.get('hook','')}\\n\\n{li.get('body','')}\\n\\n{li.get('cta','')}\"
            queue.add_post("LinkedIn", content, BRAND_NAME, INDUSTRY,
                           image_url=result.get("image_url", ""))
            print(f\"✅ Post added to approval queue\")

        print(f\"Daily job complete — {datetime.now().strftime('%H:%M:%S')}\")
    except Exception as e:
        print(f\"❌ Daily job failed: {e}\")

# Run at 9:00 AM every day
schedule.every().day.at("09:00").do(daily_job)
print(f\"⏰ Scheduler started — will run daily at 09:00\")
print(f\"   Brand: {BRAND_NAME} | Industry: {INDUSTRY}\")

# Run immediately on first start
daily_job()

# Keep running
while True:
    schedule.run_pending()
    time.sleep(60)
"""

if __name__ == "__main__":
    # Write all the deployment files
    import os

    files = {
        "Dockerfile":         DOCKERFILE.strip(),
        "docker-compose.yml": DOCKER_COMPOSE.strip(),
        "cloudbuild.yaml":    CLOUDBUILD.strip(),
        "echo_scheduler.py":  SCHEDULER.strip(),
    }

    for filename, content in files.items():
        with open(filename, "w") as f:
            f.write(content)
        print(f"✅ Created: {filename}")

    print("\n🚀 Deployment files ready!")
    print("\nTo deploy locally with Docker:")
    print("  docker-compose up --build")
    print("\nTo deploy to GCP Cloud Run:")
    print("  1. gcloud auth login")
    print("  2. gcloud config set project YOUR_PROJECT_ID")
    print("  3. gcloud builds submit --config cloudbuild.yaml")
    print("  4. Set Cloud Scheduler:")
    print("     gcloud scheduler jobs create http echo-daily \\")
    print("       --schedule='0 9 * * *' \\")
    print("       --uri=https://YOUR_SERVICE.run.app/run-daily \\")
    print("       --time-zone='Asia/Karachi'")
