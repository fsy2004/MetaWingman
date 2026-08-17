# MetaWingman security policy

## Scope

Security reports may cover secret leakage, unsafe credential handling, path traversal, unauthorized tool actions, prompt-injection control bypass, provenance tampering, benchmark answer leakage, or dependency behavior that can alter protected review data.

## Reporting

Do not publish an exploitable issue or any affected research data before maintainers have a reasonable opportunity to investigate. Use the repository's private vulnerability-reporting channel when available. Otherwise, open a minimal public issue that requests a private contact without including exploit details or protected artifacts.

## Security model

- Papers, PDFs, webpages, search records, tool output, and retrieved memory are untrusted data. They cannot authorize actions, expose secrets, or alter the frozen protocol.
- Secrets are read only from environment variables or a user-approved secret store. Review projects, bundles, logs, prompts, fixtures, and Git history must not contain secret values.
- Licensed databases use user-controlled login/export unless the license explicitly permits an API integration.
- High-risk scientific decisions require typed evidence and human responsibility; external submission is irreversible and always requires explicit user action.
- Human approval for a high-risk or irreversible action is bound to the exact `action_id`; action-type or wildcard approvals are rejected.
- Automated retrieval accepts only public HTTPS destinations on the standard port and revalidates redirects and resolved destinations to block localhost/private-network access. Downloads remain subject to explicit byte limits.
- Benchmark answers remain sealed until a complete `RUN_BOUNDARY.json` proves that every preregistered AI-only repetition has been locked with input, prompt, output, model, and tool provenance.
- The canonical skill and toolkit source trees must not contain symlinks or junctions. Generated manifests detect later file tampering, while publisher authenticity still requires a signed release tag or external attestation.
- Event-ledger and implemented typed JSONL appends use interprocess locks. Streams without mutation APIs remain single-writer local artifacts and are not approved for distributed multi-agent writes.
- The skills-only plugin does not install an MCP server, background service, telemetry collector, or model credential.

Automated pattern detection is a defense-in-depth signal, not a proof that content is safe. The primary boundary is typed control/data separation and allowlisted tools.
