#!/bin/bash

# Food Cost Management System - Local Development Startup Script
# This script sets up a virtual environment and runs the application locally
# Compatible with various Linux distributions and package managers

set -e  # Exit on any error

echo "🚀 Starting Food Cost Management System..."

# Function to detect OS and package manager
detect_os() {
    if command -v apt &> /dev/null; then
        echo "debian"
    elif command -v yum &> /dev/null; then
        echo "rhel"
    elif command -v dnf &> /dev/null; then
        echo "fedora"
    elif command -v pacman &> /dev/null; then
        echo "arch"
    elif command -v brew &> /dev/null; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# Function to install python3-venv if needed
install_python_venv() {
    local os_type=$(detect_os)
    
    echo "⚠️  python3-venv not available. Attempting to install..."
    
    case $os_type in
        "debian")
            echo "📦 Detected Debian/Ubuntu system"
            if command -v sudo &> /dev/null; then
                sudo apt update && sudo apt install -y python3-venv python3-pip
            else
                echo "❌ sudo not available. Please run: apt install python3-venv python3-pip"
                exit 1
            fi
            ;;
        "rhel")
            echo "📦 Detected RHEL/CentOS system"
            if command -v sudo &> /dev/null; then
                sudo yum install -y python3-venv python3-pip
            else
                echo "❌ sudo not available. Please run: yum install python3-venv python3-pip"
                exit 1
            fi
            ;;
        "fedora")
            echo "📦 Detected Fedora system"
            if command -v sudo &> /dev/null; then
                sudo dnf install -y python3-venv python3-pip
            else
                echo "❌ sudo not available. Please run: dnf install python3-venv python3-pip"
                exit 1
            fi
            ;;
        "arch")
            echo "📦 Detected Arch Linux system"
            if command -v sudo &> /dev/null; then
                sudo pacman -S python-virtualenv python-pip
            else
                echo "❌ sudo not available. Please run: pacman -S python-virtualenv python-pip"
                exit 1
            fi
            ;;
        "macos")
            echo "📦 Detected macOS system"
            if command -v brew &> /dev/null; then
                brew install python@3.11
            else
                echo "❌ Homebrew not available. Please install python3-venv manually or use Homebrew"
                exit 1
            fi
            ;;
        *)
            echo "❌ Unknown OS. Please install python3-venv manually for your system"
            echo "   Common packages: python3-venv, python3-virtualenv, python-virtualenv"
            exit 1
            ;;
    esac
}

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "📍 Using Python $PYTHON_VERSION"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    
    # Try to create virtual environment, install venv package if it fails
    if ! python3 -m venv venv 2>/dev/null; then
        echo "⚠️  Virtual environment creation failed. Installing python3-venv..."
        install_python_venv
        
        # Try again after installing venv package
        if ! python3 -m venv venv; then
            echo "❌ Still unable to create virtual environment. Trying alternative method..."
            
            # Try using virtualenv as fallback
            if command -v virtualenv &> /dev/null; then
                echo "📦 Using virtualenv as fallback..."
                virtualenv -p python3 venv
            else
                echo "❌ Unable to create virtual environment. Please install python3-venv or virtualenv manually."
                exit 1
            fi
        fi
    fi
    
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
else
    echo "📁 Data directory already exists"
fi

# Load .env file if it exists
if [ -f .env ]; then
    echo "📄 Loading .env file..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Set environment variables for local development (if not already set)
export SECRET_KEY="${SECRET_KEY:-local-dev-secret-key-change-in-production}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/food_cost.db}"
export TZ="${TZ:-America/Los_Angeles}"

# Export email configuration if present in .env
if [ ! -z "$RESEND_API_KEY" ]; then
    export RESEND_API_KEY
fi
if [ ! -z "$RESEND_FROM_EMAIL" ]; then
    export RESEND_FROM_EMAIL
fi

echo "🌟 Environment variables set:"
echo "   SECRET_KEY: $SECRET_KEY"
echo "   DATABASE_URL: $DATABASE_URL"
echo "   TZ: $TZ"
if [ ! -z "$RESEND_API_KEY" ]; then
    echo "   RESEND_API_KEY: [configured]"
    echo "   RESEND_FROM_EMAIL: ${RESEND_FROM_EMAIL:-not set}"
fi
echo ""
echo "📂 Database will be stored in: ./data/food_cost.db"
echo "🔗 This matches the Docker volume mount for consistency"
echo ""

# Run migrations if database exists
if [ -f "./data/food_cost.db" ]; then
    echo "📊 Existing database detected - checking for migrations..."
    python run_migrations.py
    echo ""
else
    echo "ℹ️  No existing database - will be created on first access"
    echo "ℹ️  Skipping migrations (not needed for fresh database)"
    echo ""
fi

# Start the application
echo "🚀 Starting application on http://localhost:8000"
echo "📝 Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000