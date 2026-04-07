#!/bin/bash

# 🔗 Dependency Agent v3.2 — Container relationship awareness
# Checks if upstream dependencies are running

CONF="/docker/config/dependencies.conf"
STATE="/docker/state/dependency-issues.txt"

> $STATE

if [ ! -f "$CONF" ]; then exit 0; fi

RUNNING=$(docker ps --format "{{.Names}}" 2>/dev/null)

while IFS=":" read APP DEP; do
  # Skip comments and empty lines
  [[ "$APP" =~ ^#.*$ ]] && continue
  [ -z "$APP" ] && continue

  # Check if dependency is a container name
  if ! echo "$RUNNING" | grep -q "^${DEP}$"; then
    # Check if it's a path (mount) instead
    if [[ "$DEP" == /* ]]; then
      if [ ! -d "$DEP" ] && [ ! -f "$DEP" ]; then
        echo "$APP DEPENDENCY_MISSING $DEP" >> $STATE
      fi
    else
      echo "$APP DEPENDENCY_DOWN $DEP" >> $STATE
    fi
  fi
done < $CONF
