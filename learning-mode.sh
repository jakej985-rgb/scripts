#!/bin/bash

# 🧠 Learning mode: builds baseline of normal system behavior

DATA_DIR="/tmp/system_learning"
mkdir -p "$DATA_DIR"

CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2+$4}')
MEM=$(free | awk '/Mem:/ {printf("%.0f", $3/$2 * 100)}')
DISK=$(df / | awk 'NR==2 {print $5}' | tr -d '%')

# Save samples
echo "$CPU" >> "$DATA_DIR/cpu.log"
echo "$MEM" >> "$DATA_DIR/mem.log"
echo "$DISK" >> "$DATA_DIR/disk.log"

# Keep last 100 samples
tail -n 100 "$DATA_DIR/cpu.log" > "$DATA_DIR/cpu.tmp" && mv "$DATA_DIR/cpu.tmp" "$DATA_DIR/cpu.log"
tail -n 100 "$DATA_DIR/mem.log" > "$DATA_DIR/mem.tmp" && mv "$DATA_DIR/mem.tmp" "$DATA_DIR/mem.log"
tail -n 100 "$DATA_DIR/disk.log" > "$DATA_DIR/disk.tmp" && mv "$DATA_DIR/disk.tmp" "$DATA_DIR/disk.log"
