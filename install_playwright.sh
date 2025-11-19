#!/bin/bash

# Playwright Installation Script for Production
# This script installs Playwright and all required system dependencies

set -e  # Exit on error

echo "=========================================="
echo "Playwright Installation Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Check if running as root (needed for system package installation)
if [ "$EUID" -eq 0 ]; then 
    SUDO=""
else
    SUDO="sudo"
    print_info "Some commands require sudo privileges"
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_VERSION=$VERSION_ID
else
    print_error "Cannot detect OS. Please install dependencies manually."
    exit 1
fi

print_info "Detected OS: $OS $OS_VERSION"
echo ""

# Install system dependencies based on OS
print_info "Installing system dependencies..."

if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    $SUDO apt-get update
    $SUDO apt-get install -y \
        libnspr4 \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        libatspi2.0-0 \
        libxshmfence1 \
        libxss1 \
        libgdk-pixbuf2.0-0 \
        libgtk-3-0 \
        libgdk-pixbuf2.0-0 \
        fonts-liberation \
        libappindicator3-1 \
        xdg-utils \
        poppler-utils
    print_success "System dependencies installed"
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
    if command -v dnf &> /dev/null; then
        $SUDO dnf install -y \
            nss \
            atk \
            cups-libs \
            libdrm \
            libxkbcommon \
            libXcomposite \
            libXdamage \
            libXfixes \
            libXrandr \
            mesa-libgbm \
            alsa-lib \
            pango \
            cairo \
            at-spi2-atk \
            libxshmfence \
            libXScrnSaver \
            gtk3 \
            gdk-pixbuf2 \
            liberation-fonts \
            xorg-x11-utils \
            poppler-utils
    else
        $SUDO yum install -y \
            nss \
            atk \
            cups-libs \
            libdrm \
            libxkbcommon \
            libXcomposite \
            libXdamage \
            libXfixes \
            libXrandr \
            mesa-libgbm \
            alsa-lib \
            pango \
            cairo \
            at-spi2-atk \
            libxshmfence \
            libXScrnSaver \
            gtk3 \
            gdk-pixbuf2 \
            liberation-fonts \
            xorg-x11-utils \
            poppler-utils
    fi
    print_success "System dependencies installed"
else
    print_error "Unsupported OS: $OS"
    print_info "Please install Playwright dependencies manually:"
    print_info "  sudo playwright install-deps"
    exit 1
fi

echo ""

# Check if Python virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    print_info "No virtual environment detected"
    print_info "Make sure to activate your virtual environment before running this script"
    print_info "Example: source .venv/bin/activate"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_success "Virtual environment detected: $VIRTUAL_ENV"
fi

echo ""

# Check if Poetry is being used
if command -v poetry &> /dev/null && [ -f "pyproject.toml" ]; then
    print_info "Poetry detected. Installing Playwright via Poetry..."
    poetry add playwright || poetry install
    print_success "Playwright package installed"
    
    # Install browsers using Poetry's Python
    print_info "Installing Playwright browsers..."
    poetry run playwright install chromium
    poetry run playwright install-deps || true  # May fail if already installed
    print_success "Playwright browsers installed"
elif command -v pip &> /dev/null; then
    print_info "Installing Playwright via pip..."
    pip install playwright
    print_success "Playwright package installed"
    
    # Install browsers
    print_info "Installing Playwright browsers..."
    playwright install chromium
    playwright install-deps || true  # May fail if already installed
    print_success "Playwright browsers installed"
else
    print_error "Neither Poetry nor pip found. Please install Playwright manually."
    exit 1
fi

echo ""
print_success "=========================================="
print_success "Playwright installation completed!"
print_success "=========================================="
echo ""
print_info "To verify installation, run:"
if command -v poetry &> /dev/null; then
    echo "  poetry run playwright --version"
else
    echo "  playwright --version"
fi
echo ""

