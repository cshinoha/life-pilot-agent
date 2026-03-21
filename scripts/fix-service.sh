#!/bin/bash
set -e
cp /tmp/d-brain.service /etc/systemd/system/d-brain.service
systemctl daemon-reload
systemctl stop d-brain.service
pkill -u ubuntu -f "python.*d_brain" 2>/dev/null || true
sleep 3
systemctl start d-brain.service
sleep 8
echo "Processes running:"
ps aux | grep "d_brain" | grep -v grep | wc -l
