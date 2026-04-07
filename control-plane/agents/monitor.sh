#!/bin/bash

# MONITOR AGENT
# Gathers all container states (including exited) and writes to state.json
docker ps -a --format '{{json .}}' > control-plane/state/state.json
