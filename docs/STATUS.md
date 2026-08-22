# MetaWingman status

Last reviewed: 2026-08-22

MetaWingman is under active development. The canonical Skill, schemas, Python
entry points, deterministic R toolkit, generated agent bundle, and Codex plugin
are maintained in this repository.

## Current method framing

The current writing should not present MetaWingman as mainly a safety or audit
system. The original method story remains the center: a strong evidence-synthesis
agent should form a Review Question Certificate, run Socratic stage reflection,
verify conclusion-changing steps, and feed verified failures back into Skill,
prompt, verifier, and distillation updates. The paper-facing claims compress
that story into two linked contributions:

- **C1 clinical question and synthesis co-design:** question scope, review
  family, estimand, evidence availability, and synthesis route are searched
  together instead of choosing a title first and attaching a method afterward.
- **C2 source-grounded full-review operating loop:** a persistent review case
  state lets the agent reflect, retrieve, verify, recompute, and replan only
  through source or tool observations.

Decision-aware topic opportunity control and conclusion-directed risk-impact
evidence acquisition are executable policy surfaces for C1/C2. Integrity,
sealing, access, provenance, and human responsibility are guardrails and
evaluation scaffolding, not the main novelty story.

## Current evidence

The current TOPIC, REVIEW, joint-lifecycle, and distillation claim ceilings are
derived by `metawingman/scripts/audit_innovation_evidence.py` from the
[innovation evidence ledger](../research/innovation-evidence-ledger-v1.json).
The integrated mechanism, ten-stage execution, representative-case, and student
evaluation requirements are canonicalized in the
[dual-innovation full-workflow plan](architecture/dual-innovation-evidence-and-full-workflow-plan-2026-08-22.md).

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
- A frozen two-case, four-configuration, three-seed metadata/abstract
  reconstruction completed 24/24 slots under a post-lock operational-reference
  boundary. It executed protocol generation, title/abstract screening with
  free-text extraction, and free-text synthesis; it was not an end-to-end review.
  The Ag-RDT bundle mixed a 2022-update workbook and cutoff with 2021 article
  metadata and conclusion axes, so its original numbers remain only as an invalid
  version-mixing diagnostic. The suicide/self-harm case is a development result:
  its conclusion-axis prompt/reranking proxy did not beat the generic fixed
  baseline, checkpoint and review-family closure remain unresolved, and the full
  residual-risk x downstream-impact controller was not tested. The nominal topic
  arm also changed prompt wording without instantiating the intended topic
  mechanism. See the
  [two-case direct-evidence report](architecture/two-case-direct-evidence-results-2026-08-22.md).
- A representative-case registry now binds the V3 training corpus by SHA-256,
  rejects exact DOI/title overlap from held-out admission, and records
  stage-specific material readiness. The Nature Medicine heat-exposure target
  has an exact identity in the bound training plan, and the Lancet
  antidepressant target was used for method diagnosis; both are therefore
  `diagnostic_only`, leaving zero confirmatory held-out cases. Agent-trajectory
  export governance defines the intended admission boundary: registered
  development cases, `run_ready` or explicitly verified stages, source-anchored
  trajectories, independent verification, and retained failures and
  abstentions. Its frozen export additionally binds dataset, source/audit
  artifact, prompt, tool, provider/model, registry, revocation-manifest, and
  checkpoint hashes; recursive forbidden-value and provider-alias checks fail
  closed. A governed protocol-stage export now contains 19 exact JATS-methods
  demonstrations from the BMJ adult-depression exercise NMA development family.
  Three fixed-seed Qwen2.5-1.5B LoRA students trained on 15 spans and were scored
  on four action-group-held-out spans: the base mean complete-action accuracy was
  0.000 and the student mean was 0.917 (seed values 1.000, 1.000, and 0.750);
  JSON validity was 1.000 for both. This is a same-article development-only
  signal, not an unseen-family, complete-agent, or scientific-review result. See
  the [bootstrap report](architecture/protocol-agent-distillation-bootstrap-results-2026-08-22.md)
  and [public receipt](../research/protocol-agent-distillation-training-receipt-v1.json).
