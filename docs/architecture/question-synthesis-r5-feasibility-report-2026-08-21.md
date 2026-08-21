# Question–method co-design R5 feasibility report — 2026-08-21

## Scope

This report records a locked AI-only feasibility evaluation of MetaWingman's
question–method co-design path. It does not validate a complete systematic
review, human replacement, labor savings, or clinical benefit.

The final R5 evaluation used 15 title-level reconstruction cases from five
review families. Development, calibration, and held-out splits each contained
five cases. Five configurations ran with three preregistered orchestration
seeds per case, producing 75 locked slots per split and 225 runs in total.

All configurations used the same `deepseek-v4-flash` model target and frozen
ceilings: at most three calls, 16,000 input tokens, 4,096 output tokens per
call, zero retries, and 300 seconds wall time. The provider did not expose a
sampling seed; seeds controlled local ordering and tie-breaking only.

## Server components

Two bounded components were trained on one RTX 5090 with 32,607 MiB VRAM.

| Component | Wall time | Peak VRAM | Development result | Interpretation |
|---|---:|---:|---|---|
| Section-role classifier | 564 s | 9,085 MiB | macro-F1 0.9995 | Weak-label reconstruction only |
| Evidence retriever | 4,064 s | 14,283 MiB | Recall@10 0.0058; MRR 0.0044; P@1 0.0006 | Global retrieval failure retained as a negative result |

The retriever achieved hard-negative MRR 0.9629 and P@1 0.9341, showing that
the local contrastive objective did not transfer to global retrieval.

A real PDF page was also processed with `glm-4.6v`. Five native-text anchors
and five bounded regions passed deterministic verification. This was a
representation check, not scientific acceptance of the article.

## Five configurations

1. Direct prompting.
2. Generic visible-material retrieval with proposal–opposition–judge calls.
3. Biomedical question schema.
4. Biomedical schema plus terminology-aware retrieval and synthesis routing.
5. Full biomedical package with retrieval, document/graph state, three roles,
   source and executable gates, and abstention.

Generic retrieval and the full package were call-matched and shared the same
ceilings. They were not token-matched: the full package used 174,316 held-out
input tokens and generic retrieval used 92,075. Provider monetary cost was not
returned and was not imputed.

## Held-out results

| Configuration | Correct | Partial | Critical error | Abstain | Joint success | Family/route agreement |
|---|---:|---:|---:|---:|---:|---:|
| Direct | 0 | 0 | 15 | 0 | 0.000 | 0.000 |
| Generic retrieval | 0 | 0 | 15 | 0 | 0.000 | 0.000 |
| Biomedical schema | 0 | 0 | 15 | 0 | 0.000 | 0.000 |
| Biomedical routing | 2 | 6 | 7 | 0 | 0.133 | 0.600 |
| Full biomedical package | 2 | 5 | 2 | 6 | 0.133 | 0.533 |

For the routing-versus-schema contrast, the paired joint-success difference
was 0.133 with an exact sign-flip p value of 0.50. Family/route agreement was
0.600 higher (p=0.25). This is an observed capability-enablement signal, not
proof of routing efficacy or mechanism.

For the full-package-versus-generic contrast, the paired joint-success
difference was 0.133 (p=1.00) and family/route agreement was 0.533 higher
(p=0.125). The contrast changes retrieval, biomedical context, routing,
document state, graph context, and hard gates together; it estimates only a
bundled total-package effect.

Only five case clusters were available. Bootstrap intervals are descriptive;
the exact tests govern inference.

## Post-lock scoring audit

An independent audit found a calibration rubric linkage error and a coverage
rule that allowed method/identifier metadata to contribute to clinical concept
coverage. The corrected scorer binds rubric entries to case IDs and sealed
file hashes, validates the exact case-by-configuration-by-seed Cartesian set,
checks all downloaded file hashes and receipt identities, and excludes method
metadata from content coverage.

Eight labels changed after the initial scoring results had been inspected:
six development obesity slots changed from partial to critical error, and two
full-stack prognostic slots changed from correct to partial. One of the latter
was held out, reducing full-stack held-out joint success from 3/15 to 2/15.
No raw model output changed.

Corrected artifact SHA-256 values:

- rubric: `9d3098e39a4448368d6a340e250d1186146bf9cfb37057f0462bfd54e5a41d59`;
- score JSON: `4ea675939f8aaf537194895c3f85ceab0b4f9bc0837fad6b4317f8fce1ef00c3`;
- run-level CSV: `6f3b1166ef6d0fcda917223b689078e757bd66a60f01f19492d125639bc4f43a`;
- machine-readable eight-slot delta:
  `ca7dea255de087809c24431d3c289f4d97f04289091cbd33eaa60a73378d446a`.

Raw run artifacts, sealed references, licensed/full-text material, credentials,
and provider configuration values are not stored in this public repository.

## Next validation gate

The next study must replay dependency-complete reviews, prespecify a
false-exclusion safety endpoint, use independent human assessment, increase the
number of review-family clusters, and isolate the verifier's contribution with
a factorial or single-component ablation. Until then, MetaWingman supports a
bounded feasibility claim for question–method routing and guarded release only.
