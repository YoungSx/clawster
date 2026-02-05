#!/bin/bash
# Start OpenClaw Distributed Node
NODE_ID=${1:-"node-$(hostname)"}
CONFIG=${2:-"./config.json"}

echo "Starting OpenClaw Distributed Node: $NODE_ID"
python3 scripts/node_manager.py --node-id "$NODE_ID" --config "$CONFIG"
