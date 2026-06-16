#!/bin/bash
# Terminal 4: Trigger Traffic
echo "📡 Pinging 10.0.0.1 from ns2 (Sender)..."
ip netns exec ns2 ping 10.0.0.1
