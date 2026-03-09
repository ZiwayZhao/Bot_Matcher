#!/usr/bin/env python3
"""Update a claw's service endpoint on the ERC-8004 Identity Registry.

Called when a claw starts up and its public address has changed
(e.g., new tunnel URL). Updates the on-chain registration URI
with the new endpoint.

Usage:
  python3 update_endpoint.py <data_dir> --endpoint <new_url> [--network sepolia]

Example:
  python3 update_endpoint.py ~/.bot-matcher --endpoint https://new-tunnel.trycloudflare.com

Reads chain_identity.json from data_dir to get the agent_id and wallet.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("ERROR: web3 not installed. Run: pip install web3", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from abi import IDENTITY_REGISTRY_ABI, CONTRACTS, DEFAULT_RPC
from register import build_registration_uri, load_or_create_wallet


def update_endpoint_on_chain(
    data_dir: Path,
    new_endpoint: str,
    network: str = "sepolia",
) -> dict:
    """Update the on-chain registration URI with a new endpoint."""
    # Load existing chain identity
    identity_path = data_dir / "chain_identity.json"
    if not identity_path.exists():
        raise FileNotFoundError(
            "No chain_identity.json found. Register first with register.py"
        )

    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    agent_id = identity["agent_id"]
    claw_name = identity["claw_name"]

    # Skip if endpoint hasn't changed
    if identity.get("endpoint") == new_endpoint:
        print(f"  Endpoint unchanged: {new_endpoint}")
        return identity

    contract_info = CONTRACTS[network]
    rpc_url = DEFAULT_RPC.get(network)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to {network} RPC")

    account, _ = load_or_create_wallet(data_dir)

    # Build new registration URI with updated endpoint
    new_uri = build_registration_uri(claw_name, new_endpoint, agent_id)

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_info["identity_registry"]),
        abi=IDENTITY_REGISTRY_ABI,
    )

    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.setAgentURI(agent_id, new_uri).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gas": 200_000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        }
    )

    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"  Update TX sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise RuntimeError(f"Update transaction failed: {tx_hash.hex()}")

    # Update local chain_identity.json
    identity["endpoint"] = new_endpoint
    identity["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    identity["last_update_tx"] = tx_hash.hex()
    identity_path.write_text(
        json.dumps(identity, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"  Endpoint updated: {new_endpoint}")
    return identity


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Update claw endpoint on-chain")
    parser.add_argument("data_dir", help="Bot-matcher data directory")
    parser.add_argument("--endpoint", required=True, help="New service endpoint URL")
    parser.add_argument(
        "--network",
        default="sepolia",
        choices=list(CONTRACTS.keys()),
        help="Ethereum network (default: sepolia)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser()
    print(f"[ERC-8004] Updating endpoint for claw on {args.network}...")
    try:
        result = update_endpoint_on_chain(data_dir, args.endpoint, args.network)
        print(f"\n[Done] Agent ID: {result['agent_id']}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
