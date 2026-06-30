# DEPLOY.md — Deployment Guide

> Deploy stack `coba-4` (AI DevSecOps Security Assistant) ke **VPS Atlantic** dengan domain **`iqbalhidayatrasyad.blog`**.

---

## Arsitektur

```
                        ┌─────────────────────────────────────────┐
                        │  Domain: iqbalhidayatrasyad.blog        │
                        │  (Hostinger DNS)                        │
                        └──────────┬──────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
   CNAME: @                 A: app              A: api (opsional)
   └→ Vercel CDN            └→ Cloudflare        └→ VPS Atlantic
      (blog/portofolio)        proxy=OFF            (app backend)
                               │
                               ▼
                  ┌────────────────────────────┐
                  │  VPS Atlantic              │
                  │  IP: <VPS_IP>              │
                  │                            │
                  │  Nginx (container)         │
                  │  ├─ TLS (Let's Encrypt)    │
                  │  └─ Reverse proxy          │
                  │                            │
                  │  ┌────────┬────────┬─────┐  │
                  │  │backend │ai-svc  │front│  │
                  │  │(Go)    │(Py)    │(ngx)│  │
                  │  └───┬────┴───┬────┴─────┘  │
                  │      │        │             │
                  │   postgres   redis         │
                  └────────────────────────────┘
```

**Penjelasan domain**:

| Subdomain | Tujuan | Hosting | Catatan |
|---|---|---|---|
| `iqbalhidayatrasyad.blog` | Blog/portofolio (static + ISR) | **Vercel** | CNAME root → `cname.vercel-dns.com` |
| `app.iqbalhidayatrasyad.blog` | Aplikasi AI DevSecOps | **VPS Atlantic** (Docker) | A record ke IP VPS, lewat Cloudflare proxy=OFF |
| `api.iqbalhidayatrasyad.blog` | (Opsional) Alias ke app | **VPS Atlantic** | CNAME ke `app.iqbalhidayatrasyad.blog` |

**Alasan pisah domain utama vs app**:
- Domain utama (`@`) di Vercel → SEO & speed untuk konten static
- App di subdomain `app` → env terisolasi, full control backend
- Cloudflare di subdomain `app` untuk DDoS protection + caching layer

---

## Daftar Isi

