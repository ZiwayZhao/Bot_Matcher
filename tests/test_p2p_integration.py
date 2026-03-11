#!/usr/bin/env python3
"""Bot_Matcher v2 — XMTP Integration Test Suite.

Five test scenarios covering the complete XMTP-based communication stack:

  Suite 1 — XMTP Bridge Mock E2E:    Full connect → card → message → accept flow
  Suite 2 — Local Data Operations:   check_inbox, check_trees, local_query, water_tree
  Suite 3 — ERC-8004 On-Chain:       Registration URI, resolve, wallet address
  Suite 4 — XMTP Client Wrapper:     send_xmtp, get_inbox, parse messages
  Suite 5 — Dual Agent Simulation:   Two agents communicating via mock bridge

Usage:
  python3 -m pytest tests/test_p2p_integration.py -v
  python3 tests/test_p2p_integration.py                  # unittest runner
  python3 tests/test_p2p_integration.py --report          # generate report
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "skills" / "bot-matcher" / "scripts"
SEND_CARD_SCRIPT = SCRIPTS_DIR / "send_card.py"
SEND_MESSAGE_SCRIPT = SCRIPTS_DIR / "send_message.py"
CHECK_INBOX_SCRIPT = SCRIPTS_DIR / "check_inbox.py"
CHECK_TREES_SCRIPT = SCRIPTS_DIR / "check_trees.py"
WATER_TREE_SCRIPT = SCRIPTS_DIR / "water_tree.py"
LOCAL_QUERY_SCRIPT = SCRIPTS_DIR / "local_query.py"
XMTP_CLIENT_SCRIPT = SCRIPTS_DIR / "xmtp_client.py"
CHAIN_DIR = SCRIPTS_DIR / "chain"

# Port range for mock bridge servers
_next_port = 13500
_port_lock = threading.Lock()


def _alloc_port() -> int:
    global _next_port
    with _port_lock:
        port = _next_port
        _next_port += 1
    return port


# ---------------------------------------------------------------------------
# Mock XMTP Bridge Server
# ---------------------------------------------------------------------------

class MockBridgeHandler(BaseHTTPRequestHandler):
    """Mock XMTP bridge that stores messages in-memory for testing."""

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {
                "status": "connected",
                "address": self.server.wallet_address,
                "inboxId": f"inbox_{self.server.wallet_address[:8]}",
                "env": "dev",
                "inbox_count": len(self.server.inbox),
                "uptime": 100,
            })
        elif self.path.startswith("/inbox"):
            clear = "clear=1" in self.path
            messages = list(self.server.inbox)
            if clear:
                self.server.inbox.clear()
            self._json(200, {"messages": messages, "count": len(messages)})
        elif self.path.startswith("/can-message"):
            self._json(200, {"address": "0x", "canMessage": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/send":
            body = self._read_body()
            to = body.get("to", "")
            content = body.get("content", "")
            msg_id = f"msg_{int(time.time() * 1000)}"

            # Store in the target bridge's inbox (via cross-reference)
            entry = {
                "id": msg_id,
                "senderInboxId": f"inbox_{self.server.wallet_address[:8]}",
                "conversationId": f"conv_{to[:8]}",
                "content": content,
                "sentAt": datetime.now(timezone.utc).isoformat(),
                "receivedAt": datetime.now(timezone.utc).isoformat(),
            }

            # Deliver to target if it's a linked bridge
            if to in self.server.linked_bridges:
                self.server.linked_bridges[to].inbox.append(entry)

            # Also store locally for verification
            self.server.sent_messages.append({"to": to, "content": content, "id": msg_id})

            self._json(200, {
                "status": "sent",
                "messageId": msg_id,
                "to": to,
                "conversationId": f"conv_{to[:8]}",
            })
        elif self.path == "/clear-inbox":
            count = len(self.server.inbox)
            self.server.inbox.clear()
            self._json(200, {"cleared": count})
        else:
            self._json(404, {"error": "not found"})

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _json(self, code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass  # Suppress log output during tests


def start_mock_bridge(wallet_address: str, port: int = None):
    """Start a mock XMTP bridge server. Returns (server, port)."""
    port = port or _alloc_port()
    server = HTTPServer(("127.0.0.1", port), MockBridgeHandler)
    server.wallet_address = wallet_address
    server.inbox = []
    server.sent_messages = []
    server.linked_bridges = {}  # wallet_address → server ref for cross-delivery
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def link_bridges(bridge_a, bridge_b):
    """Link two mock bridges so messages sent to each other are delivered."""
    bridge_a.linked_bridges[bridge_b.wallet_address] = bridge_b
    bridge_b.linked_bridges[bridge_a.wallet_address] = bridge_a


# ---------------------------------------------------------------------------
# Test Data Helpers
# ---------------------------------------------------------------------------

def make_data_dir(peer_id: str = "test_alice", wallet_address: str = "0xaaa",
                   bridge_port: int = None) -> Path:
    """Create a temporary data directory with basic config and wallet.

    If bridge_port is given, writes a bridge_port file so that
    xmtp_client.configure(data_dir) discovers the mock bridge port.
    """
    d = Path(tempfile.mkdtemp(prefix="clawmatch_test_"))
    for sub in ("inbox", "messages", "matches", "conversations", "criteria", "handshakes"):
        (d / sub).mkdir()

    # config.json
    (d / "config.json").write_text(json.dumps({
        "peer_id": peer_id,
        "status": "active",
        "language": "en",
        "network": "sepolia",
    }, indent=2))

    # wallet.json (mock)
    (d / "wallet.json").write_text(json.dumps({
        "address": wallet_address,
        "private_key": "0x" + "ab" * 32,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    # chain_identity.json (mock)
    (d / "chain_identity.json").write_text(json.dumps({
        "agent_id": 42,
        "claw_name": peer_id,
        "wallet_address": wallet_address,
        "network": "sepolia",
        "communication": "xmtp",
    }, indent=2))

    # bridge_port — for xmtp_client.configure(data_dir) auto-discovery
    if bridge_port is not None:
        (d / "bridge_port").write_text(str(bridge_port))

    # profile_public.md
    (d / "profile_public.md").write_text(
        f"# {peer_id}\n\nA friendly AI agent who loves distributed systems.\n"
    )

    # profile_private.md
    (d / "profile_private.md").write_text(
        f"# {peer_id} (Private)\n\nLoves distributed systems and hiking.\n"
    )

    return d


def cleanup_data_dir(d: Path):
    """Remove temp data directory."""
    import shutil
    shutil.rmtree(d, ignore_errors=True)


# ===========================================================================
# Suite 1 — XMTP Bridge Mock E2E
# ===========================================================================

class TestSuite1_E2E(unittest.TestCase):
    """Full E2E flow: connect → card → message → accept via mock XMTP bridges."""

    @classmethod
    def setUpClass(cls):
        cls.alice_wallet = "0xalice0000000000000000000000000000000001"
        cls.bob_wallet = "0xbob0000000000000000000000000000000000002"

        cls.bridge_a, cls.port_a = start_mock_bridge(cls.alice_wallet)
        cls.bridge_b, cls.port_b = start_mock_bridge(cls.bob_wallet)
        link_bridges(cls.bridge_a, cls.bridge_b)

        # Each data_dir gets a bridge_port file pointing to its mock bridge
        cls.alice_dir = make_data_dir("alice", cls.alice_wallet, bridge_port=cls.port_a)
        cls.bob_dir = make_data_dir("bob", cls.bob_wallet, bridge_port=cls.port_b)

    @classmethod
    def tearDownClass(cls):
        cls.bridge_a.shutdown()
        cls.bridge_b.shutdown()
        cleanup_data_dir(cls.alice_dir)
        cleanup_data_dir(cls.bob_dir)

    def _configure_for(self, data_dir):
        """Configure xmtp_client to use the bridge_port from a data_dir."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        import xmtp_client
        xmtp_client.configure(data_dir)

    def test_01_bridge_health(self):
        """Both mock bridges respond to health check."""
        for port in [self.port_a, self.port_b]:
            resp = urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
            data = json.loads(resp.read())
            self.assertEqual(data["status"], "connected")

    def test_02_send_card_via_xmtp(self):
        """Alice sends a card to Bob via XMTP."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        import xmtp_client
        xmtp_client.configure(self.alice_dir)  # reads bridge_port → port_a

        profile = (self.alice_dir / "profile_public.md").read_text()
        card_msg = xmtp_client.build_clawmatch_message("card", {
            "peer_id": "alice",
            "profile": profile,
        }, sender_id="alice")

        result = xmtp_client.send_xmtp(self.bob_wallet, card_msg)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], self.bob_wallet)

        # Verify bob received it
        self.assertEqual(len(self.bridge_b.inbox), 1)
        raw_content = self.bridge_b.inbox[0]["content"]
        parsed = xmtp_client.parse_clawmatch_message(raw_content)
        self.assertEqual(parsed["protocol"], "clawmatch")
        self.assertEqual(parsed["type"], "card")
        self.assertIn("alice", parsed["payload"]["peer_id"])

    def test_03_send_message_via_xmtp(self):
        """Alice sends a conversation message to Bob."""
        import xmtp_client
        xmtp_client.configure(self.alice_dir)

        msg = xmtp_client.build_clawmatch_message("message", {
            "content": "Hey Bob, love your profile!",
            "type": "conversation",
        }, sender_id="alice")

        result = xmtp_client.send_xmtp(self.bob_wallet, msg)
        self.assertEqual(result["status"], "sent")

    def test_04_receive_and_process_inbox(self):
        """Bob pulls messages from XMTP and processes them."""
        import xmtp_client
        xmtp_client.configure(self.bob_dir)

        # Get inbox
        messages = xmtp_client.get_inbox(clear=False)
        self.assertGreater(len(messages), 0)

        # Parse first message
        first = messages[0]
        parsed = xmtp_client.parse_clawmatch_message(first["content"])
        self.assertEqual(parsed["protocol"], "clawmatch")

    def test_05_connection_request_flow(self):
        """Alice sends connection request, Bob receives it."""
        import xmtp_client
        xmtp_client.configure(self.alice_dir)

        # Clear bob's inbox first
        self.bridge_b.inbox.clear()

        connect_msg = xmtp_client.build_clawmatch_message("connect", {
            "wallet_address": self.alice_wallet,
            "agent_id": 42,
        }, sender_id="alice")

        result = xmtp_client.send_xmtp(self.bob_wallet, connect_msg)
        self.assertEqual(result["status"], "sent")

        # Bob processes inbox
        xmtp_client.configure(self.bob_dir)
        messages = xmtp_client.get_inbox(clear=True)
        self.assertEqual(len(messages), 1)
        parsed = xmtp_client.parse_clawmatch_message(messages[0]["content"])
        self.assertEqual(parsed["type"], "connect")

    def test_06_accept_connection(self):
        """Bob accepts Alice's connection via local_query.py."""
        # Set up a pending connection in Bob's data
        connections = {
            "alice": {
                "from_peer": "alice",
                "wallet_address": self.alice_wallet,
                "agent_id": 42,
                "status": "pending",
                "visibility": "shadow",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        (self.bob_dir / "connections.json").write_text(
            json.dumps(connections, indent=2), encoding="utf-8"
        )

        # Create a handshake file
        handshake = {
            "handshakeId": "hs_alice_bob",
            "visibility": {"sideA": "revealed", "sideB": "shadow"},
            "stage": "initial",
            "bootstrap": {"seedBranches": [{"topic": "distributed systems", "state": "detected"}]},
        }
        (self.bob_dir / "handshakes" / "alice.json").write_text(
            json.dumps(handshake, indent=2), encoding="utf-8"
        )

        # Import and call accept
        sys.path.insert(0, str(SCRIPTS_DIR))
        import importlib
        import local_query
        import xmtp_client
        xmtp_client.configure(self.bob_dir)

        result = local_query.cmd_accept(self.bob_dir, "alice")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["visibility"], "revealed")

        # Verify handshake updated
        hs = json.loads((self.bob_dir / "handshakes" / "alice.json").read_text())
        self.assertEqual(hs["visibility"]["sideB"], "revealed")

    def test_07_bidirectional_messaging(self):
        """Both sides can send and receive messages."""
        import xmtp_client

        # Alice → Bob
        xmtp_client.configure(self.alice_dir)
        self.bridge_b.inbox.clear()
        msg1 = xmtp_client.build_clawmatch_message("message", {
            "content": "Round 1 from Alice",
            "type": "conversation",
        }, sender_id="alice")
        xmtp_client.send_xmtp(self.bob_wallet, msg1)
        self.assertEqual(len(self.bridge_b.inbox), 1)

        # Bob → Alice
        xmtp_client.configure(self.bob_dir)
        self.bridge_a.inbox.clear()
        msg2 = xmtp_client.build_clawmatch_message("message", {
            "content": "Reply from Bob",
            "type": "conversation",
        }, sender_id="bob")
        xmtp_client.send_xmtp(self.alice_wallet, msg2)
        self.assertEqual(len(self.bridge_a.inbox), 1)


# ===========================================================================
# Suite 2 — Local Data Operations
# ===========================================================================

class TestSuite2_LocalOps(unittest.TestCase):
    """Test local data operations: check_inbox, check_trees, local_query."""

    def setUp(self):
        self.data_dir = make_data_dir("test_local", "0xlocal123")

    def tearDown(self):
        cleanup_data_dir(self.data_dir)

    def test_01_check_inbox_empty(self):
        """check_inbox returns empty results on fresh data dir."""
        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["new_cards_count"], 0)
        self.assertEqual(data["new_messages_count"], 0)
        self.assertEqual(data["pending_connections_count"], 0)

    def test_02_check_inbox_with_cards(self):
        """check_inbox detects new cards without match evaluations."""
        # Create a card in inbox
        (self.data_dir / "inbox" / "peer_bob.md").write_text("# Bob\nLoves hiking\n")

        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["new_cards_count"], 1)
        self.assertEqual(data["new_cards"][0]["peer_id"], "peer_bob")

    def test_03_check_inbox_with_messages(self):
        """check_inbox detects unread messages."""
        msg = {"role": "peer_bob", "content": "Hello!", "type": "conversation",
               "timestamp": datetime.now(timezone.utc).isoformat()}
        msg_file = self.data_dir / "messages" / "peer_bob.jsonl"
        msg_file.write_text(json.dumps(msg) + "\n")

        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["new_messages_count"], 1)
        self.assertEqual(data["new_messages"][0]["unread_count"], 1)

    def test_04_check_inbox_with_pending_connections(self):
        """check_inbox detects pending connection requests."""
        connections = {
            "peer_bob": {
                "from_peer": "peer_bob",
                "wallet_address": "0xbob123",
                "agent_id": 99,
                "status": "pending",
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        (self.data_dir / "connections.json").write_text(json.dumps(connections))

        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["pending_connections_count"], 1)

    def test_05_check_trees_empty(self):
        """check_trees returns no notifications on fresh data."""
        result = subprocess.run(
            [sys.executable, str(CHECK_TREES_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["notification_count"], 0)

    def test_06_check_trees_wilt_warning(self):
        """check_trees detects wilting branches."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        handshake = {
            "createdAt": old_date,
            "visibility": {"sideA": "revealed", "sideB": "revealed"},
            "bootstrap": {"seedBranches": [{
                "topic": "hiking",
                "state": "explored",
                "confidence": 0.5,
                "last_interaction": old_date,
            }]},
        }
        (self.data_dir / "handshakes" / "peer_bob.json").write_text(json.dumps(handshake))

        result = subprocess.run(
            [sys.executable, str(CHECK_TREES_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertGreater(data["notification_count"], 0)
        self.assertEqual(data["notifications"][0]["type"], "wilt_warning")

    def test_07_check_trees_new_tree(self):
        """check_trees detects new trees needing watering."""
        now = datetime.now(timezone.utc).isoformat()
        handshake = {
            "createdAt": now,
            "visibility": {"sideA": "revealed", "sideB": "revealed"},
            "bootstrap": {"seedBranches": [{
                "topic": "cooking",
                "state": "detected",
                "confidence": 0.3,
            }]},
        }
        (self.data_dir / "handshakes" / "peer_charlie.json").write_text(json.dumps(handshake))

        result = subprocess.run(
            [sys.executable, str(CHECK_TREES_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertGreater(data["notification_count"], 0)
        self.assertEqual(data["notifications"][0]["type"], "new_tree")

    def test_08_check_trees_shadow_notification(self):
        """check_trees detects pending shadow trees."""
        connections = {
            "peer_eve": {
                "status": "pending",
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        (self.data_dir / "connections.json").write_text(json.dumps(connections))

        result = subprocess.run(
            [sys.executable, str(CHECK_TREES_SCRIPT), str(self.data_dir)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        found = [n for n in data["notifications"] if n["type"] == "shadow_tree"]
        self.assertEqual(len(found), 1)

    def test_09_local_query_status(self):
        """local_query status returns correct info."""
        result = subprocess.run(
            [sys.executable, str(LOCAL_QUERY_SCRIPT), str(self.data_dir), "status"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["peer_id"], "test_local")
        self.assertEqual(data["agent_id"], 42)
        self.assertEqual(data["communication"], "xmtp")

    def test_10_local_query_forest(self):
        """local_query forest lists trees correctly."""
        handshake = {
            "handshakeId": "hs_test",
            "stage": "enriched",
            "visibility": {"sideA": "revealed", "sideB": "revealed"},
            "bootstrap": {"seedBranches": [
                {"topic": "AI", "state": "resonance"},
                {"topic": "music", "state": "explored"},
            ]},
        }
        (self.data_dir / "handshakes" / "peer_dave.json").write_text(json.dumps(handshake))

        result = subprocess.run(
            [sys.executable, str(LOCAL_QUERY_SCRIPT), str(self.data_dir), "forest"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["trees"][0]["branch_count"], 2)
        self.assertIn("AI", data["trees"][0]["topics"])

    def test_11_local_query_accept(self):
        """local_query accept updates connection and handshake."""
        connections = {
            "peer_frank": {
                "from_peer": "peer_frank",
                "wallet_address": "0xfrank",
                "status": "pending",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        (self.data_dir / "connections.json").write_text(json.dumps(connections))

        handshake = {
            "visibility": {"sideA": "revealed", "sideB": "shadow"},
            "bootstrap": {"seedBranches": []},
        }
        (self.data_dir / "handshakes" / "peer_frank.json").write_text(json.dumps(handshake))

        sys.path.insert(0, str(SCRIPTS_DIR))
        import local_query
        result = local_query.cmd_accept(self.data_dir, "peer_frank")

        self.assertEqual(result["status"], "accepted")

        # Verify files updated
        conn = json.loads((self.data_dir / "connections.json").read_text())
        self.assertEqual(conn["peer_frank"]["status"], "accepted")

        hs = json.loads((self.data_dir / "handshakes" / "peer_frank.json").read_text())
        self.assertEqual(hs["visibility"]["sideB"], "revealed")


# ===========================================================================
# Suite 3 — ERC-8004 On-Chain (Unit Tests)
# ===========================================================================

class TestSuite3_ERC8004(unittest.TestCase):
    """Test ERC-8004 registration and resolve logic (no real chain calls)."""

    def test_01_build_registration_uri_xmtp(self):
        """Registration URI uses XMTP protocol, no endpoint URL."""
        sys.path.insert(0, str(CHAIN_DIR))
        from register import build_registration_uri

        uri = build_registration_uri("test_claw")
        self.assertTrue(uri.startswith("data:application/json;utf8,"))

        # Parse the JSON
        json_str = uri.split(";utf8,", 1)[1]
        reg = json.loads(json_str)

        self.assertEqual(reg["name"], "test_claw")
        self.assertEqual(len(reg["services"]), 1)
        self.assertEqual(reg["services"][0]["protocol"], "xmtp")
        self.assertNotIn("endpoint", reg["services"][0])

    def test_02_build_registration_uri_with_agent_id(self):
        """Registration URI includes agent ID reference when provided."""
        sys.path.insert(0, str(CHAIN_DIR))
        from register import build_registration_uri

        uri = build_registration_uri("test_claw", agent_id=42)
        json_str = uri.split(";utf8,", 1)[1]
        reg = json.loads(json_str)

        self.assertIn("registrations", reg)
        self.assertEqual(reg["registrations"][0]["agentId"], 42)

    def test_03_parse_agent_uri_data(self):
        """parse_agent_uri handles data: URIs correctly."""
        sys.path.insert(0, str(CHAIN_DIR))
        from resolve import parse_agent_uri

        test_data = {"name": "test", "services": [{"name": "clawmatch", "protocol": "xmtp"}]}
        uri = f"data:application/json;utf8,{json.dumps(test_data)}"

        parsed = parse_agent_uri(uri)
        self.assertEqual(parsed["name"], "test")
        self.assertEqual(parsed["services"][0]["protocol"], "xmtp")

    def test_04_parse_agent_uri_charset(self):
        """parse_agent_uri handles charset=utf-8 variant."""
        sys.path.insert(0, str(CHAIN_DIR))
        from resolve import parse_agent_uri

        test_data = {"name": "test2", "active": True}
        uri = f"data:application/json;charset=utf-8,{json.dumps(test_data)}"

        parsed = parse_agent_uri(uri)
        self.assertEqual(parsed["name"], "test2")

    def test_05_wallet_creation_and_loading(self):
        """load_or_create_wallet creates and loads wallets correctly."""
        sys.path.insert(0, str(CHAIN_DIR))
        try:
            from register import load_or_create_wallet
        except ImportError:
            self.skipTest("web3 not installed")

        d = Path(tempfile.mkdtemp())
        try:
            # First call creates wallet
            account1, is_new1 = load_or_create_wallet(d)
            self.assertTrue(is_new1)
            self.assertTrue((d / "wallet.json").exists())

            # Second call loads existing
            account2, is_new2 = load_or_create_wallet(d)
            self.assertFalse(is_new2)
            self.assertEqual(account1.address, account2.address)
        finally:
            import shutil
            shutil.rmtree(d)

    def test_06_no_endpoint_in_chain_identity(self):
        """chain_identity.json uses 'communication: xmtp' instead of endpoint."""
        d = make_data_dir()
        try:
            chain = json.loads((d / "chain_identity.json").read_text())
            self.assertEqual(chain["communication"], "xmtp")
            self.assertNotIn("endpoint", chain)
        finally:
            cleanup_data_dir(d)


# ===========================================================================
# Suite 4 — XMTP Client Wrapper
# ===========================================================================

class TestSuite4_XMTPClient(unittest.TestCase):
    """Test the xmtp_client.py wrapper functions."""

    @classmethod
    def setUpClass(cls):
        cls.bridge, cls.port = start_mock_bridge("0xclient_test")
        # Create a data_dir with bridge_port so configure() works
        cls.data_dir = make_data_dir("client_test", "0xclient_test", bridge_port=cls.port)
        sys.path.insert(0, str(SCRIPTS_DIR))
        import xmtp_client
        xmtp_client.configure(cls.data_dir)
        cls.xmtp_client = xmtp_client

    @classmethod
    def tearDownClass(cls):
        cls.bridge.shutdown()
        cleanup_data_dir(cls.data_dir)

    def test_01_is_bridge_running(self):
        """is_bridge_running returns True when bridge is up."""
        self.assertTrue(self.xmtp_client.is_bridge_running())

    def test_02_get_bridge_health(self):
        """get_bridge_health returns correct info."""
        health = self.xmtp_client.get_bridge_health()
        self.assertEqual(health["status"], "connected")
        self.assertEqual(health["address"], "0xclient_test")

    def test_03_send_xmtp(self):
        """send_xmtp sends a message and returns result."""
        result = self.xmtp_client.send_xmtp("0xtarget", {"test": "data"})
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], "0xtarget")

    def test_04_get_inbox_empty(self):
        """get_inbox returns empty list when no messages."""
        self.bridge.inbox.clear()
        messages = self.xmtp_client.get_inbox()
        self.assertEqual(len(messages), 0)

    def test_05_get_inbox_with_messages(self):
        """get_inbox returns messages after they arrive."""
        self.bridge.inbox.append({
            "id": "test_msg_1",
            "content": '{"protocol":"clawmatch","type":"test"}',
            "sentAt": datetime.now(timezone.utc).isoformat(),
            "receivedAt": datetime.now(timezone.utc).isoformat(),
        })
        messages = self.xmtp_client.get_inbox()
        self.assertEqual(len(messages), 1)

    def test_06_get_inbox_with_clear(self):
        """get_inbox with clear=True empties the inbox."""
        self.bridge.inbox.append({"id": "x", "content": "y"})
        messages = self.xmtp_client.get_inbox(clear=True)
        self.assertGreater(len(messages), 0)
        # Verify cleared
        messages2 = self.xmtp_client.get_inbox()
        self.assertEqual(len(messages2), 0)

    def test_07_clear_inbox(self):
        """clear_inbox empties the buffer."""
        self.bridge.inbox.extend([{"id": "a"}, {"id": "b"}])
        count = self.xmtp_client.clear_inbox()
        self.assertGreaterEqual(count, 2)

    def test_08_can_message(self):
        """can_message checks XMTP reachability."""
        result = self.xmtp_client.can_message("0xsomeone")
        self.assertTrue(result)

    def test_09_build_clawmatch_message(self):
        """build_clawmatch_message creates correct format."""
        msg = self.xmtp_client.build_clawmatch_message("card", {
            "profile": "# Test",
        }, sender_id="alice")

        self.assertEqual(msg["protocol"], "clawmatch")
        self.assertEqual(msg["version"], "2.0")
        self.assertEqual(msg["type"], "card")
        self.assertEqual(msg["payload"]["profile"], "# Test")
        self.assertEqual(msg["payload"]["sender_id"], "alice")

    def test_10_parse_clawmatch_message_valid(self):
        """parse_clawmatch_message handles valid ClawMatch JSON."""
        raw = json.dumps({"protocol": "clawmatch", "version": "2.0", "type": "card", "payload": {}})
        parsed = self.xmtp_client.parse_clawmatch_message(raw)
        self.assertEqual(parsed["protocol"], "clawmatch")
        self.assertEqual(parsed["type"], "card")

    def test_11_parse_clawmatch_message_plain_text(self):
        """parse_clawmatch_message wraps plain text."""
        parsed = self.xmtp_client.parse_clawmatch_message("Hello world")
        self.assertEqual(parsed["protocol"], "unknown")
        self.assertEqual(parsed["type"], "plain_text")

    def test_12_parse_clawmatch_message_empty(self):
        """parse_clawmatch_message handles empty input."""
        parsed = self.xmtp_client.parse_clawmatch_message("")
        self.assertEqual(parsed["type"], "empty")


# ===========================================================================
# Suite 5 — Dual Agent Simulation
# ===========================================================================

class TestSuite5_DualAgent(unittest.TestCase):
    """Simulate two agents communicating via mock XMTP bridges."""

    @classmethod
    def setUpClass(cls):
        cls.alice_wallet = "0xdual_alice_0000000000000000000000000001"
        cls.bob_wallet = "0xdual_bob_0000000000000000000000000000002"

        cls.bridge_a, cls.port_a = start_mock_bridge(cls.alice_wallet)
        cls.bridge_b, cls.port_b = start_mock_bridge(cls.bob_wallet)
        link_bridges(cls.bridge_a, cls.bridge_b)

        cls.alice_dir = make_data_dir("dual_alice", cls.alice_wallet, bridge_port=cls.port_a)
        cls.bob_dir = make_data_dir("dual_bob", cls.bob_wallet, bridge_port=cls.port_b)

        # Set up peer info
        (cls.alice_dir / "peers.json").write_text(json.dumps({
            "dual_bob": {"wallet_address": cls.bob_wallet, "last_seen": time.time()},
        }))
        (cls.bob_dir / "peers.json").write_text(json.dumps({
            "dual_alice": {"wallet_address": cls.alice_wallet, "last_seen": time.time()},
        }))

        sys.path.insert(0, str(SCRIPTS_DIR))

    @classmethod
    def tearDownClass(cls):
        cls.bridge_a.shutdown()
        cls.bridge_b.shutdown()
        cleanup_data_dir(cls.alice_dir)
        cleanup_data_dir(cls.bob_dir)

    def test_01_full_card_exchange(self):
        """Full card exchange: Alice sends card, Bob processes it."""
        import xmtp_client
        xmtp_client.configure(self.alice_dir)

        # Alice sends card
        profile = (self.alice_dir / "profile_public.md").read_text()
        card_msg = xmtp_client.build_clawmatch_message("card", {
            "peer_id": "dual_alice",
            "profile": profile,
            "agent_id": 42,
        }, sender_id="dual_alice")
        xmtp_client.send_xmtp(self.bob_wallet, card_msg)

        # Bob processes inbox
        xmtp_client.configure(self.bob_dir)
        from check_inbox import pull_xmtp_messages
        pulled = pull_xmtp_messages(self.bob_dir)
        self.assertGreater(pulled, 0)

        # Verify card saved in bob's inbox
        card_file = self.bob_dir / "inbox" / "dual_alice.md"
        self.assertTrue(card_file.exists())
        self.assertIn("dual_alice", card_file.read_text())

    def test_02_full_connection_flow(self):
        """Full connection: request → accept → revealed."""
        import xmtp_client

        # Clear inboxes
        self.bridge_a.inbox.clear()
        self.bridge_b.inbox.clear()

        # Alice sends connection request
        xmtp_client.configure(self.alice_dir)
        connect_msg = xmtp_client.build_clawmatch_message("connect", {
            "wallet_address": self.alice_wallet,
            "agent_id": 42,
        }, sender_id="dual_alice")
        xmtp_client.send_xmtp(self.bob_wallet, connect_msg)

        # Bob processes
        xmtp_client.configure(self.bob_dir)
        from check_inbox import pull_xmtp_messages
        pull_xmtp_messages(self.bob_dir)

        # Verify connection pending
        connections = json.loads((self.bob_dir / "connections.json").read_text())
        self.assertIn("dual_alice", connections)
        self.assertEqual(connections["dual_alice"]["status"], "pending")

        # Bob creates handshake and accepts
        handshake = {
            "handshakeId": "hs_dual_test",
            "visibility": {"sideA": "revealed", "sideB": "shadow"},
            "bootstrap": {"seedBranches": [{"topic": "AI", "state": "detected"}]},
        }
        (self.bob_dir / "handshakes" / "dual_alice.json").write_text(json.dumps(handshake))

        import local_query
        result = local_query.cmd_accept(self.bob_dir, "dual_alice")
        self.assertEqual(result["status"], "accepted")

        # Verify handshake revealed
        hs = json.loads((self.bob_dir / "handshakes" / "dual_alice.json").read_text())
        self.assertEqual(hs["visibility"]["sideB"], "revealed")

    def test_03_water_tree_prerequisites(self):
        """water_tree checks prerequisites correctly."""
        import water_tree

        # No handshake → fail
        result = water_tree.water_tree(self.alice_dir, "nonexistent", "AI", "test")
        self.assertFalse(result["watered"])
        self.assertIn("No handshake", result["error"])

    def test_04_water_tree_with_mock_bridge(self):
        """water_tree sends via XMTP and updates handshake."""
        import xmtp_client
        import water_tree
        xmtp_client.configure(self.alice_dir)

        # Set up handshake with revealed visibility
        handshake = {
            "handshakeId": "hs_water_test",
            "visibility": {"sideA": "revealed", "sideB": "revealed"},
            "bootstrap": {"seedBranches": [{
                "seedId": "seed_1",
                "topic": "hiking",
                "state": "detected",
                "confidence": 0.3,
                "evidence": [],
                "dialogueSeed": [],
            }]},
        }
        (self.alice_dir / "handshakes" / "dual_bob.json").write_text(json.dumps(handshake))

        result = water_tree.water_tree(
            self.alice_dir, "dual_bob", "hiking", "Tell me about your hiking adventures!"
        )
        self.assertTrue(result["watered"])
        self.assertEqual(result["branch_state"], "explored")
        self.assertGreater(result["branch_confidence"], 0.3)

        # Verify handshake updated
        hs = json.loads((self.alice_dir / "handshakes" / "dual_bob.json").read_text())
        branch = hs["bootstrap"]["seedBranches"][0]
        self.assertEqual(branch["state"], "explored")

    def test_05_concurrent_messaging(self):
        """Multiple concurrent messages don't corrupt data."""
        import xmtp_client
        xmtp_client.configure(self.alice_dir)
        self.bridge_b.inbox.clear()

        def send_msg(n):
            msg = xmtp_client.build_clawmatch_message("message", {
                "content": f"Concurrent message {n}",
                "type": "conversation",
            }, sender_id="dual_alice")
            return xmtp_client.send_xmtp(self.bob_wallet, msg)

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(send_msg, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # All should succeed
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertEqual(r["status"], "sent")

        # Bob received all
        self.assertEqual(len(self.bridge_b.inbox), 10)

    def test_06_message_type_routing(self):
        """Different message types are routed correctly."""
        import xmtp_client
        xmtp_client.configure(self.alice_dir)
        self.bridge_b.inbox.clear()

        # Send different types
        types = [
            ("card", {"peer_id": "alice", "profile": "# Test"}),
            ("message", {"content": "hello", "type": "conversation"}),
            ("message", {"content": "water!", "type": "water", "topic": "hiking"}),
            ("connect", {"wallet_address": "0xalice", "agent_id": 1}),
        ]

        for msg_type, payload in types:
            msg = xmtp_client.build_clawmatch_message(msg_type, payload, sender_id="alice")
            xmtp_client.send_xmtp(self.bob_wallet, msg)

        self.assertEqual(len(self.bridge_b.inbox), 4)

        # Process and verify routing
        xmtp_client.configure(self.bob_dir)
        from check_inbox import pull_xmtp_messages
        pulled = pull_xmtp_messages(self.bob_dir)
        self.assertEqual(pulled, 4)

    def test_07_find_or_create_branch(self):
        """water_tree find_or_create_branch works correctly."""
        import water_tree

        handshake = {
            "bootstrap": {"seedBranches": [
                {"seedId": "s1", "topic": "hiking", "state": "detected"},
                {"seedId": "s2", "topic": "cooking", "state": "explored"},
            ]}
        }

        # Exact match
        branch, is_new = water_tree.find_or_create_branch(handshake, "hiking")
        self.assertFalse(is_new)
        self.assertEqual(branch["seedId"], "s1")

        # Case-insensitive match
        branch, is_new = water_tree.find_or_create_branch(handshake, "HIKING")
        self.assertFalse(is_new)

        # Substring match
        branch, is_new = water_tree.find_or_create_branch(handshake, "mountain hiking")
        self.assertFalse(is_new)

        # No match → new branch
        branch, is_new = water_tree.find_or_create_branch(handshake, "quantum physics")
        self.assertTrue(is_new)
        self.assertEqual(branch["topic"], "quantum physics")


# ===========================================================================
# Runner
# ===========================================================================

def run_all_tests(report: bool = False):
    """Run all test suites."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSuite1_E2E))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite2_LocalOps))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite3_ERC8004))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite4_XMTPClient))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite5_DualAgent))

    if report:
        report_path = PROJECT_ROOT / "tests" / "test_report.txt"
        with open(report_path, "w") as f:
            runner = unittest.TextTestRunner(stream=f, verbosity=2)
            result = runner.run(suite)
        print(f"\nReport saved to: {report_path}")
        # Also print summary to stdout
        print(f"Tests: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}")
    else:
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

    return result


if __name__ == "__main__":
    report_mode = "--report" in sys.argv
    result = run_all_tests(report=report_mode)
    sys.exit(0 if result.wasSuccessful() else 1)
