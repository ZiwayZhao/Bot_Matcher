#!/usr/bin/env python3
"""Regression tests for bugs found during XMTP bridge debugging (2026-03-11).

Bug #1: streamAllMessages() missing await — SDK v5.5 returns Promise
Bug #2: dbEncryptionKey randomly generated — can't reopen DB after restart
Bug #3: chain/query.py missing — LLM hallucination of non-existent script
Bug #4: send_card.py misuse — LLM passes agent_id instead of wallet address

Run:
  python3 -m pytest tests/test_bridge_bugs.py -v
  # or directly:
  python3 tests/test_bridge_bugs.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
XMTP_DIR = SCRIPTS_DIR / "xmtp"
CHAIN_DIR = SCRIPTS_DIR / "chain"
BRIDGE_JS = XMTP_DIR / "xmtp_bridge.js"
START_BRIDGE_PY = SCRIPTS_DIR / "start_bridge.py"
SEND_CARD_PY = SCRIPTS_DIR / "send_card.py"
SKILL_MD = SCRIPTS_DIR.parent / "SKILL.md"


class TestBug1_StreamAwait:
    """Bug #1: streamAllMessages() must be awaited in XMTP SDK v5.5+.

    Without await, the stream variable holds a Promise instead of an
    AsyncStreamProxy, causing 'stream is not async iterable' error.
    All message reception is silently broken.
    """

    def test_stream_has_await(self):
        """Verify streamAllMessages() is preceded by 'await'."""
        source = BRIDGE_JS.read_text(encoding="utf-8")
        # Find all calls to streamAllMessages
        calls = re.findall(r"(.*streamAllMessages\(.*\))", source)
        assert len(calls) > 0, "No streamAllMessages() call found in bridge"
        for call in calls:
            assert "await" in call, (
                f"streamAllMessages() call missing 'await': {call.strip()}\n"
                f"SDK v5.5+ returns Promise<AsyncStreamProxy>, must be awaited."
            )


class TestBug2_PersistentDbKey:
    """Bug #2: dbEncryptionKey must be persisted to survive bridge restarts.

    Random key on every start means the old SQLCipher DB can't be opened,
    causing 'PRAGMA key or salt has incorrect value' fatal error.
    """

    def test_db_key_not_random_only(self):
        """Verify bridge code persists dbEncryptionKey to a file."""
        source = BRIDGE_JS.read_text(encoding="utf-8")
        # Must NOT have the old pattern: just random with no save
        old_pattern = re.search(
            r"const dbEncryptionKey\s*=\s*crypto\.getRandomValues",
            source,
        )
        assert old_pattern is None, (
            "dbEncryptionKey is generated randomly without persistence!\n"
            "This causes 'PRAGMA key or salt has incorrect value' on restart."
        )

    def test_db_key_file_read_write(self):
        """Verify bridge reads from and writes to a key file."""
        source = BRIDGE_JS.read_text(encoding="utf-8")
        assert "existsSync" in source, "Missing fs.existsSync check for key file"
        assert "readFileSync" in source, "Missing fs.readFileSync to load saved key"
        assert "writeFileSync" in source, "Missing fs.writeFileSync to save new key"

    def test_start_bridge_passes_data_dir(self):
        """Verify start_bridge.py passes CLAWMATCH_DATA_DIR env var."""
        source = START_BRIDGE_PY.read_text(encoding="utf-8")
        assert "CLAWMATCH_DATA_DIR" in source, (
            "start_bridge.py must pass CLAWMATCH_DATA_DIR to bridge "
            "so it knows where to persist the DB encryption key."
        )

    def test_db_key_persistence_roundtrip(self):
        """Verify key file can be written and read back correctly."""
        import secrets
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / ".xmtp_db_key"
            # Simulate first run: generate and save
            key = secrets.token_bytes(32)
            key_hex = key.hex()
            key_path.write_text(key_hex, encoding="utf-8")
            # Simulate second run: load
            loaded_hex = key_path.read_text(encoding="utf-8").strip()
            loaded_key = bytes.fromhex(loaded_hex)
            assert loaded_key == key, "Key roundtrip failed"


class TestBug3_ChainQueryAlias:
    """Bug #3: chain/query.py should exist as alias for resolve.py.

    LLMs sometimes hallucinate 'query.py' instead of 'resolve.py'.
    Having an alias prevents FileNotFoundError at runtime.
    """

    def test_query_py_exists(self):
        """Verify chain/query.py exists."""
        query_py = CHAIN_DIR / "query.py"
        assert query_py.exists(), (
            f"chain/query.py not found at {query_py}\n"
            f"LLMs may call 'query.py' instead of 'resolve.py'. "
            f"An alias script should exist."
        )

    def test_query_py_delegates_to_resolve(self):
        """Verify query.py references resolve.py."""
        query_py = CHAIN_DIR / "query.py"
        if query_py.exists():
            source = query_py.read_text(encoding="utf-8")
            assert "resolve" in source.lower(), (
                "chain/query.py does not reference resolve.py"
            )

    def test_resolve_py_exists(self):
        """Verify the canonical resolve.py exists."""
        resolve_py = CHAIN_DIR / "resolve.py"
        assert resolve_py.exists(), f"chain/resolve.py not found at {resolve_py}"


class TestBug4_SendCardUsage:
    """Bug #4: send_card.py requires wallet address as 2nd arg, not agent_id.

    LLMs incorrectly call: send_card.py ~/.bot-matcher --agent_id 1689
    Correct usage:        send_card.py ~/.bot-matcher 0x... --agent-id 1689
    """

    def test_send_card_requires_wallet_address(self):
        """Verify send_card.py validates wallet address format."""
        source = SEND_CARD_PY.read_text(encoding="utf-8")
        # The second positional arg should be peer_wallet (not agent_id)
        assert "peer_wallet" in source or "wallet" in source.lower(), (
            "send_card.py should clearly name the 2nd arg as wallet address"
        )

    def test_send_card_usage_string(self):
        """Verify usage string shows wallet address, not agent_id."""
        source = SEND_CARD_PY.read_text(encoding="utf-8")
        # Check docstring or usage shows wallet
        assert "peer_wallet_address" in source or "wallet" in source, (
            "send_card.py usage should clearly mention wallet address"
        )

    def test_skill_md_has_explicit_warning(self):
        """Verify SKILL.md warns about correct send_card.py argument order."""
        source = SKILL_MD.read_text(encoding="utf-8")
        assert "WALLET ADDRESS" in source or "wallet address" in source.lower(), (
            "SKILL.md should explicitly warn about using wallet address"
        )
        # Check for the explicit warning we added
        assert "NOT agent ID" in source or "not agent" in source.lower() or \
               "MUST be a wallet address" in source, (
            "SKILL.md should warn against passing agent_id as send_card.py 2nd arg"
        )

    def test_skill_md_has_resolve_before_send(self):
        """Verify SKILL.md shows resolve step before send_card step."""
        source = SKILL_MD.read_text(encoding="utf-8")
        resolve_pos = source.find("resolve.py")
        send_card_section = source.find("Send card (Profile A)")
        # resolve should appear before or near the send_card section
        assert resolve_pos > 0 and send_card_section > 0, (
            "SKILL.md should show both resolve.py and send_card.py steps"
        )


def run_tests():
    """Run all tests and report results."""
    import traceback

    test_classes = [
        TestBug1_StreamAwait,
        TestBug2_PersistentDbKey,
        TestBug3_ChainQueryAlias,
        TestBug4_SendCardUsage,
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        instance = cls()
        print(f"\n{'='*60}")
        print(f"  {cls.__name__}: {cls.__doc__.strip().split(chr(10))[0]}")
        print(f"{'='*60}")

        for method_name in sorted(dir(instance)):
            if not method_name.startswith("test_"):
                continue
            method = getattr(instance, method_name)
            total += 1
            try:
                method()
                passed += 1
                print(f"  ✅ {method_name}")
            except AssertionError as e:
                failed += 1
                errors.append((cls.__name__, method_name, str(e)))
                print(f"  ❌ {method_name}: {e}")
            except Exception as e:
                failed += 1
                errors.append((cls.__name__, method_name, traceback.format_exc()))
                print(f"  💥 {method_name}: {e}")

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")

    if errors:
        print("\nFailures:")
        for cls_name, method, msg in errors:
            print(f"  - {cls_name}.{method}: {msg[:200]}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
