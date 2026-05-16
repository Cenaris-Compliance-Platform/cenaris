#!/bin/bash

# Startup script for Azure App Service
# Ensures the app path is correctly set and starts Gunicorn

echo "Starting Cenaris Startup Script..."

# Add current directory to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:.

# Start Gunicorn
# Using 1 worker for reliability on dev tier
gunicorn --bind=0.0.0.0:8000 --workers 1 --timeout 180 --graceful-timeout 30 run:app
