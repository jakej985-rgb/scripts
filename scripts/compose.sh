#!/bin/bash
# M3TAL Unified Stack Operator (v2.0 Hardened)
# Enforces Centralized Authority and Shared Network Integrity

# Determine repo root relative to this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT="$( dirname "$SCRIPT_DIR" )"
ENV_FILE="$ROOT/.env"

# 1. Fail early if .env is missing (Audit Fix)
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ ERROR: .env file not found at $ENV_FILE"
    echo "   M3TAL requires a valid .env at the repository root to load configuration."
    exit 1
fi

# 2. Guarantee shared network exists (Audit Fix)
echo "🌐 Checking shared 'proxy' network..."
docker network inspect proxy >/dev/null 2>&1 || docker network create proxy

# Selective Stack Control
STACK=$1

if [ -n "$STACK" ]; then
    echo "🚀 Launching M3TAL Selective Stack: $STACK..."
    COMPOSE_FILE="$ROOT/docker/$STACK/docker-compose.yml"
    
    if [ -f "$COMPOSE_FILE" ]; then
        docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
    else
        echo "❌ Error: Stack '$STACK' not found at $COMPOSE_FILE"
        exit 1
    fi
else
    echo "🚀 Launching ALL M3TAL Stacks (Production Authority)..."
    
    # Define stacks in order of dependency
    # We use multiple -f flags to ensure a single compose context (Audit Rec)
    docker compose --env-file "$ENV_FILE" \
        -f "$ROOT/docker/routing/docker-compose.yml" \
        -f "$ROOT/docker/media/docker-compose.yml" \
        -f "$ROOT/docker/maintenance/docker-compose.yml" \
        up -d
fi

echo "✅ Deployment processed."
