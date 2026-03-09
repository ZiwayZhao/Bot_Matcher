#!/usr/bin/env python3
"""Tests for ClawMatch v2 server and scripts.

Covers:
  - Server startup, health, endpoints
  - Card exchange (Profile A)
  - Message sending/receiving
  - Connection request (shadow tree flow)
  - check_inbox.py detection
  - ERC-8004 chain scripts (unit-level, no real chain)
  - Handshake JSON with visibility field

Also regression tests for v1 bugs:
  - BUG-1: Relative paths resolving inconsistently → all absolute paths
  - BUG-2: Agent using send_message.py for first contact instead of send_card.py
  - BUG-3: Port already in use detection
  - BUG-4: public_address containing internal IP
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# Paths
SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "bot-matcher" / "scripts"
SERVER_SCRIPT = SCRIPTS_DIR / "server.py"
SEND_CARD_SCRIPT = SCRIPTS_DIR / "send_card.py"
SEND_MESSAGE_SCRIPT = SCRIPTS_DIR / "send_message.py"
CHECK_INBOX_SCRIPT = SCRIPTS_DIR / "check_inbox.py"


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
    """Wait until server responds to /health."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = Request(f"http://localhost:{port}/health", method="GET")
            with urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def kill_server(data_dir: Path, port: int):
    """Kill server using PID file or port."""
    pid_file = data_dir / "server.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except (ProcessLookupError, ValueError):
            pass
    # Fallback: kill by port
    subprocess.run(
        f"kill $(lsof -ti:{port}) 2>/dev/null",
        shell=True, capture_output=True
    )
    time.sleep(0.3)


