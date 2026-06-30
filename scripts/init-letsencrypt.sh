#!/bin/bash
set -e

DOMAIN="${1:-app.iqbalhidayatrasyad.blog}"
EMAIL="${2:-admin@iqbalhidayatrasyad.blog}"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
WEBROOT="/var/www/certbot"
NGINX_CERT_DIR="/opt/ai-devsecops/nginx/certs"
NGINX_LETSENCRYPT_DIR="/opt/ai-devsecops/nginx/letsencrypt"

echo "=== Let's Encrypt Certificate Setup ==="
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Create directories
mkdir -p "$WEBROOT"
mkdir -p "$NGINX_CERT_DIR"
mkdir -p "$NGINX_LETSENCRYPT_DIR"

# Check if cert already exists
if [ -d "$CERT_DIR" ]; then
    echo "[SKIP] Certificate already exists at $CERT_DIR"
    echo "Expiry: $(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -dates | grep notAfter)"
    echo ""
    echo "To force renew, run: sudo certbot renew"
    exit 0
fi

# Verify domain resolves to this server
echo "[1/5] Verifying domain DNS resolution..."
RESOLVED_IP=$(dig +short "$DOMAIN" @1.1.1.1 | tail -1)
SERVER_IP=$(curl -s ifconfig.me)

if [ "$RESOLVED_IP" != "$SERVER_IP" ]; then
    echo "[WARN] Domain $DOMAIN resolves to $RESOLVED_IP but this server is $SERVER_IP"
    echo "DNS may not have propagated yet, or A record is wrong."
    echo "Continue anyway? (y/n)"
    read -r answer
    if [ "$answer" != "y" ]; then
        exit 1
    fi
else
    echo "[OK] Domain resolves correctly to this server ($SERVER_IP)"
fi

# Start nginx with temporary HTTP config for ACME challenge
echo "[2/5] Starting nginx for ACME challenge..."
cat > /tmp/nginx-temp.conf <<'EOF'
events {}
http {
    server {
        listen 80;
        server_name _;
        root /var/www/certbot;
        location /.well-known/acme-challenge/ {
            try_files $uri =404;
        }
    }
}
EOF
docker run --rm -d \
    --name nginx-acme \
    -p 80:80 \
    -v /tmp/nginx-temp.conf:/etc/nginx/nginx.conf:ro \
    -v /var/www/certbot:/var/www/certbot:ro \
    nginx:alpine

sleep 3

# Test ACME endpoint
echo "[3/5] Testing ACME endpoint..."
if curl -s http://localhost/.well-known/acme-challenge/test -o /dev/null; then
    echo "[OK] Nginx serving ACME challenges correctly"
else
    echo "[WARN] ACME endpoint not responding, but continuing..."
fi

# Issue certificate
echo "[4/5] Issuing certificate via certbot..."
certbot certonly \
    --webroot \
    --webroot-path "$WEBROOT" \
    --domain "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --keep-until-expiring

# Link certs to app directory
echo "[5/5] Linking certificates..."
ln -sfn "$CERT_DIR" "$NGINX_CERT_DIR"
ln -sfn "$CERT_DIR" "$NGINX_LETSENCRYPT_DIR"

# Stop temporary nginx
docker stop nginx-acme

echo ""
echo "=== Certificate issued successfully ==="
echo "Certificate location: $CERT_DIR"
echo "Expiry: $(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -dates | grep notAfter)"
echo ""
echo "Now update nginx/prod-nginx.conf if needed, then run:"
echo "  cd /opt/ai-devsecops"
echo "  docker compose -f docker-compose.prod.yml up -d nginx"
