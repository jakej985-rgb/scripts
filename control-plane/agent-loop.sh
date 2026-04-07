#!/bin/bash

while true; do
  bash control-plane/agents/monitor.sh
  bash control-plane/agents/anomaly-agent.sh
  bash control-plane/agents/decision-engine.sh
  bash control-plane/agents/reconcile.sh

  sleep 30
done
