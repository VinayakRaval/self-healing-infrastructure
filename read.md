# Self-Healing Infrastructure

Automated service monitoring and recovery using **Prometheus, Alertmanager, Blackbox Exporter, Python Flask, Ansible, Docker and AWS EC2**.

## Project Overview

This project demonstrates a self-healing infrastructure system that detects an NGINX service failure and attempts to restore it automatically.

Instead of manually restarting a failed service, monitoring and automation components work together to detect the issue, trigger an alert and execute an Ansible recovery playbook.

## Architecture

```text
             NGINX Application
                    |
                    v
             Blackbox Exporter
                    |
                    v
                Prometheus
                    |
                    v
               Alertmanager
                    |
                    v
           Python Flask Webhook
                    |
                    v
             Ansible Playbook
                    |
                    v
           NGINX Container Restart
```

## Technologies Used

- AWS EC2
- Ubuntu Linux
- Docker
- Docker Compose
- Prometheus
- Blackbox Exporter
- Alertmanager
- Python
- Flask
- Ansible
- YAML
- Git and GitHub

## Project Structure

```text
self-healing-infrastructure/
│
├── ansible/
│   └── restart-nginx.yml
│
├── alertmanager/
│   ├── alertmanager.yml
│   └── alertmanager.example.yml
│
├── blackbox/
│   └── blackbox.yml
│
├── prometheus/
│   ├── prometheus.yml
│   └── alert.rules.yml
│
├── webhook/
│   ├── app.py
│   └── Dockerfile
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

# Complete Installation and Setup

## Step 1: Create AWS EC2 Instance

1. Open the AWS Management Console.
2. Navigate to EC2.
3. Launch an Ubuntu EC2 instance.
4. Select an appropriate instance type.
5. Create or select a key pair and download the `.pem` file.
6. Configure the security group.

Recommended inbound rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your IP |
| HTTP | 80 | 0.0.0.0/0 |

Do not expose ports 5001, 9090, 9093 or 9115 publicly. Access monitoring dashboards through SSH tunnelling.

## Step 2: Connect to EC2

From Windows PowerShell:

```powershell
cd C:\Users\YOUR_USERNAME\OneDrive\Desktop\devops

ssh -i "vinu.pem" ubuntu@YOUR_EC2_PUBLIC_DNS
```

Replace `YOUR_EC2_PUBLIC_DNS` with your EC2 public DNS.

## Step 3: Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

Install required packages:

```bash
sudo apt install -y \
  ca-certificates \
  curl \
  gnupg \
  git \
  python3 \
  python3-pip \
  python3-flask \
  ansible
```

## Step 4: Install Docker

Add Docker's official package repository:

```bash
sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Install Docker Engine and Compose:

```bash
sudo apt update

sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Start Docker:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Verify installation:

```bash
sudo docker --version
sudo docker compose version
```

## Step 5: Create Project Directories

```bash
mkdir -p ~/self-healing-infrastructure

cd ~/self-healing-infrastructure

mkdir -p ansible
mkdir -p alertmanager
mkdir -p blackbox
mkdir -p prometheus
mkdir -p webhook
```

Verify:

```bash
tree
```

If `tree` is unavailable:

```bash
sudo apt install tree -y
tree
```

## Step 6: Configure Blackbox Exporter

Create the configuration:

```bash
nano blackbox/blackbox.yml
```

Configuration:

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      method: GET
      preferred_ip_protocol: ip4
```

Save and exit Nano using `Ctrl + O`, `Enter`, and `Ctrl + X`.

## Step 7: Configure Prometheus

Create the configuration:

```bash
nano prometheus/prometheus.yml
```

Configuration:

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

rule_files:
  - /etc/prometheus/alert.rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

scrape_configs:

  - job_name: prometheus
    static_configs:
      - targets:
          - localhost:9090

  - job_name: nginx
    metrics_path: /probe
    params:
      module: [http_2xx]

    static_configs:
      - targets:
          - http://nginx-app:80

    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target

      - source_labels: [__param_target]
        target_label: instance

      - target_label: __address__
        replacement: blackbox-exporter:9115
