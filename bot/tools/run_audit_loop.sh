#!/bin/bash
# Continuous audit loop - runs every hour through the night

LOG_FILE="audit_log_$(date +%Y%m%d_%H%M%S).txt"

echo "Starting continuous audit loop..." | tee "$LOG_FILE"

for i in {1..24}; do
    echo "" | tee -a "$LOG_FILE"
    echo "=== AUDIT RUN $i ===" | tee -a "$LOG_FILE"
    python tools/continuous_audit.py 2>&1 | tee -a "$LOG_FILE"
    
    echo "Next audit in 60 minutes..." | tee -a "$LOG_FILE"
    sleep 3600
done

echo "Audit loop complete" | tee -a "$LOG_FILE"
