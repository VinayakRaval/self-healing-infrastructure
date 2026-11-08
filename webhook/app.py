import os
import hmac
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# Webhook authentication token
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")

# Ansible playbook path
PLAYBOOK = "/home/ubuntu/self-healing-infrastructure/ansible/restart-nginx.yml"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "Webhook receiver is running"
    }), 200


@app.route("/webhook", methods=["POST"])
def receive_alert():

    # Verify authentication
    auth_header = request.headers.get("Authorization", "")
    expected_header = f"Bearer {WEBHOOK_TOKEN}" if WEBHOOK_TOKEN else ""

    if not WEBHOOK_TOKEN or not hmac.compare_digest(
        auth_header, expected_header
    ):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    alert_status = data.get("status")

    print(f"Received Alert: {alert_status}", flush=True)

    # Process only firing alerts
    if alert_status != "firing":
        return jsonify({
            "message": "No recovery required"
        }), 200

    # Execute Ansible recovery playbook
    try:
        result = subprocess.run(
            [
                "sudo",
                "/usr/bin/ansible-playbook",
                PLAYBOOK
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print("NGINX recovery successful!", flush=True)

            return jsonify({
                "status": "success",
                "message": "NGINX restarted successfully",
                "ansible_output": result.stdout
            }), 200

        print(result.stderr, flush=True)

        return jsonify({
            "status": "failed",
            "message": "Ansible recovery failed",
            "error": result.stderr
        }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "failed",
            "message": "Ansible execution timed out"
        }), 500

    except Exception as error:
        return jsonify({
            "status": "failed",
            "message": str(error)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False
    )