#!/usr/bin/env python3
"""Store, inspect, or delete a MetaWingman provider secret outside the repository."""

from __future__ import annotations

import argparse
import getpass
import json

from metawingman_core.provider_secrets import (
    DEEPSEEK_CREDENTIAL_TARGET,
    ProviderSecretError,
    delete_windows_credential,
    read_windows_credential,
    store_windows_credential,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("store", "status", "delete"))
    parser.add_argument("--provider", choices=("deepseek",), default="deepseek")
    args = parser.parse_args()
    target = DEEPSEEK_CREDENTIAL_TARGET
    try:
        if args.action == "store":
            secret = getpass.getpass("DeepSeek API key: ")
            store_windows_credential(target, secret)
            result = {"status": "stored", "provider": args.provider, "target": target}
        elif args.action == "delete":
            deleted = delete_windows_credential(target)
            result = {"status": "deleted" if deleted else "absent", "provider": args.provider, "target": target}
        else:
            present = bool(read_windows_credential(target))
            result = {"status": "configured" if present else "absent", "provider": args.provider, "target": target}
    except ProviderSecretError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
