#!/bin/bash

###############################################################################
# Server Monitoring Agent - Installation Script
# 
# This script automates the setup of the Server Monitoring Agent on remote
# Linux servers. It installs dependencies, generates a secure API token,
# and starts the Flask application.
#
# Usage: ./install_shell.sh
###############################################################################

set -e  # Exit immediately on error

#------------------------------------------------------------------------------
# ANSI Color Codes for Output
#------------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD_GREEN='\033[1;32m'
BOLD_RED='\033[1;31m'
NC='\033[0m' # No Color

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------

print_banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Server Monitoring Agent - Installation Script        ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}This script will:${NC}"
    echo -e "  1. Check for Python 3 and pip3"
    echo -e "  2. Install required dependencies from requirements.txt"
    echo -e "  3. Generate a secure API token (if .env doesn't exist)"
    echo -e "  4. Start the Flask agent application"
    echo ""
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 is not installed or not in PATH."
        return 1
    fi
    return 0
}

generate_uuid() {
    # Generate a secure random 32-character UUID
    if command -v uuidgen &> /dev/null; then
        uuidgen | tr -d '-' | cut -c1-32
    elif [ -f /proc/sys/kernel/random/uuid ]; then
        cat /proc/sys/kernel/random/uuid | tr -d '-' | cut -c1-32
    else
        # Fallback using Python
        python3 -c "import uuid; print(uuid.uuid4().hex[:32])"
    fi
}

#------------------------------------------------------------------------------
# Main Script Execution
#------------------------------------------------------------------------------

print_banner

#------------------------------------------------------------------------------
# Step 1: Check for Python 3 and pip3
#------------------------------------------------------------------------------
print_info "Checking for Python 3 and pip3..."

if ! check_command "python3"; then
    print_error "Python 3 is required but not found."
    print_info "Please install Python 3 and try again."
    exit 1
fi

if ! check_command "pip3"; then
    print_error "pip3 is required but not found."
    print_info "Please install pip3 and try again."
    exit 1
fi

print_success "Python 3 and pip3 are available."

#------------------------------------------------------------------------------
# Step 2: Install Dependencies
#------------------------------------------------------------------------------
print_info "Installing dependencies from requirements.txt..."

if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found in current directory."
    print_info "Please ensure you're running this script from the agent repository root."
    exit 1
fi

if pip3 install -r requirements.txt; then
    print_success "Dependencies installed successfully."
else
    print_error "Failed to install dependencies."
    print_info "Please check the error messages above and ensure you have network access."
    exit 1
fi

#------------------------------------------------------------------------------
# Step 3: Handle .env File and API Token
#------------------------------------------------------------------------------
print_info "Checking for existing .env file..."

if [ -f ".env" ]; then
    print_info "Existing .env found. Using existing API Token."
    print_warning "If you need to regenerate the token, delete .env and run this script again."
else
    print_info "No .env file found. Generating new API token..."
    
    # Generate secure token
    API_TOKEN=$(generate_uuid)
    
    # Create .env file
    echo "API_TOKEN=${API_TOKEN}" > .env
    
    # Set restrictive permissions on .env file
    chmod 600 .env
    
    print_success ".env file created with new API token."
    echo ""
    echo -e "${BOLD_GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD_GREEN}  YOUR API TOKEN: ${API_TOKEN}${NC}"
    echo -e "${BOLD_GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${RED}⚠️  COPY THIS TOKEN! You will need it for the Master Dashboard.${NC}"
    echo -e "${YELLOW}   Store it securely. It will be used to authenticate connections.${NC}"
    echo ""
fi

#------------------------------------------------------------------------------
# Step 4: Start the Flask Application
#------------------------------------------------------------------------------
echo ""
print_success "Setup complete!"
echo ""
print_info "Starting Agent on port 5000..."
echo ""
echo -e "${BLUE}─────────────────────────────────────────────────────────────${NC}"
echo -e "${YELLOW}The agent is now running. Press Ctrl+C to stop.${NC}"
echo -e "${BLUE}─────────────────────────────────────────────────────────────${NC}"
echo ""

# Start the Flask application (this will run until stopped)
exec python3 agent_app.py
