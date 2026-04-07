#!/bin/bash

# metrics.sh - Collects container CPU usage signals

docker stats --no-stream --format "{{.Name}} {{.CPUPerc}}" > control-plane/state/metrics.txt