```

## Step 8: Configure Prometheus Alert Rules

Create:

```bash
nano prometheus/alert.rules.yml
```

Configuration:

```yaml
groups:
  - name: nginx-self-healing
    rules:
      - alert: NginxDown
        expr: probe_success{job="nginx"} == 0
        for: 15s
        labels:
          severity: critical
        annotations:
          summary: "NGINX service is down"
          description: "NGINX HTTP health check has failed."
```

Validate the rules after Prometheus is running:

```bash
sudo docker exec prometheus \
  promtool check rules /etc/prometheus/alert.rules.yml
```

## Step 9: Configure Alertmanager

Create the actual configuration:

```bash
nano alertmanager/alertmanager.yml
```

Configuration:

```yaml
global:
  resolve_timeout: 1m

route:
  receiver: self-healing-webhook
  group_wait: 5s
  group_interval: 10s
  repeat_interval: 1m

receivers:
  - name: self-healing-webhook
    webhook_configs:
      - url: http://host.docker.internal:5001/webhook
        send_resolved: false
        http_config:
          authorization:
            type: Bearer
            credentials: REPLACE_WITH_YOUR_NEW_TOKEN
```

Generate a new secure token:

```bash
openssl rand -hex 32
```

Replace `REPLACE_WITH_YOUR_NEW_TOKEN` with the generated token.

**Security:** Use the same token in the Flask process. Never publish your real token in GitHub.

## Step 10: Create Ansible Recovery Playbook

Create:

```bash
nano ansible/restart-nginx.yml
```

Configuration:

```yaml
---
- name: Self-Healing NGINX Recovery
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Restart NGINX Docker container
      command: docker restart nginx-app

    - name: Verify NGINX container is running
      command: docker inspect -f '{{.State.Running}}' nginx-app
      register: nginx_status
      retries: 5
      delay: 3
      until: nginx_status.stdout == "true"

    - name: Verify NGINX HTTP response
      uri:
        url: http://localhost
        status_code: 200
      register: nginx_http
      retries: 5
      delay: 3
      until: nginx_http.status == 200

    - name: Display recovery result
      debug:
        msg: "NGINX recovered successfully!"
```

Test the playbook manually after starting NGINX:

```bash
cd ~/self-healing-infrastructure

sudo ansible-playbook ansible/restart-nginx.yml
```

## Step 11: Configure Restricted Ansible Permissions

Create a sudoers file:

```bash
sudo visudo -f /etc/sudoers.d/self-healing
```

Add:

```text
ubuntu ALL=(root) NOPASSWD: /usr/bin/ansible-playbook /home/ubuntu/self-healing-infrastructure/ansible/restart-nginx.yml
```

Validate:

```bash
sudo visudo -cf /etc/sudoers.d/self-healing
```

Test passwordless execution:

```bash
sudo -n /usr/bin/ansible-playbook \
  /home/ubuntu/self-healing-infrastructure/ansible/restart-nginx.yml
```

## Step 12: Create Flask Webhook Application

Create:

```bash
nano webhook/app.py
```

Configuration:

```python
import os
import hmac
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")

PLAYBOOK = (
    "/home/ubuntu/self-healing-infrastructure/"
    "ansible/restart-nginx.yml"
)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "Webhook receiver is running"
    }), 200


@app.route("/webhook", methods=["POST"])
def receive_alert():

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

    if alert_status != "firing":
        return jsonify({
            "message": "No recovery required"
        }), 200

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
            return jsonify({
                "status": "success",
                "message": "NGINX restarted successfully",
                "ansible_output": result.stdout
            }), 200

        return jsonify({
            "status": "failed",
            "error": result.stderr
        }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "failed",
            "message": "Ansible execution timed out"
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False
    )
```

## Step 13: Start Flask Webhook

Generate or use the same new token configured in Alertmanager.

```bash
export WEBHOOK_TOKEN='YOUR_NEW_TOKEN'
```

Start Flask:

```bash
cd ~/self-healing-infrastructure/webhook

