#!/usr/bin/env bash
# Copyright 2026 Chronos Ledger Contributors (Apache 2.0)
#
# One-command organization deployment script.
# Detects the server's LAN IP, configures the environment, and launches
# all services via Docker Compose.
#
# Usage (from repo root):
#   chmod +x setup.sh && ./setup.sh
#
# Flags (all optional; without them the script asks interactively):
#   --build   build images from source (skips the mode prompt)
#   --ghcr    pull pre-built images from GHCR (skips the mode prompt)
#   --demo    load a small demo data set after boot (see docs/demo.md)
#
# Prerequisites: Docker >= 24, Docker Compose >= 2.20, git, openssl

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
TEAL='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log()    { echo -e "${TEAL}[chronos]${NC} $*"; }
ok()     { echo -e "${GREEN}  ✔${NC} $*"; }
warn()   { echo -e "${YELLOW}  ⚠${NC} $*"; }
err()    { echo -e "${RED}  ✗${NC} $*" >&2; exit 1; }
header() { echo -e "\n${BOLD}$*${NC}"; }

# ── Preflight checks ──────────────────────────────────────────────────────────
header "Chronos Ledger: Setup"
log "Checking prerequisites..."

command -v docker  >/dev/null 2>&1 || err "Docker is not installed. Install from https://docs.docker.com/get-docker/"
command -v openssl >/dev/null 2>&1 || err "openssl is required."

DOCKER_COMPOSE_CMD="docker compose"
$DOCKER_COMPOSE_CMD version >/dev/null 2>&1 || err "Docker Compose v2 not found. Update Docker Desktop or install the plugin."

ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
ok "Docker Compose $($DOCKER_COMPOSE_CMD version --short)"

# ── Detect LAN IP ─────────────────────────────────────────────────────────────
header "Detecting server LAN IP..."
if command -v ip >/dev/null 2>&1; then
  LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
elif command -v ipconfig >/dev/null 2>&1; then
  # macOS / Windows
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
fi

# Windows ipconfig has no getifaddr and prints its usage text to stdout;
# keep only a real IPv4 address, otherwise fall back below.
if [[ ! "${LAN_IP:-}" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  LAN_IP=""
fi

if [[ -z "${LAN_IP:-}" ]]; then
  warn "Could not auto-detect LAN IP. Falling back to localhost."
  LAN_IP="localhost"
fi
ok "LAN IP: ${LAN_IP}"

# ── Environment configuration ─────────────────────────────────────────────────
header "Configuring environment..."

if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Created .env from template"
else
  warn ".env already exists, skipping creation (using existing values)"
fi

# Generate JWT secret if placeholder is still present
if grep -q "replace_with_64_char_hex" .env 2>/dev/null; then
  JWT_SECRET=$(openssl rand -hex 32)
  # Use | as sed delimiter to avoid issues with / in paths
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|replace_with_64_char_hex_secret_generated_by_openssl_rand_hex_32|${JWT_SECRET}|g" .env
  else
    sed -i "s|replace_with_64_char_hex_secret_generated_by_openssl_rand_hex_32|${JWT_SECRET}|g" .env
  fi
  ok "Generated JWT_SECRET_SIGNING_KEY"
fi

# Generate DB password if placeholder is present
if grep -q "change_me_password" .env 2>/dev/null; then
  DB_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|change_me_password|${DB_PASS}|g" .env
  else
    sed -i "s|change_me_password|${DB_PASS}|g" .env
  fi
  ok "Generated DB_PASSWORD"
fi

# Generate the administrator's first password if the placeholder is present
if grep -q "replace_with_the_first_admin_password" .env 2>/dev/null; then
  ADMIN_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|replace_with_the_first_admin_password|${ADMIN_PASS}|g" .env
  else
    sed -i "s|replace_with_the_first_admin_password|${ADMIN_PASS}|g" .env
  fi
  # Held back for the summary: it is generated here and printed nowhere
  # else, and nothing can log in as the administrator without it.
  ok "Generated INITIAL_ADMIN_PASSWORD"
elif ! grep -q "INITIAL_ADMIN_PASSWORD" .env 2>/dev/null; then
  # An .env written before this variable existed. Leave it empty rather
  # than generating something: the variable is only read while that
  # account is still waiting for a first password, and on an install this
  # old it chose one long ago.
  {
    echo ""
    echo "# The first password for the built-in administrator account,"
    echo "# applied on boot while that account is still waiting for one."
    echo "# Empty because this .env predates the variable, so that account"
    echo "# has had a password of its own for a while. See .env.example."
    echo "INITIAL_ADMIN_PASSWORD="
  } >> .env
  ok "Added INITIAL_ADMIN_PASSWORD to your existing .env, left empty"
fi

# Stamp LAN IP into frontend URLs
if [[ "$(uname)" == "Darwin" ]]; then
  sed -i '' "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://${LAN_IP}/api/v1|g" .env
  sed -i '' "s|NEXT_PUBLIC_WS_URL=.*|NEXT_PUBLIC_WS_URL=ws://${LAN_IP}/ws|g" .env
  sed -i '' "s|APP_CORS_ORIGINS=.*|APP_CORS_ORIGINS=http://${LAN_IP},http://localhost|g" .env
else
  sed -i "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://${LAN_IP}/api/v1|g" .env
  sed -i "s|NEXT_PUBLIC_WS_URL=.*|NEXT_PUBLIC_WS_URL=ws://${LAN_IP}/ws|g" .env
  sed -i "s|APP_CORS_ORIGINS=.*|APP_CORS_ORIGINS=http://${LAN_IP},http://localhost|g" .env
fi
ok "Frontend URLs set to http://${LAN_IP}"

# ── Optional: VAPID keys ──────────────────────────────────────────────────────
if grep -q "your_vapid" .env 2>/dev/null; then
  if command -v npx >/dev/null 2>&1; then
    log "Generating VAPID keys..."
    VAPID_OUTPUT=$(npx --yes web-push generate-vapid-keys --json 2>/dev/null || echo "")
    if [[ -n "${VAPID_OUTPUT}" ]]; then
      VAPID_PUB=$(echo "${VAPID_OUTPUT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['publicKey'])" 2>/dev/null || echo "")
      VAPID_PRIV=$(echo "${VAPID_OUTPUT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['privateKey'])" 2>/dev/null || echo "")
      if [[ -n "${VAPID_PUB}" ]]; then
        if [[ "$(uname)" == "Darwin" ]]; then
          sed -i '' "s|VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=${VAPID_PUB}|g" .env
          sed -i '' "s|VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=${VAPID_PRIV}|g" .env
          sed -i '' "s|NEXT_PUBLIC_VAPID_PUBLIC_KEY=.*|NEXT_PUBLIC_VAPID_PUBLIC_KEY=${VAPID_PUB}|g" .env
        else
          sed -i "s|VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=${VAPID_PUB}|g" .env
          sed -i "s|VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=${VAPID_PRIV}|g" .env
          sed -i "s|NEXT_PUBLIC_VAPID_PUBLIC_KEY=.*|NEXT_PUBLIC_VAPID_PUBLIC_KEY=${VAPID_PUB}|g" .env
        fi
        ok "Generated VAPID keys"
      fi
    fi
  else
    warn "Node.js/npx not found, skipping VAPID key generation."
    warn "Push notifications will not work. Run: npx web-push generate-vapid-keys"
  fi
fi

# ── Choose deployment mode ────────────────────────────────────────────────────
MODE=""
SEED_DEMO=0
for arg in "$@"; do
  case "${arg}" in
    --build) MODE=1 ;;
    --ghcr)  MODE=2 ;;
    --demo)  SEED_DEMO=1 ;;
  esac
