FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /app/instance

EXPOSE 8000

ENV FLASK_CONFIG=production
ENV PYTHONUNBUFFERED=1

# Initialize database and start app
CMD ["sh", "-c", "python -c 'from app import create_app; from app.database import init_database; app = create_app(); app.app_context().push(); init_database(); print(\"Database initialized\")' && gunicorn --bind=0.0.0.0:8000 --workers=2 wsgi:app"]
