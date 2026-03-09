# Cross-Network Testing Guide

## Quick Start: Two-Tunnel Local Test

The simplest way to test cross-internet behavior on one machine:

```bash
# Install cloudflared
brew install cloudflared

# Terminal 1: Start Alice's server
python3 scripts/server.py /tmp/alice 18800 alice

# Terminal 2: Create tunnel for Alice
cloudflared tunnel --url http://localhost:18800
# → https://xxx-alice.trycloudflare.com

# Terminal 3: Start Bob's server
python3 scripts/server.py /tmp/bob 18801 bob

# Terminal 4: Create tunnel for Bob
cloudflared tunnel --url http://localhost:18801
# → https://yyy-bob.trycloudflare.com

# Terminal 5: Start Alice's server with public address
kill $(lsof -ti:18800)
python3 scripts/server.py /tmp/alice 18800 alice --public-address https://xxx-alice.trycloudflare.com

# Terminal 6: Start Bob's server with public address
kill $(lsof -ti:18801)
python3 scripts/server.py /tmp/bob 18801 bob --public-address https://yyy-bob.trycloudflare.com
```

Now test the flow using tunnel URLs:
```bash
# Alice connects to Bob via tunnel
curl -s -X POST https://yyy-bob.trycloudflare.com/connect \
  -H "Content-Type: application/json" \
  -d '{"peer_id":"alice","address":"https://xxx-alice.trycloudflare.com","agent_id":1}'

# Alice sends card to Bob via tunnel
python3 scripts/send_card.py /tmp/alice/profile_public.md \
  https://yyy-bob.trycloudflare.com alice https://xxx-alice.trycloudflare.com

# Alice sends message via tunnel
python3 scripts/send_message.py https://yyy-bob.trycloudflare.com alice "Hello from Alice!"
```

## Network Condition Simulation

### Toxiproxy (Recommended)

```bash
brew install toxiproxy
pip install toxiproxy-python

# Start toxiproxy server
toxiproxy-server &

# Create proxy between peers
toxiproxy-cli create peer_b -l 127.0.0.1:9001 -u 127.0.0.1:18801

# Add latency
toxiproxy-cli toxic add peer_b -t latency -a latency=200 -a jitter=50

# Add packet loss
toxiproxy-cli toxic add peer_b -t timeout -a timeout=5000

# Now connect via proxy port 9001 instead of 18801
python3 scripts/send_card.py /tmp/alice/profile_public.md localhost:9001 alice
```

### macOS Native (pfctl + dummynet)

```bash
# Add 200ms latency + 5% loss to port 18801
sudo dnctl pipe 1 config delay 200 plr 0.05
echo "dummynet in proto tcp from any to 127.0.0.1 port 18801 pipe 1" | sudo pfctl -a test -f -
sudo pfctl -e

# Cleanup
sudo dnctl -q flush
sudo pfctl -a test -F all
sudo pfctl -d
```

## HTTPS Testing

### mkcert (Local TLS)

```bash
brew install mkcert
mkcert -install
mkcert localhost 127.0.0.1
# Use the generated .pem files with your server
```

### trustme (Automated Tests)

```python
import trustme
ca = trustme.CA()
server_cert = ca.issue_cert("localhost")
# Use in test fixtures
```

## Checklist

- [ ] Two servers start independently
- [ ] Connection request via tunnel URL
- [ ] Card exchange via tunnel URL
- [ ] Messages via tunnel URL
- [ ] Water messages via tunnel URL
- [ ] Accept connection (shadow → revealed)
- [ ] Health shows correct public_address
- [ ] Tunnel URL change → update_endpoint.py works
- [ ] Server restart with new tunnel URL
- [ ] Timeout handling when peer is down
- [ ] Large profile transfer (>10KB)