done

if [[ -z "${MODE}" ]]; then
header "Deployment mode"
echo ""
echo "  [1] Build locally , builds images from source (slower, always fresh)"
echo "  [2] Pull from GHCR, pulls pre-built images (faster, requires login for private repos)"
echo ""
read -rp "  Choose [1]: " MODE
MODE="${MODE:-1}"
fi

COMPOSE_FILE="docker-compose.yml"
if [[ "${MODE}" == "2" ]]; then
  COMPOSE_FILE="docker-compose.prod.yml"
  if ! grep -q "GHCR_OWNER" .env 2>/dev/null; then
    read -rp "  GitHub org/username for GHCR images: " GHCR_OWNER
    # A registry path is lowercase only, and a GitHub account need not be.
    echo "GHCR_OWNER=$(echo "${GHCR_OWNER}" | tr '[:upper:]' '[:lower:]')" >> .env
  fi
fi

# ── Launch ────────────────────────────────────────────────────────────────────
header "Launching Chronos Ledger..."
$DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" up --build -d

# ── Wait for health ───────────────────────────────────────────────────────────
log "Waiting for services to be healthy..."
ATTEMPTS=0
MAX=30
until docker inspect --format='{{.State.Health.Status}}' chronos_core_engine 2>/dev/null | grep -q "healthy"; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [[ $ATTEMPTS -ge $MAX ]]; then
    warn "Backend healthcheck timed out. Check logs: docker logs chronos_core_engine"
    break
  fi
  sleep 3
  echo -n "."
done
echo ""

# Optional demo data (see docs/demo.md)
if [[ "${SEED_DEMO}" == "1" ]]; then
  log "Loading demo data..."
  DEMO_OUTPUT="$($DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" run --rm chronos-app uv run --no-sync python -m app.demo_seed)"
  echo "${DEMO_OUTPUT}"
  # Held back for the summary too: it scrolls past during the compose run, and
  # the visitor kiosk cannot be set up without it.
  DEMO_KIOSK_KEY="$(echo "${DEMO_OUTPUT}" | sed -n 's/^Kiosk key[^:]*: //p')"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
header "All done!"
echo ""
ok "App:       http://${LAN_IP}"
ok "API docs:  http://${LAN_IP}/docs"
ok "Login:     admin@org.internal"
if [[ -n "${ADMIN_PASS:-}" ]]; then
  ok "Password:  ${ADMIN_PASS}"
  echo -e "${YELLOW}  Printed once, here. It is also in .env as INITIAL_ADMIN_PASSWORD.${NC}"
else
  ok "Password:  whatever INITIAL_ADMIN_PASSWORD says in your .env"
fi
echo -e "${YELLOW}  IMPORTANT: You will be prompted to set a new password on first login.${NC}"
echo ""
if [[ -n "${DEMO_KIOSK_KEY:-}" ]]; then
  ok "Kiosk key: ${DEMO_KIOSK_KEY}"
  echo -e "${YELLOW}  Paste this once at http://${LAN_IP}/guest/kiosk/ to activate the visitor kiosk.${NC}"
  echo ""
fi
echo "  Useful commands:"
echo "    docker compose logs -f                  # Stream all logs"
echo "    docker compose logs -f chronos-app      # FastAPI logs only"
echo "    docker compose down                     # Stop all services"
echo "    docker compose pull && docker compose up -d  # Update to latest"
echo ""
