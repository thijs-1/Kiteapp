# Kiteapp Deployment Guide - Ubuntu + Nginx

Step-by-step guide for deploying Kiteapp on an Ubuntu server with nginx (no containerization).

**Note:** This guide is optimized for homelab/personal server deployments.

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
- Domain name pointing to server IP

### Pre-deployment Checklist

- [ ] Server SSH access configured
- [ ] Domain DNS records configured (A record pointing to server IP)
- [ ] Firewall allows HTTP/HTTPS traffic

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
```

### 4. Setup Application Directory

```bash
# Switch to application user
sudo su - kiteapp

# Create application directory in home
mkdir -p ~/kiteapp
cd ~/kiteapp
```

---

## Application Deployment

### 1. Clone Repository

```bash
# As kiteapp user in ~/kiteapp
git clone https://github.com/thijs-1/kiteapp.git .

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

# Test backend (optional)
python -m backend.main  # Should start on port 8000
# Press Ctrl+C to stop
```

### 3. Configure Backend Environment

Create environment file:

```bash
nano ~/.env
```

Add configuration (adjust domain as needed):

```bash
# .env file
KITEAPP_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
KITEAPP_API_TITLE=Kiteapp API
KITEAPP_API_VERSION=1.0.0
```

Update `backend/config.py` to load CORS origins from environment or update the hardcoded value:

```python
cors_origins: list = ["https://yourdomain.com"]  # Update this
```

### 4. Frontend Build

```bash
# Navigate to frontend directory
cd ~/kiteapp/frontend

# Install dependencies
npm install

# Build production bundle
npm run build

# This creates frontend/dist/ directory with static files
```

### 5. Verify Data Files

Ensure processed data files are present:

```bash
# Verify data directory structure
ls -la ~/kiteapp/data/processed/

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

### 1. Create Nginx Configuration File

```bash
sudo nano /etc/nginx/sites-available/kiteapp
```

### 2. Basic Configuration

```nginx
# /etc/nginx/sites-available/kiteapp

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

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
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration (update paths after obtaining certificates)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Root directory for static files
    root /home/kiteapp/kiteapp/frontend/dist;
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

**Important:** Replace `yourdomain.com` with your actual domain name throughout the configuration.

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
Type=simple
User=kiteapp
Group=kiteapp
WorkingDirectory=/home/kiteapp/kiteapp
Environment="PATH=/home/kiteapp/kiteapp/venv/bin"

# Using Uvicorn (simple and efficient for homelab)
ExecStart=/home/kiteapp/kiteapp/venv/bin/uvicorn \
    backend.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --log-level info

# Restart policy
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Note:** For a homelab setup, Uvicorn alone is sufficient. If you later need higher performance with multiple workers, you can switch to Gunicorn + Uvicorn workers.

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

# View status
sudo systemctl status kiteapp

# View logs (live)
sudo journalctl -u kiteapp -f

# View recent logs
sudo journalctl -u kiteapp -n 100 --no-pager
sudo tail -f /var/log/kiteapp/error.log
```

---

## SSL/TLS Configuration

### Using Let's Encrypt (Free, Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate (nginx plugin - easiest method)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Certbot will automatically:
# - Obtain the certificate
# - Update nginx configuration
# - Set up auto-renewal

# Verify auto-renewal is enabled
sudo systemctl status certbot.timer

# Test renewal process
sudo certbot renew --dry-run
```

**Alternative: Manual certificate with webroot**

```bash
# Create webroot directory
sudo mkdir -p /var/www/certbot

# Obtain certificate
sudo certbot certonly --webroot -w /var/www/certbot \
    -d yourdomain.com -d www.yourdomain.com

# Certificates will be placed in:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Reload nginx after certificate is obtained
sudo systemctl reload nginx
```

---

## Data Pipeline Setup

If you need to run the data pipeline on the production server to generate or update data:

### 1. CDS API Configuration

```bash
# As kiteapp user
nano ~/.cdsapirc
```

Add your Copernicus CDS API credentials:

```yaml
url: https://cds.climate.copernicus.eu/api
key: YOUR_UID:YOUR_API_KEY
```

Set proper permissions:

```bash
chmod 600 ~/.cdsapirc
```

### 2. Run Data Pipeline

```bash
# Activate virtual environment
cd ~/kiteapp
source venv/bin/activate

# Test with one grid cell first
python -m data_pipelines.main --max-cells 1

# Full pipeline run with cleanup
python -m data_pipelines.main --cleanup
```

**Note:** The full pipeline takes significant time and bandwidth. Consider running data pipeline locally and uploading processed files instead.

### 3. Schedule Regular Updates (Optional)

If you want annual data updates:

```bash
# Edit crontab as kiteapp user
crontab -e
```

Add this line (runs January 1st at 2 AM each year):

```cron
0 2 1 1 * cd ~/kiteapp && ~/kiteapp/venv/bin/python -m data_pipelines.main --cleanup >> ~/kiteapp/logs/pipeline.log 2>&1
```

**Note:** ERA5 historical data changes infrequently. You may prefer to run the pipeline manually when needed rather than scheduling it.

---

## Troubleshooting

### Backend Issues

**Service won't start:**

```bash
# Check service status
sudo systemctl status kiteapp

# Check logs for errors
sudo journalctl -u kiteapp -n 50 --no-pager
sudo tail -f /var/log/kiteapp/error.log

# Common issues:
# - Port 8000 already in use: sudo lsof -i :8000
# - Missing data files: ls -la ~/kiteapp/data/processed/
# - Wrong Python version: ~/kiteapp/venv/bin/python --version
# - Missing dependencies: cd ~/kiteapp && source venv/bin/activate && pip install -r requirements.txt
```

**502 Bad Gateway:**

```bash
# Check if backend is running
sudo systemctl status kiteapp

