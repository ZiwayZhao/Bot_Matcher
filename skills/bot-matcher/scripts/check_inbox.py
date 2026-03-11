#!/usr/bin/env python3
"""Check for new profiles, messages, and connection requests.

Pulls new messages from the XMTP bridge, processes them into local files,
then scans local directories for actionable items.

Usage:
  python3 check_inbox.py <data_dir>

Example:
  python3 check_inbox.py ~/.bot-matcher

Output (stdout): JSON summary of:
  - new_cards: peers who sent Profile A but haven't been evaluated yet
  - new_messages: peers with unread conversation messages
  - pending_connections: incoming connection requests awaiting acceptance
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xmtp_client import configure, get_inbox, is_bridge_running, parse_clawmatch_message


def pull_xmtp_messages(data_dir: Path) -> int:
    """Pull new messages from XMTP bridge and process into local files.

    Returns count of new messages processed.
    """
    if not is_bridge_running():
        return 0

    try:
        messages = get_inbox(clear=True)
    except Exception:
        return 0

    processed = 0
    for raw_msg in messages:
        content_str = raw_msg.get("content", "")
        sender_inbox_id = raw_msg.get("senderInboxId", "unknown")

        # Parse ClawMatch protocol message
        msg = parse_clawmatch_message(content_str)

        if msg.get("protocol") != "clawmatch":
            # Not a ClawMatch message, skip
            continue

        msg_type = msg.get("type", "")
        payload = msg.get("payload", {})
        sender_id = payload.get("sender_id", sender_inbox_id[:12])

        if msg_type == "card":
            # Profile A received — save to inbox
            profile = payload.get("profile", "")
            if profile:
                inbox_dir = data_dir / "inbox"
                inbox_dir.mkdir(parents=True, exist_ok=True)
                card_path = inbox_dir / f"{sender_id}.md"
                card_path.write_text(profile, encoding="utf-8")

                # Save peer info
                _save_peer_info(data_dir, sender_id, payload)
                processed += 1

        elif msg_type == "message":
            # Conversation/water message — append to messages/
            content = payload.get("content", "")
            msg_sub_type = payload.get("type", "conversation")
            topic = payload.get("topic")

            msg_dir = data_dir / "messages"
            msg_dir.mkdir(parents=True, exist_ok=True)
            msg_file = msg_dir / f"{sender_id}.jsonl"

            entry = {
                "role": sender_id,
                "content": content,
                "type": msg_sub_type,
                "timestamp": raw_msg.get("sentAt", datetime.now(timezone.utc).isoformat()),
            }
            if topic:
                entry["topic"] = topic

            with open(msg_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            processed += 1

        elif msg_type == "connect":
            # Connection request — update connections.json
            connections_file = data_dir / "connections.json"
            connections = {}
            if connections_file.exists():
                try:
                    connections = json.loads(connections_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass

            if sender_id not in connections:
                connections[sender_id] = {
                    "from_peer": sender_id,
                    "wallet_address": payload.get("wallet_address", ""),
                    "agent_id": payload.get("agent_id"),
                    "status": "pending",
                    "visibility": "shadow",
                    "received_at": raw_msg.get("sentAt", datetime.now(timezone.utc).isoformat()),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                connections[sender_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

            connections_file.write_text(
                json.dumps(connections, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            _save_peer_info(data_dir, sender_id, payload)
            processed += 1

        elif msg_type == "accept":
            # Connection accepted by peer — update our handshake
            hs_path = data_dir / "handshakes" / f"{sender_id}.json"
            if hs_path.exists():
                hs = json.loads(hs_path.read_text(encoding="utf-8"))
                hs["visibility"]["sideB"] = "revealed"
                hs_path.write_text(
                    json.dumps(hs, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            processed += 1

    return processed


def _save_peer_info(data_dir: Path, peer_id: str, payload: dict):
    """Save peer info (wallet_address, agent_id) to peers.json."""
    peers_path = data_dir / "peers.json"
    peers = {}
    if peers_path.exists():
        try:
            peers = json.loads(peers_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    import time
    peer_entry = peers.get(peer_id, {})
    if payload.get("wallet_address"):
        peer_entry["wallet_address"] = payload["wallet_address"]
    if payload.get("agent_id") is not None:
        peer_entry["agent_id"] = payload["agent_id"]
    peer_entry["last_seen"] = time.time()
    peers[peer_id] = peer_entry

    peers_path.write_text(json.dumps(peers, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <data_dir>")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).expanduser()
    configure(data_dir)
    inbox_dir = data_dir / "inbox"
    matches_dir = data_dir / "matches"
    messages_dir = data_dir / "messages"
    conversations_dir = data_dir / "conversations"
    connections_file = data_dir / "connections.json"

    # --- 0. Pull new messages from XMTP ---
    xmtp_pulled = pull_xmtp_messages(data_dir)

    # --- 1. New cards (in inbox but no match evaluation yet) ---
    new_cards = []
    if inbox_dir.exists():
        for card_file in sorted(inbox_dir.glob("*.md")):
            peer_id = card_file.stem
            match_file = matches_dir / f"{peer_id}.md"
            if not match_file.exists():
                content = card_file.read_text(encoding="utf-8")
                preview = content[:200] + "..." if len(content) > 200 else content
                new_cards.append({
                    "peer_id": peer_id,
                    "file": str(card_file),
                    "preview": preview,
                })

    # --- 2. New messages (received but not yet in conversation log) ---
    new_messages = []
    if messages_dir.exists():
        for msg_file in sorted(messages_dir.glob("*.jsonl")):
            peer_id = msg_file.stem
            conv_file = conversations_dir / f"{peer_id}.jsonl"

            incoming_lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
            incoming_count = len([line for line in incoming_lines if line.strip()])

            processed_count = 0
            if conv_file.exists():
                conv_lines = conv_file.read_text(encoding="utf-8").strip().split("\n")
                for line in conv_lines:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            if entry.get("role") == peer_id:
                                processed_count += 1
                        except json.JSONDecodeError:
                            pass

            unread = incoming_count - processed_count
            if unread > 0:
                latest = []
                for line in incoming_lines[processed_count:]:
                    if line.strip():
                        try:
                            latest.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                new_messages.append({
                    "peer_id": peer_id,
                    "unread_count": unread,
                    "latest": latest[-3:],
                })

    # --- 3. Pending connection requests ---
    pending_connections = []
    if connections_file.exists():
        try:
            connections = json.loads(connections_file.read_text(encoding="utf-8"))
            for peer_id, conn in connections.items():
                if conn.get("status") == "pending":
                    pending_connections.append({
                        "peer_id": peer_id,
                        "agent_id": conn.get("agent_id"),
                        "wallet_address": conn.get("wallet_address"),
                        "received_at": conn.get("received_at"),
                    })
        except (json.JSONDecodeError, KeyError):
            pass

    result = {
        "xmtp_pulled": xmtp_pulled,
        "new_cards": new_cards,
        "new_cards_count": len(new_cards),
        "new_messages": new_messages,
        "new_messages_count": len(new_messages),
        "pending_connections": pending_connections,
        "pending_connections_count": len(pending_connections),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
