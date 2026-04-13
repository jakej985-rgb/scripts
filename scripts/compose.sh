#!/bin/bash
# M3TAL Unified Stack Operator
# Enforces environment variable propagation across all compose projects.

# Determine repo root relative to this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT="$( dirname "$SCRIPT_DIR" )"
ENV_FILE="$ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found at $ENV_FILE"
    exit 1
fi

echo "🚀 Launching M3TAL Stacks..."

# Define stacks in order of dependency
STACKS=(
    "docker/routing"
    "docker/media"
    "docker/maintenance"
)

for STACK in "${STACKS[@]}"; do
    COMPOSE_FILE="$ROOT/$STACK/docker-compose.yml"
    if [ -f "$COMPOSE_FILE" ]; then
        echo "  📦 Starting $STACK..."
        docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
    else
        echo "  ⚠️ Warning: $COMPOSE_FILE not found, skipping..."
    fi
done

echo "✅ All stacks processed."
