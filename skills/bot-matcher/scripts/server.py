#!/usr/bin/env python3
"""Bot-Matcher HTTP server. Python stdlib only, zero external dependencies.

Endpoints:
  GET  /id                       - Return this bot's peer_id
  GET  /health                   - Health check with uptime
  POST /card                     - Receive a Profile A (MD), return own Profile A
  POST /message                  - Receive a conversation message
  GET  /messages?peer=X&since=N  - Fetch messages from a peer since line N

Usage:
  python3 server.py <data_dir> <port> <peer_id>

Storage layout under <data_dir>:
  inbox/{peer_id}.md             - received Profile A from peers
  messages/{peer_id}.jsonl       - received conversation messages
  profile_public.md              - own Profile A (read-only, created by agent)
  server.pid                     - PID file for management
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs


class CardHandler(BaseHTTPRequestHandler):
    """Handle profile exchange and conversation HTTP requests."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/id":
            self._json_response(200, {"peer_id": self.server.peer_id})

        elif path == "/health":
            inbox_dir = self.server.data_dir / "inbox"
            inbox_count = len(list(inbox_dir.glob("*.md"))) if inbox_dir.exists() else 0
            self._json_response(200, {
                "status": "ok",
                "peer_id": self.server.peer_id,
                "uptime": int(time.time() - self.server.start_time),
                "inbox_count": inbox_count,
            })

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
        else:
            self._json_response(404, {"error": "not found"})

    def _handle_card(self):
        """Receive a peer's Profile A (markdown), save to inbox, return own Profile A."""
        try:
            body = self._read_body()
            peer_id = body.get("peer_id")
            profile = body.get("profile")
            if not peer_id:
                self._json_response(400, {"error": "missing peer_id"})
                return
            if not profile:
                self._json_response(400, {"error": "missing profile (markdown content)"})
                return

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
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys.stdout.write(f"[{ts}] {format % args}\n")
        sys.stdout.flush()


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <data_dir> <port> <peer_id>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    port = int(sys.argv[2])
    peer_id = sys.argv[3]

    # Ensure data directories exist
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "inbox").mkdir(exist_ok=True)
    (data_dir / "messages").mkdir(exist_ok=True)
    (data_dir / "matches").mkdir(exist_ok=True)
    (data_dir / "conversations").mkdir(exist_ok=True)

    server = HTTPServer(("0.0.0.0", port), CardHandler)
    server.peer_id = peer_id
    server.data_dir = data_dir
    server.start_time = time.time()

    # Write PID file
    pid_path = data_dir / "server.pid"
    pid_path.write_text(str(os.getpid()))

    print(f"Bot-Matcher server started: peer_id={peer_id} port={port} data_dir={data_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped.")
    finally:
        pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
