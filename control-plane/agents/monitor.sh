#!/bin/bash

# MONITOR AGENT
echo "[MONITOR] Running..."
docker ps --format '{{json .}}' > control-plane/state/state.json
echo "[MONITOR] State updated."
