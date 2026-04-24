# VM Deployment + CI/CD

This project now includes:

- `docker-compose.prod.yml` for production services (Postgres, Redis, FastAPI, Frontend+Nginx)
- `.github/workflows/deploy-vm.yml` for CI + auto deploy on `main`
- `backend/.env.prod.example` as the production env template

## Shared VM safety (important)

This setup is tuned to avoid impacting other apps on the same VM:

- Uses a dedicated compose project name: `skill-intelligence`
- Does not run destructive cleanup commands like `docker system prune`
- Frontend binds to `127.0.0.1:${APP_HOST_PORT:-8088}` instead of host port `80`

## 1) One-time VM setup

SSH to your server:

```bash
ssh <username>@<server-ip>
```

Install required packages:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
```

Install Docker + Compose plugin:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Clone your repo:

```bash
mkdir -p /opt/skill-intelligence
cd /opt/skill-intelligence
git clone <your-repo-url> .
```

Create production env file:

```bash
cp backend/.env.prod.example backend/.env

# Optional: choose a host port that does not conflict with other services
echo "APP_HOST_PORT=8088" > .env

# Keep Docker resources isolated from other projects on this VM
export COMPOSE_PROJECT_NAME=skill-intelligence
```

Edit `backend/.env` and set at least:

- `SECRET_KEY`
- `OPENAI_API_KEY` and/or `GEMINI_API_KEY` (if needed)

Start once manually:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1:8088/api/health
```

## 2) Configure GitHub Actions secrets

In your repo settings, add:

- `VM_HOST` = your server public IP
- `VM_USER` = VM SSH username
- `VM_SSH_PRIVATE_KEY` = private key used for SSH auth
- `VM_DEPLOY_PATH` = `/opt/skill-intelligence`

## 3) CI/CD flow

On every push to `main`:

1. Backend dependency install + compile check
2. Frontend build check
3. SSH into VM
4. `git pull --ff-only origin main`
5. `docker compose -f docker-compose.prod.yml up -d --build`
6. API health check runs inside the `api` container (does not rely on host ports)

## 4) Recommended hardening

- Use SSH keys (disable password auth in SSH later)
- Put Nginx with TLS (Let's Encrypt) in front if exposing directly to internet
- Restrict firewall to only ports 22/80/443
- Rotate secrets and API keys periodically
