#!/usr/bin/env python3
"""Alias for resolve.py — resolves a claw's identity from the ERC-8004 registry.

This file exists because LLMs sometimes call "query.py" instead of "resolve.py".
It simply delegates all arguments to resolve.py.

Usage (identical to resolve.py):
  python3 query.py <agent_id> [--network sepolia]
"""

import runpy
import sys
from pathlib import Path

# Run resolve.py with the same arguments
resolve_path = Path(__file__).parent / "resolve.py"
if not resolve_path.exists():
    print(f"ERROR: resolve.py not found at {resolve_path}", file=sys.stderr)
    sys.exit(1)

sys.argv[0] = str(resolve_path)
runpy.run_path(str(resolve_path), run_name="__main__")
