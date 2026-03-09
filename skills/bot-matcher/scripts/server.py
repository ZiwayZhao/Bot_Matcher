#!/usr/bin/env python3
"""ClawMatch P2P HTTP server (v2).

Replaces gossip-based discovery with ERC-8004 on-chain identity resolution.
Adds connection request handling for the shadow tree mechanism.

Python stdlib only, zero external dependencies.

Endpoints:
  GET  /id                       - Return this claw's peer_id + agent_id
  GET  /health                   - Health check with uptime + peer count
  GET  /peers                    - List all known peers
  POST /card                     - Receive a Profile A (MD), return own Profile A
  POST /message                  - Receive a conversation message
  GET  /messages?peer=X&since=N  - Fetch messages from a peer since line N
  POST /connect                  - Receive a connection request (triggers shadow tree)
  GET  /connections              - List pending/active connection requests
  GET  /forest                   - List all trees (handshakes) with status
  GET  /handshake?peer=X         - Get handshake JSON for a specific peer
  POST /accept                   - Accept a pending connection (reveal shadow tree)
  GET  /notifications            - Get proactive watering reminders

Usage:
  python3 server.py <data_dir> <port> <peer_id> [--public-address ADDR]

Example:
  python3 server.py ~/.bot-matcher 18800 alice
  python3 server.py ~/.bot-matcher 18800 alice --public-address https://abc.trycloudflare.com
"""

import json
import os
import signal
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# URL Helper
# ---------------------------------------------------------------------------

def make_url(address: str, path: str) -> str:
    """Build a full URL from an address and path.

    Supports:
      - "localhost:18800"                → "http://localhost:18800/path"
      - "1.2.3.4:18800"                 → "http://1.2.3.4:18800/path"
      - "http://host:port"              → "http://host:port/path"
      - "https://abc.trycloudflare.com" → "https://abc.trycloudflare.com/path"
    """
    if address.startswith("http://") or address.startswith("https://"):
        return f"{address.rstrip('/')}{path}"
    return f"http://{address}{path}"


# ---------------------------------------------------------------------------
# Peer Manager (simplified, no gossip)
# ---------------------------------------------------------------------------

class PeerManager:
    """Thread-safe registry of known peers. Peers are added via direct
    connection (ERC-8004 lookup + card exchange), not gossip."""

    def __init__(self, own_id: str, own_address: str, data_dir: Path):
        self.own_id = own_id
        self.own_address = own_address
        self.data_dir = data_dir
        self._lock = threading.Lock()
        self._peers: dict[str, dict] = {}
        self._load()

    def _load(self):
        path = self.data_dir / "peers.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for pid, info in data.items():
                    if pid != self.own_id:
                        self._peers[pid] = {
                            "address": info.get("address", ""),
                            "last_seen": info.get("last_seen", 0),
                        }
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        path = self.data_dir / "peers.json"
        with self._lock:
            data = {
                pid: {"address": info["address"], "last_seen": info["last_seen"]}
                for pid, info in self._peers.items()
            }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_peer(self, peer_id: str, address: str) -> bool:
        """Add or update a peer. Returns True if NEW."""
        if peer_id == self.own_id:
            return False
        is_new = False
        with self._lock:
            if peer_id not in self._peers:
                is_new = True
                _log(f"New peer: {peer_id} at {address}")
            self._peers[peer_id] = {
                "address": address,
                "last_seen": time.time(),
            }
        self._save()
        return is_new

    def get_peer(self, peer_id: str) -> dict | None:
        with self._lock:
            return self._peers.get(peer_id)

    def get_all_peers(self) -> dict[str, dict]:
        with self._lock:
            return {pid: dict(info) for pid, info in self._peers.items()}


