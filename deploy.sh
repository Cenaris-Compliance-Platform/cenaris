#!/bin/bash

echo "🚀 Deploying Cenaris Updates"
echo "============================"

echo "📦 Building new image..."
az acr build \
  --registry cenarisacr1762093207 \
  --image cenaris:latest \
  --file Dockerfile \
  .

echo "🔄 Restarting container..."
az container restart \
  --resource-group cenaris-fixed-rg \
  --name cenaris-app

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo "🌐 Live at: http://cenaris-app-1762093207.westus2.azurecontainer.io:8000"
echo "⏳ Changes will be live in 2-3 minutes"
