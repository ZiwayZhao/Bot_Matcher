#!/usr/bin/env python3
"""Start the XMTP Bridge process.

Reads wallet.json from the data directory, sets up environment variables,
and launches the Node.js XMTP bridge. Manages the bridge lifecycle.

Usage:
  python3 start_bridge.py <data_dir> [--env ENV] [--port PORT]

Example:
  python3 start_bridge.py ~/.bot-matcher
  python3 start_bridge.py ~/.bot-matcher --env production --port 3500

Output (stdout): JSON with bridge status.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


def find_node() -> str:
    """Find a working Node.js binary (>= v20)."""
    import shutil
    for name in ("node", "nodejs"):
        path = shutil.which(name)
        if path:
            try:
                out = subprocess.check_output([path, "--version"], text=True).strip()
                major = int(out.lstrip("v").split(".")[0])
                if major >= 20:
                    return path
            except (subprocess.CalledProcessError, ValueError):
                continue
    return None


def check_npm_deps(xmtp_dir: Path) -> bool:
    """Check if npm dependencies are installed."""
    return (xmtp_dir / "node_modules").exists()


def install_npm_deps(xmtp_dir: Path, node_path: str):
    """Install npm dependencies."""
    import shutil
    npm_path = shutil.which("npm")
    if not npm_path:
        raise RuntimeError("npm not found. Install Node.js >= 20 with npm.")
    print("[Bridge] Installing npm dependencies...")
    result = subprocess.run(
        [npm_path, "install", "--production"],
        cwd=str(xmtp_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"npm install failed:\n{result.stderr}")
    print("[Bridge] Dependencies installed.")


def start_bridge(
    data_dir: Path,
    env: str = "dev",
    port: int = 3500,
) -> dict:
    """Start the XMTP bridge process."""
    data_dir = data_dir.expanduser()

    # 1. Load wallet
    wallet_path = data_dir / "wallet.json"
    if not wallet_path.exists():
        return {"error": f"No wallet.json found at {wallet_path}. Register on ERC-8004 first."}

    wallet = json.loads(wallet_path.read_text(encoding="utf-8"))
    private_key = wallet.get("private_key", "")
    if not private_key:
        return {"error": "wallet.json has no private_key"}

    # 2. Find Node.js
    node_path = find_node()
    if not node_path:
        return {"error": "Node.js >= 20 not found. Install: https://nodejs.org/"}

    # 3. Check bridge script exists
    script_dir = Path(__file__).parent
    xmtp_dir = script_dir / "xmtp"
    bridge_script = xmtp_dir / "xmtp_bridge.js"
    if not bridge_script.exists():
        return {"error": f"Bridge script not found: {bridge_script}"}

    # 4. Install deps if needed
    if not check_npm_deps(xmtp_dir):
        try:
            install_npm_deps(xmtp_dir, node_path)
        except RuntimeError as e:
            return {"error": str(e)}

    # 5. Check if bridge already running
    try:
        req = Request(f"http://127.0.0.1:{port}/health")
        with urlopen(req, timeout=3) as resp:
            health = json.loads(resp.read())
            if health.get("status") == "connected":
                return {
                    "status": "already_running",
                    "address": health.get("address"),
                    "env": health.get("env"),
                    "port": port,
                }
    except (URLError, OSError):
        pass  # Not running, continue to start

    # 6. Launch bridge process
    bridge_env = os.environ.copy()
    bridge_env["XMTP_PRIVATE_KEY"] = private_key
    bridge_env["XMTP_ENV"] = env
    bridge_env["BRIDGE_PORT"] = str(port)

    log_path = data_dir / "bridge.log"
    log_file = open(log_path, "w")

    proc = subprocess.Popen(
        [node_path, str(bridge_script)],
        cwd=str(xmtp_dir),
        env=bridge_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    # Write PID file
    pid_path = data_dir / "bridge.pid"
    pid_path.write_text(str(proc.pid))

    # 7. Wait for bridge to be ready (up to 30s)
    for attempt in range(30):
        time.sleep(1)
        if proc.poll() is not None:
            # Process exited
            log_file.close()
            log_content = log_path.read_text(encoding="utf-8")
            return {"error": f"Bridge exited with code {proc.returncode}", "log": log_content[-500:]}
        try:
            req = Request(f"http://127.0.0.1:{port}/health")
            with urlopen(req, timeout=3) as resp:
                health = json.loads(resp.read())
                if health.get("status") == "connected":
                    return {
                        "status": "started",
                        "pid": proc.pid,
                        "address": health.get("address"),
                        "inboxId": health.get("inboxId"),
                        "env": health.get("env"),
                        "port": port,
                        "log_path": str(log_path),
                    }
        except (URLError, OSError):
            continue

    return {"error": "Bridge started but did not become ready within 30 seconds", "pid": proc.pid}


def stop_bridge(data_dir: Path, port: int = 3500) -> dict:
    """Stop the running XMTP bridge."""
    data_dir = data_dir.expanduser()
    pid_path = data_dir / "bridge.pid"

    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            pid_path.unlink(missing_ok=True)
            return {"status": "stopped", "pid": pid}
        except (ProcessLookupError, ValueError):
            pid_path.unlink(missing_ok=True)
            return {"status": "not_running"}
    return {"status": "not_running"}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Start/stop XMTP bridge")
    parser.add_argument("data_dir", help="Data directory (e.g. ~/.bot-matcher)")
    parser.add_argument("--env", default="dev", choices=["dev", "production", "local"],
                        help="XMTP environment (default: dev)")
    parser.add_argument("--port", type=int, default=3500, help="Bridge HTTP port (default: 3500)")
    parser.add_argument("--stop", action="store_true", help="Stop the bridge instead of starting")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser()

    if args.stop:
        result = stop_bridge(data_dir, args.port)
    else:
        result = start_bridge(data_dir, args.env, args.port)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
