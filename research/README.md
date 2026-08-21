# Research assets

This directory stores public, versioned inputs needed to reproduce MetaWingman
development decisions. It does not store licensed full text, credentials, or
raw private review data.

## Tracked material

- review-family and topic registries;
- metadata-only training-corpus plans and frozen weak-label exports;
- benchmark material plans and reconstruction-case contracts;
- literature and architecture syntheses that support implementation decisions.

Large tracked JSON files are immutable research snapshots. Replace them only
with a new versioned file and a recorded generation/audit path; do not edit a
frozen snapshot in place.

## Local-only material

- `research/method-literature/` is reserved for fetched papers, HTML, XML, and
  extracted text. It is ignored by Git.
- `validation-output/` at the repository root is reserved for generated runs,
  figures, adapter output, logs, and local benchmark material. It is ignored by
  Git.

Keep full text outside the public repository even when it is open access. A
public manifest may record article identity, license, retrieval source, and
SHA-256 when redistribution is lawful and necessary.

## Adding a research snapshot

1. State the source, cutoff, license boundary, and generation command.
2. Split by review family where leakage matters.
3. Record hashes and weak/gold label status.
4. Run the applicable dataset and leakage audits.
5. Add a dated report under `docs/architecture/` that explains what the
   snapshot supports and does not support.
