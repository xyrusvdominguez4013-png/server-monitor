# Server Monitoring Agent

A distributed server monitoring agent that streams real-time hardware metrics via Server-Sent Events (SSE). This is the **Agent** component of a two-part monitoring system designed for local network deployment.

## Overview

This repository contains the Agent application that runs on remote Linux servers. It collects and streams:

- **CPU Usage** - Real-time processor utilization percentage
- **Memory (RAM)** - Total, used, available memory and usage percentage
- **Disk Usage** - Root partition statistics (total, used, free, percent)
- **Network Speed** - Real-time upload/download speeds in MB/s
- **Server Uptime** - Time elapsed since last boot in seconds

The Agent exposes a secure SSE endpoint that the Master Dashboard (running on your laptop) connects to for live data visualization.

### Audit Trail Feature

The system now includes comprehensive audit trail functionality that records and monitors user access with the following information:

- **Date and Time of Access** - ISO format timestamp of each access event
- **Client IP Address** - IP address of the connecting client
- **Client MAC Address** - MAC address (for local network connections via ARP lookup)
- **Username** - Derived from authentication token or anonymous
- **Device/Browser Information** - Browser type, OS, and device type extracted from User-Agent
- **Menu/Module Accessed** - Which API endpoint was accessed
- **Action Performed** - Type of action (View, Disconnect, etc.)
- **Server Status** - Current online/offline status of the server

## Architecture & Network Design

### System Architecture

The server-monitor operates both as an API provider (for the Global Dashboard) and a standalone Web Application (for the Inventory System). Here is how the components communicate across the network:

```mermaid
flowchart TD
    %% Define Styles
    classDef client fill:#0a0e17,stroke:#00f0ff,stroke-width:2px,color:#fff
    classDef agent fill:#111824,stroke:#00ff9d,stroke-width:2px,color:#fff
    classDef dash fill:#172030,stroke:#ffb700,stroke-width:2px,color:#fff
    classDef db fill:#020408,stroke:#e2e8f0,stroke-width:1px,color:#fff,stroke-dasharray: 5 5

    %% Nodes
    subgraph Users ["Client Endpoints (Web Browsers)"]
        U_Admin["Dashboard Admin"]:::client
        U_Manager["Inventory Manager"]:::client
        U_Clerk["Inventory Clerk"]:::client
    end

    subgraph Master ["Global Dashboard Server (Laptop/Master)"]
        Dash_App["Flask Dashboard App"]:::dash
        Dash_UI["Dashboard Web UI"]:::dash
    end

    subgraph Agent ["Server-Monitor Agent (Remote Server/VM)"]
        direction TB
        Agent_Flask["Agent Flask Application (port 5000)"]:::agent
        
        subgraph Services ["Agent Services"]
            SSE["SSE Stream (/stream)"]:::agent
            REST["REST APIs (/health, /audit-logs)"]:::agent
            WebUI["Inventory Web UI (/login, /inventory)"]:::agent
            AuthLogger["Audit Trail Logger"]:::agent
            SysMetrics["psutil (Hardware Metrics)"]:::agent
        end
        
        subgraph Storage ["Local CSV Databases"]
            DB_Users[("users.csv")]:::db
            DB_Inventory[("inventory.csv")]:::db
        end
    end

    %% Connections - Users to Dashboard
    U_Admin <-->|"Views Global Logs & Metrics"| Dash_UI
    Dash_UI <-->|"Fetches combined data"| Dash_App
    
    %% Connections - Users to Agent Web UI
    U_Manager & U_Clerk <-->|"HTTP GET/POST<br>(Inventory CRUD, Manage Users)"| WebUI
    WebUI <--> DB_Users & DB_Inventory
    
    %% Connections - Dashboard to Agent
    Dash_App == "HTTP Server-Sent Events (SSE)<br>Bearer Token Auth" ==> SSE
    Dash_App == "HTTP GET (Polling)<br>Bearer Token Auth" ==> REST
    
    %% Internal Agent Connections
    SysMetrics -->|"Provides live metrics"| SSE
    WebUI -->|"Triggers UI action logs"| AuthLogger
    REST -->|"Fetches logged actions"| AuthLogger
    SSE -->|"Triggers view logs"| AuthLogger
```

### Data Flow

1. **Metric Collection**: Each Agent continuously collects system metrics using `psutil`
2. **SSE Streaming**: Metrics are formatted as JSON and streamed via Server-Sent Events every 2 seconds
3. **Authentication**: All requests require Bearer token authentication
4. **Dashboard Connection**: The Master Dashboard connects to multiple agents simultaneously
5. **Real-time Display**: Live metrics are displayed and updated in the dashboard UI

