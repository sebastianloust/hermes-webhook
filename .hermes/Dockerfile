FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scripts
COPY scripts/webhook_flask_railway.py .
COPY .env.clean .env

# Create log directory
RUN mkdir -p /app/logs

# Health check (no healthcheck - Railway handles it)
EXPOSE 8000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "webhook_flask_railway:app"]