1. [Prasyarat](#1-prasyarat)
2. [Setup VPS Atlantic](#2-setup-vps-atlantic)
3. [Konfigurasi Domain di Hostinger](#3-konfigurasi-domain-di-hostinger)
4. [Setup Cloudflare untuk Subdomain App](#4-setup-cloudflare-untuk-subdomain-app)
5. [Setup Vercel untuk Domain Utama](#5-setup-vercel-untuk-domain-utama)
6. [Konfigurasi Environment](#6-konfigurasi-environment)
7. [Deploy Aplikasi](#7-deploy-aplikasi)
8. [Setup HTTPS / Let's Encrypt](#8-setup-https--lets-encrypt)
9. [Verifikasi & Testing](#9-verifikasi--testing)
10. [Maintenance](#10-maintenance)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prasyarat

### 1.1 Yang Anda Butuhkan

- [x] VPS Atlantic (Debian 11/12 atau Ubuntu 22.04/24.04, ≥ 4 GB RAM, ≥ 40 GB SSD)
- [x] Domain `iqbalhidayatrasyad.blog` di Hostinger
- [ ] Akun Cloudflare (gratis) — daftar di https://dash.cloudflare.com/sign-up
- [ ] Akun Vercel (gratis) — daftar di https://vercel.com/signup
- [ ] API key LLM (minimal 1: OpenAI / Anthropic / OpenRouter)
- [ ] SSH key lokal: `ssh-keygen -t ed25519 -C "atlantic-ai-devsecops"`

### 1.2 Sizing Minimum Atlantic

| Resource | Minimum | Recommended |
|---|---|---|
| vCPU | 2 | 2 |
| RAM | 2 GB | **4 GB** |
| Disk | 20 GB SSD | 40 GB SSD |
| Bandwidth | 1 TB | 2 TB |
| OS | Debian 12 / Ubuntu 22.04 | Ubuntu 22.04 LTS |

**Cek VM Anda**:
```bash
ssh root@<VPS_IP>
cat /etc/os-release
free -h
df -h
nproc
```

### 1.3 File yang Akan Dibuat

| Path | Tujuan |
|---|---|
| `docker-compose.prod.yml` | Override production untuk compose |
| `frontend/Dockerfile.prod` | Multi-stage build static frontend |
| `frontend/nginx-frontend.conf` | Nginx config di dalam container frontend |
| `nginx/prod-nginx.conf` | Nginx prod: TLS + reverse proxy |
| `.env.production.example` | Template env production |
| `.gitignore` (update) | Tambah exclude cert/secret |
| `scripts/setup-vps.sh` | Install Docker, UFW, fail2ban |
| `scripts/deploy.sh` | Git pull + build + up |
| `scripts/init-letsencrypt.sh` | Issue cert Let's Encrypt (idempotent) |
| `scripts/renew-certs.sh` | Cron-friendly cert renewal |
| `backend/internal/middleware/cors.go` (edit) | Env-driven CORS origin |
| **`DEPLOY.md`** | File ini |

---

## 2. Setup VPS Atlantic

### 2.1 Pertama Kali Login

```bash
# Dari laptop lokal
ssh root@<VPS_IP_ATLANTIC>
# (Atlantic biasanya kasih password root di email welcome)
```

### 2.2 Buat User Non-Root (Best Practice)

```bash
# Buat user 'deploy' dengan sudo
adduser deploy
usermod -aG sudo deploy

# Setup SSH key untuk user deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Test login dari laptop
ssh deploy@<VPS_IP_ATLANTIC>
```

### 2.3 Clone Repo & Install Dependencies

```bash
# Login sebagai deploy
ssh deploy@<VPS_IP_ATLANTIC>

# Clone project
sudo mkdir -p /opt/ai-devsecops
sudo chown deploy:deploy /opt/ai-devsecops
git clone <URL_REPO_GITHUB> /opt/ai-devsecops
cd /opt/ai-devsecops

# Jalankan setup otomatis
bash scripts/setup-vps.sh
```

**`scripts/setup-vps.sh`** melakukan:
1. `apt update && apt upgrade -y`
2. Install: `docker.io`, `docker-compose-plugin`, `ufw`, `fail2ban`, `unattended-upgrades`, `curl`, `git`
3. Tambah user ke group `docker` (supaya tidak perlu `sudo` untuk docker)
4. Setup **UFW**:
   - Default deny incoming
   - Allow 22/tcp (SSH)
   - Allow 80/tcp (HTTP)
   - Allow 443/tcp (HTTPS)
   - Enable UFW
5. Setup **fail2ban**: proteksi SSH (5 failed attempt = ban 1 jam)
6. Enable **unattended-upgrades** untuk security patch otomatis
7. Setup timezone ke `Asia/Jakarta`
8. Print ringkasan (IP, RAM, disk)

Verifikasi:
```bash
docker --version
docker compose version
ufw status
sudo fail2ban-client status sshd
```

### 2.4 Atlantic-Specific Notes

- **Atlantic** (juga dikenal Atlantic.Net) menggunakan KVM virtualization, full VPS — semua command Linux standar berlaku
- **IP statis**: konfirmasi di panel Atlantic bahwa VM Anda punya IPv4 statis (default sudah)
- **Firewall eksternal**: Atlantic tidak punya firewall default di luar VM (beda dengan Azure NSG), jadi **UFW di OS adalah satu-satunya firewall** — pastikan allow 22, 80, 443
- **Backup**: Atlantic biasanya punya opsi snapshot di panel — opsional tapi recommended

---

## 3. Konfigurasi Domain di Hostinger

Anda punya `iqbalhidayatrasyad.blog` di Hostinger. Ada **2 bagian** yang harus dikonfigurasi:

### 3.1 Nameserver: Tetap di Hostinger atau Pindah ke Cloudflare?

**Rekomendasi**: **Tetap pakai Hostinger nameserver** untuk domain utama (karena domain utama di Vercel, Hostinger DNS bisa langsung pointing ke Vercel). Subdomain `app` tetap di-handle Hostinger DNS zone.

**Alternatif**: Pindah NS ke Cloudflare → semua DNS record di Cloudflare. Pilih salah satu.

Saya dokumentasikan **Opsi A (Hostinger NS tetap)** karena lebih simpel untuk setup Vercel + VPS.

### 3.2 Opsi A — Hostinger Nameserver (Recommended)

#### Login Hostinger
1. Buka https://hpanel.hostinger.com
2. Pilih domain `iqbalhidayatrasyad.blog`
3. Klik **DNS Zone** (atau **DNS / Nameservers** → **Manage DNS records**)

#### Tambah Records untuk Subdomain `app`

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `76.76.21.21` | 300 |
| CNAME | `www` | `iqbalhidayatrasyad.blog` | 300 |
| **A** | **`app`** | **`<VPS_IP_ATLANTIC>`** | **300** |
| CNAME | `api` | `app.iqbalhidayatrasyad.blog` | 300 |

**Penjelasan**:
- Record `A` untuk `@` → Vercel IP (`76.76.21.21` adalah salah satu IP Vercel; Vercel biasanya minta CNAME `cname.vercel-dns.com` tapi IP juga bisa fallback)
- Record `A` untuk `app` → IP VPS Atlantic (ini yang jadi server app kita)
- Record `CNAME` untuk `api` (opsional) → alias ke `app`

⚠️ **Untuk Vercel**, lihat Section 5 — biasanya lebih clean pakai CNAME `cname.vercel-dns.com` daripada IP, karena IP Vercel bisa berubah.

**Rekomendasi record yang lebih clean**:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `76.76.21.21` | 300 |
| CNAME | `www` | `cname.vercel-dns.com.` | 300 |
| **A** | **`app`** | **`<VPS_IP_ATLANTIC>`** | **300** |
| **CNAME** | **`api`** | **`app.iqbalhidayatrasyad.blog.`** | **300** |

#### Verifikasi DNS Propagation

```bash
# Dari laptop atau server
dig app.iqbalhidayatrasyad.blog
# Seharusnya return <VPS_IP_ATLANTIC>

dig iqbalhidayatrasyad.blog
# Seharusnya return 76.76.21.21 (Vercel)

# Atau pakai tool online
# https://dnschecker.org/#A/app.iqbalhidayatrasyad.blog
```

DNS propagation bisa 5 menit – 24 jam. Biasanya <30 menit untuk Hostinger.

### 3.3 Opsi B — Pindah NS ke Cloudflare

Kalau mau semua DNS di Cloudflare (untuk proteksi DDoS subdomain `app` juga):

1. Daftar Cloudflare → Add site `iqbalhidayatrasyad.blog`
2. Ganti NS di Hostinger ke NS Cloudflare (mis. `isla.ns.cloudflare.com`)
3. Tunggu propagasi NS (~30 menit)
4. Di Cloudflare DNS Records, tambahkan sama seperti tabel di atas

**⚠️ PENTING untuk Cloudflare + VPS**:
- Set proxy `app.iqbalhidayatrasyad.blog` ke **DNS only (grey cloud)** — kalau proxy ON (orange), Let's Encrypt http-01 challenge akan gagal
- Atau pakai **DNS-01 challenge** dengan certbot + Cloudflare API token (lebih ribet)

Lihat detail di Section 4.

---

## 4. Setup Cloudflare untuk Subdomain App

> Cloudflare untuk subdomain `app` hanya kalau Anda **pindah NS ke Cloudflare (Opsi B)** di Section 3.

### 4.1 Add Site

1. Login https://dash.cloudflare.com
2. Klik **+ Add a Site** → `iqbalhidayatrasyad.blog`
3. Plan: **Free**
4. Cloudflare scan existing DNS records → klik **Continue**

### 4.2 Update Nameserver di Hostinger

Cloudflare akan kasih 2 NS, mis:
```
isla.ns.cloudflare.com
sid.ns.cloudflare.com
```

**Di Hostinger**:
1. Domain → **DNS / Nameservers**
2. Pilih **Use custom nameservers**
3. Paste 2 NS dari Cloudflare
4. Save

Propagasi NS: 10 menit – 24 jam.

### 4.3 DNS Records di Cloudflare

Setelah NS propagasi, di **Cloudflare Dashboard → DNS → Records**:

| Type | Name | Content | Proxy | TTL |
|---|---|---|---|---|
| A | @ | `76.76.21.21` | **DNS only** (grey) | Auto |
| CNAME | www | `iqbalhidayatrasyad.blog` | **DNS only** | Auto |
| **A** | **app** | **`<VPS_IP>`** | **DNS only** (grey) ⚠️ | Auto |
| CNAME | api | `app.iqbalhidayatrasyad.blog` | DNS only | Auto |

⚠️ **`app` HARUS "DNS only" (grey cloud)**, BUKAN "Proxied" (orange cloud).

**Alasan**: Let's Encrypt http-01 challenge mengirim request ke IP origin (VPS). Kalau Cloudflare proxy ON, request ke VPS ditolak karena IP behind proxy. Dengan proxy OFF, request langsung ke VPS, dan certbot bisa validasi.

**Alternatif kalau mau Cloudflare proxy ON**: pakai **DNS-01 challenge** (certbot + Cloudflare API token). Ini setup-nya lebih ribet — lihat https://certbot-dns-cloudflare.readthedocs.io/

### 4.4 Cloudflare SSL/TLS Setting

Dashboard → **SSL/TLS** → pilih **Full (Strict)**:

```
Flexible       → ❌ JANGAN (Cloudflare→VPS pakai HTTP, rentan MITM)
Full           → ✓ OK (Cloudflare→VPS pakai HTTPS, cert self-signed OK)
Full (Strict)  → ✓✓ RECOMMENDED (butuh cert valid di VPS — Let's Encrypt cukup)
```

### 4.5 Cloudflare Caching untuk App (Opsional)

Dashboard → **Caching** → **Configuration**:
- Browser Cache TTL: 4 hours
- Crawler Hints: ON
- Always Online: ON

Dashboard → **Rules** → **Cache Rules** → **Create rule**:
- Name: `Cache static assets`
- URL: `app.iqbalhidayatrasyad.blog/assets/*`
- Setting: Cache eligible, Edge TTL: 1 month

Buat rule kedua:
- Name: `Bypass dynamic`
- URL: `app.iqbalhidayatrasyad.blog/api/*` dan `app.iqbalhidayatrasyad.blog/ai/*`
- Setting: Bypass cache

### 4.6 Cloudflare Security (Opsional)

Dashboard → **Security**:
- Security Level: Medium
- Bot Fight Mode: ON

---

## 5. Setup Vercel untuk Domain Utama

> Domain `iqbalhidayatrasyad.blog` (root + `www`) di-host di Vercel untuk blog/portofolio.

### 5.1 Tambah Project Vercel

1. Login https://vercel.com
2. **+ Add New Project** → Import dari GitHub (repo blog/portofolio Anda)
3. Framework Preset: pilih sesuai (Next.js/Astro/Hugo/Jekyll/static)
4. Klik **Deploy**

### 5.2 Tambah Custom Domain

1. Di Vercel project → **Settings** → **Domains**
2. Ketik `iqbalhidayatrasyad.blog` → klik **Add**
3. Vercel akan kasih instruksi DNS — biasanya:

   ```
   Type: A
   Name: @
   Value: 76.76.21.21
   ```

   atau

   ```
   Type: CNAME
   Name: www
   Value: cname.vercel-dns.com
   ```

4. Tambahkan record tersebut di **Hostinger DNS Zone** (kalau Opsi A) atau **Cloudflare** (kalau Opsi B)

### 5.3 Verifikasi

```bash
dig iqbalhidayatrasyad.blog
# Harus return 76.76.21.21 atau IP Vercel lain

curl -I https://iqbalhidayatrasyad.blog
# Expected: HTTP/2 200 (atau 308 redirect ke www)
```

Vercel otomatis issue **Let's Encrypt cert** untuk domain Anda — tidak perlu setup cert manual.

---

## 6. Konfigurasi Environment

### 6.1 Generate Secrets

Di VPS (atau lokal), generate semua secret:

```bash
# Postgres password
openssl rand -hex 16
# Output: 8f3a9c2b1d4e5f6a7b8c9d0e1f2a3b4c

# JWT secret
openssl rand -hex 32
# Output: (64 hex char)

# Encryption key (32 byte = 64 hex char)
openssl rand -hex 32
```

### 6.2 Buat `.env` Production

Di VPS:

```bash
cd /opt/ai-devsecops
cp .env.production.example .env
nano .env
chmod 600 .env
```

Isi dengan:

```bash
# === Database ===
DATABASE_URL=postgres://ai_devsecops:8f3a9c2b1d4e5f6a7b8c9d0e1f2a3b4c@postgres:5432/ai_devsecops
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_USER=ai_devsecops
DATABASE_PASSWORD=8f3a9c2b1d4e5f6a7b8c9d0e1f2a3b4c
DATABASE_NAME=ai_devsecops
DATABASE_SSLMODE=disable

# === Redis ===
REDIS_URL=redis://redis:6379
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# === Backend ===
SERVER_PORT=8080
SERVER_HOST=0.0.0.0
JWT_SECRET=a1b2c3d4e5f6...64hex
JWT_ACCESS_DURATION=15m
JWT_REFRESH_DURATION=168h
ENCRYPTION_KEY=f6e5d4c3b2a1...64hex
AI_SERVICE_URL=http://ai-service:8000
CORS_ALLOWED_ORIGINS=https://app.iqbalhidayatrasyad.blog,https://iqbalhidayatrasyad.blog

# === AI Service ===
HOST=0.0.0.0
PORT=8000
APP_NAME=AI DevSecOps Security Assistant
DEBUG=false
BACKEND_API_URL=http://backend:8080/api/v1

# === LLM (isi minimal 1) ===
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-v4-flash
LLM_REQUEST_TIMEOUT=120

# === GitHub (opsional) ===
GITHUB_TOKEN=ghp_...

# === Frontend (DI-BAKE saat build, bukan runtime!) ===
VITE_API_URL=https://app.iqbalhidayatrasyad.blog/api/v1
```

⚠️ **PENTING**:
- `DATABASE_HOST=postgres` (hostname docker-compose, **JANGAN** `localhost`)
- `REDIS_HOST=redis` (hostname docker-compose)
- `VITE_API_URL` di-bake ke JS bundle saat build. Setiap ganti URL, harus rebuild frontend.
- `CORS_ALLOWED_ORIGINS` harus match persis dengan origin frontend (scheme + host, **tanpa trailing slash**)

### 6.3 Perbandingan dengan .env Dev

| Variable | Dev | Production | Alasan |
|---|---|---|---|
| `POSTGRES_PASSWORD` | `postgres` | `<random 32 char>` | Jangan pakai default |
| `POSTGRES_USER` | `postgres` | `ai_devsecops` | Jangan pakai user default |
| `JWT_SECRET` | `change-me-in-production` | `<random 32 byte>` | Validasi token JWT |
| `ENCRYPTION_KEY` | kosong | `<random 32 byte>` | Enkripsi data sensitif |
| `DEBUG` (ai-service) | `true` | `false` | Hindari leak info internal |
| `VITE_API_URL` | `http://localhost:8082/api/v1` | `https://app.iqbalhidayatrasyad.blog/api/v1` | HTTPS di prod |
| `CORS_ALLOWED_ORIGINS` | (tidak ada / `*`) | domain spesifik | Strict CORS |
| API keys LLM | bisa dummy | real production key | Rate limit berbeda |

---

## 7. Deploy Aplikasi

### 7.1 Pertama Kali Deploy

```bash
cd /opt/ai-devsecops

# Step 1: Build & start postgres, redis dulu
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build postgres redis

# Tunggu ~10 detik sampai DB ready
sleep 10
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs postgres | grep "ready"
# Expected: "database system is ready to accept connections"

# Step 2: Start backend & ai-service
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build backend ai-service

# Step 3: Start frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build frontend

# Step 4: Cek semua container
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

**Expected output**:
```
NAME                            STATUS
ai-devsecops-postgres-1         Up (healthy)
ai-devsecops-redis-1            Up (healthy)
ai-devsecops-backend-1          Up
ai-devsecops-ai-service-1       Up
ai-devsecops-frontend-1         Up
```

**Belum start nginx** — perlu issue cert dulu (Section 8).

### 7.2 Test Internal (Tanpa HTTPS)

```bash
# Test backend langsung dari dalam container
docker compose exec backend wget -qO- http://localhost:8080/api/v1/health
# Expected: {"status":"ok"} atau similar

# Test AI service
docker compose exec ai-service wget -qO- http://localhost:8000/api/health
```

### 7.3 Update / Redeploy

Setiap ada perubahan code:

```bash
cd /opt/ai-devsecops
bash scripts/deploy.sh
```

**`scripts/deploy.sh`** melakukan:
1. `git pull origin main`
2. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
3. `docker image prune -f` (cleanup image lama)
4. Print status container

---

## 8. Setup HTTPS / Let's Encrypt

### 8.1 Prerequisites

- [x] Domain `app.iqbalhidayatrasyad.blog` sudah pointing ke IP VPS (verify `dig`)
- [x] Port 80 dan 443 terbuka (UFW: `sudo ufw status`)
- [x] Container postgres, redis, backend, ai-service, frontend running
- [ ] `certbot` sudah terinstall (akan di-handle script)

### 8.2 Pertama Kali Issue Cert

```bash
cd /opt/ai-devsecops

# Install certbot jika belum
sudo apt install -y certbot

# Issue cert (script akan handle nginx config swap)
sudo bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog
```

**`scripts/init-letsencrypt.sh`** melakukan:
1. Cek apakah cert sudah ada di `/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/`
2. Kalau ada, skip
3. Test ACME challenge (cek domain resolve ke VPS)
4. Start nginx container dengan config **HTTP-only** (untuk ACME webroot)
5. `certbot certonly --webroot -w /var/www/certbot -d app.iqbalhidayatrasyad.blog --email ...`
6. Swap nginx config dari HTTP-only ke **TLS-enabled** (listen 80 + 443)
7. Reload nginx
8. Verifikasi HTTPS reachable

### 8.3 Verifikasi HTTPS

```bash
# Dari VPS
curl -I https://app.iqbalhidayatrasyad.blog
# Expected: HTTP/2 200

# Cek cert
echo | openssl s_client -connect app.iqbalhidayatrasyad.blog:443 -servername app.iqbalhidayatrasyad.blog 2>/dev/null | openssl x509 -noout -subject -dates
# Expected: subject=CN = app.iqbalhidayatrasyad.blog, dates OK

# Test SSL grade
# Buka https://www.ssllabs.com/ssltest/analyze.html?d=app.iqbalhidayatrasyad.blog
# Expected: Grade A atau A+
```

### 8.4 Auto-Renewal (Cron)

Cert Let's Encrypt berlaku 90 hari, perlu di-renew sebelum expire.

```bash
# Tambah cron job
crontab -e
```

Tambah baris:

```cron
0 3,15 * * * /opt/ai-devsecops/scripts/renew-certs.sh >> /var/log/le-renew.log 2>&1
```

**`scripts/renew-certs.sh`** melakukan:
- `certbot renew --quiet`
- Kalau cert baru: `docker compose exec nginx nginx -s reload`

### 8.5 Nginx Production Config (Ringkasan)

File `nginx/prod-nginx.conf` (akan dibuat saat eksekusi):

```nginx
events {}

http {
    # HTTP → HTTPS redirect + ACME webroot
    server {
        listen 80;
        server_name app.iqbalhidayatrasyad.blog;

        # Let's Encrypt webroot
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Redirect everything else to HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name app.iqbalhidayatrasyad.blog;

        ssl_certificate /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/privkey.pem;

        # Modern SSL config
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 1d;
        ssl_session_tickets off;

        # HSTS
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Reverse proxy
        location /api/v1/ai/ {
            rewrite ^/api/v1/ai/(.*) /api/$1 break;
            proxy_pass http://ai-service:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Authorization $http_authorization;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
        }

        location /ai/ {
            rewrite ^/ai/(.*) /api/$1 break;
            proxy_pass http://ai-service:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 600s;
            proxy_send_timeout 600s;
        }

        location /api/ {
            proxy_pass http://backend:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            proxy_pass http://frontend:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## 9. Verifikasi & Testing

### 9.1 End-to-End Test

Buka browser ke **https://app.iqbalhidayatrasyad.blog**:

1. **Frontend load** → landing page tampil
2. **Login/Register** → coba register user baru
3. **Dashboard** → cek data tampil
4. **AI endpoint** → coba kirim prompt (kalau ada fitur chat)
5. **Logout** → cookie cleared

### 9.2 Cek Service Health

```bash
# Dari VPS
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
# Semua STATUS = Up

docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 ai-service

# Test dari luar (laptop)
curl -I https://app.iqbalhidayatrasyad.blog
curl https://app.iqbalhidayatrasyad.blog/api/v1/health
```

### 9.3 Cek DNS Resolution

```bash
# app harus resolve ke IP VPS
dig +short app.iqbalhidayatrasyad.blog

# domain utama harus resolve ke Vercel
dig +short iqbalhidayatrasyad.blog
# Expected: 76.76.21.21 atau IP Vercel lain
```

### 9.4 Cek Cert Expiry

```bash
sudo certbot certificates
# Output:
# Certificate Name: app.iqbalhidayatrasyad.blog
#     Domains: app.iqbalhidayatrasyad.blog
#     Expiry Date: 2026-09-29 (VALID 89 days)
```

---

## 10. Maintenance

### 10.1 Command Harian

```bash
# Status semua container
cd /opt/ai-devsecops
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Log real-time
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100

# Restart service tertentu
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart ai-service

# Masuk ke container (debug)
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U ai_devsecops -d ai_devsecops
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli

# Disk usage
docker system df
df -h

# Cleanup
docker image prune -f
docker system prune -a --volumes  # HATI-HATI, hapus semua unused
```

### 10.2 Update Aplikasi

```bash
cd /opt/ai-devsecops
git pull origin main
bash scripts/deploy.sh
```

### 10.3 Backup Postgres (Recommended)

Tambah cron job untuk auto-backup:

```bash
sudo crontab -e
```

Tambah:

```cron
# Backup Postgres setiap hari jam 2 pagi
0 2 * * * /opt/ai-devsecops/scripts/backup-postgres.sh >> /var/log/pg-backup.log 2>&1
```

**`scripts/backup-postgres.sh`**:
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/postgres"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker compose -f /opt/ai-devsecops/docker-compose.yml \
               -f /opt/ai-devsecops/docker-compose.prod.yml \
               exec -T postgres \
  pg_dump -U ai_devsecops ai_devsecops | gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

# Keep only last 7 days
find "$BACKUP_DIR" -name "postgres_*.sql.gz" -mtime +7 -delete
```

### 10.4 Monitor Cert Expiry (Alert)

Tambah script cek cert (opsional):

```bash
# Tambah cron 1x seminggu
0 9 * * 1 /opt/ai-devsecops/scripts/check-cert.sh
```

Kalau cert <14 hari, kirim email/ke Telegram.

### 10.5 Restart Server (kalau perlu reboot)

```bash
# Graceful: stop containers dulu
cd /opt/ai-devsecops
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Reboot
sudo reboot

# Setelah up, jalankan ulang
cd /opt/ai-devsecops
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Atau biar auto-start, tambahkan di `docker-compose.prod.yml`:
```yaml
services:
  backend:
    restart: unless-stopped
  # ... dst
```

(Docker akan auto-start container setelah reboot karena policy `restart: unless-stopped`)

---

## 11. Troubleshooting

### 11.1 DNS Tidak Resolve

```bash
# Cek dari beberapa DNS server
dig app.iqbalhidayatrasyad.blog @1.1.1.1
dig app.iqbalhidayatrasyad.blog @8.8.8.8
dig app.iqbalhidayatrasyad.blog @ns1.dns-parking.com  # Hostinger NS

# Cek di dashboard Hostinger apakah record sudah masuk
# Cek di Cloudflare (kalau Opsi B) apakah proxy = DNS only
```

### 11.2 Let's Encrypt Gagal

**Symptom**: `Challenge failed for domain app.iqbalhidayatrasyad.blog`

**Cek urutan**:
```bash
# 1. Domain resolve ke VPS?
dig app.iqbalhidayatrasyad.blog

# 2. Port 80 terbuka?
sudo ufw status
curl http://app.iqbalhidayatrasyad.blog/.well-known/acme-challenge/test

# 3. Nginx container running?
docker compose ps nginx

# 4. Cloudflare proxy OFF? (kalau pakai Cloudflare)
# Dashboard Cloudflare → DNS → app record → harus "DNS only" (grey)

# 5. Log certbot
sudo cat /var/log/letsencrypt/letsencrypt.log
```

**Fix umum**:
- Tunggu DNS propagation (cek berkala 5-10 menit)
- Set Cloudflare proxy = DNS only
- Pastikan nginx config HTTP-only listen di 80
- `sudo ufw allow 80/tcp` kalau tertutup

### 11.3 Container Crash / Restart Loop

```bash
# Lihat log
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail=100

# Cek healthcheck
docker inspect --format='{{.State.Health.Status}}' ai-devsecops-backend-1
```

**Common causes**:
- `.env` tidak ter-load atau ada typo
- Postgres/Redis belum ready (butuh `depends_on: condition: service_healthy`)
- Port bentrok (kalau ada proses lain di host yang pakai 80/443)

### 11.4 Frontend Panggil API ke localhost:8080

**Symptom**: di browser DevTools, request API ke `http://localhost:8080` (atau `8082`).

**Fix**: `VITE_API_URL` di `.env` harus `https://app.iqbalhidayatrasyad.blog/api/v1`. Rebuild:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d frontend
```

`VITE_*` env di-bake ke JS bundle saat build. Tidak bisa diubah di runtime.

### 11.5 CORS Error

**Symptom**: `Access to XMLHttpRequest at '...' from origin '...' has been blocked by CORS policy`

**Fix**: `CORS_ALLOWED_ORIGINS` di `.env` harus match **persis** dengan origin frontend.

```bash
# Cek
docker compose exec backend env | grep CORS

# Edit .env di VPS
nano /opt/ai-devsecops/.env

# Rebuild & restart
cd /opt/ai-devsecops
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build backend
```

Format: `https://app.iqbalhidayatrasyad.blog` (tanpa trailing slash, tanpa path)

### 11.6 Cert Hampir Expire / Tidak Auto-Renew

```bash
# Test renewal manual
sudo certbot renew --dry-run

# Cek log renewal
cat /var/log/le-renew.log

# Cek cron job
crontab -l | grep cert

# Manual renew
sudo certbot renew
docker compose -f /opt/ai-devsecops/docker-compose.yml -f /opt/ai-devsecops/docker-compose.prod.yml exec nginx nginx -s reload
```

### 11.7 Atlantic VM Tidak Bisa Diakses

**Symbash**: SSH timeout, IP tidak respond.

**Cek**:
1. Atlantic panel: VM status = Running?
2. Atlantic panel: ada notifikasi maintenance?
3. Atlantic panel: bandwidth sudah over quota?
4. Coba Atlantic VNC console (kalau ada) untuk debug dari dalam

**Recovery**: Restart dari panel Atlantic, atau kontak Atlantic support.

---

## Lampiran A: Ringkasan Perintah Penting

```bash
# === Setup Awal ===
ssh deploy@<VPS_IP>
cd /opt/ai-devsecops
bash scripts/setup-vps.sh
cp .env.production.example .env
nano .env
chmod 600 .env

# === Deploy ===
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# === HTTPS ===
sudo bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog

# === Verify ===
curl -I https://app.iqbalhidayatrasyad.blog
sudo certbot certificates
docker compose ps

# === Update ===
cd /opt/ai-devsecops
bash scripts/deploy.sh

# === Debug ===
docker compose logs -f --tail=100 <service>
docker compose exec <service> sh
docker system df
```

---

## Lampiran B: Estimasi Biaya

| Item | Provider | Harga |
|---|---|---|
| VPS Atlantic 4GB | Atlantic.Net | ~$12–20/bulan |
| Domain `.blog` | Hostinger | ~$10–15/tahun |
| Cloudflare Free | Cloudflare | $0 |
| Let's Encrypt | Let's Encrypt | $0 |
| Vercel Free | Vercel | $0 |
| **Total bulanan** | | **~$13–22** |

---

## Lampiran C: Catatan Khusus Atlantic.Net

Atlantic.Net punya **Atlantic Cloud Platform** dengan:
- Data center: New York, Ashburn, Dallas, San Jose, London, Frankfurt, Singapore, Sydney
- **Rekomendasi untuk Indonesia**: pilih Singapore DC (paling dekat, latency ~30ms)
- OS images: Ubuntu 22.04/24.04, Debian 11/12, CentOS, Rocky, AlmaLinux, Windows
- **Snapshots**: tersedia di panel, bisa untuk backup sebelum update
- **Object Storage**: opsional, bisa untuk backup file di luar VM
- **Load Balancer**: opsional, kalau nanti mau scale horizontal

**Perintah Atlantic-specific** (tidak selalu ada di semua VPS):
```bash
# Cek metadata Atlantic
curl -s http://169.254.169.254/latest/meta-data/public-ipv4
```

---

## Checklist Final Sebelum Go-Live

- [ ] VPS Atlantic dibuat, RAM ≥ 4 GB, region Singapore
- [ ] SSH key sudah di-add, login sebagai `deploy` (non-root)
- [ ] `scripts/setup-vps.sh` selesai, Docker + UFW + fail2ban aktif
- [ ] Repo di-clone ke `/opt/ai-devsecops`
- [ ] `.env` production sudah diisi semua secret, `chmod 600`
- [ ] DNS di Hostinger: A record `app` → IP VPS sudah masuk
- [ ] `dig app.iqbalhidayatrasyad.blog` return IP VPS
- [ ] DNS di Hostinger: CNAME/A record root → Vercel sudah masuk
- [ ] `dig iqbalhidayatrasyad.blog` return IP Vercel
- [ ] Vercel project sudah deploy dan domain sudah di-add
- [ ] `docker compose ... up -d --build` semua container running
- [ ] `bash scripts/init-letsencrypt.sh` cert berhasil issue
- [ ] `curl -I https://app.iqbalhidayatrasyad.blog` return HTTP/2 200
- [ ] Browser bisa akses https://app.iqbalhidayatrasyad.blog
- [ ] Login & register berhasil
- [ ] 1 endpoint AI test berhasil
- [ ] Cron cert renewal sudah ditambah
- [ ] (Opsional) Backup Postgres cron sudah ditambah
- [ ] (Opsional) Cloudflare account dibuat (kalau Opsi B)

---

**Dokumen ini akan di-update setelah eksekusi.**
