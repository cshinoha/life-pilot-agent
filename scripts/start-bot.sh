#!/bin/bash
# Kill any rogue instances not managed by systemd
pkill -u ubuntu -f "python.*d_brain" 2>/dev/null || true
sleep 2
# exec replaces this bash process — systemd tracks uv as Main PID
exec /home/ubuntu/.local/bin/uv run python -m d_brain