- After restoring the original method contract, a new protocol-stage bootstrap
  and a multi-family method-agent run were completed on the project server. The
  protocol-method bootstrap used source build `7d260b8b6dca1974`, 15 training
  examples, and four same-family development examples; the base complete-method
  action accuracy was 0.000 and the student scored 0.750, with method-trace
  completeness improving from 0.000 to 1.000
  (`receipt_sha256=34a66c29f2705fe7c6adc0f61a9a9cafb17a65ba430102933f4c5ae946a1dd06`).
  The stronger multi-family run used source build `4804d7935605b4c4`, 1,130 raw
  training examples from 157 families, deterministic action balancing to 3,033
  training examples, and 200 scored development examples from 53 families. Its
  primary metric was complete-method-action accuracy: base 0.000, Skill-method
  student 0.975; JSON validity improved from 0.575 to 1.000, decision accuracy
  from 0.000 to 1.000, and method-trace completeness from 0.000 to 1.000
  (`receipt_sha256=c3eee98cd1cab8c8c93daca57ec76a93d453f6c9b21910f9cbad88ba8fca387f`).
  This is the strongest current evidence that the restored Skill-driven method
  behavior is learnable across development families, but it remains
  protocol-action-stage evidence rather than full ten-stage systematic-review
  efficacy. See the
  [method-agent training report](architecture/method-agent-training-results-2026-08-22.md).
- The registry now covers all eight prespecified methodological profile strata
  with 11 authoritative, broadly relevant cases. The added BMJ type 2 diabetes
  risk-model review and JAMA Pediatrics global childhood-obesity prevalence
  review are deliberately `development`, `audit_only`, and
  `blocked_material_audit`. Their official OA packages are hash-frozen on the
  correct project server, but neither exposes the record-level screening,
  full-text exclusion, and original extraction/analysis gold needed for
  run-ready or confirmatory use.
- A machine-audited joint-lifecycle preregistration now binds the topic candidate
  generator, decision-aware topic controller, and an action-execute-replan
  residual-risk x downstream-impact acquisition loop. It requires two new
  confirmatory families, four matched 2 x 2 arms, three seeds, and an exact
  240-receipt ten-stage grid before published references can be opened. The
  current status is `blocked_not_run`: 0/240 receipts are locked and the
  published references remain sealed.
- All ten canonical lifecycle stages now have hash-chainable execution adapters:
  direct topic generation/control, deterministic protocol and target-independent
  query compilation, fixed or risk-impact action-execute-replan search, complete
  record accounting, a distinct criterion-complete full-text eligibility gate
  with exact quoted exclusion reasons, public-full-text result lineage only for
  eligible reports, framework-bound appraisal
  plus missing-evidence state, frozen verified-effect synthesis or explicit SWiM,
  conservative evaluation certainty and claims, evidence-bound reporting, and a
  post-cutoff living delta. These adapters have fixture-level behavior tests but
  have not yet completed one scientific case-arm-seed grid, so they are
  infrastructure rather than end-to-end efficacy evidence.
- Reporting now binds the official PRISMA 2020 checklist sources distributed by
  the PRISMA site under CC BY 4.0. Checklist status is determined item by item
  from structured evidence. Chapter prose alone cannot mark unavailable
  exclusions, study characteristics, heterogeneity, sensitivity analyses,
  registration, funding, or conflicts as reported.
- Full-text screening is no longer implicit in extraction. Every report carried
  forward from title/abstract screening must be included, excluded, or abstained
  against every frozen criterion. Exclusions are citation-bound; abstentions and
  invalid model outputs cannot enter the report-study-result-estimand chain.
- The representative adult-depression exercise NMA now has a reverified server
  snapshot of its official CC BY-NC PMC package plus a hash-bound inventory of
  30 public OSF files. The inventory confirms stage-relevant search, full-text
  exclusion, extraction, risk-of-bias, and analysis materials, while also
  recording that the OSF node has no selected license. The case remains
  development-only and not run-ready because a complete cutoff-specific search
  export and title/abstract decision ledger are unverified.
- Topic signal calculation now fails closed unless decision relevance is tied to
  verified pre-cutoff guideline, HTA, priority, or stakeholder anchors;
  cross-domain evidence is record-level; and source diversity uses explicit
  study/source families. Existing broad-query corpora lack those complete
  annotations, so their operationalization is incomplete rather than silently
  receiving global-domain, PMID-family, or PICO-completeness credit.
- New source acquisition retains explicit PubMed MeSH descriptors, publication
  types, trial-registry identifiers, and eligible guideline/HTA/priority anchors.
  A target-independent exact-MeSH annotation step can assign record-level domains
  while leaving unavailable domains and study families empty; it refuses
  target-reference-derived mappings and never treats a PMID as a study family.
