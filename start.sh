#!/bin/bash

# Food Cost Management System - Local Development Startup Script
# This script sets up a virtual environment and runs the application locally

set -e  # Exit on any error

echo "🚀 Starting Food Cost Management System..."

# Check if Python 3.11+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "📍 Using Python $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "📦 Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Create data directory if it doesn't exist
if [ ! -d "data" ]; then
    echo "📁 Creating data directory..."
    mkdir -p data
    echo "✅ Data directory created"
fi

# Set environment variables for local development
export SECRET_KEY="local-dev-secret-key-change-in-production"
export DATABASE_URL="sqlite:///./data/food_cost.db"

echo "🌟 Environment variables set:"
echo "   SECRET_KEY: $SECRET_KEY"
echo "   DATABASE_URL: $DATABASE_URL"

# Start the application
echo "🚀 Starting application on http://localhost:8000"
echo "📝 Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000