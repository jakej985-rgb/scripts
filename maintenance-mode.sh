#!/bin/bash

# 🔧 Toggle maintenance mode

FLAG="/tmp/maintenance_mode"

if [ -f "$FLAG" ]; then
  rm "$FLAG"
  echo "Maintenance mode OFF"
else
  touch "$FLAG"
  echo "Maintenance mode ON"
fi