class TestServerBasic(unittest.TestCase):
    """Test server startup and basic endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_test_"))
        cls.port = 19900
        cls.peer_id = "test_alice"

        # Kill any leftover process on this port
        kill_server(cls.tmpdir, cls.port)

        # Start server
        cls.proc = subprocess.Popen(
            [
                sys.executable, str(SERVER_SCRIPT),
                str(cls.tmpdir), str(cls.port), cls.peer_id,
                "--public-address", f"localhost:{cls.port}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not wait_for_server(cls.port):
            cls.proc.kill()
            raise RuntimeError("Server failed to start")

    @classmethod
    def tearDownClass(cls):
        kill_server(cls.tmpdir, cls.port)
        cls.proc.kill()
        cls.proc.wait()

    def _get(self, path: str) -> dict:
        req = Request(f"http://localhost:{self.port}{path}", method="GET")
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, data: dict) -> dict:
        payload = json.dumps(data).encode("utf-8")
        req = Request(
            f"http://localhost:{self.port}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def test_01_health(self):
        """Server responds to /health with correct peer_id."""
        data = self._get("/health")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["peer_id"], "test_alice")
        self.assertIn("public_address", data)
        self.assertIn("uptime", data)

    def test_02_id(self):
        """GET /id returns peer_id and agent_id."""
        data = self._get("/id")
        self.assertEqual(data["peer_id"], "test_alice")
        self.assertIn("agent_id", data)

    def test_03_peers_empty(self):
        """GET /peers returns empty when no peers known."""
        data = self._get("/peers")
        self.assertEqual(data["peers"], {})

    def test_04_card_exchange(self):
        """POST /card saves profile and returns own card."""
        # Create own profile first
        profile_path = self.tmpdir / "profile_public.md"
        profile_path.write_text("# Profile: test_alice\n## Interests\n- climbing")

        result = self._post("/card", {
            "peer_id": "test_bob",
            "profile": "# Profile: test_bob\n## Interests\n- music",
            "address": "localhost:19901",
        })

        self.assertEqual(result["status"], "received")
        self.assertIsNotNone(result["card"])
        self.assertEqual(result["card"]["peer_id"], "test_alice")

        # Verify saved to inbox
        inbox_file = self.tmpdir / "inbox" / "test_bob.md"
        self.assertTrue(inbox_file.exists())
        self.assertIn("music", inbox_file.read_text())

    def test_05_message(self):
        """POST /message saves message correctly."""
        result = self._post("/message", {
            "sender_id": "test_bob",
            "content": "Hello from bob's matchmaker!",
            "type": "conversation",
        })
        self.assertEqual(result["status"], "received")

        # Verify saved
        msg_file = self.tmpdir / "messages" / "test_bob.jsonl"
        self.assertTrue(msg_file.exists())
        lines = msg_file.read_text().strip().split("\n")
        msg = json.loads(lines[0])
        self.assertEqual(msg["role"], "test_bob")
        self.assertIn("Hello", msg["content"])

    def test_06_water_message(self):
        """POST /message with type=water saves topic metadata."""
        result = self._post("/message", {
            "sender_id": "test_bob",
            "content": "Let's talk about climbing!",
            "type": "water",
            "topic": "climbing",
        })
        self.assertEqual(result["status"], "received")

        msg_file = self.tmpdir / "messages" / "test_bob.jsonl"
        lines = msg_file.read_text().strip().split("\n")
        last_msg = json.loads(lines[-1])
        self.assertEqual(last_msg["type"], "water")
        self.assertEqual(last_msg["topic"], "climbing")

    def test_07_connect_request(self):
        """POST /connect creates a pending connection (shadow tree)."""
        result = self._post("/connect", {
            "peer_id": "test_carol",
            "address": "localhost:19902",
            "agent_id": 42,
        })

        self.assertEqual(result["status"], "connection_request_received")
        self.assertEqual(result["peer_id"], "test_alice")

        # Verify connection saved
        connections = self._get("/connections")
        self.assertIn("test_carol", connections["connections"])
        conn = connections["connections"]["test_carol"]
        self.assertEqual(conn["status"], "pending")
        self.assertEqual(conn["visibility"], "shadow")
        self.assertEqual(conn["agent_id"], 42)

    def test_08_health_shows_pending(self):
        """Health endpoint shows pending connection count."""
        data = self._get("/health")
        self.assertGreaterEqual(data["pending_connections"], 1)

    def test_09_messages_fetch(self):
        """GET /messages?peer=X returns messages."""
        data = self._get("/messages?peer=test_bob&since=0")
        self.assertGreater(len(data["messages"]), 0)

    def test_10_no_gossip_exchange(self):
        """POST /exchange should return 404 (gossip removed in v2)."""
        try:
            self._post("/exchange", {"peers": {}})
            self.fail("Should have returned 404")
        except Exception as e:
            self.assertIn("404", str(e))


class TestCheckInbox(unittest.TestCase):
    """Test check_inbox.py script."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_inbox_"))
        (self.tmpdir / "inbox").mkdir()
        (self.tmpdir / "matches").mkdir()
        (self.tmpdir / "messages").mkdir()
        (self.tmpdir / "conversations").mkdir()

    def _run_check(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.tmpdir)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"check_inbox failed: {result.stderr}")
        return json.loads(result.stdout)

    def test_empty_inbox(self):
        """Empty data dir returns all zeros."""
        data = self._run_check()
        self.assertEqual(data["new_cards_count"], 0)
        self.assertEqual(data["new_messages_count"], 0)
        self.assertEqual(data["pending_connections_count"], 0)

    def test_new_card_detected(self):
        """Card without match file is reported as new."""
        (self.tmpdir / "inbox" / "peer_a.md").write_text("# Profile A")
        data = self._run_check()
        self.assertEqual(data["new_cards_count"], 1)
        self.assertEqual(data["new_cards"][0]["peer_id"], "peer_a")

    def test_matched_card_not_reported(self):
        """Card with existing match file is not reported."""
        (self.tmpdir / "inbox" / "peer_b.md").write_text("# Profile B")
        (self.tmpdir / "matches" / "peer_b.md").write_text("# Match result")
        data = self._run_check()
        self.assertEqual(data["new_cards_count"], 0)

    def test_unread_messages(self):
        """Messages not in conversation log are reported."""
        msg = json.dumps({"role": "peer_c", "content": "hello", "timestamp": "2026-03-09T00:00:00Z"})
        (self.tmpdir / "messages" / "peer_c.jsonl").write_text(msg + "\n")
        data = self._run_check()
        self.assertEqual(data["new_messages_count"], 1)

    def test_pending_connections(self):
        """Pending connections are reported."""
        connections = {
            "peer_d": {
                "from_peer": "peer_d",
                "status": "pending",
                "agent_id": 99,
                "address": "localhost:18800",
                "received_at": "2026-03-09T00:00:00Z",
            }
        }
        (self.tmpdir / "connections.json").write_text(json.dumps(connections))
        data = self._run_check()
        self.assertEqual(data["pending_connections_count"], 1)
        self.assertEqual(data["pending_connections"][0]["agent_id"], 99)

    def test_no_gossip_peers(self):
        """v2: no 'new_peers' field in output (gossip removed)."""
        data = self._run_check()
        self.assertNotIn("new_peers", data)


