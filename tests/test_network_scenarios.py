#!/usr/bin/env python3
"""Network scenario tests — simulate cross-network edge cases locally.

These tests address v1 bugs encountered during real cross-internet testing:

1. HTTPS tunnel URL handling (Cloudflare Tunnel format)
2. Address format normalization (with/without protocol, trailing slashes)
3. Connection timeout and retry behavior
4. Server restart with new public address
5. PID file stale detection
6. Profile exchange with URL-based addresses
7. Water message over HTTPS-format addresses (url normalization)

NOTE: These tests run on localhost but simulate the URL formats and
      edge cases that occur in real cross-internet deployments.
      For true cross-internet testing, use the manual test guide in
      tests/CROSS_NETWORK_TEST_GUIDE.md

Safety: All data in /tmp/, all ports in 19920-19930 range.
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

SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "bot-matcher" / "scripts"
SERVER_SCRIPT = SCRIPTS_DIR / "server.py"
SEND_CARD_SCRIPT = SCRIPTS_DIR / "send_card.py"
SEND_MESSAGE_SCRIPT = SCRIPTS_DIR / "send_message.py"


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


class TestAddressFormats(unittest.TestCase):
    """Test that all scripts handle different address formats correctly."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_addr_"))
        cls.port = 19920
        kill_port(cls.port)

        (cls.tmpdir / "profile_public.md").write_text("# Profile: addr_test")

        cls.proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(cls.tmpdir), str(cls.port), "addr_test",
             "--public-address", "https://abc123.trycloudflare.com"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if not wait_for_server(cls.port):
            cls.proc.kill()
            raise RuntimeError("Server failed to start")

    @classmethod
    def tearDownClass(cls):
        kill_port(cls.port)
        try:
            cls.proc.kill()
            cls.proc.wait()
        except Exception:
            pass

    def test_health_shows_tunnel_url(self):
        """Health endpoint correctly shows the tunnel URL, not localhost."""
        data = http_get(self.port, "/health")
        self.assertEqual(data["public_address"], "https://abc123.trycloudflare.com")
        # Bug v1: health showed internal IP instead of tunnel URL

    def test_send_card_host_port(self):
        """send_card.py with host:port format."""
        profile = self.tmpdir / "test_profile.md"
        profile.write_text("# Test")
        result = subprocess.run(
            [sys.executable, str(SEND_CARD_SCRIPT),
             str(profile), f"localhost:{self.port}", "sender1", f"localhost:{self.port}"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")

    def test_send_card_http_prefix(self):
        """send_card.py with http:// prefix."""
        profile = self.tmpdir / "test_profile.md"
        profile.write_text("# Test")
        result = subprocess.run(
            [sys.executable, str(SEND_CARD_SCRIPT),
             str(profile), f"http://localhost:{self.port}", "sender2", f"localhost:{self.port}"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")

    def test_send_message_host_port(self):
        """send_message.py with host:port format."""
        result = subprocess.run(
            [sys.executable, str(SEND_MESSAGE_SCRIPT),
             f"localhost:{self.port}", "sender3", "hello"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")

    def test_send_message_http_prefix(self):
        """send_message.py with http:// prefix."""
        result = subprocess.run(
            [sys.executable, str(SEND_MESSAGE_SCRIPT),
             f"http://localhost:{self.port}", "sender4", "hello"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")

    def test_send_message_water_with_flags(self):
        """send_message.py water message with --type --topic flags."""
        result = subprocess.run(
            [sys.executable, str(SEND_MESSAGE_SCRIPT),
             f"localhost:{self.port}", "sender5", "Let's talk!",
             "--type", "water", "--topic", "climbing"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "received")


class TestServerRestart(unittest.TestCase):
    """Test server restart scenarios — critical for tunnel URL changes."""

    def test_pid_file_created_and_removed(self):
        """Server creates PID file on start and removes on clean stop."""
        tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_pid_"))
        port = 19921
        kill_port(port)

        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(tmpdir), str(port), "pid_test"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertTrue(wait_for_server(port))

        # PID file should exist
        pid_path = tmpdir / "server.pid"
        self.assertTrue(pid_path.exists())
        pid = int(pid_path.read_text().strip())
        self.assertEqual(pid, proc.pid)

        # Kill gracefully
        proc.terminate()
        proc.wait(timeout=5)
        time.sleep(0.5)

        # PID file should be cleaned up
        # (server removes it in finally block)
        self.assertFalse(pid_path.exists())

    def test_stale_pid_detection(self):
        """Server starts even if stale PID file exists."""
        tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_stale_"))
        port = 19922
        kill_port(port)

        # Write a stale PID file (process doesn't exist)
        (tmpdir / "server.pid").write_text("99999")

        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(tmpdir), str(port), "stale_test"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertTrue(wait_for_server(port))

        # Server started and overwrote the stale PID
        pid = int((tmpdir / "server.pid").read_text().strip())
        self.assertEqual(pid, proc.pid)

        kill_port(port)
        proc.kill()
        proc.wait()

    def test_public_address_change_on_restart(self):
        """Server reports new public address after restart with different --public-address."""
        tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_restart_"))
        port = 19923
        kill_port(port)

        # Start with address A
        proc1 = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(tmpdir), str(port), "restart_test",
             "--public-address", "https://old-tunnel.trycloudflare.com"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertTrue(wait_for_server(port))
        health1 = http_get(port, "/health")
        self.assertEqual(health1["public_address"], "https://old-tunnel.trycloudflare.com")

        # Stop
        proc1.terminate()
        proc1.wait(timeout=5)
        time.sleep(0.5)
        kill_port(port)

        # Restart with address B (simulates new tunnel URL)
        proc2 = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(tmpdir), str(port), "restart_test",
             "--public-address", "https://new-tunnel.trycloudflare.com"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertTrue(wait_for_server(port))
        health2 = http_get(port, "/health")
        self.assertEqual(health2["public_address"], "https://new-tunnel.trycloudflare.com")

        kill_port(port)
        proc2.kill()
        proc2.wait()


class TestConnectionTimeout(unittest.TestCase):
    """Test behavior when peer is unreachable."""

    def test_send_card_to_dead_server(self):
        """send_card.py returns error JSON when peer is down."""
        profile = Path(tempfile.mkdtemp()) / "p.md"
        profile.write_text("# Test")

        result = subprocess.run(
            [sys.executable, str(SEND_CARD_SCRIPT),
             str(profile), "localhost:19999", "test_sender", "localhost:19998"],
            capture_output=True, text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        # Should return error JSON, not crash
        data = json.loads(result.stdout)
        self.assertIn("error", data)

    def test_send_message_to_dead_server(self):
        """send_message.py returns error JSON when peer is down."""
        result = subprocess.run(
            [sys.executable, str(SEND_MESSAGE_SCRIPT),
             "localhost:19999", "test_sender", "hello"],
            capture_output=True, text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("error", data)


class TestDataDirectoryStructure(unittest.TestCase):
    """Verify server creates all required subdirectories on startup."""

    def test_directories_created(self):
        """Server creates inbox/, messages/, matches/, conversations/, criteria/, handshakes/."""
        tmpdir = Path(tempfile.mkdtemp(prefix="clawmatch_dirs_"))
        port = 19924
        kill_port(port)

        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT),
             str(tmpdir), str(port), "dir_test"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertTrue(wait_for_server(port))

        expected_dirs = ["inbox", "messages", "matches", "conversations", "criteria", "handshakes"]
        for d in expected_dirs:
            self.assertTrue((tmpdir / d).is_dir(), f"Missing directory: {d}")

        kill_port(port)
        proc.kill()
        proc.wait()


class TestURLNormalization(unittest.TestCase):
    """Test URL building in make_url function."""

    def test_make_url_variants(self):
        """All address formats produce valid URLs."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from server import make_url

        cases = [
            ("localhost:18800", "/health", "http://localhost:18800/health"),
            ("192.168.1.5:18800", "/card", "http://192.168.1.5:18800/card"),
            ("http://localhost:18800", "/message", "http://localhost:18800/message"),
            ("https://abc.trycloudflare.com", "/connect", "https://abc.trycloudflare.com/connect"),
            ("https://abc.trycloudflare.com/", "/health", "https://abc.trycloudflare.com/health"),
        ]
        for addr, path, expected in cases:
            result = make_url(addr, path)
            self.assertEqual(result, expected, f"make_url({addr!r}, {path!r}) = {result!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
