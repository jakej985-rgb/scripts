#!/bin/bash

# Analyzer Agent - reads from monitor.json, detects patterns, suggests actions
# Safe - read only, no actions

LOCKFILE="/tmp/m3tal_analyzer.lock"
if [ -f "$LOCKFILE" ]; then exit 0; fi
trap "rm -f $LOCKFILE" EXIT
touch $LOCKFILE

INFILE="/docker/state/monitor.json"
OUTFILE="/docker/state/analyzer.json"

if [ ! -f "$INFILE" ]; then
    echo '{"error": "monitor.json not found"}' > "$OUTFILE"
    exit 0
fi

RECOMMENDATIONS="["
FIRST=1

add_recommendation() {
    local type="$1"
    local target="$2"
    local reason="$3"
    if [ $FIRST -eq 0 ]; then
        RECOMMENDATIONS="$RECOMMENDATIONS,"
    fi
    FIRST=0
    RECOMMENDATIONS="$RECOMMENDATIONS {\"action\": \"$type\", \"target\": \"$target\", \"reason\": \"$reason\"}"
}

# Use python to parse JSON safely since jq might not be guaranteed
python3 -c "
import json
import sys

try:
    with open('$INFILE') as f:
        data = json.load(f)

    cpu = data.get('system', {}).get('cpu_usage', 0)
    mem = data.get('system', {}).get('mem_usage', 0)
    disk = data.get('system', {}).get('disk_usage', 0)

    if cpu > 90:
        print('alert system high_cpu')
    if mem > 90:
        print('alert system high_mem')
    if disk > 90:
        print('prune docker high_disk')

    for c in data.get('containers', []):
        name = c.get('name')
        status = c.get('status')
        health = c.get('health')

        if status != 'running':
            print(f'start {name} container_stopped')
        elif health == 'unhealthy':
            print(f'restart {name} container_unhealthy')
        elif health == 'healthy':
            print(f'healthy {name} container_healthy')

    for l in data.get('logs', []):
        fname = l.get('file')
        err = l.get('errors', '').lower()
        if 'permission denied' in err:
            print(f'alert {fname} permission_issue')
        elif 'error' in err or 'failed' in err or 'critical' in err or 'panic' in err:
            print(f'alert {fname} log_errors')

except Exception as e:
    pass
" | while read -r action target reason; do
    if [ ! -z "$action" ]; then
        add_recommendation "$action" "$target" "$reason"
    fi
done

RECOMMENDATIONS="$RECOMMENDATIONS]"

cat > "$OUTFILE" <<EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "recommendations": $RECOMMENDATIONS
}
EOF
