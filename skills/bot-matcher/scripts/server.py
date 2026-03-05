#!/usr/bin/env python3
"""Bot-Matcher HTTP server with gossip peer discovery.

Python stdlib only, zero external dependencies.

Endpoints:
  GET  /id                       - Return this bot's peer_id
  GET  /health                   - Health check with uptime + peer count
  GET  /peers                    - List all known peers
  POST /exchange                 - Gossip: exchange peer lists
  POST /card                     - Receive a Profile A (MD), return own Profile A
  POST /message                  - Receive a conversation message
  GET  /messages?peer=X&since=N  - Fetch messages from a peer since line N

Usage:
  python3 server.py <data_dir> <port> <peer_id> [bootstrap_peers...]

  bootstrap_peers: space-separated host:port addresses of known peers

Example:
  python3 server.py context-match 18800 agent_alice
  python3 server.py context-match 18801 agent_bob localhost:18800

Storage layout under <data_dir>:
  inbox/{peer_id}.md             - received Profile A from peers
  messages/{peer_id}.jsonl       - received conversation messages
  profile_public.md              - own Profile A (read-only, created by agent)
  peers.json                     - known peers registry (auto-managed)
  server.pid                     - PID file for management
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import URLError


# ---------------------------------------------------------------------------
# Peer Manager
# ---------------------------------------------------------------------------

class PeerManager:
    """Thread-safe registry of known peers."""

    def __init__(self, own_id: str, own_address: str, data_dir: Path):
        self.own_id = own_id
        self.own_address = own_address
        self.data_dir = data_dir
        self._lock = threading.Lock()
        self._peers: dict[str, dict] = {}  # peer_id -> {address, last_seen, online}
        self._load()

    def _load(self):
        """Load persisted peers from disk."""
        path = self.data_dir / "peers.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for pid, info in data.items():
                    if pid != self.own_id:
                        self._peers[pid] = {
                            "address": info.get("address", ""),
                            "last_seen": info.get("last_seen", 0),
                            "online": False,  # will be confirmed by gossip
                        }
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        """Persist peers to disk."""
        path = self.data_dir / "peers.json"
        data = {}
        with self._lock:
            for pid, info in self._peers.items():
                data[pid] = {
                    "address": info["address"],
                    "last_seen": info["last_seen"],
                }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_peer(self, peer_id: str, address: str) -> bool:
        """Add or update a peer. Returns True if this is a NEW peer."""
        if peer_id == self.own_id:
            return False
        is_new = False
        with self._lock:
            if peer_id not in self._peers:
                is_new = True
                _log(f"Discovered new peer: {peer_id} at {address}")
            self._peers[peer_id] = {
                "address": address,
                "last_seen": time.time(),
                "online": True,
            }
        self._save()
        return is_new

    def mark_offline(self, peer_id: str):
        with self._lock:
            if peer_id in self._peers:
                self._peers[peer_id]["online"] = False

    def get_online_peers(self) -> dict[str, str]:
        """Return {peer_id: address} for all online peers."""
        with self._lock:
            return {
                pid: info["address"]
                for pid, info in self._peers.items()
                if info["online"]
            }

    def get_all_peers(self) -> dict[str, dict]:
        """Return all peers with status."""
        with self._lock:
            return {
                pid: {
                    "address": info["address"],
                    "online": info["online"],
                    "last_seen": info["last_seen"],
                }
                for pid, info in self._peers.items()
            }

    def get_peers_for_exchange(self, exclude: str = "") -> dict[str, str]:
        """Return {peer_id: address} for gossip exchange, excluding a target peer."""
        result = {self.own_id: self.own_address}
        with self._lock:
            for pid, info in self._peers.items():
                if pid != exclude:
                    result[pid] = info["address"]
        return result


# ---------------------------------------------------------------------------
# Gossip Loop
# ---------------------------------------------------------------------------

def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sys.stdout.write(f"[{ts}] {msg}\n")
    sys.stdout.flush()


def gossip_loop(peer_manager: PeerManager, interval: int = 30):
    """Periodically exchange peer lists with all known online peers."""
    while True:
        time.sleep(interval)
        online = peer_manager.get_online_peers()
        if not online:
            continue

        for peer_id, address in online.items():
            try:
                our_peers = peer_manager.get_peers_for_exchange(exclude=peer_id)
                payload = json.dumps({"peers": our_peers}).encode("utf-8")
                req = Request(
                    f"http://{address}/exchange",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read())
                        for rid, raddr in data.get("peers", {}).items():
                            peer_manager.add_peer(rid, raddr)
            except Exception:
                peer_manager.mark_offline(peer_id)


def bootstrap_peers(peer_manager: PeerManager, addresses: list[str]):
    """Connect to bootstrap peers: discover their IDs, add them."""
    for addr in addresses:
        try:
            req = Request(f"http://{addr}/id", method="GET")
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                pid = data.get("peer_id")
                if pid:
                    peer_manager.add_peer(pid, addr)
                    _log(f"Bootstrap: connected to {pid} at {addr}")
        except Exception as e:
            _log(f"Bootstrap: failed to reach {addr} ({e})")


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class BotMatcherHandler(BaseHTTPRequestHandler):
    """Handle all Bot-Matcher HTTP requests."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/id":
            self._json_response(200, {"peer_id": self.server.peer_id})

        elif path == "/health":
            inbox_dir = self.server.data_dir / "inbox"
            inbox_count = len(list(inbox_dir.glob("*.md"))) if inbox_dir.exists() else 0
            all_peers = self.server.peer_manager.get_all_peers()
            self._json_response(200, {
                "status": "ok",
                "peer_id": self.server.peer_id,
                "uptime": int(time.time() - self.server.start_time),
                "inbox_count": inbox_count,
                "peers_total": len(all_peers),
                "peers_online": sum(1 for p in all_peers.values() if p["online"]),
            })

        elif path == "/peers":
            all_peers = self.server.peer_manager.get_all_peers()
            self._json_response(200, {"peers": all_peers})

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

        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/card":
            self._handle_card()
        elif path == "/message":
            self._handle_message()
        elif path == "/exchange":
            self._handle_exchange()
        else:
            self._json_response(404, {"error": "not found"})

    def _handle_exchange(self):
        """Gossip: receive peer list, merge with ours, return ours."""
        try:
            body = self._read_body()
            remote_peers = body.get("peers", {})

            # Add all remote peers to our registry
            for pid, addr in remote_peers.items():
                self.server.peer_manager.add_peer(pid, addr)

            # Return our peers (excluding the sender if we can identify them)
            # We return all since we don't know the sender's ID from the request
            our_peers = self.server.peer_manager.get_peers_for_exchange()
            self._json_response(200, {"peers": our_peers})
        except (json.JSONDecodeError, ValueError) as e:
            self._json_response(400, {"error": str(e)})

    def _handle_card(self):
        """Receive a peer's Profile A (markdown), save to inbox, return own Profile A."""
        try:
            body = self._read_body()
            peer_id = body.get("peer_id")
            profile = body.get("profile")
            sender_address = body.get("address")  # optional: for auto-discovery
            if not peer_id:
                self._json_response(400, {"error": "missing peer_id"})
                return
            if not profile:
                self._json_response(400, {"error": "missing profile (markdown content)"})
                return

            # Auto-discover sender if address provided
            if sender_address:
                self.server.peer_manager.add_peer(peer_id, sender_address)

            # Save to inbox as .md
            inbox_dir = self.server.data_dir / "inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            card_path = inbox_dir / f"{peer_id}.md"
            card_path.write_text(profile, encoding="utf-8")

            # Return own Profile A if available
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
            if not sender_id or content is None:
                self._json_response(400, {"error": "missing sender_id or content"})
                return

            msg_dir = self.server.data_dir / "messages"
            msg_dir.mkdir(parents=True, exist_ok=True)
            msg_file = msg_dir / f"{sender_id}.jsonl"

            entry = {
                "role": sender_id,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(msg_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            self._json_response(200, {"status": "received"})
        except (json.JSONDecodeError, ValueError) as e:
            self._json_response(400, {"error": str(e)})

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _json_response(self, code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        _log(format % args)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <data_dir> <port> <peer_id> [bootstrap_peer ...]")
        print(f"  Example: {sys.argv[0]} context-match 18800 alice")
        print(f"  Example: {sys.argv[0]} context-match 18801 bob localhost:18800")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    port = int(sys.argv[2])
    peer_id = sys.argv[3]
    bootstrap_addrs = sys.argv[4:]  # optional: host:port of known peers

    # Ensure data directories exist
    data_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("inbox", "messages", "matches", "conversations"):
        (data_dir / sub).mkdir(exist_ok=True)

    # Initialize peer manager
    own_address = f"localhost:{port}"
    peer_manager = PeerManager(peer_id, own_address, data_dir)

    # Bootstrap: connect to known peers
    if bootstrap_addrs:
        _log(f"Bootstrapping to {len(bootstrap_addrs)} peer(s)...")
        bootstrap_peers(peer_manager, bootstrap_addrs)

    # Create HTTP server
    server = HTTPServer(("0.0.0.0", port), BotMatcherHandler)
    server.peer_id = peer_id
    server.data_dir = data_dir
    server.peer_manager = peer_manager
    server.start_time = time.time()

    # Write PID file
    pid_path = data_dir / "server.pid"
    pid_path.write_text(str(os.getpid()))

    # Start gossip thread (daemon so it dies with main)
    gossip_thread = threading.Thread(
        target=gossip_loop,
        args=(peer_manager, 30),
        daemon=True,
    )
    gossip_thread.start()
    _log(f"Gossip thread started (interval=30s)")

    _log(f"Bot-Matcher server started: peer_id={peer_id} port={port} data_dir={data_dir}")
    if bootstrap_addrs:
        online = peer_manager.get_online_peers()
        _log(f"Known peers: {list(online.keys())}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Server stopped.")
    finally:
        pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