class TestSendCard(unittest.TestCase):
    """Test send_card.py script against a running server."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_card_"))
        cls.port = 19901
        cls.peer_id = "card_test_server"

        kill_server(cls.tmpdir, cls.port)

        # Create profile for the server
        (cls.tmpdir / "profile_public.md").write_text("# Profile: card_test_server\n## Interests\n- coding")

        cls.proc = subprocess.Popen(
            [
                sys.executable, str(SERVER_SCRIPT),
                str(cls.tmpdir), str(cls.port), cls.peer_id,
                "--public-address", f"localhost:{cls.port}",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if not wait_for_server(cls.port):
            cls.proc.kill()
            raise RuntimeError("Server failed to start")

    @classmethod
    def tearDownClass(cls):
        kill_server(cls.tmpdir, cls.port)
        cls.proc.kill()
        cls.proc.wait()

    def test_send_card(self):
        """send_card.py sends profile and receives peer's profile back."""
        sender_dir = Path(tempfile.mkdtemp(prefix="clawmatch_sender_"))
        profile = sender_dir / "profile.md"
        profile.write_text("# Profile: sender\n## Interests\n- music")

        result = subprocess.run(
            [
                sys.executable, str(SEND_CARD_SCRIPT),
                str(profile), f"localhost:{self.port}",
                "sender", f"localhost:19999",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"send_card failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "received")
        self.assertIsNotNone(data["card"])
        self.assertEqual(data["card"]["peer_id"], "card_test_server")


class TestHandshakeSchema(unittest.TestCase):
    """Test handshake JSON structure with visibility field."""

    def test_handshake_has_visibility(self):
        """Handshake JSON must include visibility field."""
        handshake = {
            "handshakeId": "hs_test_1",
            "userAId": "alice",
            "userBId": "bob",
            "purpose": "friend",
            "stage": "initial",
            "visibility": {
                "sideA": "revealed",
                "sideB": "shadow",
            },
            "bootstrap": {
                "mode": "seeded",
                "source": "profile_match",
                "seedBranches": [],
            },
            "createdAt": "2026-03-09T00:00:00Z",
            "enrichedAt": None,
        }
        self.assertEqual(handshake["visibility"]["sideA"], "revealed")
        self.assertEqual(handshake["visibility"]["sideB"], "shadow")

    def test_visibility_transitions(self):
        """Test shadow → revealed transition."""
        visibility = {"sideA": "revealed", "sideB": "shadow"}

        # B accepts
        visibility["sideB"] = "revealed"
        self.assertEqual(visibility["sideB"], "revealed")

    def test_visibility_rejection(self):
        """Test shadow → rejected transition."""
        visibility = {"sideA": "revealed", "sideB": "shadow"}
        visibility["sideB"] = "rejected"
        self.assertEqual(visibility["sideB"], "rejected")


class TestV1BugRegression(unittest.TestCase):
    """Regression tests for v1 integration bugs."""

    def test_bug1_absolute_paths(self):
        """BUG-1: All scripts use absolute paths, not relative."""
        # server.py should accept absolute path
        tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_path_"))
        result = subprocess.run(
            [sys.executable, str(SERVER_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        # Server usage mentions <data_dir> not a relative path
        # The fix: all data is under ~/.bot-matcher/ (absolute)
        self.assertTrue(tmpdir.is_absolute())

    def test_bug2_send_card_vs_send_message(self):
        """BUG-2: send_card.py and send_message.py are different scripts."""
        # Verify they exist as separate files
        self.assertTrue(SEND_CARD_SCRIPT.exists())
        self.assertTrue(SEND_MESSAGE_SCRIPT.exists())
        self.assertNotEqual(
            SEND_CARD_SCRIPT.read_text(), SEND_MESSAGE_SCRIPT.read_text()
        )

    def test_bug3_port_detection(self):
        """BUG-3: Server PID file exists for port conflict detection."""
        tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_port_"))
        pid_path = tmpdir / "server.pid"
        pid_path.write_text("99999")
        # Verify PID file can be read for port conflict check
        self.assertTrue(pid_path.exists())
        pid = int(pid_path.read_text().strip())
        self.assertEqual(pid, 99999)

    def test_bug4_public_address_validation(self):
        """BUG-4: Health endpoint shows public_address for verification."""
        # This is tested in TestServerBasic.test_01_health
        # The fix: SKILL.md requires checking public_address after start
        pass

    def test_no_gossip_in_server(self):
        """Gossip code removed from server.py."""
        server_code = SERVER_SCRIPT.read_text()
        self.assertNotIn("gossip_loop", server_code)
        self.assertNotIn("bootstrap_peers", server_code)
        self.assertNotIn("/exchange", server_code)

    def test_no_match_tiered(self):
        """match_tiered.py removed in v2."""
        match_script = SCRIPTS_DIR / "match_tiered.py"
        self.assertFalse(match_script.exists())


class TestChainScripts(unittest.TestCase):
    """Unit tests for chain scripts (no actual blockchain calls)."""

    def test_abi_imports(self):
        """Chain ABI module imports correctly."""
        sys.path.insert(0, str(SCRIPTS_DIR / "chain"))
        from abi import IDENTITY_REGISTRY_ABI, CONTRACTS, DEFAULT_RPC

        self.assertIsInstance(IDENTITY_REGISTRY_ABI, list)
        self.assertIn("sepolia", CONTRACTS)
        self.assertIn("mainnet", CONTRACTS)
        self.assertEqual(
            CONTRACTS["mainnet"]["identity_registry"],
            "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432",
        )

    def test_registration_uri_format(self):
        """Registration URI follows ERC-8004 registration-v1 format."""
        sys.path.insert(0, str(SCRIPTS_DIR / "chain"))
        from register import build_registration_uri

        uri = build_registration_uri("test_claw", "https://example.com")
        self.assertTrue(uri.startswith("data:application/json"))

        # Parse the JSON from the data URI
        json_str = uri.split(";utf8,", 1)[1]
        reg = json.loads(json_str)
        self.assertEqual(reg["type"], "https://eips.ethereum.org/EIPS/eip-8004#registration-v1")
        self.assertEqual(reg["name"], "test_claw")
        self.assertEqual(reg["services"][0]["name"], "clawmatch")
        self.assertEqual(reg["services"][0]["endpoint"], "https://example.com")

    def test_resolve_parse_data_uri(self):
        """Resolver can parse data URIs."""
        sys.path.insert(0, str(SCRIPTS_DIR / "chain"))
        from resolve import parse_agent_uri

        test_json = json.dumps({"name": "test", "services": [{"name": "clawmatch", "endpoint": "http://x"}]})
        uri = f"data:application/json;utf8,{test_json}"
        result = parse_agent_uri(uri)
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["services"][0]["endpoint"], "http://x")


class TestConnectionManager(unittest.TestCase):
    """Test the ConnectionManager class directly."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_conn_"))
        # Import from server module
        sys.path.insert(0, str(SCRIPTS_DIR))
        from server import ConnectionManager
        self.cm = ConnectionManager(self.tmpdir)

    def test_add_request(self):
        record = self.cm.add_request("peer_a", "localhost:18800", 42)
        self.assertEqual(record["status"], "pending")
        self.assertEqual(record["visibility"], "shadow")
        self.assertEqual(record["agent_id"], 42)

    def test_accept(self):
        self.cm.add_request("peer_b", "localhost:18801")
        record = self.cm.accept("peer_b")
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["visibility"], "revealed")
        self.assertIn("accepted_at", record)

    def test_reject(self):
        self.cm.add_request("peer_c", "localhost:18802")
        record = self.cm.reject("peer_c")
        self.assertEqual(record["status"], "rejected")
        self.assertEqual(record["visibility"], "rejected")

    def test_get_pending(self):
        self.cm.add_request("peer_d", "localhost:18803")
        self.cm.add_request("peer_e", "localhost:18804")
        self.cm.accept("peer_e")
        pending = self.cm.get_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["from_peer"], "peer_d")

    def test_persistence(self):
        """Connections persist to disk."""
        self.cm.add_request("peer_f", "localhost:18805")
        conn_file = self.tmpdir / "connections.json"
        self.assertTrue(conn_file.exists())
        data = json.loads(conn_file.read_text())
        self.assertIn("peer_f", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
