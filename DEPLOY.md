# Amazon Review Insight Server Deployment

This guide deploys the app with Docker Compose on a Linux server.

## 1. Server Prerequisites

Ubuntu/Debian example:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

Optional, allow the current SSH user to run Docker without `sudo`:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

## 2. Upload Or Clone Project

If using Git:

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> amazon-review-insight
sudo chown -R "$USER":"$USER" /opt/amazon-review-insight
cd /opt/amazon-review-insight
```

If copying from your local machine:

```bash
rsync -av --exclude .git --exclude .venv --exclude node_modules --exclude frontend/node_modules \
  /path/to/amazon-review-insight/ user@SERVER_IP:/opt/amazon-review-insight/
```

Then on the server:

```bash
cd /opt/amazon-review-insight
```

## 3. Configure Environment

```bash
cp .env.production.example .env
openssl rand -hex 32
nano .env
```

Fill at least:

```env
APP_PORT=80
ANALYTICS_ADMIN_TOKEN=<token-from-openssl>
DEEPSEEK_API_KEY=<your-provider-key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

If another service already owns port `80`, set:

```env
APP_PORT=8081
```

## 4. Start Production Stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Check health:

```bash
set -a
source .env
set +a
curl -i http://127.0.0.1:${APP_PORT:-80}/api/health
curl -i http://127.0.0.1:${APP_PORT:-80}/
```

Visit:

- User app: `http://SERVER_IP/`
- Admin analytics: `http://SERVER_IP/admin`

The admin page requires `ANALYTICS_ADMIN_TOKEN`.

## 5. Firewall

If the app owns port `80`:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

Do not expose Redis or backend ports publicly. `docker-compose.prod.yml` only publishes the frontend port.

## 6. Domain And HTTPS

### Option A: Use Cloudflare / external HTTPS proxy

Point your domain to the server and proxy traffic to:

```text
http://SERVER_IP:80
```

The app records visitor IPs from these headers, in order:

1. `CF-Connecting-IP`
2. `X-Forwarded-For`
3. `X-Real-IP`
4. direct client IP

### Option B: Host Nginx reverse proxy on the server

Set `.env`:

```env
APP_PORT=8081
```

Restart:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Install Nginx:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/amazon-review-insight`:

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN.com;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and issue TLS:

```bash
sudo ln -s /etc/nginx/sites-available/amazon-review-insight /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d YOUR_DOMAIN.com
```

## 7. Common Operations

Deploy updates:

```bash
cd /opt/amazon-review-insight
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

View logs:

```bash
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
```

Restart:

```bash
docker compose -f docker-compose.prod.yml restart
```

Stop:

```bash
docker compose -f docker-compose.prod.yml down
```

Backup run artifacts and Redis analytics/job data:

```bash
mkdir -p backups
tar -czf "backups/runs-$(date +%Y%m%d-%H%M%S).tar.gz" runs
docker run --rm \
  -v amazon-review-insight_redis_data:/data \
  -v "$PWD/backups:/backup" \
  alpine tar -czf "/backup/redis-$(date +%Y%m%d-%H%M%S).tar.gz" /data
```

## 8. Security Checklist

- Replace `ANALYTICS_ADMIN_TOKEN` with a strong random value.
- Keep `.env` private and never commit it.
- Expose only the frontend port publicly.
- Put HTTPS in front before sharing the site.
- Make sure reverse proxies pass `X-Forwarded-For` or `CF-Connecting-IP` so IP tracking is accurate.