- The acquisition loop and a deterministic semantic/numeric evidence verifier
  have fixture-level tests. The loop performs budgeted action execution, artifact
  hashing, risk-state update, replanning, and governed stopping. The verifier
  rejects temporal, identity, version, lineage, estimand, arm, timepoint,
  numerator/denominator, value, and source-span mismatches. Neither has a
  scientific source adapter or real-case accuracy estimate, so these are
  infrastructure evidence only.
- A topic-opportunity diagnostic used a broad, target-excluding PubMed query for
  the BMJ exercise-and-depression NMA development family. The manually authored
  concept vocabulary nevertheless included the target intervention and is now
  recorded as a concept-layer contamination failure. Two of three proposal
  batches abstained and none rediscovered the published framework. On the only
  non-empty repeat, frozen decision-aware gates reduced false-opportunity rate
  from 0.5 for four direct controls to 0.0 while selecting one of two candidates.
  Four pre-reference trajectories were initially frozen, but the later
  concept-contamination audit now blocks this topic stage from student
  training; the artifact remains only for audit. This is a negative,
  contaminated development result with a bounded filtering signal. See the
  [direct topic-opportunity report](architecture/topic-opportunity-direct-results-2026-08-22.md).
- A separate JAMA Pediatrics development calibration used a target-excluding
  3,090-record PubMed pool and deterministic exhaustive shards covering all
  2,954 admissible records once. It generated 51 proposals and recovered a
  screen-use/sleep framework. The original RCT-only audit and lexical alias set
  failed; post-lock study-design adaptation, anchor-derived synonym expansion,
  and cap-triggered retrieval achieved 23 mapped primary studies, known-item
  recall 1.0, no decision-gate failures, and alias-calibrated framework
  similarity 0.89. These are development counterfactuals, not held-out proof.
- A historically labeled Lancet adult-depression antidepressant NMA diagnostic
  covered all 4,174 admissible pre-cutoff publications once across 35 shards.
  One generation pipeline produced 89 proposals and 83 audited candidates; all
  controls and ablations reranked or gated that shared set. The full policy
  recovered a target at Top-1 and Top-3, while bibliometric count, graph-only,
  and raw LLM order missed at Top-3. False-opportunity rate was defined by the
  same frozen gates used in the full policy. The run also predates the current
  construct contract and lacks complete record-level domain, explicit
  study/source-family, and verified pre-cutoff decision-anchor mappings. It is
  now a legacy pre-construct-fix shared-candidate result, not current positive
  controller evidence or evidence for better candidate generation, an
  independent false-opportunity outcome, cross-family generalization, or
  component necessity. See the
  [direct topic-opportunity report](architecture/topic-opportunity-direct-results-2026-08-22.md).

- A frozen, family-held-out, matched-budget method-action test set was attempted by building a test corpus from review families not used for training or development. The corpus plan exposes 11,771 remaining families and Europe PMC full text is reachable, but the deterministic extraction (`extract_method_examples`) returns zero examples for those families because most use flat JATS structure (method subsections are siblings of the "Methods" container rather than nested under it), while the training corpus was built only from nested-method articles (~212 families). Under the exact training extraction the same plan therefore cannot supply a fresh frozen method-action test set. The existing family-held-out result (receipt `c3eee98cd1cab8c8c93daca57ec76a93d453f6c9b21910f9cbad88ba8fca387f`) remains the primary frozen, matched-budget, family-isolated evidence, and the attempt is recorded as a negative structural finding rather than a claim.

The repository implements typed review state, protocol and stage gates,
provenance, lawful acquisition planning, question–method routing, deterministic
R adapters, sealed evaluation, and bounded training entry points. A concrete
review still requires its own protocol, source access, independent decisions,
extraction verification, appraisal, analysis freeze, and accountable authors.

## Not established

The current evidence does not establish human replacement, lower workload,
clinical benefit, complete-review accuracy, false-exclusion safety, an
independent effect of the full conclusion-directed controller, or an independent
verifier effect. Same-provider roles are test-time compute, not independent
scientific corroboration. Topic work has one historically labeled held-out legacy shared-candidate
ranking-and-gating result that fails the current construct contract; current
positive controller evidence, candidate-generation benefit, cross-family
generalization, and distilled-student improvement are not established.

## Status maintenance

Update this file when a dated validation report changes a supported boundary.
The root README links here rather than copying every experiment. README-derived
repository metrics are maintained by `scripts/update_readme.py` and checked on
every GitHub push and pull request.
