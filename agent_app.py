#!/usr/bin/env python3
"""
Server Monitoring Agent - Flask Application

This application runs on remote servers and streams real-time hardware metrics
(CPU, RAM, Disk, Network) via Server-Sent Events (SSE) to a Master Dashboard.

Security: All endpoints require Bearer token authentication via API_TOKEN.
"""

import os
import time
import uuid
from flask import Flask, Response, jsonify, request, make_response
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

    Handles client disconnects gracefully without crashing the server.
    """

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

                # Compile all metrics into a single payload
                metrics = {
                    'cpu': cpu_percent,
                    'ram': memory_stats,
                    'disk': disk_stats,
                    'network': network_stats,
                    'timestamp': time.time()
                }

                # Format as SSE: "data: {json}\n\n"
                yield f"data: {json.dumps(metrics)}\n\n"

                # Wait 2 seconds before next reading
                time.sleep(2)

        except (GeneratorExit, BrokenPipeError, ConnectionResetError):
            # Client disconnected - exit gracefully
            print("[INFO] Client disconnected from /stream endpoint")
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
    """
    return jsonify({
        'status': 'healthy',
        'service': 'server-monitoring-agent'
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
    print(f"[INFO] API Token: {API_TOKEN}")
    print("")
    print("═══════════════════════════════════════════════════════════")
    print(f"  YOUR API TOKEN: {API_TOKEN}")
    print("═══════════════════════════════════════════════════════════")
    print("")

    # Run Flask app (debug=False for production)
    app.run(host=host, port=port, debug=False, threaded=True)
