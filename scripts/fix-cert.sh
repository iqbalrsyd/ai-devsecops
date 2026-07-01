#!/bin/bash
set -e

echo "=== Fix Cert: Diagnose & Repair (v3) ==="

CERT_HOST_DIR="/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog"
CERT_HOST_ARCHIVE="/etc/letsencrypt/archive/app.iqbalhidayatrasyad.blog"
CERT_FLAT_DIR="/opt/ai-devsecops/cert-files"

echo ""
echo "[1/7] Verify cert files exist on host..."
if [ ! -f "$CERT_HOST_DIR/fullchain.pem" ]; then
    echo "  ERROR: cert files missing at $CERT_HOST_DIR"
    echo ""
    echo "  Contents of /etc/letsencrypt/live/:"
    ls -la /etc/letsencrypt/live/ 2>&1 || echo "  (directory does not exist)"
    echo ""
    echo "  Re-run: sudo bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog"
    exit 1
fi
echo "  OK - fullchain.pem and privkey.pem exist"

# Verify symlinks
echo ""
echo "[2/7] Check Let's Encrypt symlink structure..."
ls -la "$CERT_HOST_DIR/"
if [ -L "$CERT_HOST_DIR/fullchain.pem" ]; then
    echo "  Note: fullchain.pem is a symlink"
    REAL_FILE=$(readlink -f "$CERT_HOST_DIR/fullchain.pem")
    echo "  Resolves to: $REAL_FILE"
fi

# Create flat directory with actual cert files (resolve symlinks)
echo ""
echo "[3/7] Create flat cert directory (resolve symlinks)..."
sudo rm -rf "$CERT_FLAT_DIR"
sudo mkdir -p "$CERT_FLAT_DIR"
# Use cp -L to dereference symlinks, or cp -P to preserve
sudo cp -L "$CERT_HOST_DIR/fullchain.pem" "$CERT_FLAT_DIR/fullchain.pem"
sudo cp -L "$CERT_HOST_DIR/privkey.pem" "$CERT_FLAT_DIR/privkey.pem"
sudo cp -L "$CERT_HOST_DIR/chain.pem" "$CERT_FLAT_DIR/chain.pem" 2>/dev/null || true
sudo cp -L "$CERT_HOST_DIR/cert.pem" "$CERT_FLAT_DIR/cert.pem" 2>/dev/null || true
sudo chmod 644 "$CERT_FLAT_DIR"/*.pem
ls -la "$CERT_FLAT_DIR/"

echo ""
echo "[4/7] Update docker-compose.prod.yml to use flat dir..."
cd /opt/ai-devsecops
# Backup
sudo cp docker-compose.prod.yml docker-compose.prod.yml.bak
# Replace the cert mount line
sudo sed -i "s|- /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:ro|- $CERT_FLAT_DIR:/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:ro|" docker-compose.prod.yml
grep -A1 "volumes:" docker-compose.prod.yml | tail -10

echo ""
echo "[5/7] Stop & recreate nginx..."
docker stop ai-devsecops-nginx-1 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps nginx
sleep 8

echo ""
echo "[6/7] Verify cert in container..."
docker exec ai-devsecops-nginx-1 ls -la /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/ 2>&1

echo ""
echo "[7/7] Check nginx log..."
docker logs ai-devsecops-nginx-1 --tail=15

echo ""
echo "=== Testing ==="
echo "--- HTTP (expect 301) ---"
curl -sI http://localhost 2>&1 | head -5
echo ""
echo "--- HTTPS localhost (expect 200) ---"
curl -sIk https://localhost 2>&1 | head -5
echo ""
echo "--- HTTPS domain (expect 200) ---"
curl -sIk https://app.iqbalhidayatrasyad.blog 2>&1 | head -5
