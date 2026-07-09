#!/usr/bin/env python3
"""
Server Monitoring Agent - Flask Application

This application runs on remote servers and streams real-time hardware metrics
(CPU, RAM, Disk, Network) via Server-Sent Events (SSE) to a Master Dashboard.

Security: All endpoints require Bearer token authentication via API_TOKEN.

Audit Trail: Records and monitors user access with detailed logging including
date/time, client IP, MAC address, username, device info, module accessed,
action performed, and server status.
"""

import os
import time
import uuid
import socket
import subprocess
from datetime import datetime
from flask import Flask, Response, jsonify, request, make_response
from flask_swagger_ui import get_swaggerui_blueprint
from dotenv import load_dotenv
import psutil
import json
import platform
import subprocess

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configuration
API_TOKEN = os.getenv('API_TOKEN')

if not API_TOKEN:
    raise RuntimeError(
        "API_TOKEN not found in environment variables. "
        "Please ensure .env file exists with API_TOKEN set."
    )

# Swagger UI Configuration
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Server Monitoring Agent API",
        'docExpansion': 'list',
        'defaultModelsExpandDepth': 2
    }
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


class AuditTrailLogger:
    """
    Records and maintains an audit trail of user activities.
    Logs access information including IP, MAC, username, device info,
    module accessed, action performed, and server status.
    """

    def __init__(self):
        self.access_logs = []
        self.max_logs = 1000  # Keep last 1000 entries in memory

    def get_client_mac(self, ip_address):
        """
        Attempt to get the MAC address of a client IP on the local network.
        Returns None if not available (e.g., remote connections).
        """
        try:
            # Try ARP lookup for local network
            result = subprocess.run(
                ['arp', '-n', ip_address],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                output = result.stdout
                # Look for MAC address pattern in arp output
                for line in output.split('\n'):
                    if ip_address in line:
                        parts = line.split()
                        for part in parts:
                            if len(part) == 17 and part.count(':') == 5:
                                return part
        except Exception:
            pass
        return None

    def get_device_info(self, user_agent):
        """
        Extract device/browser information from User-Agent string.
        """
        if not user_agent:
            return {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'}

        user_agent_lower = user_agent.lower()

        # Detect browser
        browser = 'Unknown'
        if 'firefox' in user_agent_lower:
            browser = 'Firefox'
        elif 'chrome' in user_agent_lower and 'edg' not in user_agent_lower:
            browser = 'Chrome'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            browser = 'Safari'
        elif 'edg' in user_agent_lower:
            browser = 'Edge'
        elif 'msie' in user_agent_lower or 'trident' in user_agent_lower:
            browser = 'Internet Explorer'
        elif 'curl' in user_agent_lower:
            browser = 'curl'
        elif 'python' in user_agent_lower:
            browser = 'Python Requests'

        # Detect OS
        os_name = 'Unknown'
        if 'windows' in user_agent_lower:
            os_name = 'Windows'
        elif 'mac os' in user_agent_lower or 'macintosh' in user_agent_lower:
            os_name = 'macOS'
        elif 'linux' in user_agent_lower:
            os_name = 'Linux'
        elif 'android' in user_agent_lower:
            os_name = 'Android'
        elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            os_name = 'iOS'

        # Detect device type
        device = 'Desktop'
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower or 'iphone' in user_agent_lower:
            device = 'Mobile'
        elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
            device = 'Tablet'

        return {
            'browser': browser,
            'os': os_name,
            'device': device,
            'user_agent': user_agent[:200]  # Truncate long user agents
        }

    def log_access(self, username=None, module=None, action=None, extra_data=None):
        """
        Log an access event with all required audit trail information.
        """
        client_ip = request.remote_addr or 'Unknown'
        user_agent = request.headers.get('User-Agent', '')
        auth_header = request.headers.get('Authorization', '')

        # Extract username from auth header if available
        if not username:
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                # Use first 8 chars of token as pseudo-username for tracking
                username = f"token_{token[:8]}" if token else 'anonymous'

        timestamp = datetime.now().isoformat()

        # Get MAC address (only works for local network)
        mac_address = self.get_client_mac(client_ip)

        # Get device/browser info
        device_info = self.get_device_info(user_agent)

        # Determine server status
        server_status = 'Online'

        # Build audit log entry
        log_entry = {
            'timestamp': timestamp,
            'client_ip': client_ip,
            'client_mac': mac_address if mac_address else 'N/A (remote)',
            'username': username or 'anonymous',
            'device_info': device_info,
            'module_accessed': module or request.endpoint or 'Unknown',
            'action_performed': action or 'View',
            'server_status': server_status,
            'request_method': request.method,
            'request_path': request.path
        }

        # Add any extra data passed
        if extra_data:
            log_entry['extra_data'] = extra_data

        # Store in memory (circular buffer)
        self.access_logs.append(log_entry)
        if len(self.access_logs) > self.max_logs:
            self.access_logs.pop(0)

        return log_entry

    def get_recent_logs(self, limit=100):
        """Return the most recent audit logs."""
        return self.access_logs[-limit:]

    def get_server_status(self):
        """Get current server status."""
        return 'Online'


# Global audit trail logger instance
audit_logger = AuditTrailLogger()


class NetworkSpeedMonitor:
    """
    Monitor network speed by calculating the difference in bytes sent/received
    between consecutive readings.
    """

    def __init__(self):
        self._last_sent = None
        self._last_recv = None
        self._last_time = None

    def get_speed(self):
        """
        Calculate network speed in MB/s for both sent and received data.

        Returns:
            dict: Contains 'sent_mb_s' and 'recv_mb_s' values.
        """
        current_stats = psutil.net_io_counters()
        current_time = time.time()

        # Initialize on first call
        if self._last_sent is None:
            self._last_sent = current_stats.bytes_sent
            self._last_recv = current_stats.bytes_recv
            self._last_time = current_time
            return {'sent_mb_s': 0.0, 'recv_mb_s': 0.0}

        # Calculate time elapsed and byte differences
        time_elapsed = current_time - self._last_time
        if time_elapsed <= 0:
            time_elapsed = 1e-6  # Prevent division by zero

        bytes_sent_diff = current_stats.bytes_sent - self._last_sent
        bytes_recv_diff = current_stats.bytes_recv - self._last_recv

        # Convert to MB/s (bytes / seconds / 1024^2)
        sent_mb_s = (bytes_sent_diff / time_elapsed) / (1024 * 1024)
        recv_mb_s = (bytes_recv_diff / time_elapsed) / (1024 * 1024)

        # Update last values for next iteration
        self._last_sent = current_stats.bytes_sent
        self._last_recv = current_stats.bytes_recv
        self._last_time = current_time

        return {
            'sent_mb_s': round(sent_mb_s, 4),
            'recv_mb_s': round(recv_mb_s, 4)
        }


# Global network monitor instance
network_monitor = NetworkSpeedMonitor()


@app.before_request
def verify_authorization():
    """
    Middleware to verify Bearer token authentication on every request.

    Expects header: Authorization: Bearer <API_TOKEN>
    Returns 401 Unauthorized if token is missing or invalid.
    """
    # Handle CORS preflight explicitly
    if request.method == 'OPTIONS':
        res = make_response('', 204)
        res.headers['Access-Control-Allow-Origin'] = '*'
        res.headers['Access-Control-Allow-Methods'] = '*'
        res.headers['Access-Control-Allow-Headers'] = '*'
        return res
    
    # Skip authorization for Swagger UI endpoints
    if request.path.startswith('/swagger') or request.path.startswith('/static'):
        return None

    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return jsonify({'error': 'Missing Authorization header'}), 401

    # Expected format: "Bearer <token>"
    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return jsonify({'error': 'Invalid Authorization header format. Use: Bearer <token>'}), 401

    token = parts[1]

    if token != API_TOKEN:
        return jsonify({'error': 'Invalid API token'}), 401

    return None


@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    return response

@app.route('/stream', methods=['GET', 'OPTIONS'])
def stream_metrics():
    """
    Server-Sent Events endpoint that streams real-time system metrics.

    Emits JSON-formatted metrics every 2 seconds including:
    - CPU usage percentage
    - Memory stats (total, used, available, percent)
    - Disk stats (total, used, free, percent)
    - Network speed (MB/s sent and received)
    - Server uptime in seconds

    Handles client disconnects gracefully without crashing the server.
    
    Audit Trail: Logs access with timestamp, client IP, MAC address, username,
    device info, module accessed, action performed, and server status.
    """

    # Log initial access to the stream endpoint
    audit_logger.log_access(
        module='stream',
        action='View',
        extra_data={'endpoint_type': 'SSE_stream'}
    )

    def generate_metrics():
        """Generator function that yields SSE-formatted metrics."""
        try:
            while True:
                # Gather CPU metrics
                cpu_percent = psutil.cpu_percent(interval=None)

                # Gather Memory metrics
                memory = psutil.virtual_memory()
                memory_stats = {
                    'total_gb': round(memory.total / (1024 ** 3), 2),
                    'used_gb': round(memory.used / (1024 ** 3), 2),
                    'available_gb': round(memory.available / (1024 ** 3), 2),
                    'percent': memory.percent
                }

                # Gather Disk metrics (root partition)
                disk = psutil.disk_usage('/')
                disk_stats = {
                    'total_gb': round(disk.total / (1024 ** 3), 2),
                    'used_gb': round(disk.used / (1024 ** 3), 2),
                    'free_gb': round(disk.free / (1024 ** 3), 2),
                    'percent': disk.percent
                }

                # Gather Network speed metrics
                network_stats = network_monitor.get_speed()

                # Calculate server uptime in seconds
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time

                # Compile all metrics into a single payload
                metrics = {
                    'cpu': cpu_percent,
                    'ram': memory_stats,
                    'disk': disk_stats,
                    'network': network_stats,
                    'uptime': round(uptime_seconds, 2),
                    'timestamp': time.time(),
                    'server_status': audit_logger.get_server_status()
                }

                # Format as SSE: "data: {json}\n\n"
                yield f"data: {json.dumps(metrics)}\n\n"

                # Wait 2 seconds before next reading
                time.sleep(2)

        except (GeneratorExit, BrokenPipeError, ConnectionResetError):
            # Client disconnected - exit gracefully
            print("[INFO] Client disconnected from /stream endpoint")
            # Log disconnection
            audit_logger.log_access(
                module='stream',
                action='Disconnect',
                extra_data={'endpoint_type': 'SSE_stream'}
            )
            return
        except Exception as e:
            # Log unexpected errors but don't crash
            print(f"[ERROR] Unexpected error in metrics generator: {e}")
            return

    # Return SSE response with appropriate headers
    return Response(
        generate_metrics(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering if applicable
        }
    )


@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    """
    Health check endpoint for verifying the agent is running.
    Requires valid authentication.
    
    Audit Trail: Logs access with timestamp, client IP, MAC address, username,
    device info, module accessed, action performed, and server status.
    """
    # Log access to health endpoint
    audit_logger.log_access(
        module='health',
        action='View',
        extra_data={'endpoint_type': 'health_check'}
    )
    
    return jsonify({
        'status': 'healthy',
        'service': 'server-monitoring-agent',
        'server_status': audit_logger.get_server_status()
    }), 200


@app.route('/audit-logs', methods=['GET'])
def get_audit_logs():
    """
    Endpoint to retrieve recent audit trail logs.
    Returns the most recent access logs for the dashboard.
    
    Query Parameters:
    - limit: Number of logs to return (default: 100, max: 1000)
    
    Audit Trail: Logs access to this endpoint itself.
    """
    # Log access to audit logs endpoint
    audit_logger.log_access(
        module='audit-logs',
        action='View',
        extra_data={'endpoint_type': 'audit_log_retrieval'}
    )
    
    # Get limit from query params
    try:
        limit = int(request.args.get('limit', 100))
        limit = min(limit, 1000)  # Cap at 1000
        limit = max(limit, 1)     # Minimum 1
    except ValueError:
        limit = 100
    
    logs = audit_logger.get_recent_logs(limit)
    
    return jsonify({
        'count': len(logs),
        'limit': limit,
        'logs': logs
    }), 200


def get_gpu_info():
    """Attempt to get basic GPU info using lspci or wmic."""
    gpus = []
    try:
        system = platform.system()
        if system == "Windows":
            result = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"], 
                text=True, stderr=subprocess.DEVNULL
            )
            lines = [line.strip() for line in result.split('\n') if line.strip()]
            if len(lines) > 1:
                gpus.extend(lines[1:])
        elif system == "Linux":
            result = subprocess.check_output(
                ["lspci"], 
                text=True, stderr=subprocess.DEVNULL
            )
            for line in result.split('\n'):
                if "VGA compatible controller" in line or "3D controller" in line:
                    gpus.append(line.split(":")[-1].strip())
    except Exception:
        pass
    return gpus if gpus else ["Unknown GPU or not detected"]

@app.route('/api/specs', methods=['GET', 'OPTIONS'])
def get_specs():
    """Returns static hardware specifications of the server."""
    if request.method == 'OPTIONS':
        res = make_response('', 204)
        res.headers['Access-Control-Allow-Origin'] = '*'
        res.headers['Access-Control-Allow-Methods'] = '*'
        res.headers['Access-Control-Allow-Headers'] = '*'
        return res

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    specs = {
        'hostname': platform.node(),
        'os': f"{platform.system()} {platform.release()} ({platform.machine()})",
        'cpu': {
            'model': platform.processor() or "Unknown CPU",
            'cores': psutil.cpu_count(logical=False),
            'threads': psutil.cpu_count(logical=True)
        },
        'ram': {
            'total_gb': round(memory.total / (1024**3), 2)
        },
        'disk': {
            'total_gb': round(disk.total / (1024**3), 2)
        },
        'gpu': get_gpu_info()
    }
    return jsonify(specs), 200


@app.errorhandler(401)
def unauthorized_error(error):
    """Custom handler for 401 Unauthorized errors."""
    return jsonify({'error': 'Unauthorized - Invalid or missing API token'}), 401


@app.errorhandler(404)
def not_found_error(error):
    """Custom handler for 404 Not Found errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Custom handler for 500 Internal Server errors."""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Get host and port from environment or use defaults
    host = os.getenv('AGENT_HOST', '0.0.0.0')
    port = int(os.getenv('AGENT_PORT', 5000))

    print(f"[INFO] Starting Server Monitoring Agent on {host}:{port}")
    print(f"[INFO] SSE Endpoint: http://{host}:{port}/stream")
    print(f"[INFO] Health Check: http://{host}:{port}/health")
    print(f"[INFO] Audit Logs: http://{host}:{port}/audit-logs")
    print(f"[INFO] Swagger UI: http://{host}:{port}/swagger")
    print(f"[INFO] API Token: {API_TOKEN}")
    print("")
    print("═══════════════════════════════════════════════════════════")
    print(f"  YOUR API TOKEN: {API_TOKEN}")
    print("═══════════════════════════════════════════════════════════")
    print("")
    print("Audit Trail Features:")
    print("  - Date and Time of Access")
    print("  - Client IP Address")
    print("  - Client MAC Address (local network only)")
    print("  - Username (from token)")
    print("  - Device/Browser Information")
    print("  - Menu/Module Accessed")
    print("  - Action Performed (View, Disconnect, etc.)")
    print("  - Server Status (Online/Offline)")
    print("")

    # Run Flask app (debug=False for production)
    app.run(host=host, port=port, debug=False, threaded=True)