### Communication Protocol

- **Protocol**: HTTP/1.1 with Server-Sent Events (SSE)
- **Content Type**: `text/event-stream`
- **Authentication**: Bearer token via `Authorization` header
- **Update Frequency**: Every 2 seconds per agent
- **Connection**: Persistent keep-alive connections

## Prerequisites

- **Python 3.8+** installed on the target server
- **pip3** (Python package manager)
- **Linux environment** (tested on Ubuntu/Debian, should work on most distributions)
- Network access between the Agent servers and the Master Dashboard

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Run the Installation Script (Recommended)

The easiest way to configure the agent is to run the setup script.

**Linux / macOS:**
```bash
chmod +x install_shell.sh
./install_shell.sh
```

**Windows:**
For native Windows setup, open **PowerShell** and run the included PowerShell script:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```
*(Alternatively, you can run `bash install_shell.sh` if using Git Bash or WSL).*

The script will automatically:
1. Check for Python 3 and pip3 availability
2. Install required dependencies (Flask, psutil, python-dotenv)
3. Generate a secure 32-character API token (if `.env` doesn't exist)
4. Start the Flask agent application on port 5000

### 4. Save Your API Token

When you first run the installation script, a unique API token will be generated and displayed in **bold green**. **Copy this token immediately** - you will need it to configure the Master Dashboard to connect to this agent.

Example output:
```
═══════════════════════════════════════════════════════════
  YOUR API TOKEN: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
═══════════════════════════════════════════════════════════

⚠️  COPY THIS TOKEN! You will need it for the Master Dashboard.
   Store it securely. It will be used to authenticate connections.
```

## Configuration

### Environment Variables

The Agent uses a `.env` file for configuration. After running the installation script, you'll find:

| Variable | Description | Default |
|----------|-------------|---------|
| `API_TOKEN` | Secure token for authentication | Auto-generated UUID |
| `AGENT_HOST` | Host address to bind to | `0.0.0.0` |
| `AGENT_PORT` | Port to listen on | `5000` |

### Customizing the Port or Host

To change the default host or port, edit the `.env` file:

```bash
API_TOKEN=your_token_here
AGENT_HOST=0.0.0.0
AGENT_PORT=8080
```

## API Endpoints

### `/stream` (GET)

Server-Sent Events endpoint that streams real-time metrics.

**Authentication Required:** Yes (Bearer token)

**Audit Trail:** Logs access with timestamp, client IP, MAC address, username, device info, module accessed, action performed, and server status.

**Request Example:**
```bash
curl -H "Authorization: Bearer your_token_here" http://localhost:5000/stream
```

**Response Format (SSE):**

Each SSE event contains a JSON object with the following structure:

```json
{
  "cpu": 12.5,                    // CPU usage percentage
  "ram": {                        // Memory statistics
    "total_gb": 16.0,             // Total RAM in GB
    "used_gb": 8.2,               // Used RAM in GB
    "available_gb": 7.8,          // Available RAM in GB
    "percent": 51.25              // RAM usage percentage
  },
  "disk": {                       // Disk statistics (root partition)
    "total_gb": 500.0,            // Total disk space in GB
    "used_gb": 125.5,             // Used disk space in GB
    "free_gb": 374.5,             // Free disk space in GB
    "percent": 25.1               // Disk usage percentage
  },
  "network": {                    // Network speed statistics
    "sent_mb_s": 0.0523,          // Upload speed in MB/s
    "recv_mb_s": 1.2341           // Download speed in MB/s
  },
  "uptime": 86400.52,             // Server uptime in seconds since last boot
  "timestamp": 1699564823.123     // Unix timestamp of the metric collection
}
```

**Example SSE Stream Output:**
```
data: {"cpu": 12.5, "ram": {"total_gb": 16.0, "used_gb": 8.2, "available_gb": 7.8, "percent": 51.25}, "disk": {"total_gb": 500.0, "used_gb": 125.5, "free_gb": 374.5, "percent": 25.1}, "network": {"sent_mb_s": 0.0523, "recv_mb_s": 1.2341}, "uptime": 86400.52, "timestamp": 1699564823.123}

