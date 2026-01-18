# Kiteapp Deployment Guide - Ubuntu + Nginx

Comprehensive guide for deploying Kiteapp on an Ubuntu server with nginx (no containerization).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Setup](#system-setup)
3. [Application Deployment](#application-deployment)
4. [Nginx Configuration](#nginx-configuration)
5. [Systemd Service Setup](#systemd-service-setup)
6. [SSL/TLS Configuration](#ssltls-configuration)
7. [Data Pipeline Setup](#data-pipeline-setup)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance](#maintenance)

---

## Prerequisites

### Server Requirements

- Ubuntu 20.04 LTS or newer
- Minimum 2GB RAM (4GB+ recommended for data processing)
- 10GB+ free disk space (more if running data pipeline)
- Sudo access
- Domain name pointing to server IP (for production deployment)

### Pre-deployment Checklist

- [ ] Server SSH access configured
- [ ] Domain DNS records configured
- [ ] Firewall rules planned
- [ ] SSL certificate strategy decided

---

## System Setup

### 1. Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install System Dependencies

```bash
# Core dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git

# Required for data processing libraries
sudo apt install -y build-essential libhdf5-dev libnetcdf-dev

# Node.js (for frontend build)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installations
python3.11 --version
node --version
npm --version
nginx -v
```

### 3. Create Application User

```bash
# Create dedicated user for running the application
sudo useradd -m -s /bin/bash kiteapp
sudo usermod -aG sudo kiteapp  # Optional: if user needs sudo access
```

### 4. Setup Application Directory

```bash
# Switch to application user
sudo su - kiteapp

# Create application directory
sudo mkdir -p /var/www/kiteapp
sudo chown kiteapp:kiteapp /var/www/kiteapp
cd /var/www/kiteapp
```

---

## Application Deployment

### 1. Clone Repository

```bash
# As kiteapp user in /var/www/kiteapp
git clone https://github.com/yourusername/kiteapp.git .

# Or upload via SCP/SFTP if using private repository
```

### 2. Backend Setup

```bash
# Create Python virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Install production server
pip install gunicorn

# Test backend
python -m backend.main  # Should start on port 8000
# Press Ctrl+C to stop
```

### 3. Configure Backend Environment

```bash
# Create environment file
nano /var/www/kiteapp/.env
```

Add configuration (adjust as needed):

```bash
# .env file
KITEAPP_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
KITEAPP_API_TITLE=Kiteapp API
KITEAPP_API_VERSION=1.0.0
```

**Note:** Update `backend/config.py` to load CORS origins from environment:

```python
cors_origins: list = ["https://yourdomain.com"]  # Update this line
```

### 4. Frontend Build

```bash
# Navigate to frontend directory
cd /var/www/kiteapp/frontend

# Install dependencies
npm install

# Build production bundle
npm run build

# This creates frontend/dist/ directory with static files
```

### 5. Data Files Deployment

Ensure processed data files are present:

```bash
# Verify data directory structure
ls -la /var/www/kiteapp/data/processed/

# Expected files:
# - spots.pkl
# - histograms_1d.pkl
# - histograms_2d/ (directory)
```

If data files are missing, either:
- Copy from development environment
- Run data pipeline (see [Data Pipeline Setup](#data-pipeline-setup))

---

## Nginx Configuration

### 1. Understanding Multi-App Setup

Since another app is already running on the server, we'll configure nginx to:
- Serve both applications on the same server
- Use different subdomains or paths
- Proxy API requests to the backend
- Serve static frontend files

### 2. Create Nginx Configuration

```bash
# Create configuration file
sudo nano /etc/nginx/sites-available/kiteapp
```

**Option A: Subdomain Setup** (Recommended)

```nginx
# /etc/nginx/sites-available/kiteapp

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name kiteapp.yourdomain.com;

    # Let's Encrypt challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server Block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name kiteapp.yourdomain.com;

    # SSL Configuration (update paths after obtaining certificates)
    ssl_certificate /etc/letsencrypt/live/kiteapp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kiteapp.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Root directory for static files
    root /var/www/kiteapp/frontend/dist;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/javascript application/xml+rss application/json;

    # API proxy to FastAPI backend
    location /api/ {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;

        # CORS headers (if needed beyond backend)
        add_header Access-Control-Allow-Origin "https://kiteapp.yourdomain.com" always;
    }

    # Static files with caching
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Frontend SPA routing - all routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Additional security - deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

**Option B: Path-Based Setup**

If you prefer serving from a path (e.g., yourdomain.com/kiteapp):

```nginx
# Add to existing server block in /etc/nginx/sites-available/yourdomain

# API proxy
location /kiteapp/api/ {
    rewrite ^/kiteapp/api/(.*) /$1 break;
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Frontend static files
location /kiteapp/ {
    alias /var/www/kiteapp/frontend/dist/;
    try_files $uri $uri/ /kiteapp/index.html;
    index index.html;
}
```

**Important:** For path-based routing, you'll need to:
1. Update Vite config to set `base: '/kiteapp/'`
2. Update frontend API calls to use `/kiteapp/api/`
3. Rebuild frontend

### 3. Enable Site Configuration

```bash
# Create symbolic link to enable site
sudo ln -s /etc/nginx/sites-available/kiteapp /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx
```

### 4. Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'

# Or specific ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

---

## Systemd Service Setup

Create a systemd service to manage the FastAPI backend.

### 1. Create Service File

```bash
sudo nano /etc/systemd/system/kiteapp.service
```

### 2. Service Configuration

```ini
[Unit]
Description=Kiteapp FastAPI Backend
After=network.target

[Service]
Type=notify
User=kiteapp
Group=kiteapp
WorkingDirectory=/var/www/kiteapp
Environment="PATH=/var/www/kiteapp/venv/bin"
EnvironmentFile=/var/www/kiteapp/.env

# Using Gunicorn with Uvicorn workers (production-ready)
ExecStart=/var/www/kiteapp/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --access-logfile /var/log/kiteapp/access.log \
    --error-logfile /var/log/kiteapp/error.log \
    --log-level info \
    backend.main:app

# Restart policy
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 3. Create Log Directory

```bash
sudo mkdir -p /var/log/kiteapp
sudo chown kiteapp:kiteapp /var/log/kiteapp
```

### 4. Enable and Start Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable kiteapp

# Start the service
sudo systemctl start kiteapp

# Check status
sudo systemctl status kiteapp

# View logs
sudo journalctl -u kiteapp -f
```

### 5. Service Management Commands

```bash
# Start
sudo systemctl start kiteapp

# Stop
sudo systemctl stop kiteapp

# Restart
sudo systemctl restart kiteapp

# Reload (graceful restart)
sudo systemctl reload kiteapp

# View status
sudo systemctl status kiteapp

# View logs
sudo journalctl -u kiteapp -n 100 --no-pager
sudo tail -f /var/log/kiteapp/error.log
```

---

## SSL/TLS Configuration

### Option 1: Let's Encrypt (Free, Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate (nginx plugin)
sudo certbot --nginx -d kiteapp.yourdomain.com

# Or manual mode
sudo certbot certonly --webroot -w /var/www/certbot -d kiteapp.yourdomain.com

# Certbot auto-renew (verify it's enabled)
sudo systemctl status certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

### Option 2: Manual SSL Certificate

If using a purchased or manually obtained certificate:

```bash
# Copy certificate files to server
sudo mkdir -p /etc/ssl/certs/kiteapp
sudo cp fullchain.pem /etc/ssl/certs/kiteapp/
sudo cp privkey.pem /etc/ssl/private/kiteapp/

# Set permissions
sudo chmod 644 /etc/ssl/certs/kiteapp/fullchain.pem
sudo chmod 600 /etc/ssl/private/kiteapp/privkey.pem

# Update nginx configuration with correct paths
# Then reload nginx
sudo systemctl reload nginx
```

---

## Data Pipeline Setup

If you need to run the data pipeline on the production server:

### 1. CDS API Configuration

```bash
# As kiteapp user
nano ~/.cdsapirc
```

Add credentials:

```yaml
url: https://cds.climate.copernicus.eu/api
key: YOUR_UID:YOUR_API_KEY
```

Set permissions:

```bash
chmod 600 ~/.cdsapirc
```

### 2. Run Data Pipeline

```bash
# Activate virtual environment
cd /var/www/kiteapp
source venv/bin/activate

# Test with one cell
python -m data_pipelines.main --max-cells 1

# Full run with cleanup
python -m data_pipelines.main --cleanup
```

### 3. Schedule Regular Updates (Optional)

```bash
# Create cron job for monthly updates
crontab -e
```

Add line (runs first of each month at 2 AM):

```cron
0 2 1 * * cd /var/www/kiteapp && /var/www/kiteapp/venv/bin/python -m data_pipelines.main --cleanup >> /var/log/kiteapp/pipeline.log 2>&1
```

---

## Troubleshooting

### Backend Issues

**Service won't start:**

```bash
# Check service status
sudo systemctl status kiteapp

# Check logs
sudo journalctl -u kiteapp -n 50 --no-pager
sudo tail -f /var/log/kiteapp/error.log

# Common issues:
# - Port 8000 already in use: sudo lsof -i :8000
# - Missing data files: ls -la /var/www/kiteapp/data/processed/
# - Python environment: /var/www/kiteapp/venv/bin/python --version
```

**502 Bad Gateway:**

```bash
# Backend not running
sudo systemctl status kiteapp

# Port mismatch - verify nginx proxy_pass matches backend port
sudo nginx -t
grep -r "proxy_pass" /etc/nginx/sites-enabled/

# SELinux blocking (if enabled)
sudo setsebool -P httpd_can_network_connect 1
```

### Frontend Issues

**Blank page or 404 errors:**

```bash
# Verify build files exist
ls -la /var/www/kiteapp/frontend/dist/

# Check nginx root path
sudo nginx -T | grep "root"

# Rebuild frontend
cd /var/www/kiteapp/frontend
npm run build

# Check browser console for errors
```

**API calls failing:**

```bash
# Check CORS configuration in backend/config.py
# Verify nginx proxy configuration
# Check browser network tab for blocked requests
```

### Nginx Issues

**Configuration test fails:**

```bash
sudo nginx -t
# Read error message carefully - usually syntax error or missing file
```

**Port already in use:**

```bash
# Check what's using port 80/443
sudo lsof -i :80
sudo lsof -i :443

# Check if another nginx instance is running
ps aux | grep nginx
```

### SSL Certificate Issues

```bash
# Verify certificate files exist
sudo ls -la /etc/letsencrypt/live/kiteapp.yourdomain.com/

# Check certificate expiry
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R kiteapp:kiteapp /var/www/kiteapp

# Fix permissions
sudo chmod -R 755 /var/www/kiteapp
sudo chmod -R 644 /var/www/kiteapp/data/processed/*.pkl

# Service file permissions
sudo chmod 644 /etc/systemd/system/kiteapp.service
```

### Performance Issues

**High memory usage:**

```bash
# Check process memory
top -u kiteapp
htop -u kiteapp

# Reduce Gunicorn workers in systemd service
# Edit /etc/systemd/system/kiteapp.service
# Change --workers 4 to --workers 2
sudo systemctl daemon-reload
sudo systemctl restart kiteapp
```

**Slow API responses:**

```bash
# Check backend logs for slow queries
sudo tail -f /var/log/kiteapp/access.log

# Monitor nginx
sudo tail -f /var/log/nginx/access.log

# Check disk I/O
iostat -x 1

# Verify data files are not corrupted
cd /var/www/kiteapp
source venv/bin/activate
python -c "import pickle; pickle.load(open('data/processed/spots.pkl', 'rb'))"
```

---

## Maintenance

### Regular Updates

```bash
# Pull latest code
cd /var/www/kiteapp
git pull origin main

# Update backend dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Rebuild frontend
cd frontend
npm install
npm run build

# Restart backend service
sudo systemctl restart kiteapp

# Reload nginx (if config changed)
sudo systemctl reload nginx
```

### Backup Strategy

```bash
# Create backup script
sudo nano /usr/local/bin/kiteapp-backup.sh
```

```bash
#!/bin/bash
# Kiteapp backup script

BACKUP_DIR="/backups/kiteapp"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="/var/www/kiteapp"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup data files
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" "$APP_DIR/data"

# Backup configuration
cp "$APP_DIR/.env" "$BACKUP_DIR/env_$DATE"
cp /etc/nginx/sites-available/kiteapp "$BACKUP_DIR/nginx_$DATE"
cp /etc/systemd/system/kiteapp.service "$BACKUP_DIR/service_$DATE"

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Make executable and schedule:

```bash
sudo chmod +x /usr/local/bin/kiteapp-backup.sh

# Add to crontab (daily at 3 AM)
sudo crontab -e
# Add: 0 3 * * * /usr/local/bin/kiteapp-backup.sh >> /var/log/kiteapp/backup.log 2>&1
```

### Log Rotation

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/kiteapp
```

```
/var/log/kiteapp/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 kiteapp kiteapp
    sharedscripts
    postrotate
        systemctl reload kiteapp > /dev/null 2>&1 || true
    endscript
}
```

### Monitoring

**Basic health check script:**

```bash
# Create monitoring script
nano /usr/local/bin/kiteapp-healthcheck.sh
```

```bash
#!/bin/bash
# Basic health check for Kiteapp

# Check if backend is responding
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)

if [ "$HEALTH" != "200" ]; then
    echo "Backend health check failed: $HEALTH"
    # Restart service
    systemctl restart kiteapp
    # Send notification (configure email/slack as needed)
fi

# Check nginx
if ! systemctl is-active --quiet nginx; then
    echo "Nginx is not running"
    systemctl restart nginx
fi
```

### Security Updates

```bash
# Regular system updates
sudo apt update
sudo apt upgrade -y

# Update Python packages
cd /var/www/kiteapp
source venv/bin/activate
pip list --outdated
pip install -r requirements.txt --upgrade

# Update Node packages
cd frontend
npm audit
npm audit fix
npm update
```

---

## Quick Reference

### Important Paths

| Path | Description |
|------|-------------|
| `/var/www/kiteapp` | Application root |
| `/var/www/kiteapp/venv` | Python virtual environment |
| `/var/www/kiteapp/frontend/dist` | Built frontend files |
| `/var/www/kiteapp/data/processed` | Data files |
| `/etc/nginx/sites-available/kiteapp` | Nginx configuration |
| `/etc/systemd/system/kiteapp.service` | Systemd service file |
| `/var/log/kiteapp/` | Application logs |
| `/var/log/nginx/` | Nginx logs |

### Important Commands

```bash
# Backend service
sudo systemctl [start|stop|restart|status] kiteapp

# Nginx
sudo systemctl [start|stop|restart|reload|status] nginx
sudo nginx -t  # Test configuration

# View logs
sudo journalctl -u kiteapp -f
sudo tail -f /var/log/kiteapp/error.log
sudo tail -f /var/log/nginx/error.log

# Rebuild frontend
cd /var/www/kiteapp/frontend && npm run build

# Activate Python environment
cd /var/www/kiteapp && source venv/bin/activate
```

### Verification Checklist

After deployment, verify:

- [ ] Backend service is running: `sudo systemctl status kiteapp`
- [ ] Backend responds to health check: `curl http://127.0.0.1:8000/health`
- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] Nginx configuration is valid: `sudo nginx -t`
- [ ] Frontend loads in browser
- [ ] API calls work from frontend
- [ ] SSL certificate is valid (if configured)
- [ ] Firewall allows HTTP/HTTPS
- [ ] Logs are being written: `ls -la /var/log/kiteapp/`
- [ ] Data files are accessible: `ls -la /var/www/kiteapp/data/processed/`

---

## Production Deployment Checklist

Before going live:

- [ ] Update CORS origins in `backend/config.py` or `.env`
- [ ] Configure proper domain name
- [ ] Obtain and configure SSL certificate
- [ ] Set up log rotation
- [ ] Configure backups
- [ ] Set up monitoring/alerting
- [ ] Document any server-specific configurations
- [ ] Test all API endpoints
- [ ] Test frontend functionality
- [ ] Load test backend (optional but recommended)
- [ ] Set up firewall rules
- [ ] Disable debug mode in all components
- [ ] Review security headers in nginx
- [ ] Document emergency procedures

---

## Support

For issues specific to this deployment guide, check:
- Application logs: `/var/log/kiteapp/`
- System logs: `sudo journalctl -u kiteapp`
- Nginx logs: `/var/log/nginx/`

For application issues, refer to:
- `README.md` - Project overview
- `CLAUDE.md` - Development guide
- `TESTING_PLAN.md` - Testing procedures
