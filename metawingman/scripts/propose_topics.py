#!/usr/bin/env python3
"""Generate evidence-bound topic proposals with a configured hosted model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.deepseek_provider import DeepSeekProvider, ProviderRequestError
from metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman_core.topic_proposer import TopicProposalError, propose_topics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("--provider", default="deepseek", help="legacy built-in adapter name")
    parser.add_argument("--provider-config", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--max-proposals", type=int, default=5)
    parser.add_argument("--max-prompt-characters", type=int, default=250_000)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument(
        "--generation-mode",
        choices=("decision_aware", "generic_direct"),
        default="decision_aware",
        help="Run the decision-aware proposer or the independent generic direct baseline.",
    )
    parser.add_argument(
        "--allow-hosted-data-transfer",
        action="store_true",
        help="Confirm that the validated landscape may be sent to the selected provider.",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.allow_hosted_data_transfer:
        print(json.dumps({
            "status": "error",
            "error": "hosted data transfer requires --allow-hosted-data-transfer",
        }, indent=2))
        return 1
    try:
        landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
        if args.provider_config:
            config = load_provider_config(args.provider_config)
            if args.model:
                config = {**config, "model": args.model}
            provider = build_provider(config)
        elif args.provider == "deepseek":
            provider = DeepSeekProvider(model=args.model)
        else:
            raise ProviderRequestError(
                "non-DeepSeek providers require --provider-config"
            )
        batch = propose_topics(
            landscape,
            provider,
            maximum_proposals=args.max_proposals,
            maximum_prompt_characters=args.max_prompt_characters,
            thinking=args.thinking,
            generation_mode=args.generation_mode,
        )
    except (OSError, json.JSONDecodeError, ProviderRequestError, TopicProposalError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    payload = json.dumps(batch, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if batch["status"] == "proposals_generated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
