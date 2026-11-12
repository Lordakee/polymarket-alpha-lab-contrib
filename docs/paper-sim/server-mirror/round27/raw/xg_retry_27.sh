#!/bin/bash
# Retry the Understat fetch every 3 min for up to ~45 min; stop on success.
for i in $(seq 1 15); do
  echo "=== attempt $i $(date -u +%H:%M:%SZ) ==="
  if python3 /home/ubuntu/paper-sim/round27/raw/xg_fetch_27.py >> /home/ubuntu/paper-sim/round27/raw/xg_retry.log 2>&1; then
    echo SUCCESS at attempt $i
    exit 0
  fi
  sleep 180
done
echo GAVE-UP
exit 1
