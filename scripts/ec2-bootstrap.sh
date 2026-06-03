#!/usr/bin/env bash
# First-time EC2 setup (Amazon Linux 2023 or Ubuntu 22.04+).
# Run with: sudo bash scripts/ec2-bootstrap.sh
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

if command -v dnf &>/dev/null; then
  dnf update -y
  dnf install -y git
  dnf install -y docker docker-compose-plugin
  systemctl enable --now docker
elif command -v apt-get &>/dev/null; then
  apt-get update -y
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" >/etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  echo "Unsupported OS: install Docker Engine and Compose plugin manually." >&2
  exit 1
fi

# Optional: allow ec2-user/ubuntu to use docker
for u in ec2-user ubuntu; do
  if id "$u" &>/dev/null; then
    usermod -aG docker "$u" || true
  fi
done

echo "Docker is ready. Clone the repo, copy .env from .env.example, then:"
echo "  cd Chatbot-engine && docker compose -f deploy/docker-compose.ec2.yml up -d --build"
