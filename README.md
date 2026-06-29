# Server Monitoring Agent

A distributed server monitoring agent that streams real-time hardware metrics via Server-Sent Events (SSE). This is the **Agent** component of a two-part monitoring system designed for local network deployment.

## Overview

This repository contains the Agent application that runs on remote Linux servers. It collects and streams:

- **CPU Usage** - Real-time processor utilization percentage
- **Memory (RAM)** - Total, used, available memory and usage percentage
- **Disk Usage** - Root partition statistics (total, used, free, percent)
- **Network Speed** - Real-time upload/download speeds in MB/s

The Agent exposes a secure SSE endpoint that the Master Dashboard (running on your laptop) connects to for live data visualization.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Agent Server  │     │   Agent Server  │     │   Agent Server  │
│   (Remote #1)   │     │   (Remote #2)   │     │   (Remote #3)   │
│                 │     │                 │     │                 │
│  - Flask App    │     │  - Flask App    │     │  - Flask App    │
│  - psutil       │     │  - psutil       │     │  - psutil       │
│  - SSE Stream   │     │  - SSE Stream   │     │  - SSE Stream   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  Bearer Token Auth    │  Bearer Token Auth    │  Bearer Token Auth
         │  + SSE Stream         │  + SSE Stream         │  + SSE Stream
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Master Dashboard (Your Laptop)                │
│              (Separate Repository - Future Task)                 │
│         - UI for displaying live metrics from all agents         │
│         - Configuration management (IPs and tokens)              │
└─────────────────────────────────────────────────────────────────┘
```

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

### 2. Make the Installation Script Executable

```bash
chmod +x install_shell.sh
```

### 3. Run the Installation Script

```bash
./install_shell.sh
```

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

**Request Example:**
```bash
curl -H "Authorization: Bearer your_token_here" http://localhost:5000/stream
```

**Response Format (SSE):**
```
data: {"cpu": 12.5, "ram": {"total_gb": 16.0, "used_gb": 8.2, ...}, ...}

data: {"cpu": 15.3, "ram": {"total_gb": 16.0, "used_gb": 8.3, ...}, ...}
```

Metrics are emitted every 2 seconds.

### `/health` (GET)

Health check endpoint to verify the agent is running.

**Authentication Required:** Yes (Bearer token)

**Response:**
```json
{
  "status": "healthy",
  "service": "server-monitoring-agent"
}
```

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