# ---------------------------------------------------------------------------
# Connection Request Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages incoming connection requests and their shadow tree state."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._lock = threading.Lock()
        self._connections: dict[str, dict] = {}
        self._load()

    def _path(self) -> Path:
        return self.data_dir / "connections.json"

    def _load(self):
        if self._path().exists():
            try:
                self._connections = json.loads(
                    self._path().read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        with self._lock:
            data = dict(self._connections)
        self._path().write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add_request(self, from_peer: str, from_address: str, agent_id: int | None = None) -> dict:
        """Record an incoming connection request. Returns the connection record."""
        with self._lock:
            if from_peer in self._connections:
                # Already exists, update address
                self._connections[from_peer]["address"] = from_address
                self._connections[from_peer]["updated_at"] = datetime.now(timezone.utc).isoformat()
                record = self._connections[from_peer]
            else:
                record = {
                    "from_peer": from_peer,
                    "address": from_address,
                    "agent_id": agent_id,
                    "status": "pending",  # pending | accepted | rejected
                    "visibility": "shadow",  # shadow | revealed
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self._connections[from_peer] = record
        self._save()
        return record

    def accept(self, peer_id: str) -> dict | None:
        with self._lock:
            if peer_id not in self._connections:
                return None
            self._connections[peer_id]["status"] = "accepted"
            self._connections[peer_id]["visibility"] = "revealed"
            self._connections[peer_id]["accepted_at"] = datetime.now(timezone.utc).isoformat()
            self._connections[peer_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            record = self._connections[peer_id]
        self._save()
        return record

    def reject(self, peer_id: str) -> dict | None:
        with self._lock:
            if peer_id not in self._connections:
                return None
            self._connections[peer_id]["status"] = "rejected"
            self._connections[peer_id]["visibility"] = "rejected"
            self._connections[peer_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            record = self._connections[peer_id]
        self._save()
        return record

    def get_all(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._connections)

    def get_pending(self) -> list[dict]:
        with self._lock:
            return [c for c in self._connections.values() if c["status"] == "pending"]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sys.stdout.write(f"[{ts}] {msg}\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ClawMatchHandler(BaseHTTPRequestHandler):
    """Handle all ClawMatch HTTP requests."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/id":
            # Include chain agent_id if registered
            chain_id = self.server.chain_agent_id
            self._json_response(200, {
                "peer_id": self.server.peer_id,
                "agent_id": chain_id,
            })

        elif path == "/health":
            inbox_dir = self.server.data_dir / "inbox"
            inbox_count = len(list(inbox_dir.glob("*.md"))) if inbox_dir.exists() else 0
            all_peers = self.server.peer_manager.get_all_peers()
            pending = self.server.connection_manager.get_pending()
            self._json_response(200, {
                "status": "ok",
                "peer_id": self.server.peer_id,
                "agent_id": self.server.chain_agent_id,
                "public_address": self.server.peer_manager.own_address,
                "uptime": int(time.time() - self.server.start_time),
                "inbox_count": inbox_count,
                "peers_total": len(all_peers),
                "pending_connections": len(pending),
            })

        elif path == "/peers":
            all_peers = self.server.peer_manager.get_all_peers()
            self._json_response(200, {"peers": all_peers})

        elif path == "/connections":
            connections = self.server.connection_manager.get_all()
            self._json_response(200, {"connections": connections})

        elif path == "/messages":
            params = parse_qs(parsed.query)
            peer = params.get("peer", [None])[0]
            since = int(params.get("since", [0])[0])
            if not peer:
                self._json_response(400, {"error": "missing 'peer' parameter"})
                return
            msg_file = self.server.data_dir / "messages" / f"{peer}.jsonl"
            messages = []
            if msg_file.exists():
                lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
                for line in lines[since:]:
                    if line.strip():
                        messages.append(json.loads(line))
            self._json_response(200, {
                "messages": messages,
                "total": since + len(messages),
            })

        elif path == "/forest":
            self._handle_forest()

        elif path == "/handshake":
            params = parse_qs(parsed.query)
            peer = params.get("peer", [None])[0]
            if not peer:
                self._json_response(400, {"error": "missing 'peer' parameter"})
                return
            hs_path = self.server.data_dir / "handshakes" / f"{peer}.json"
            if not hs_path.exists():
                self._json_response(404, {"error": f"No handshake for {peer}"})
                return
            hs = json.loads(hs_path.read_text(encoding="utf-8"))
            self._json_response(200, hs)

        elif path == "/notifications":
            self._handle_notifications()

        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/card":
            self._handle_card()
        elif path == "/message":
            self._handle_message()
        elif path == "/connect":
            self._handle_connect()
        elif path == "/accept":
            self._handle_accept()
        else:
            self._json_response(404, {"error": "not found"})

    def _handle_connect(self):
        """Handle incoming connection request. Creates a shadow tree on this side."""
        try:
            body = self._read_body()
            peer_id = body.get("peer_id")
            address = body.get("address")
            agent_id = body.get("agent_id")

            if not peer_id:
                self._json_response(400, {"error": "missing peer_id"})
                return

            # Record connection request
            record = self.server.connection_manager.add_request(
                peer_id, address or "", agent_id
            )

            # Register as peer if address provided
            if address:
                self.server.peer_manager.add_peer(peer_id, address)

            _log(f"Connection request from {peer_id} (agent #{agent_id})")

            self._json_response(200, {
                "status": "connection_request_received",
                "peer_id": self.server.peer_id,
                "agent_id": self.server.chain_agent_id,
                "connection_status": record["status"],
            })
        except (json.JSONDecodeError, ValueError) as e:
            self._json_response(400, {"error": str(e)})

    def _handle_card(self):
        """Receive a peer's Profile A (markdown), save to inbox, return own Profile A."""
        try:
            body = self._read_body()
            peer_id = body.get("peer_id")
            profile = body.get("profile")
            sender_address = body.get("address")
            if not peer_id:
                self._json_response(400, {"error": "missing peer_id"})
                return
            if not profile:
                self._json_response(400, {"error": "missing profile (markdown content)"})
                return

            if sender_address:
                self.server.peer_manager.add_peer(peer_id, sender_address)

            inbox_dir = self.server.data_dir / "inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            card_path = inbox_dir / f"{peer_id}.md"
            card_path.write_text(profile, encoding="utf-8")

            own_profile_path = self.server.data_dir / "profile_public.md"
            own_card = None
            if own_profile_path.exists():
                own_card = {
                    "peer_id": self.server.peer_id,
                    "profile": own_profile_path.read_text(encoding="utf-8"),
                }

            self._json_response(200, {
                "status": "received",
                "card": own_card,
            })
        except (json.JSONDecodeError, ValueError) as e:
            self._json_response(400, {"error": str(e)})

    def _handle_message(self):
        """Receive a conversation message, append to messages/{sender_id}.jsonl."""
        try:
            body = self._read_body()
            sender_id = body.get("sender_id")
            content = body.get("content")
            msg_type = body.get("type", "conversation")  # conversation | water
            topic = body.get("topic")  # for watering messages
            if not sender_id or content is None:
                self._json_response(400, {"error": "missing sender_id or content"})
                return

            msg_dir = self.server.data_dir / "messages"
            msg_dir.mkdir(parents=True, exist_ok=True)
            msg_file = msg_dir / f"{sender_id}.jsonl"

            entry = {
                "role": sender_id,
                "content": content,
                "type": msg_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if topic:
                entry["topic"] = topic
            with open(msg_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            self._json_response(200, {"status": "received"})
        except (json.JSONDecodeError, ValueError) as e:
            self._json_response(400, {"error": str(e)})

    def _handle_accept(self):
        """Accept a pending connection — reveal the shadow tree."""
        try:
            body = self._read_body()
            peer_id = body.get("peer_id")
            if not peer_id:
                self._json_response(400, {"error": "missing peer_id"})
                return

            record = self.server.connection_manager.accept(peer_id)
            if not record:
                self._json_response(404, {"error": f"No pending connection from {peer_id}"})
                return

            # Also update handshake visibility if it exists
            hs_path = self.server.data_dir / "handshakes" / f"{peer_id}.json"
            if hs_path.exists():
                hs = json.loads(hs_path.read_text(encoding="utf-8"))
                hs["visibility"]["sideB"] = "revealed"
                hs_path.write_text(
                    json.dumps(hs, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            _log(f"Connection accepted: {peer_id} — tree revealed!")

            self._json_response(200, {
                "status": "accepted",
                "peer_id": peer_id,
                "visibility": "revealed",
                "message": f"Your tree with {peer_id} has been revealed!",
            })
        except (json.JSONDecodeError, ValueError) as e:
            self._json_response(400, {"error": str(e)})

    def _handle_forest(self):
        """Return all trees (handshakes) with summary info for the frontend."""
        hs_dir = self.server.data_dir / "handshakes"
        trees = []
        if hs_dir.exists():
            for hs_file in sorted(hs_dir.glob("*.json")):
                try:
                    hs = json.loads(hs_file.read_text(encoding="utf-8"))
                    branches = hs.get("bootstrap", {}).get("seedBranches", [])
                    trees.append({
                        "peer_id": hs_file.stem,
                        "handshakeId": hs.get("handshakeId"),
                        "stage": hs.get("stage", "initial"),
                        "visibility": hs.get("visibility", {}),
                        "branch_count": len(branches),
                        "topics": [b.get("topic", "") for b in branches],
                        "match_score": hs.get("matchSummary", {}).get("score"),
                        "createdAt": hs.get("createdAt"),
                        "enrichedAt": hs.get("enrichedAt"),
                        "lastWateredAt": hs.get("lastWateredAt"),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue

        # Also include shadow trees from pending connections without handshakes
        connections = self.server.connection_manager.get_all()
        hs_peers = {t["peer_id"] for t in trees}
        for peer_id, conn in connections.items():
            if peer_id not in hs_peers and conn.get("status") == "pending":
                trees.append({
                    "peer_id": peer_id,
                    "handshakeId": None,
                    "stage": "shadow",
                    "visibility": {"sideA": "unknown", "sideB": "shadow"},
                    "branch_count": 0,
                    "topics": [],
                    "match_score": None,
                    "createdAt": conn.get("received_at"),
                    "enrichedAt": None,
                    "lastWateredAt": None,
                })

        self._json_response(200, {"trees": trees, "count": len(trees)})

    def _handle_notifications(self):
        """Run check_trees logic inline and return notifications."""
        from datetime import timedelta
        hs_dir = self.server.data_dir / "handshakes"
        now = datetime.now(timezone.utc)
        notifications = []

        if hs_dir.exists():
            for hs_file in hs_dir.glob("*.json"):
                try:
                    peer_id = hs_file.stem
                    hs = json.loads(hs_file.read_text(encoding="utf-8"))
                    vis = hs.get("visibility", {})

                    if vis.get("sideB") != "revealed":
                        continue

                    created_at = self._parse_iso(hs.get("createdAt"))
                    last_watered = self._parse_iso(hs.get("lastWateredAt"))
                    branches = hs.get("bootstrap", {}).get("seedBranches", [])

                    # New tree (< 3 days, no watering)
                    if created_at and (now - created_at) < timedelta(days=3) and not last_watered:
                        topics = [b.get("topic", "?") for b in branches[:3]]
                        notifications.append({
                            "type": "new_tree", "peer_id": peer_id,
                            "priority": "medium",
                            "message": f"Your new tree with {peer_id} just sprouted!",
                            "suggested_topics": topics,
                        })
                        continue

                    for branch in branches:
                        topic = branch.get("topic", "unknown")
                        state = branch.get("state", "detected")
                        confidence = branch.get("confidence", 0)
                        last_int = self._parse_iso(branch.get("last_interaction")) or created_at

                        if last_int and (now - last_int) > timedelta(days=7):
                            notifications.append({
                                "type": "wilt_warning", "peer_id": peer_id,
                                "topic": topic, "priority": "high",
                                "message": f"Your {topic} branch with {peer_id} is wilting!",
                                "days_since_interaction": (now - last_int).days,
                            })
                        elif state == "resonance" and confidence >= 0.8:
                            notifications.append({
                                "type": "resonance_opportunity", "peer_id": peer_id,
                                "topic": topic, "priority": "low",
                                "message": f"You and {peer_id} click on {topic}!",
                            })
                except (json.JSONDecodeError, KeyError):
                    continue

        # Shadow trees
        for peer_id, conn in self.server.connection_manager.get_all().items():
            if conn.get("status") == "pending":
                notifications.append({
                    "type": "shadow_tree", "peer_id": peer_id,
                    "priority": "medium",
                    "message": f"A mysterious tree from {peer_id}... Reveal it?",
                })

        self._json_response(200, {
            "notifications": notifications,
            "count": len(notifications),
        })

    @staticmethod
    def _parse_iso(ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        _log(format % args)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _detect_public_ip() -> str | None:
    """Try to detect public IP via free API. Returns IP string or None."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=5) as resp:
                ip = resp.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            continue
    return None


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <data_dir> <port> <peer_id> [--public-address ADDR]")
        print(f"  Example: {sys.argv[0]} ~/.bot-matcher 18800 alice")
        print(f"  Example: {sys.argv[0]} ~/.bot-matcher 18800 alice --public-address https://abc.trycloudflare.com")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    port = int(sys.argv[2])
    peer_id = sys.argv[3]

    # Parse --public-address
    public_address = None
    args = sys.argv[4:]
    i = 0
    while i < len(args):
        if args[i] == "--public-address" and i + 1 < len(args):
            public_address = args[i + 1]
            i += 2
        else:
            i += 1

    # Determine own address
    if public_address:
        own_address = public_address
        _log(f"Using provided public address: {own_address}")
    else:
        detected_ip = _detect_public_ip()
        if detected_ip:
            own_address = f"{detected_ip}:{port}"
            _log(f"Auto-detected public address: {own_address}")
        else:
            own_address = f"localhost:{port}"
            _log(f"Using localhost (no public address detected): {own_address}")

    # Ensure data directories exist
    data_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("inbox", "messages", "matches", "conversations", "criteria", "handshakes"):
        (data_dir / sub).mkdir(exist_ok=True)

    # Load chain identity if registered
    chain_agent_id = None
    chain_identity_path = data_dir / "chain_identity.json"
    if chain_identity_path.exists():
        try:
            chain_data = json.loads(chain_identity_path.read_text(encoding="utf-8"))
            chain_agent_id = chain_data.get("agent_id")
            _log(f"Chain identity loaded: agent #{chain_agent_id}")
        except Exception:
            pass

    # Initialize managers
    peer_manager = PeerManager(peer_id, own_address, data_dir)
    connection_manager = ConnectionManager(data_dir)

    # Create HTTP server
    server = HTTPServer(("0.0.0.0", port), ClawMatchHandler)
    server.peer_id = peer_id
    server.data_dir = data_dir
    server.peer_manager = peer_manager
    server.connection_manager = connection_manager
    server.chain_agent_id = chain_agent_id
    server.start_time = time.time()

    # Write PID file
    pid_path = data_dir / "server.pid"
    pid_path.write_text(str(os.getpid()))

    # Handle SIGTERM for clean shutdown (PID file cleanup)
    def _handle_sigterm(signum, frame):
        _log("Received SIGTERM, shutting down...")
        pid_path.unlink(missing_ok=True)
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _handle_sigterm)

    _log(f"ClawMatch server started: peer_id={peer_id} port={port} data_dir={data_dir}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Server stopped.")
    finally:
        pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
