#!/bin/bash
set -e

echo "=== AI DevSecOps VPS Setup ==="
echo "Running on: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo ""

# Update system
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# Install dependencies
echo "[2/8] Installing Docker, docker-compose, UFW, fail2ban..."
apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    unattended-upgrades \
    git \
    certbot \
   openssl \
    tzdata

# Add Docker GPG key and repository
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Add current user to docker group
usermod -aG docker "$SUDO_USER" || usermod -aG docker $(whoami)

# Setup UFW
echo "[3/8] Configuring UFW..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ufw status numbered

# Setup fail2ban
echo "[4/8] Configuring fail2ban..."
cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
findtime = 600
EOF
systemctl enable fail2ban
systemctl start fail2ban
fail2ban-client status sshd

# Setup unattended-upgrades
echo "[5/8] Enabling unattended-upgrades..."
dpkg-reconfigure -plow unattended-upgrades || true
cat > /etc/apt/apt.conf.d/99periodic <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Set timezone
echo "[6/8] Setting timezone to Asia/Jakarta..."
timedatectl set-timezone Asia/Jakarta

# Create certbot directories
echo "[7/8] Creating certbot directories..."
mkdir -p /var/www/certbot
mkdir -p /opt/ai-devsecops/nginx/certs
mkdir -p /opt/ai-devsecops/nginx/letsencrypt

# Print summary
echo "[8/8] Setup complete!"
echo ""
echo "=== Summary ==="
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version)"
echo "UFW status:"
ufw status | grep -E "^(Status|[0-9])"
echo "Fail2ban SSH status:"
fail2ban-client status sshd 2>/dev/null || echo "  (checking...)"
echo ""
echo "Next steps:"
echo "  1. git clone <repo> /opt/ai-devsecops"
echo "  2. cd /opt/ai-devsecops"
echo "  3. cp .env.production.example .env"
echo "  4. nano .env  # fill in all values"
echo "  5. chmod 600 .env"
echo "  6. bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog"
echo "  7. docker compose -f docker-compose.prod.yml up -d --build"
echo ""
