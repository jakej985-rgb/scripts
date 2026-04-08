#!/bin/bash

# MONITOR AGENT
# Gathers all container states (including exited) and writes to state.json
# Write to temp and move to ensure atomic update (prevents race with dashboard)
docker ps -a --format '{{json .}}' > control-plane/state/state.json.tmp
mv control-plane/state/state.json.tmp control-plane/state/state.json
