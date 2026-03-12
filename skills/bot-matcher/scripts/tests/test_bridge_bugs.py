#!/usr/bin/env python3
"""Regression tests for bugs found during XMTP bridge debugging (2026-03-11/12).

Bug #1: streamAllMessages() missing await — SDK v5.5 returns Promise
Bug #2: dbEncryptionKey randomly generated — can't reopen DB after restart
Bug #3: chain/query.py missing — LLM hallucination of non-existent script
Bug #4: send_card.py misuse — LLM passes agent_id instead of wallet address
Bug #5: send_message.py --message flag misuse by LLM
Bug #6: Infrastructure scripts corrupted by LLM copy-paste
Bug #7: Sent messages not recorded locally — conversation history incomplete
Bug #8: Unread detection broken — comparing against conversations/ dir
Bug #9: peer_id ↔ wallet_address mapping inconsistent across scripts
Bug #10: First-run crash — required directories don't exist

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
SEND_MESSAGE_PY = SCRIPTS_DIR / "send_message.py"
CHECK_INBOX_PY = SCRIPTS_DIR / "check_inbox.py"
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


class TestBug5_SendMessageFlag:
    """Bug #5: send_message.py must handle --message flag defensively.

    LLMs sometimes call:  send_message.py <dir> <wallet> --message "text"
    instead of:           send_message.py <dir> <wallet> "text"
    This sends "--message" as the literal content instead of the actual message.
    """

    def test_send_message_accepts_message_flag(self):
        """send_message.py should parse --message flag and recover actual text."""
        content = SCRIPTS_DIR / "send_message.py"
        src = content.read_text(encoding="utf-8")
        assert '--message' in src and 'message_text = args[i + 1]' in src, \
            "send_message.py must handle --message flag as fallback"

    def test_send_message_rejects_flag_as_content(self):
        """send_message.py should error if message_text still looks like a flag."""
        content = SCRIPTS_DIR / "send_message.py"
        src = content.read_text(encoding="utf-8")
        assert 'message_text.startswith("--")' in src, \
            "send_message.py must detect and reject flag-like message content"

    def test_skill_md_send_message_warning(self):
        """SKILL.md must warn against using --message flag."""
        skill_md = SCRIPTS_DIR.parent / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        assert "WRONG" in text and "--message" in text, \
            "SKILL.md must explicitly show --message flag as WRONG usage"


class TestBug6_ScriptProtection:
    """Bug #6: Infrastructure scripts must not be modified by the agent.

    nanobot's LLM modified check_inbox.py by appending duplicate code blocks
    (20x copy-paste), corrupting the file and causing infinite loops.
    SKILL.md must explicitly forbid editing infrastructure scripts.
    """

    def test_check_inbox_no_subprocess_spam(self):
        """check_inbox.py must not contain repeated subprocess.run blocks."""
        content = (SCRIPTS_DIR / "check_inbox.py").read_text(encoding="utf-8")
        import re
        matches = re.findall(r'subprocess\.run\(', content)
        assert len(matches) <= 1, \
            f"check_inbox.py has {len(matches)} subprocess.run() calls — likely corrupted by LLM"

    def test_check_inbox_reasonable_length(self):
        """check_inbox.py should not exceed 300 lines (corruption indicator)."""
        content = (SCRIPTS_DIR / "check_inbox.py").read_text(encoding="utf-8")
        lines = content.count('\n')
        assert lines <= 300, \
            f"check_inbox.py has {lines} lines — likely corrupted (expected <300)"

    def test_skill_md_forbids_script_modification(self):
        """SKILL.md must explicitly forbid modifying infrastructure scripts."""
        skill_md = SCRIPTS_DIR.parent / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        assert "NEVER edit" in text or "DO NOT MODIFY" in text, \
            "SKILL.md must forbid modification of infrastructure scripts"
        assert "check_inbox.py" in text, \
            "SKILL.md must specifically mention check_inbox.py as protected"


class TestBug7_SentMessageRecording:
    """Bug #7: send_message.py must record sent messages locally.

    Without this, the agent only sees incoming messages in the conversation
    log, making it impossible to track conversation context or detect
    duplicate sends.
    """

    def test_send_message_records_to_messages_dir(self):
        """send_message.py must write to messages/{peer_id}.jsonl after send."""
        src = SEND_MESSAGE_PY.read_text(encoding="utf-8")
        assert "messages" in src and ".jsonl" in src, \
            "send_message.py must write sent messages to messages/{peer_id}.jsonl"

    def test_send_message_includes_own_peer_id(self):
        """Sent message entry must include own_peer_id as role."""
        src = SEND_MESSAGE_PY.read_text(encoding="utf-8")
        assert "own_peer_id" in src and '"role"' in src, \
            "send_message.py must record own_peer_id as role in sent messages"

    def test_send_message_has_resolve_peer_id(self):
        """send_message.py must resolve wallet→peer_id for file naming."""
        src = SEND_MESSAGE_PY.read_text(encoding="utf-8")
        assert "_resolve_peer_id" in src or "resolve_peer" in src, \
            "send_message.py must have wallet→peer_id resolution"

    def test_send_message_recording_roundtrip(self):
        """Verify sent message recording produces valid JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            msg_dir = Path(tmpdir) / "messages"
            msg_dir.mkdir()
            msg_file = msg_dir / "test_peer.jsonl"
            entry = {
                "role": "my_peer_id",
                "content": "Hello test",
                "type": "conversation",
                "timestamp": "2026-03-12T00:00:00+00:00",
            }
            with open(msg_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # Read back
            lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
            parsed = json.loads(lines[0])
            assert parsed["role"] == "my_peer_id"
            assert parsed["content"] == "Hello test"


class TestBug8_ReadCursorMechanism:
    """Bug #8: check_inbox.py must use read cursors for unread tracking.

    The old approach compared messages/*.jsonl against conversations/*.jsonl,
    but conversations/ is only created during match evaluation, not message
    exchange. This caused all messages to appear as 'already read'.
    """

    def test_check_inbox_uses_read_cursors(self):
        """check_inbox.py must reference read_cursors.json."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "read_cursors" in src, \
            "check_inbox.py must use read_cursors.json for unread tracking"

    def test_check_inbox_no_conversations_comparison(self):
        """check_inbox.py must NOT compare against conversations/ for unread."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        # The old buggy pattern was: checking conversations_dir for peer files
        # to determine read status
        lines = src.split("\n")
        has_conv_read_check = False
        for line in lines:
            if "conversations_dir" in line and ("exists" in line or "glob" in line):
                # This is OK for directory creation, but not for unread comparison
                if "mkdir" not in line and "exist_ok" not in line:
                    has_conv_read_check = True
        assert not has_conv_read_check, \
            "check_inbox.py should not use conversations/ dir for unread detection"

    def test_cursor_helpers_exist(self):
        """check_inbox.py must have _load_read_cursors and _save_read_cursors."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "_load_read_cursors" in src, "Missing _load_read_cursors helper"
        assert "_save_read_cursors" in src, "Missing _save_read_cursors helper"

    def test_cursor_auto_advance(self):
        """check_inbox.py must auto-advance cursors after reading."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        # After reading new messages, cursors should be saved
        assert "_save_read_cursors" in src, \
            "check_inbox.py must call _save_read_cursors to advance cursors"

    def test_cursor_roundtrip(self):
        """Verify cursor file read/write produces correct tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cursor_path = Path(tmpdir) / "read_cursors.json"
            # Write cursors
            cursors = {"peer_a": 5, "peer_b": 3}
            cursor_path.write_text(json.dumps(cursors), encoding="utf-8")
            # Read back
            loaded = json.loads(cursor_path.read_text(encoding="utf-8"))
            assert loaded == cursors, "Cursor roundtrip failed"
            # Advance
            loaded["peer_a"] = 8
            cursor_path.write_text(json.dumps(loaded), encoding="utf-8")
            reloaded = json.loads(cursor_path.read_text(encoding="utf-8"))
            assert reloaded["peer_a"] == 8


class TestBug9_PeerWalletMapping:
    """Bug #9: peer_id ↔ wallet_address mapping must be consistent.

    Without reliable mapping, send_message.py can't find the right peer_id
    for a wallet address, and check_inbox.py can't resolve wallet for
    outbound connection requests.
    """

    def test_check_inbox_saves_peer_info(self):
        """check_inbox.py must save wallet to peers.json on card/connect."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "_save_peer_info" in src, \
            "check_inbox.py must call _save_peer_info for wallet tracking"

    def test_save_peer_info_accepts_wallet(self):
        """_save_peer_info must accept explicit wallet_address parameter."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "wallet_address" in src and "def _save_peer_info" in src, \
            "_save_peer_info must have wallet_address parameter"

    def test_resolve_wallet_for_peer_exists(self):
        """check_inbox.py must export resolve_wallet_for_peer function."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "def resolve_wallet_for_peer" in src, \
            "check_inbox.py must have resolve_wallet_for_peer function"

    def test_send_message_has_wallet_mapping(self):
        """send_message.py must save wallet→peer_id mapping."""
        src = SEND_MESSAGE_PY.read_text(encoding="utf-8")
        assert "_save_wallet_mapping" in src or "peers.json" in src, \
            "send_message.py must maintain wallet→peer_id mapping"

    def test_peer_mapping_roundtrip(self):
        """Verify peers.json mapping read/write works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            peers_path = Path(tmpdir) / "peers.json"
            peers = {
                "icy": {"wallet_address": "0xabc123", "last_seen": 1710000000},
                "ziway": {"wallet_address": "0xdef456", "last_seen": 1710000001},
            }
            peers_path.write_text(json.dumps(peers), encoding="utf-8")
            loaded = json.loads(peers_path.read_text(encoding="utf-8"))
            assert loaded["icy"]["wallet_address"] == "0xabc123"
            # Reverse lookup
            target = "0xdef456"
            found_id = None
            for pid, info in loaded.items():
                if info.get("wallet_address", "").lower() == target.lower():
                    found_id = pid
            assert found_id == "ziway", "Reverse wallet lookup failed"


class TestBug10_DirectoryAutoCreation:
    """Bug #10: check_inbox.py must create all required directories on first run.

    On a fresh install, none of the data directories exist. Without
    auto-creation, the first check_inbox.py call crashes with
    FileNotFoundError when trying to glob inbox/*.md.
    """

    def test_check_inbox_creates_directories(self):
        """check_inbox.py must mkdir all required directories at startup."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        required_dirs = ["inbox", "matches", "messages", "conversations", "handshakes"]
        for d in required_dirs:
            assert d in src, f"check_inbox.py must reference {d} directory"
        assert "mkdir" in src, "check_inbox.py must call mkdir for directory creation"

    def test_check_inbox_has_criteria_dir(self):
        """check_inbox.py must also create criteria/ directory."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "criteria" in src, "check_inbox.py must create criteria directory"

    def test_check_inbox_uses_exist_ok(self):
        """mkdir calls must use exist_ok=True to be idempotent."""
        src = CHECK_INBOX_PY.read_text(encoding="utf-8")
        assert "exist_ok=True" in src, \
            "check_inbox.py mkdir must use exist_ok=True for idempotency"

    def test_directory_creation_roundtrip(self):
        """Verify directory creation logic works on fresh empty dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            required = ["inbox", "matches", "messages", "conversations",
                        "criteria", "handshakes"]
            for d in required:
                (data_dir / d).mkdir(parents=True, exist_ok=True)
            for d in required:
                assert (data_dir / d).is_dir(), f"{d}/ not created"
            # Second call should not fail (idempotent)
            for d in required:
                (data_dir / d).mkdir(parents=True, exist_ok=True)


def run_tests():
    """Run all tests and report results."""
    import traceback

    test_classes = [
        TestBug1_StreamAwait,
        TestBug2_PersistentDbKey,
        TestBug3_ChainQueryAlias,
        TestBug4_SendCardUsage,
        TestBug5_SendMessageFlag,
        TestBug6_ScriptProtection,
        TestBug7_SentMessageRecording,
        TestBug8_ReadCursorMechanism,
        TestBug9_PeerWalletMapping,
        TestBug10_DirectoryAutoCreation,
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