data: {"cpu": 15.3, "ram": {"total_gb": 16.0, "used_gb": 8.3, "available_gb": 7.7, "percent": 51.88}, "disk": {"total_gb": 500.0, "used_gb": 125.5, "free_gb": 374.5, "percent": 25.1}, "network": {"sent_mb_s": 0.0412, "recv_mb_s": 0.9876}, "uptime": 86402.52, "timestamp": 1699564825.123}
```

Metrics are emitted every 2 seconds as long as the connection remains open.

### `/health` (GET)

Health check endpoint to verify the agent is running.

**Authentication Required:** Yes (Bearer token)

**Audit Trail:** Logs access with full audit trail information.

**Response:**
```json
{
  "status": "healthy",
  "service": "server-monitoring-agent",
  "server_status": "Online"
}
```

### `/audit-logs` (GET)

Retrieve recent audit trail logs for dashboard display.

**Authentication Required:** Yes (Bearer token)

**Query Parameters:**
- `limit` (optional): Number of logs to return (default: 100, max: 1000)

**Audit Trail:** Logs access to this endpoint itself.

**Request Example:**
```bash
curl -H "Authorization: Bearer your_token_here" "http://localhost:5000/audit-logs?limit=50"
```

**Response:**
```json
{
  "count": 5,
  "limit": 50,
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:45.123456",
      "client_ip": "192.168.1.100",
      "client_mac": "00:1A:2B:3C:4D:5E",
      "username": "token_a1b2c3d4",
      "device_info": {
        "browser": "Chrome",
        "os": "Linux",
        "device": "Desktop",
        "user_agent": "Mozilla/5.0..."
      },
      "module_accessed": "stream",
      "action_performed": "View",
      "server_status": "Online",
      "request_method": "GET",
      "request_path": "/stream"
    }
  ]
}
```

### `/swagger` (GET)

Interactive API documentation powered by Swagger UI. Allows you to explore and test all API endpoints directly from your browser.

**Authentication Required:** No (public endpoint for documentation)

**Features:**
- Interactive API explorer
- Try out endpoints directly from the browser
- View request/response schemas
- Authentication support via "Authorize" button

**Access:**
```
http://localhost:5000/swagger/
```

**Note:** While the Swagger UI itself is public, actual API calls to protected endpoints still require valid Bearer token authentication.

### `/static/swagger.json` (GET)

Raw OpenAPI 3.0 specification in JSON format.

**Authentication Required:** No (public endpoint for documentation)

**Usage:**
- Used internally by Swagger UI
- Can be imported into API testing tools (Postman, Insomnia)
- Machine-readable API documentation

## API Documentation

The server includes built-in interactive API documentation via Swagger UI:

- **Swagger UI:** `http://localhost:5000/swagger/`
- **OpenAPI Spec:** `http://localhost:5000/static/swagger.json`

The Swagger documentation includes:
- Complete endpoint descriptions
- Request/response schemas
- Authentication requirements
- Audit trail information for each endpoint
- Try-it-out functionality for testing APIs

## Security

- **Bearer Token Authentication:** Every request must include a valid `Authorization: Bearer <token>` header
- **Token Storage:** The API token is stored in `.env` which is gitignored by default
- **File Permissions:** The `.env` file is created with restrictive permissions (600)

### Connecting from Master Dashboard

When configuring the Master Dashboard, you'll need:
1. The Agent server's IP address
2. The API token (from the `.env` file or installation output)
3. The port number (default: 5000)

Example connection string format:
```
http://192.168.1.100:5000/stream
Authorization: Bearer a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

## Running as a Background Service

For production use, consider running the agent as a systemd service:

```bash
sudo nano /etc/systemd/system/server-monitor-agent.service
```

Example service file:
```ini
[Unit]
Description=Server Monitoring Agent
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/agent
ExecStart=/usr/bin/python3 /path/to/agent/agent_app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable server-monitor-agent
sudo systemctl start server-monitor-agent
```

## Troubleshooting

### "API_TOKEN not found" Error

Ensure the `.env` file exists in the same directory as `agent_app.py` and contains a valid `API_TOKEN`.

### Connection Refused

- Verify the agent is running: `ps aux | grep agent_app.py`
- Check firewall settings: `sudo ufw allow 5000/tcp`
- Ensure the agent is binding to the correct interface (0.0.0.0 for all interfaces)

### High CPU Usage from Agent

The agent uses `psutil.cpu_percent(interval=None)` which is non-blocking. If you experience issues, consider adding a small interval parameter.

## License

MIT License - See LICENSE file for details.

## Support

For issues related to the Agent, please open an issue in this repository. For Master Dashboard issues, refer to the separate repository.
