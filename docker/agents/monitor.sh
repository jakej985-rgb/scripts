#!/bin/bash

# Monitor Agent - collects health, logs, disk/CPU metrics
# Safe - read only, no actions

LOCKFILE="/tmp/m3tal_monitor.lock"
if [ -f "$LOCKFILE" ]; then exit 0; fi
trap "rm -f $LOCKFILE" EXIT
touch $LOCKFILE

# Source connections
source "/docker/connections.env"

OUTFILE="/docker/state/monitor.json"

# Collect CPU
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2+$4}')
# Collect Mem
MEM=$(free | awk '/Mem:/ {printf("%.0f", $3/$2 * 100)}')
# Collect Disk
DISK=$(df / | awk 'NR==2 {print $5}' | tr -d '%')

# Collect Container info
CONTAINERS_JSON="["
FIRST=1
for NAME in $(docker ps -a --format "{{.Names}}"); do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$NAME")
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$NAME" 2>/dev/null || echo "none")

    if [ $FIRST -eq 0 ]; then
        CONTAINERS_JSON="$CONTAINERS_JSON,"
    fi
    FIRST=0
    CONTAINERS_JSON="$CONTAINERS_JSON {\"name\": \"$NAME\", \"status\": \"$STATUS\", \"health\": \"$HEALTH\"}"
done
CONTAINERS_JSON="$CONTAINERS_JSON]"

# Get recent errors from logs
LOG_DIR="/docker/maintenance/logs"
KEYWORDS="error|failed|unhealthy|panic|critical|permission denied"
LOGS_JSON="["
if [ -d "$LOG_DIR" ]; then
    FIRST=1
    for file in "$LOG_DIR"/*.log; do
        if [ -f "$file" ]; then
            MSG=$(grep -Ei "$KEYWORDS" "$file" | tail -n 5 | tr '\n' ' ' | sed 's/"/\\"/g')
            if [ ! -z "$MSG" ]; then
                if [ $FIRST -eq 0 ]; then
                    LOGS_JSON="$LOGS_JSON,"
                fi
                FIRST=0
                BASENAME=$(basename "$file")
                LOGS_JSON="$LOGS_JSON {\"file\": \"$BASENAME\", \"errors\": \"$MSG\"}"
            fi
        fi
    done
fi
LOGS_JSON="$LOGS_JSON]"

# Output JSON
cat > "$OUTFILE" <<EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "system": {
        "cpu_usage": $CPU,
        "mem_usage": $MEM,
        "disk_usage": $DISK
    },
    "containers": $CONTAINERS_JSON,
    "logs": $LOGS_JSON
}
EOF
