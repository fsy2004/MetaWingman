# Evidence and citation integrity

## Evidence states

Label material claims as one of:

- `verified-primary`: checked against full primary source or official record;
- `verified-secondary`: checked against a reliable secondary source, with primary source unavailable;
- `registry-only`: supported by a registry record, not a publication;
- `abstract-only`: only abstract verified; do not use for full-text-dependent fields;
- `inference`: a transparent inference from cited evidence;
- `unverified`: exclude from conclusions and bibliography until resolved.

## Reference identity gate

For every cited work, verify normalized title, first author or group, year, journal/publisher, DOI and/or PMID/PMCID/registry ID, publication type, retraction/correction status, and the exact claim supported. Store retrieval URL and date. A DOI resolving to a different title is a failure.

Maintain a claim-evidence ledger with `claim_id`, manuscript location, claim text, evidence state, reference ID, supporting location, verifier, date, and notes. One citation may support only the claims actually present in the source.

## Evidence extraction gate

Each numerical or methodological field must include a source anchor: report ID, page, section, table, figure, supplement, registry module, or author correspondence. Keep the original text or cell alongside the normalized value and transformation code.

Do not:

- merge details from separate papers into a synthetic citation;
- use a review's description as if it were the primary study result;
- infer denominator, analysis population, follow-up, adjusted covariates, event attribution, or outcome hierarchy;
- replace missing standard deviations or correlations without a prespecified, documented method and sensitivity analysis;
- treat absence of reporting as absence of an event.

## AI-specific rules

Record model/tool, version if available, date, task, input scope, operating mode, verification state, and whether content entered the final review. AI suggestions remain provisional until they pass the mode/profile decision rule. Preserve prompts or structured audit outputs when they affect decisions.

Use AI first for search-term expansion, prioritization, duplicate-candidate detection, criterion dossiers, anchored extraction, appraisal dossiers, code generation, consistency checks, and draft critique. In `assurance` mode, retain the human verification, independent decisions, signatures, and final responsibility required by the selected authority and protocol. Test replacement of a mandated human task only in a preregistered `evaluation` workflow with an explicit reference standard and error limits; declare shortcuts in `rapid` mode.
