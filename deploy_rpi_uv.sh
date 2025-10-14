#!/bin/bash
###############################################################################
# RPi UV Analyzer - One-Click Deployment Script
# 
# This script automatically:
# 1. Checks prerequisites
# 2. Clones the repository from GitHub
# 3. Runs the installation
# 4. Starts the application in kiosk mode
#
# Usage: bash deploy_rpi_uv.sh
#
# Repository: https://github.com/srosendal/rpi_uv
###############################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/srosendal/rpi_uv.git"
INSTALL_DIR="$HOME/rpi_uv"

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  RPi UV Analyzer - Auto Deploy${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

###############################################################################
# Pre-flight Checks
###############################################################################

check_internet() {
    print_step "Checking internet connectivity..."
    if ping -c 1 google.com &> /dev/null || ping -c 1 8.8.8.8 &> /dev/null; then
        print_success "Internet connection OK"
        return 0
    else
        print_error "No internet connection detected"
        print_info "Please connect to the internet and try again"
        exit 1
    fi
}

check_and_install_git() {
    print_step "Checking for git..."
    if command -v git &> /dev/null; then
        print_success "Git is installed"
    else
        print_warning "Git not found. Installing..."
        sudo apt-get update -qq
        sudo apt-get install -y git
        print_success "Git installed"
    fi
}

###############################################################################
# Main Installation
###############################################################################

clone_repository() {
    print_step "Cloning repository..."
    
    # Remove existing installation if present
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Found existing installation at $INSTALL_DIR"
        read -p "Remove and reinstall? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing old installation..."
            rm -rf "$INSTALL_DIR"
        else
            print_info "Keeping existing installation. Updating instead..."
            cd "$INSTALL_DIR"
            git pull origin main
            return 0
        fi
    fi
    
    # Clone repository
    print_info "Cloning from: $REPO_URL"
    git clone "$REPO_URL" "$INSTALL_DIR"
    print_success "Repository cloned to $INSTALL_DIR"
}

run_installation() {
    print_step "Running installation script..."
    cd "$INSTALL_DIR"
    
    if [ ! -f "install.sh" ]; then
        print_error "install.sh not found in repository"
        exit 1
    fi
    
    chmod +x install.sh
    print_info "This may take 5-10 minutes..."
    bash install.sh
    
    print_success "Installation complete"
}

start_kiosk_mode() {
    print_step "Starting kiosk mode..."
    cd "$INSTALL_DIR"
    
    if [ ! -f "start_kiosk.sh" ]; then
        print_error "start_kiosk.sh not found"
        exit 1
    fi
    
    chmod +x start_kiosk.sh
    print_success "Starting application..."
    print_info "The kiosk will start in a few seconds..."
    echo ""
    bash start_kiosk.sh
}

###############################################################################
# Main Script
###############################################################################

main() {
    print_header
    
    print_info "Starting automatic deployment..."
    print_info "This script will install the RPi UV Analyzer"
    echo ""
    
    # Run all steps
    check_internet
    check_and_install_git
    clone_repository
    run_installation
    
    echo ""
    print_success "==============================================="
    print_success "  Installation Complete!"
    print_success "==============================================="
    print_info "Starting kiosk mode in 3 seconds..."
    sleep 3
    
    start_kiosk_mode
}

# Run main function
main