python3 app.py
```

Keep this terminal running.

Open another SSH terminal and test:

```bash
curl http://localhost:5001/health
```

Expected response:

```json
{
  "status": "Webhook receiver is running"
}
```

## Step 14: Create Docker Compose Configuration

Create the root-level file:

```bash
cd ~/self-healing-infrastructure

nano docker-compose.yml
```

Configuration:

```yaml
services:

  nginx:
    image: nginx:alpine
    container_name: nginx-app
    ports:
      - "80:80"
    networks:
      - monitoring
    restart: unless-stopped

  blackbox-exporter:
    image: prom/blackbox-exporter:latest
    container_name: blackbox-exporter
    command:
      - "--config.file=/etc/blackbox_exporter/config.yml"
    volumes:
      - ./blackbox/blackbox.yml:/etc/blackbox_exporter/config.yml:ro
    ports:
      - "127.0.0.1:9115:9115"
    networks:
      - monitoring
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/alert.rules.yml:/etc/prometheus/alert.rules.yml:ro
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
    ports:
      - "127.0.0.1:9090:9090"
    depends_on:
      - blackbox-exporter
      - alertmanager
    networks:
      - monitoring
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    command:
      - "--config.file=/etc/alertmanager/alertmanager.yml"
    ports:
      - "127.0.0.1:9093:9093"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - monitoring
    restart: unless-stopped

networks:
  monitoring:
    name: monitoring
    driver: bridge

volumes:
  prometheus-data:
```

## Step 15: Start All Docker Services

Validate the Compose configuration:

```bash
sudo docker compose config
```

Start all services:

```bash
sudo docker compose up -d
```

Check container status:

```bash
sudo docker compose ps
```

View logs:

```bash
sudo docker compose logs
```

View individual service logs:

```bash
sudo docker logs nginx-app
sudo docker logs prometheus
sudo docker logs blackbox-exporter
sudo docker logs alertmanager
```

## Step 16: Validate Prometheus and Alertmanager

Check Prometheus configuration:

```bash
sudo docker exec prometheus \
  promtool check config /etc/prometheus/prometheus.yml
```

Check alert rules:

```bash
sudo docker exec prometheus \
  promtool check rules /etc/prometheus/alert.rules.yml
```

Check Alertmanager configuration:

```bash
sudo docker exec alertmanager \
  amtool check-config /etc/alertmanager/alertmanager.yml
```

Check service readiness:

```bash
curl http://localhost:9090/-/ready
curl http://localhost:9093/-/ready
curl http://localhost:5001/health
```

## Step 17: Access Prometheus Dashboard

On your Windows PowerShell, open an SSH tunnel:

```powershell
ssh -i "vinu.pem" -L 9090:localhost:9090 ubuntu@YOUR_EC2_PUBLIC_DNS
```

Keep the SSH session open.

Open your browser:

```text
http://localhost:9090
```

Run this Prometheus query:

```promql
probe_success
```

Expected result:

```text
1
```

Meaning:

- `1` = NGINX is reachable.
- `0` = NGINX health check failed.

## Step 18: Access Alertmanager Dashboard

Open another PowerShell terminal:

```powershell
ssh -i "vinu.pem" -L 9093:localhost:9093 ubuntu@YOUR_EC2_PUBLIC_DNS
```

Open:

```text
http://localhost:9093
```

## Step 19: Test Docker-to-Flask Connectivity

From the EC2 terminal:

```bash
sudo docker run --rm \
  --network monitoring \
  --add-host host.docker.internal:host-gateway \
  curlimages/curl:latest \
  http://host.docker.internal:5001/health
