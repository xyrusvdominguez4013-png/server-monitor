<#
.SYNOPSIS
    Server Monitoring Agent - Installation Script (Windows)
.DESCRIPTION
    This script automates the setup of the Server Monitoring Agent on Windows.
    It installs dependencies, generates a secure API token, and starts the Flask app.
#>

$ErrorActionPreference = "Stop"

function Print-Header($text) {
    Write-Host "`n==========================================================" -ForegroundColor Cyan
    Write-Host "     Server Monitoring Agent - Installation Script" -ForegroundColor Cyan
    Write-Host "==========================================================`n" -ForegroundColor Cyan
    
    Write-Host "This script will:" -ForegroundColor Yellow
    Write-Host "  1. Check for Python"
    Write-Host "  2. Install required dependencies from requirements.txt"
    Write-Host "  3. Generate a secure API token (if .env doesn't exist)"
    Write-Host "  4. Start the Flask agent application`n"
}

function Print-Success($text) {
    Write-Host "[SUCCESS] $text" -ForegroundColor Green
}

function Print-Warning($text) {
    Write-Host "[WARNING] $text" -ForegroundColor Yellow
}

function Print-Error($text) {
    Write-Host "[ERROR] $text" -ForegroundColor Red
}

function Print-Info($text) {
    Write-Host "[INFO] $text" -ForegroundColor Blue
}

Print-Header

# 1. Check Python
Print-Info "Checking for Python..."
$pythonCmd = "python"
if (!(Get-Command $pythonCmd -ErrorAction SilentlyContinue)) {
    $pythonCmd = "python3"
    if (!(Get-Command $pythonCmd -ErrorAction SilentlyContinue)) {
        Print-Error "Python is not installed or not in PATH."
        exit 1
    }
}
$pythonVersion = & $pythonCmd --version 2>&1
Print-Success "Python is available: $pythonVersion"

# 2. Install Dependencies
Print-Info "Installing dependencies from requirements.txt..."
if (!(Test-Path "requirements.txt")) {
    Print-Error "requirements.txt not found in current directory."
    exit 1
}

$pipCmd = "pip"
if (!(Get-Command $pipCmd -ErrorAction SilentlyContinue)) {
    $pipCmd = "pip3"
}

try {
    & $pipCmd install -r requirements.txt
    Print-Success "Dependencies installed successfully."
} catch {
    Print-Error "Failed to install dependencies."
    exit 1
}

# 3. Handle .env File and API Token
Print-Info "Checking for existing .env file..."
if (Test-Path ".env") {
    Print-Info "Existing .env found. Using existing API Token."
    Print-Warning "If you need to regenerate the token, delete .env and run this script again."
} else {
    Print-Info "No .env file found. Generating new API token..."
    
    # Generate secure token
    $ApiToken = [guid]::NewGuid().ToString('N')
    
    # Create .env file
    "API_TOKEN=$ApiToken" | Out-File -FilePath ".env" -Encoding ASCII
    
    Print-Success ".env file created with new API token.`n"
    Write-Host "===========================================================" -ForegroundColor Green
    Write-Host "  YOUR API TOKEN: $ApiToken" -ForegroundColor Green
    Write-Host "===========================================================`n" -ForegroundColor Green
    Write-Host "⚠️ COPY THIS TOKEN! You will need it for the Master Dashboard." -ForegroundColor Red
    Write-Host "Store it securely. It will be used to authenticate connections.`n" -ForegroundColor Yellow
}

# 4. Start the Flask Application
Print-Success "Setup complete!`n"
Print-Info "Starting Agent on port 5000..."
Write-Host "`n─────────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host "The agent is now running. Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────`n" -ForegroundColor Cyan

# Start the Flask application
& $pythonCmd agent_app.py
