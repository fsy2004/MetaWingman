# MetaWingman status

Last reviewed: 2026-08-21

MetaWingman is under active development. The canonical Skill, schemas, Python
entry points, deterministic R toolkit, generated agent bundle, and Codex plugin
are maintained in this repository.

## Current evidence

- Interface, schema, bundle, dependency, and R-adapter regression suites are
  executable locally and in the documented server environment.
- The latest locked question–method evaluation completed 225 AI-only runs over
  development, calibration, and held-out splits. It supports a bounded
  capability-enablement signal, not end-to-end review efficacy. See the
  [R5 feasibility report](architecture/question-synthesis-r5-feasibility-report-2026-08-21.md).
- A section-role component reproduced weak labels accurately. After retaining
  the earlier full-pool retrieval failure, a frozen asymmetric MedCPT V4 run
  increased family-macro development Recall@10 from 0.4119 zero shot to a
  three-seed mean of 0.6836 across 2,211 families; the secondary query-micro
  result was 0.3764 to 0.6549 over 10,882 queries. This is component evidence,
  not database-search or complete-review recall. See the
  [V4 retrieval report](architecture/retrieval-v4-asymmetric-medcpt-results-2026-08-21.md).
- A real PDF page passed a `glm-4.6v` representation and anchor-verification
  pilot. This does not validate scientific interpretation of the document.

## Supported boundary

The repository implements typed review state, protocol and stage gates,
provenance, lawful acquisition planning, question–method routing, deterministic
R adapters, sealed evaluation, and bounded training entry points. A concrete
review still requires its own protocol, source access, independent decisions,
extraction verification, appraisal, analysis freeze, and accountable authors.

## Not established

The current evidence does not establish human replacement, lower workload,
clinical benefit, complete-review accuracy, false-exclusion safety, or an
independent effect of the verifier. Same-provider roles are test-time compute,
not independent scientific corroboration.

## Status maintenance

Update this file when a dated validation report changes a supported boundary.
The root README links here rather than copying every experiment. README-derived
repository metrics are maintained by `scripts/update_readme.py` and checked on
every GitHub push and pull request.