```

Expected response:

```json
{
  "status": "Webhook receiver is running"
}
```

If this fails, check that Flask is running and listening on `0.0.0.0:5001`.

## Step 20: Test Automatic Recovery

First verify that NGINX is running:

```bash
sudo docker ps
```

Stop NGINX to simulate a failure:

```bash
sudo docker stop nginx-app
```

Wait for Prometheus to detect the failure and Alertmanager to send the webhook.

Check Prometheus:

```bash
curl -s "http://localhost:9090/api/v1/query?query=probe_success"
```

Check Flask terminal output for the incoming alert and Ansible execution.

Check NGINX status:

```bash
sudo docker ps -a
```

Check the HTTP response:

```bash
curl -I http://localhost
```

Expected successful HTTP response:

```text
HTTP/1.1 200 OK
```

The test is successful only when the firing alert reaches Flask, Ansible executes successfully, and NGINX becomes available again.

## Step 21: Useful Docker Commands

Check running containers:

```bash
sudo docker ps
```

Check all containers:

```bash
sudo docker ps -a
```

Stop services:

```bash
sudo docker compose down
```

Start services:

```bash
sudo docker compose up -d
```

Restart services:

```bash
sudo docker compose restart
```

Rebuild and start services:

```bash
sudo docker compose up -d --build
```

Follow logs:

```bash
sudo docker compose logs -f
```

Restart an individual container:

```bash
sudo docker restart nginx-app
```

## Step 22: GitHub Repository Setup

Create a new GitHub repository named:

```text
self-healing-infrastructure
```

Initialize Git:

```bash
cd ~/self-healing-infrastructure

git init -b main
```

Configure your Git identity:

```bash
git config --global user.name "Vinayak Raval"
git config --global user.email "YOUR_GITHUB_EMAIL"
```

Create `.gitignore`:

```bash
nano .gitignore
```

Add:

```gitignore
.env
.env.*
!.env.example

*.pem
*.key
secrets/

alertmanager/alertmanager.yml

__pycache__/
*.pyc
.venv/
*.log
.DS_Store
```

Create a safe example Alertmanager configuration for GitHub:

```bash
cp alertmanager/alertmanager.yml \
   alertmanager/alertmanager.example.yml
```

Edit the example:

```bash
nano alertmanager/alertmanager.example.yml
```

Replace the actual token with:

```text
REPLACE_WITH_YOUR_NEW_TOKEN
```

Check that the real configuration is ignored:

```bash
git check-ignore alertmanager/alertmanager.yml
```

Check files before committing:

```bash
git status
```

Add files:

```bash
git add .
```

Review staged files:

```bash
git status
```

Commit:

```bash
git commit -m "Initial commit: Self-Healing Infrastructure"
```

Connect your GitHub repository:

```bash
git remote add origin \
  https://github.com/YOUR_GITHUB_USERNAME/self-healing-infrastructure.git
```

Push:

```bash
git push -u origin main
```

For HTTPS authentication, use a GitHub Personal Access Token when prompted. Never put the token in the remote URL or commit it to the repository.

---

# How the Project Works

1. NGINX runs inside a Docker container.
2. Blackbox Exporter continuously checks NGINX HTTP availability.
3. Prometheus collects the health-check metrics.
4. If `probe_success` becomes `0` for 15 seconds, the `NginxDown` alert fires.
5. Alertmanager sends an authenticated webhook notification.
6. Python Flask receives and verifies the alert.
7. Flask invokes the Ansible recovery playbook.
8. Ansible restarts the NGINX container.
9. Ansible checks that NGINX is running and returns an HTTP 200 response.

# Security

- Never commit AWS `.pem` files or webhook tokens.
- Keep the real `alertmanager.yml` out of GitHub.
- Keep Prometheus, Alertmanager, Blackbox Exporter and Flask ports private.
- Use SSH tunnels to access monitoring dashboards.
- Restrict passwordless sudo to the specific Ansible playbook.
- Use a newly generated webhook token if an earlier token was exposed.

# Project Status

The monitoring setup, Prometheus alert-rule validation, Alertmanager readiness and Flask health endpoint have been tested.

**End-to-end automatic recovery must be confirmed through the NGINX failure simulation before claiming that the complete recovery workflow is operational.**

# Future Enhancements

- Add Grafana dashboards for infrastructure visualization.
- Monitor additional application services.
- Add recovery notifications.
- Add more advanced recovery and health-check policies.

# Author

**Vinayak Raval**

Cloud & DevOps Engineering

GitHub: https://github.com/VinayakRaval