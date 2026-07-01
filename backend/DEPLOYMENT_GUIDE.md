# 🚀 Deployment Guide — IoT Smart Home System

**Version**: 1.0  
**Last Updated**: April 19, 2026  
**Status**: Production-Ready

---

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Configuration](#environment-configuration)
3. [Database Setup](#database-setup)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Mobile Deployment](#mobile-deployment)
7. [IoT Device Provisioning](#iot-device-provisioning)
8. [Monitoring & Alerts](#monitoring--alerts)
9. [Rollback Procedures](#rollback-procedures)

---

## Pre-Deployment Checklist

### Security Verification ✅
- [ ] All secrets in `.env` (not in version control)
- [ ] Database credentials rotated
- [ ] MQTT broker credentials updated
- [ ] SSL/TLS certificates valid (not self-signed in prod)
- [ ] API rate limiting configured
- [ ] JWT refresh token TTL set (15 min access, 7 day refresh)
- [ ] CORS whitelist configured for frontend domain
- [ ] Database backups configured

### Functionality Tests ✅
- [ ] Backend health check passes: `GET /api/health` → 200
- [ ] Frontend loads without errors
- [ ] Mobile app connects to backend
- [ ] Device control works end-to-end
- [ ] Medicine reminders trigger on schedule
- [ ] Email alerts send correctly
- [ ] MQTT listener receives device updates

### Performance ✅
- [ ] Database indexes created
- [ ] API response time < 200ms (p95)
- [ ] WebSocket connections < 5s handshake
- [ ] Mobile app startup < 3s

---

## Environment Configuration

### 1. Backend (Python/Flask)

**File**: `.env`
```env
# Flask Configuration
FLASK_ENV=production
FLASK_APP=run.py
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')

# Database (MySQL)
DB_HOST=your-mysql-host.com
DB_PORT=3306
DB_USER=iot_prod_user
DB_PASS=$(python -c 'import secrets; print(secrets.token_urlsafe(24))')
DB_NAME=batman_os_prod
USE_SQLITE_DEV=false

# MQTT Broker
MQTT_BROKER_URL=your-mqtt-host.com
MQTT_BROKER_PORT=8883
MQTT_USERNAME=mqtt_prod_user
MQTT_PASSWORD=$(python -c 'import secrets; print(secrets.token_urlsafe(24))')
MQTT_USE_TLS=true
MQTT_ALLOW_INSECURE_TLS=false

# AI Services
GEMINI_API_KEY=sk-xxx...
OLLAMA_BASE_URL=http://ollama-server:11434
OLLAMA_MODEL=qwen2.5:3b

# Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@eldercare.local
SMTP_PASSWORD=$(python -c 'import secrets; print(secrets.token_urlsafe(24))')
SMTP_FROM_EMAIL=alerts@eldercare.local
SMTP_FROM_NAME=Smart Home Alerts

# Alert Recipients
ALERT_RECIPIENTS=admin@eldercare.local;caregiver@eldercare.local

# Redis (for rate limiting & caching)
REDIS_URL=redis://redis-server:6379/0

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 2. Frontend (Vite + Vue)

**File**: `.env.production`
```
VITE_API_URL=https://api.eldercare.local
VITE_SOCKET_URL=https://api.eldercare.local
VITE_SOCKET_PATH=/socket.io
VITE_ENABLE_DEBUG=false
VITE_SESSION_TIMEOUT_MINUTES=30
```

### 3. Mobile (Flutter)

**File**: `pubspec.yaml` (build configuration)
```yaml
flutter:
  uses-material-design: true

# Add to android/app/build.gradle.kts
defaultConfig {
    applicationId "com.smarthomelderlycare.prod"
    minSdkVersion 24
    targetSdkVersion 35
}

# Add to ios/Podfile
post_install do |installer|
  installer.pods_project.targets.each do |target|
    flutter_additional_ios_build_settings(target)
  end
end
```

---

## Database Setup

### 1. Create Production Database

```bash
# Connect to MySQL
mysql -h your-mysql-host -u root -p

# Create user and database
CREATE DATABASE batman_os_prod;
CREATE USER 'iot_prod_user'@'%' IDENTIFIED BY 'secure-password';
GRANT ALL PRIVILEGES ON batman_os_prod.* TO 'iot_prod_user'@'%';
FLUSH PRIVILEGES;
```

### 2. Initialize Schema

```bash
cd backend

# Apply migrations
python -m flask db upgrade

# Verify schema
python -c "from app import create_app; app = create_app(); print('Database initialized')"
```

### 3. Backup Strategy

```bash
# Daily backup (add to crontab)
0 2 * * * mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASS batman_os_prod | gzip > /backups/batman_os_$(date +%Y%m%d).sql.gz

# Keep 30-day backup retention
find /backups -name "batman_os_*.sql.gz" -mtime +30 -delete
```

---

## Backend Deployment

### Option 1: Docker (Recommended)

```bash
# Build image
docker build -t batman-os-backend:1.0 -f backend/Dockerfile .

# Run container
docker run -d \
  --name batman-backend \
  --env-file .env \
  --publish 5000:5000 \
  --network smart-home-net \
  batman-os-backend:1.0
```

### Option 2: System Service (Gunicorn + Nginx)

```bash
# Install gunicorn
pip install gunicorn==21.2.0

# Create systemd service
cat > /etc/systemd/system/batman-backend.service << EOF
[Unit]
Description=Batman OS Backend
After=network.target mysql.service

[Service]
Type=notify
User=batman
WorkingDirectory=/opt/batman-os/backend
Environment="PATH=/opt/batman-os/.venv/bin"
ExecStart=/opt/batman-os/.venv/bin/gunicorn --workers 4 --worker-class eventlet --bind 0.0.0.0:5000 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable batman-backend
systemctl start batman-backend
```

### Option 3: Cloud Platform (Heroku, Railway)

```bash
# Deploy to Heroku
heroku login
heroku create batman-os-backend
heroku config:set --from-file .env
git push heroku main

# View logs
heroku logs --tail
```

---

## Frontend Deployment

### Build for Production

```bash
cd frontend

# Install dependencies
npm ci

# Build optimized bundle
npm run build

# Output in dist/ directory
```

### Deploy to CDN

```bash
# Option 1: AWS S3 + CloudFront
aws s3 sync dist/ s3://batman-os-frontend/ --delete
aws cloudfront create-invalidation --distribution-id E123ABC --paths "/*"

# Option 2: Netlify
netlify deploy --prod --dir=dist

# Option 3: Vercel
vercel --prod
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name eldercare.local;

    ssl_certificate /etc/ssl/certs/eldercare.crt;
    ssl_certificate_key /etc/ssl/private/eldercare.key;

    # Frontend assets
    location / {
        root /var/www/batman-os-frontend;
        try_files $uri $uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public, max-age=3600";
    }

    # API proxy
    location /api {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /socket.io {
        proxy_pass http://localhost:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

---

## Mobile Deployment

### Android (Google Play Store)

```bash
cd MOBILE

# Build release APK
flutter build apk --split-per-abi --release

# Build App Bundle (recommended for Play Store)
flutter build appbundle --release

# Output: build/app/outputs/bundle/release/app-release.aab
```

### iOS (App Store)

```bash
# Build iOS release
flutter build ios --release

# Upload via Xcode or Transporter
open build/ios/ipa/smart_home_mobile.ipa
```

### Configuration per Environment

```dart
// lib/config/environment.dart
enum Environment { dev, staging, production }

class AppConfig {
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'https://api.staging.eldercare.local',
  );
  
  static const String socketUrl = String.fromEnvironment(
    'SOCKET_URL',
    defaultValue: 'https://api.staging.eldercare.local',
  );
}

// Run with:
// flutter run --dart-define=API_URL=https://api.eldercare.local
```

---

## IoT Device Provisioning

### ESP32 Configuration

```cpp
// Arduino/ESP32/esp32_secrets.h
#define WIFI_SSID "YourNetworkName"
#define WIFI_PASSWORD "YourSecurePassword"
#define MQTT_BROKER "your-mqtt-host.com"
#define MQTT_PORT 8883
#define MQTT_USERNAME "esp32_prod_user"
#define MQTT_PASSWORD "secure-password"
#define MQTT_USE_TLS 1
#define MQTT_ALLOW_INSECURE_TLS 0
```

### Flash Firmware

```bash
# Using PlatformIO
pio run -e esp32-prod --target upload

# Using Arduino CLI
arduino-cli compile -b esp32:esp32:esp32 Arduino/ESP32/
arduino-cli upload -b esp32:esp32:esp32 -p /dev/ttyUSB0
```

---

## Monitoring & Alerts

### Health Checks

```bash
# Backend health
curl https://api.eldercare.local/api/health

# Expected response:
{
  "status": "ok",
  "service": "Batman OS",
  "database": "ok",
  "mqtt": "connected"
}
```

### Logging & Analytics

```bash
# View backend logs
docker logs -f batman-backend

# Centralize with ELK Stack
# - Elasticsearch: logs storage
# - Logstash: log processing
# - Kibana: visualization
```

### Uptime Monitoring

```bash
# Uptime Robot
- Monitor: https://api.eldercare.local/api/health
- Check interval: 5 minutes
- Alert threshold: 2 failures
```

---

## Rollback Procedures

### Quick Rollback

```bash
# Stop current version
docker stop batman-backend

# Restart previous version
docker run -d \
  --name batman-backend \
  --env-file .env \
  batman-os-backend:0.9
```

### Database Rollback

```bash
# List backups
ls -lah /backups/

# Restore from backup
mysql batman_os_prod < /backups/batman_os_20260418.sql
```

---

## Checklist for Go-Live

- [ ] All environment variables configured
- [ ] SSL certificates installed and valid
- [ ] Database backups tested
- [ ] Monitoring alerts configured
- [ ] Support team trained
- [ ] Runbook prepared
- [ ] Incident response plan documented
- [ ] 24/7 on-call rotation assigned

**Go-Live Date**: ______  
**Deployed By**: ______  
**Approved By**: ______
