#!/bin/bash

# 🌐 Node Agent v5 — Lightweight status broadcaster
# Runs on each server in the cluster
# Reports container status for the master dashboard to aggregate

while true; do
  docker ps --format "{{.Names}} {{.Status}}" > /docker/state/node-status.txt
  sleep 5
done
