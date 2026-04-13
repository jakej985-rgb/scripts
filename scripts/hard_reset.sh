#!/bin/bash
echo "🛑 [RESET] Stopping all M3TAL stacks..."

# Array of compose files
FILES=(
  "control-plane/docker-compose.yml"
  "docker/routing/docker-compose.yml"
  "docker/maintenance/docker-compose.yml"
  "docker/media/docker-compose.yml"
  "docker/network/docker-compose.yml"
  "docker/apps/tattoo-app/docker-compose.yml"
)

for f in "${FILES[@]}"; do
  echo "Stopping $f..."
  docker compose -f "$f" down --remove-orphans
done

echo "🧹 [CLEAN] Pruning disconnected Docker networks..."
docker network prune -f

echo "🚀 [START] Re-launching core infrastructure..."

echo "Enuring proxy network..."
docker network create proxy 2>/dev/null || true

echo "Starting Routing..."
docker compose -f docker/routing/docker-compose.yml up -d

echo "Starting Control Plane..."
docker compose -f control-plane/docker-compose.yml up -d

echo "✅ [DONE] Infrastructure redeployed."
echo "👉 Run 'python m3tal.py audit' to verify."
