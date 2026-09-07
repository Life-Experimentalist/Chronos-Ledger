#!/bin/sh
# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
#
# chronos_intranet_autodiscover.sh
# Detects the server's LAN IP, writes environment files, and launches containers.

set -e

echo "========================================================================="
echo " CHRONOS LEDGER — Intranet Auto-Discovery Initialization"
echo "========================================================================="

# Detect local IPv4 address (works on Linux and macOS)
DETECTED_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}')
if [ -z "$DETECTED_IP" ]; then
    DETECTED_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "$DETECTED_IP" ]; then
    DETECTED_IP="127.0.0.1"
fi

echo " Detected Interface IP : http://$DETECTED_IP"
echo "=========================================================================\n"

# Inject discovered IP into build-time and runtime env
cat > .env.production << EOF
NEXT_PUBLIC_API_URL=http://$DETECTED_IP/api/v1
NEXT_PUBLIC_WS_URL=ws://$DETECTED_IP/ws
EOF

# Merge with base .env if it exists
if [ -f ".env" ]; then
    grep -v "^NEXT_PUBLIC" .env >> .env.production || true
fi

echo "Generated .env.production with:"
cat .env.production

echo "\n========================================================================="
echo " Starting Chronos Ledger container stack..."
echo "========================================================================="

docker compose down --remove-orphans
docker compose --env-file .env.production up --build -d

echo "\n========================================================================="
echo " Container health status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo "\n Organization devices should navigate to: http://$DETECTED_IP"
echo "========================================================================="