# Verify port configuration matches
# Backend should be on 127.0.0.1:8000
# Nginx should proxy to http://127.0.0.1:8000

# Check nginx config
sudo nginx -t
grep -r "proxy_pass" /etc/nginx/sites-enabled/kiteapp
```

### Frontend Issues

**Blank page or 404 errors:**

```bash
# Verify build files exist
ls -la ~/kiteapp/frontend/dist/
ls -la ~/kiteapp/frontend/dist/index.html

# Check nginx root path is correct
sudo nginx -T | grep -A 5 "server_name yourdomain.com"

# Rebuild frontend if needed
cd ~/kiteapp/frontend
npm run build

# Check browser console (F12) for JavaScript errors
```

**API calls failing (CORS errors):**

```bash
# Update CORS origins in backend/config.py
# Make sure it matches your domain exactly (including https://)

# Restart backend after config changes
sudo systemctl restart kiteapp

# Check browser network tab for:
# - Failed requests
# - CORS error messages
# - Blocked requests
```

### Nginx Issues

**Configuration test fails:**

```bash
sudo nginx -t
# Read the error message carefully - usually indicates:
# - Syntax error in config file
# - Missing semicolon
# - Invalid directive
# - File path doesn't exist
```

**Port already in use:**

```bash
# Check what's using port 80/443
sudo lsof -i :80
sudo lsof -i :443

# If another nginx process
ps aux | grep nginx
sudo systemctl status nginx
```

### SSL Certificate Issues

```bash
# Check certificate files exist
sudo ls -la /etc/letsencrypt/live/yourdomain.com/

# View certificate details
sudo certbot certificates

# Check certificate expiry
echo | openssl s_client -servername yourdomain.com -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates

# Manually renew if needed
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

### Permission Issues

```bash
# Fix application directory ownership (should already be correct)
sudo chown -R kiteapp:kiteapp /home/kiteapp/kiteapp

# Fix permissions if needed
chmod -R 755 ~/kiteapp
chmod 644 ~/kiteapp/data/processed/*.pkl

# Fix service file permissions
sudo chmod 644 /etc/systemd/system/kiteapp.service
sudo systemctl daemon-reload
```

### Performance Issues

**High memory usage:**

```bash
# Check process memory
top -u kiteapp
# or
htop -u kiteapp

# Check what's consuming memory
ps aux | grep kiteapp
```

**Slow API responses:**

```bash
# Check backend logs for slow requests
sudo tail -f /var/log/kiteapp/access.log

# Check nginx logs
sudo tail -f /var/log/nginx/access.log

# Verify data files are accessible and not corrupted
cd ~/kiteapp
source venv/bin/activate
python -c "import pickle; data = pickle.load(open('data/processed/spots.pkl', 'rb')); print(f'Loaded {len(data)} spots')"
```

---

## Maintenance

### Updating the Application

```bash
# As kiteapp user
cd ~/kiteapp
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

# Reload nginx if configuration changed
sudo systemctl reload nginx
```

### Log Rotation

Configure automatic log rotation to prevent disk space issues:

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

### System Updates

```bash
# Regular system updates
sudo apt update
sudo apt upgrade -y

# Update Python packages
cd ~/kiteapp
source venv/bin/activate
pip list --outdated
pip install -r requirements.txt --upgrade

# Update Node packages (check for breaking changes first)
cd frontend
npm audit
npm update
```

---

## Quick Reference

### Important Paths

| Path | Description |
|------|-------------|
| `/home/kiteapp/kiteapp` | Application root |
| `/home/kiteapp/kiteapp/venv` | Python virtual environment |
| `/home/kiteapp/kiteapp/frontend/dist` | Built frontend files |
| `/home/kiteapp/kiteapp/data/processed` | Data files |
| `/home/kiteapp/.env` | Environment configuration |
| `/etc/nginx/sites-available/kiteapp` | Nginx configuration |
| `/etc/systemd/system/kiteapp.service` | Systemd service file |
| `/var/log/kiteapp/` | Application logs |
| `/var/log/nginx/` | Nginx logs |

### Essential Commands

```bash
# Backend service
sudo systemctl [start|stop|restart|status] kiteapp
sudo journalctl -u kiteapp -f

# Nginx
sudo systemctl [start|stop|restart|reload|status] nginx
sudo nginx -t  # Test configuration

# View logs
sudo tail -f /var/log/kiteapp/error.log
sudo tail -f /var/log/nginx/error.log

# Rebuild frontend
cd ~/kiteapp/frontend && npm run build

# Activate Python environment
cd ~/kiteapp && source venv/bin/activate
```

### Post-Deployment Verification

After deployment, verify everything works:

- [ ] Backend service is running: `sudo systemctl status kiteapp`
- [ ] Backend responds: `curl http://127.0.0.1:8000/docs` (should show FastAPI docs)
- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] Nginx configuration is valid: `sudo nginx -t`
- [ ] Domain resolves to server: `ping yourdomain.com`
- [ ] Frontend loads in browser: `https://yourdomain.com`
- [ ] API calls work from frontend (check browser console)
- [ ] SSL certificate is valid (green padlock in browser)
- [ ] Data files exist: `ls -la ~/kiteapp/data/processed/`

---

## Production Checklist

Before going live:

- [ ] Update domain name in all configuration files
- [ ] Update CORS origins in `backend/config.py` or `.env`
- [ ] Obtain and configure SSL certificate
- [ ] Test all functionality (map, filters, spot details)
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Document any server-specific configurations
- [ ] Test from different devices/browsers
- [ ] Verify data files are complete and up-to-date
