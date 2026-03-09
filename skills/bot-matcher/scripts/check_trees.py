#!/usr/bin/env python3
"""Check tree health and generate proactive watering reminders.

Scans all handshakes and connections to produce notifications:
1. Wilt warning — branch last_interaction > 7 days
2. Resonance opportunity — branch confidence > 0.8 AND state == "resonance"
3. New tree prompt — handshake created < 3 days AND no watering
4. Shadow tree notification — pending connections

Usage:
  python3 check_trees.py <data_dir>

Output (stdout): JSON with notifications array.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


WILT_THRESHOLD_DAYS = 7
NEW_TREE_THRESHOLD_DAYS = 3
RESONANCE_CONFIDENCE = 0.8


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return {}


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # Handle both with and without timezone
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def check_trees(data_dir: Path) -> dict:
    """Check all trees and generate notifications."""
    data_dir = data_dir.expanduser()
    handshakes_dir = data_dir / "handshakes"
    now = datetime.now(timezone.utc)
    notifications = []

    # 1. Check handshakes for tree health
    if handshakes_dir.exists():
        for hs_file in handshakes_dir.glob("*.json"):
            peer_id = hs_file.stem
            hs = load_json(hs_file)

            visibility = hs.get("visibility", {})
            side_b = visibility.get("sideB", "shadow")

            # Only check revealed trees for watering reminders
            if side_b != "revealed":
                continue

            created_at = parse_iso(hs.get("createdAt"))
            last_watered = parse_iso(hs.get("lastWateredAt"))
            branches = hs.get("bootstrap", {}).get("seedBranches", [])

            # 3. New tree prompt (created < 3 days, no watering)
            if created_at and (now - created_at) < timedelta(days=NEW_TREE_THRESHOLD_DAYS):
                if not last_watered:
                    topics = [b.get("topic", "?") for b in branches[:3]]
                    notifications.append({
                        "type": "new_tree",
                        "peer_id": peer_id,
                        "priority": "medium",
                        "message": f"Your new tree with {peer_id} just sprouted. Want to start growing it?",
                        "suggested_topics": topics,
                        "created_at": hs.get("createdAt"),
                    })
                    continue  # Don't check branches on brand new trees

            # Check individual branches
            for branch in branches:
                topic = branch.get("topic", "unknown")
                state = branch.get("state", "detected")
                confidence = branch.get("confidence", 0)
                last_interaction_str = branch.get("last_interaction")
                last_interaction = parse_iso(last_interaction_str)

                # Use handshake creation time as fallback
                if not last_interaction:
                    last_interaction = created_at

                # 1. Wilt warning (> 7 days since last interaction)
                if last_interaction and (now - last_interaction) > timedelta(days=WILT_THRESHOLD_DAYS):
                    days_ago = (now - last_interaction).days
                    notifications.append({
                        "type": "wilt_warning",
                        "peer_id": peer_id,
                        "topic": topic,
                        "priority": "high",
                        "message": f"Your {topic} branch with {peer_id} is starting to wilt ({days_ago} days). Want to water it?",
                        "days_since_interaction": days_ago,
                        "branch_state": state,
                    })

                # 2. Resonance opportunity (confidence > 0.8 AND state == resonance)
                elif state == "resonance" and confidence >= RESONANCE_CONFIDENCE:
                    notifications.append({
                        "type": "resonance_opportunity",
                        "peer_id": peer_id,
                        "topic": topic,
                        "priority": "low",
                        "message": f"You and {peer_id} really click on {topic}! Want to explore deeper?",
                        "confidence": confidence,
                    })

    # 4. Shadow tree notifications (pending connections)
    connections = load_json(data_dir / "connections.json")
    for peer_id, conn in connections.items():
        if conn.get("status") == "pending":
            notifications.append({
                "type": "shadow_tree",
                "peer_id": peer_id,
                "priority": "medium",
                "message": f"A mysterious tree appeared in your forest from {peer_id}... Want to reveal it?",
                "agent_id": conn.get("agent_id"),
                "received_at": conn.get("received_at"),
            })

    # Sort: high priority first
    priority_order = {"high": 0, "medium": 1, "low": 2}
    notifications.sort(key=lambda n: priority_order.get(n.get("priority", "low"), 2))

    return {
        "notifications": notifications,
        "notification_count": len(notifications),
        "trees_checked": len(list(handshakes_dir.glob("*.json"))) if handshakes_dir.exists() else 0,
        "checked_at": now.isoformat(),
    }


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <data_dir>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    result = check_trees(data_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
