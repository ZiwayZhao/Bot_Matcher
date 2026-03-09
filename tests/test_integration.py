#!/usr/bin/env python3
"""Integration test: simulate full ClawMatch v2 flow with two server instances.

Tests the complete lifecycle:
  1. Start two servers (Alice on 19910, Bob on 19911)
  2. Alice sends connection request to Bob
  3. Alice sends Profile A to Bob (card exchange)
  4. Bob receives card, check_inbox detects it
  5. Alice sends matchmaker conversation messages
  6. Bob receives messages, check_inbox detects them
  7. Bob accepts the connection (shadow → revealed)
  8. Alice waters a tree branch
  9. check_trees detects tree health notifications
  10. Cleanup: kill both servers, remove temp dirs

All data lives in /tmp/ — no touching of ~/.bot-matcher/ or real data.
All processes are tracked and killed in tearDown — no orphan processes.

Safety:
  - Uses /tmp/ temp dirs only
  - Uses high ports (19910, 19911) to avoid conflicts
  - All processes are killed in tearDownClass
  - No nanobot instances are started
  - No network calls outside localhost
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
CHECK_TREES_SCRIPT = SCRIPTS_DIR / "check_trees.py"
WATER_TREE_SCRIPT = SCRIPTS_DIR / "water_tree.py"

ALICE_PORT = 19910
BOB_PORT = 19911


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
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


def kill_port(port: int):
    subprocess.run(f"kill $(lsof -ti:{port}) 2>/dev/null", shell=True, capture_output=True)
    time.sleep(0.3)


def http_get(port: int, path: str) -> dict:
    req = Request(f"http://localhost:{port}{path}", method="GET")
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def http_post(port: int, path: str, data: dict) -> dict:
    payload = json.dumps(data).encode("utf-8")
    req = Request(
        f"http://localhost:{port}{path}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


class TestFullFlow(unittest.TestCase):
    """Simulate the complete ClawMatch v2 flow between two parties."""

    @classmethod
    def setUpClass(cls):
        """Start two server instances with temp data dirs."""
        # Clean up any leftover processes on these ports
        kill_port(ALICE_PORT)
        kill_port(BOB_PORT)

        # Create temp data dirs
        cls.alice_dir = Path(tempfile.mkdtemp(prefix="clawmatch_alice_"))
        cls.bob_dir = Path(tempfile.mkdtemp(prefix="clawmatch_bob_"))

        # Create profiles
        (cls.alice_dir / "profile_public.md").write_text(
            "# Profile: alice_claw\n> Generated: 2026-03-09\n\n"
            "## Demographics\n- Tech professional\n\n"
            "## Interests\n### Deep\n- Distributed systems\n- P2P protocols\n\n"
            "### Active\n- Rock climbing\n- Trail running\n\n"
            "## Values\n- Open source\n- Privacy\n"
        )
        (cls.bob_dir / "profile_public.md").write_text(
            "# Profile: bob_claw\n> Generated: 2026-03-09\n\n"
            "## Demographics\n- Researcher\n\n"
            "## Interests\n### Deep\n- Machine learning\n- Distributed systems\n\n"
            "### Active\n- Hiking\n- Rock climbing\n\n"
            "## Values\n- Open source\n- Collaboration\n"
        )

        # Create configs
        (cls.alice_dir / "config.json").write_text(json.dumps({
            "peer_id": "alice_claw", "port": ALICE_PORT, "status": "active"
        }))
        (cls.bob_dir / "config.json").write_text(json.dumps({
            "peer_id": "bob_claw", "port": BOB_PORT, "status": "active"
        }))

        # Start Alice's server
        cls.alice_proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(cls.alice_dir), str(ALICE_PORT), "alice_claw",
             "--public-address", f"localhost:{ALICE_PORT}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        # Start Bob's server
        cls.bob_proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(cls.bob_dir), str(BOB_PORT), "bob_claw",
             "--public-address", f"localhost:{BOB_PORT}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        # Wait for both servers
        if not wait_for_server(ALICE_PORT):
            cls._cleanup()
            raise RuntimeError("Alice's server failed to start")
        if not wait_for_server(BOB_PORT):
            cls._cleanup()
            raise RuntimeError("Bob's server failed to start")

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    @classmethod
    def _cleanup(cls):
        """Kill all server processes and clean up."""
        for proc in [cls.alice_proc, cls.bob_proc]:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
        kill_port(ALICE_PORT)
        kill_port(BOB_PORT)
        # Temp dirs are in /tmp/ and will be cleaned by OS

    def test_01_both_servers_healthy(self):
        """Both servers respond to /health."""
        alice_health = http_get(ALICE_PORT, "/health")
        self.assertEqual(alice_health["status"], "ok")
        self.assertEqual(alice_health["peer_id"], "alice_claw")

        bob_health = http_get(BOB_PORT, "/health")
        self.assertEqual(bob_health["status"], "ok")
        self.assertEqual(bob_health["peer_id"], "bob_claw")

    def test_02_alice_connects_to_bob(self):
        """Alice sends connection request to Bob → Bob has pending shadow tree."""
        result = http_post(BOB_PORT, "/connect", {
            "peer_id": "alice_claw",
            "address": f"localhost:{ALICE_PORT}",
            "agent_id": 1,
        })
        self.assertEqual(result["status"], "connection_request_received")
        self.assertEqual(result["peer_id"], "bob_claw")

        # Verify Bob has a pending connection
        conns = http_get(BOB_PORT, "/connections")
        self.assertIn("alice_claw", conns["connections"])
        self.assertEqual(conns["connections"]["alice_claw"]["status"], "pending")
        self.assertEqual(conns["connections"]["alice_claw"]["visibility"], "shadow")

    def test_03_alice_sends_card_to_bob(self):
        """Alice sends Profile A to Bob via send_card.py → Bob's inbox has it."""
        result = subprocess.run(
            [sys.executable, str(SEND_CARD_SCRIPT),
             str(self.alice_dir / "profile_public.md"),
             f"localhost:{BOB_PORT}", "alice_claw",
             f"localhost:{ALICE_PORT}"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"send_card failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "received")

        # Alice got Bob's card back
        self.assertIsNotNone(data["card"])
        self.assertEqual(data["card"]["peer_id"], "bob_claw")

        # Verify Bob's inbox has Alice's profile
        inbox_file = self.bob_dir / "inbox" / "alice_claw.md"
        self.assertTrue(inbox_file.exists())
        content = inbox_file.read_text()
        self.assertIn("Distributed systems", content)

    def test_04_bob_check_inbox_detects_card(self):
        """Bob's check_inbox.py detects Alice's new card."""
        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.bob_dir)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["new_cards_count"], 1)
        self.assertEqual(data["new_cards"][0]["peer_id"], "alice_claw")

        # Also has pending connection
        self.assertEqual(data["pending_connections_count"], 1)

    def test_05_alice_sends_matchmaker_messages(self):
        """Alice sends conversation messages to Bob."""
        messages = [
            "Hello! My human is really into distributed systems and P2P protocols.",
            "They also love rock climbing — do you think our humans would get along?",
            "What kind of research does your human do?",
        ]
        for msg in messages:
            result = subprocess.run(
                [sys.executable, str(SEND_MESSAGE_SCRIPT),
                 f"localhost:{BOB_PORT}", "alice_claw", msg],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"send_message failed: {result.stderr}")
            data = json.loads(result.stdout)
            self.assertEqual(data["status"], "received")

        # Verify messages saved on Bob's side
        msg_file = self.bob_dir / "messages" / "alice_claw.jsonl"
        self.assertTrue(msg_file.exists())
        lines = msg_file.read_text().strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_06_bob_check_inbox_detects_messages(self):
        """Bob's check_inbox.py detects unread messages."""
        result = subprocess.run(
            [sys.executable, str(CHECK_INBOX_SCRIPT), str(self.bob_dir)],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        self.assertGreaterEqual(data["new_messages_count"], 1)

    def test_07_create_handshake_and_accept(self):
        """Create handshake for Alice-Bob, then Bob accepts (shadow → revealed)."""
        # Create initial handshake on Bob's side (normally done by the agent)
        handshake = {
            "requestId": "hs_test_flow",
            "handshakeId": "handshake_alice_bob_test",
            "userAId": "alice_claw",
            "userBId": "bob_claw",
            "purpose": "friend",
            "stage": "enriched",
            "visibility": {"sideA": "revealed", "sideB": "shadow"},
            "bootstrap": {
                "mode": "seeded",
                "source": "conversation",
                "seedBranches": [
                    {
                        "seedId": "seed_1",
                        "topic": "distributed systems",
                        "parentSeedId": None,
                        "state": "explored",
                        "initiatedBy": "both",
                        "memoryTierUsed": "t1",
                        "matchDimension": "intellectual_resonance",
                        "summaryA": "Both interested in P2P",
                        "summaryB": "Shared passion for distributed systems",
                        "dialogueSeed": [
                            {"speaker": "alice_claw", "text": "My human loves P2P protocols"},
                            {"speaker": "bob_claw", "text": "Mine too! They research distributed ML"}
                        ],
                        "evidence": [{"sourceType": "chat_message", "occurredAt": "2026-03-09T00:00:00Z"}],
                        "confidence": 0.7,
                    },
                    {
                        "seedId": "seed_2",
                        "topic": "rock climbing",
                        "parentSeedId": None,
                        "state": "detected",
                        "initiatedBy": "both",
                        "memoryTierUsed": "t1",
                        "matchDimension": "emotional_alignment",
                        "summaryA": "Alice's human climbs",
                        "summaryB": "Bob's human also climbs",
                        "dialogueSeed": [],
                        "evidence": [{"sourceType": "profile_match", "occurredAt": "2026-03-09T00:00:00Z"}],
                        "confidence": 0.5,
                    },
                ],
            },
            "matchSummary": {
                "score": 8,
                "dimensionScores": {
                    "emotional_alignment": {"depth": 1, "level": "moderate"},
                    "intellectual_resonance": {"depth": 3, "level": "high"},
                    "value_compatibility": {"depth": 2, "level": "high"},
                    "growth_potential": {"depth": 1, "level": "moderate"},
                    "communication_style_fit": {"depth": 2, "level": "high"},
                },
            },
            "createdAt": "2026-03-09T00:00:00Z",
            "enrichedAt": "2026-03-09T00:30:00Z",
        }
        hs_path = self.bob_dir / "handshakes" / "alice_claw.json"
        hs_path.parent.mkdir(exist_ok=True)
        hs_path.write_text(json.dumps(handshake, indent=2))

        # Before accept: Bob sees shadow tree in forest
        forest = http_get(BOB_PORT, "/forest")
        alice_tree = [t for t in forest["trees"] if t["peer_id"] == "alice_claw"]
        self.assertEqual(len(alice_tree), 1)
        self.assertEqual(alice_tree[0]["visibility"]["sideB"], "shadow")

        # Bob accepts the connection
        result = http_post(BOB_PORT, "/accept", {"peer_id": "alice_claw"})
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["visibility"], "revealed")

        # After accept: handshake visibility updated
        hs_data = http_get(BOB_PORT, "/handshake?peer=alice_claw")
        self.assertEqual(hs_data["visibility"]["sideB"], "revealed")

        # Connection status updated
        conns = http_get(BOB_PORT, "/connections")
        self.assertEqual(conns["connections"]["alice_claw"]["status"], "accepted")
        self.assertEqual(conns["connections"]["alice_claw"]["visibility"], "revealed")

    def test_08_water_tree_branch(self):
        """Water a tree branch and verify handshake update."""
        # Also create handshake on Alice's side for watering
        alice_hs_dir = self.alice_dir / "handshakes"
        alice_hs_dir.mkdir(exist_ok=True)

        handshake = {
            "handshakeId": "handshake_alice_bob_test",
            "userAId": "alice_claw",
            "userBId": "bob_claw",
            "stage": "enriched",
            "visibility": {"sideA": "revealed", "sideB": "revealed"},
            "bootstrap": {
                "mode": "seeded",
                "source": "conversation",
                "seedBranches": [
                    {
                        "seedId": "seed_1",
                        "topic": "distributed systems",
                        "state": "explored",
                        "initiatedBy": "both",
                        "memoryTierUsed": "t1",
                        "dialogueSeed": [],
                        "evidence": [{"sourceType": "chat_message", "occurredAt": "2026-03-09T00:00:00Z"}],
                        "confidence": 0.6,
                    },
                ],
            },
            "createdAt": "2026-03-09T00:00:00Z",
            "enrichedAt": "2026-03-09T00:30:00Z",
        }
        (alice_hs_dir / "bob_claw.json").write_text(json.dumps(handshake, indent=2))

        # Alice's peers.json needs Bob's address
        peers = {"bob_claw": {"address": f"localhost:{BOB_PORT}", "last_seen": time.time()}}
        (self.alice_dir / "peers.json").write_text(json.dumps(peers))

        # Alice waters the "distributed systems" branch
        result = subprocess.run(
            [sys.executable, str(WATER_TREE_SCRIPT),
             str(self.alice_dir), "bob_claw", "distributed systems",
             "Let's dive deeper into P2P gossip protocols!"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"water_tree failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue(data["watered"])
        self.assertEqual(data["topic"], "distributed systems")
        self.assertFalse(data["is_new_branch"])

        # Verify handshake was updated
        hs = json.loads((alice_hs_dir / "bob_claw.json").read_text())
        branch = hs["bootstrap"]["seedBranches"][0]
        self.assertGreater(branch["confidence"], 0.6)
        self.assertIn("last_interaction", branch)

        # Verify the water message was received on Bob's side
        msg_file = self.bob_dir / "messages" / "alice_claw.jsonl"
        lines = msg_file.read_text().strip().split("\n")
        last_msg = json.loads(lines[-1])
        self.assertEqual(last_msg["type"], "water")
        self.assertEqual(last_msg["topic"], "distributed systems")

    def test_09_water_new_topic_creates_branch(self):
        """Watering a new topic creates a new branch."""
        result = subprocess.run(
            [sys.executable, str(WATER_TREE_SCRIPT),
             str(self.alice_dir), "bob_claw", "cooking",
             "Does your human enjoy cooking too?"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data["watered"])
        self.assertTrue(data["is_new_branch"])
        self.assertEqual(data["topic"], "cooking")

        # Verify new branch in handshake
        hs = json.loads((self.alice_dir / "handshakes" / "bob_claw.json").read_text())
        topics = [b["topic"] for b in hs["bootstrap"]["seedBranches"]]
        self.assertIn("cooking", topics)

    def test_10_check_trees_notifications(self):
        """check_trees.py generates appropriate notifications."""
        result = subprocess.run(
            [sys.executable, str(CHECK_TREES_SCRIPT), str(self.alice_dir)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("notifications", data)
        self.assertGreaterEqual(data["trees_checked"], 1)

    def test_11_forest_endpoint_complete(self):
        """Forest endpoint returns all trees with correct data."""
        forest = http_get(ALICE_PORT, "/forest")
        # Alice should not have a handshake tree (handshake is in alice_dir not loaded by server)
        # But Bob's forest should show alice's tree
        bob_forest = http_get(BOB_PORT, "/forest")
        alice_tree = [t for t in bob_forest["trees"] if t["peer_id"] == "alice_claw"]
        self.assertEqual(len(alice_tree), 1)
        self.assertEqual(alice_tree[0]["visibility"]["sideB"], "revealed")
        self.assertIn("distributed systems", alice_tree[0]["topics"])

    def test_12_water_blocked_on_shadow_tree(self):
        """Watering is blocked when tree is still shadow (not accepted)."""
        # Create a shadow handshake
        shadow_hs = {
            "visibility": {"sideA": "revealed", "sideB": "shadow"},
            "bootstrap": {"seedBranches": [{"seedId": "s1", "topic": "test"}]},
        }
        shadow_dir = self.alice_dir / "handshakes"
        (shadow_dir / "shadow_peer.json").write_text(json.dumps(shadow_hs))

        result = subprocess.run(
            [sys.executable, str(WATER_TREE_SCRIPT),
             str(self.alice_dir), "shadow_peer", "test", "hello"],
            capture_output=True, text=True,
        )
        # Should fail because sideB is shadow
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["watered"])
        self.assertIn("accept", data["error"].lower())

    def test_13_notifications_endpoint_matches_script(self):
        """Server /notifications endpoint produces same types as check_trees.py."""
        server_notifs = http_get(BOB_PORT, "/notifications")
        script_result = subprocess.run(
            [sys.executable, str(CHECK_TREES_SCRIPT), str(self.bob_dir)],
            capture_output=True, text=True,
        )
        script_notifs = json.loads(script_result.stdout)

        # Both should have same notification types
        server_types = {n["type"] for n in server_notifs["notifications"]}
        script_types = {n["type"] for n in script_notifs["notifications"]}
        self.assertEqual(server_types, script_types)


if __name__ == "__main__":
    unittest.main(verbosity=2)
