# Biomedical Local Training Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make biomedical scope executable across project scaffolding, domain
routing, corpus stratification, AI-only evaluation, and a server-ready training
handoff without starting bulk retrieval or training.

**Architecture:** Keep the existing evidence-synthesis kernel authoritative.
Add typed biomedical context and pack manifests, deterministic weak domain
resolution, family-isolated medical corpus strata, and fail-closed server job
manifests. Generate repo and plugin skills only from the canonical
`metawingman/` tree.

**Tech Stack:** Python 3.10+, JSON Schema 2020-12, standard-library CLI tools,
`jsonschema`, `unittest`, existing MetaWingman bundle scripts, optional
Hugging Face training runtime on the future server.

**Spec:** `docs/architecture/biomedical-application-contract.md`

## Global Constraints

- Keep the product name and skill slug `metawingman`.
- Public scope is human health and clinical translational biomedicine.
- Veterinary, agricultural, and basic-mechanism-only reviews are OOD in v1.
- Domain packs cannot override protocols, authorities, estimands, appraisal,
  certainty, permissions, or human responsibility gates.
- Preserve source wording beside every normalized biomedical concept.
- Keep provider APIs outside the standalone skill bundle.
- Treat all deterministic and model-generated training labels as candidates.
- Split training and evaluation only by review family; held-out stays disabled
  until the family and temporal audits pass.
- Do not use journal identity or prestige as a model feature or target.
- Do not commit raw full text, credentials, checkpoints, or server outputs.
- Do not contact or modify the four servers during this plan.

## File Map

- `metawingman/schemas/biomedical_context.schema.json`: project domain state.
- `metawingman/schemas/domain_pack_manifest.schema.json`: versioned pack
  contract.
- `metawingman/schemas/domain_routing_decision.schema.json`: auditable pack
  selection and fallback.
- `metawingman/schemas/biomedical_training_stratum.schema.json`: medical
  corpus labels and evidence.
- `metawingman/schemas/domain_coverage_report.schema.json`: claims-safe
  capability audit.
- `metawingman/schemas/training_pair.schema.json`: contrastive retrieval item.
- `metawingman/schemas/component_training_job.schema.json`: frozen server job.
- `metawingman/references/domain-packs/*.json`: canonical foundation,
  review-profile, and specialty manifests.
- `metawingman/scripts/metawingman_core/biomedical_domain.py`: domain resolver
  and pack router.
- `metawingman/scripts/resolve_biomedical_context.py`: resolver CLI.
- `metawingman/scripts/route_domain_packs.py`: pack-routing CLI.
- `metawingman/scripts/migrate_biomedical_context.py`: explicit migration for
  existing review projects.
- `metawingman/scripts/metawingman_core/training_corpus.py`: stratified plan,
  pair export, and job manifest primitives.
- `metawingman/scripts/prepare_component_training.py`: immutable job builder.
- `metawingman/scripts/preflight_component_training.py`: offline fail-closed
  server readiness check.
- `metawingman/scripts/run_component_training.py`: validated optional server
  runtime for the first bounded components.
- `metawingman/scripts/audit_biomedical_coverage.py`: domain coverage CLI.
- `tests/test_biomedical_application_contract.py`: schema, resolver, routing,
  scaffold, migration, and coverage tests.
- `tests/test_reproducible_training_corpus.py`: medical strata, pairs, and job
  tests.

---

### Task 1: Add Biomedical Domain Contracts and Pack Manifests

**Files:**
- Create: `metawingman/schemas/biomedical_context.schema.json`
- Create: `metawingman/schemas/domain_pack_manifest.schema.json`
- Create: `metawingman/schemas/domain_routing_decision.schema.json`
- Create: `metawingman/schemas/biomedical_training_stratum.schema.json`
- Create: `metawingman/schemas/domain_coverage_report.schema.json`
- Create: `metawingman/references/domain-packs/biomedical-foundation.json`
- Create: `metawingman/references/domain-packs/profile-intervention.json`
- Create: `metawingman/references/domain-packs/profile-diagnostic.json`
- Create: `metawingman/references/domain-packs/profile-prognostic.json`
- Create: `metawingman/references/domain-packs/profile-harms.json`
- Create: `metawingman/references/domain-packs/specialty-registry.json`
- Create: `tests/test_biomedical_application_contract.py`

**Interfaces:**
- Consumes: `validate_document(document, schema_name)` from `schema_guard.py`.
- Produces: schema names `biomedical_context`, `domain_pack_manifest`,
  `domain_routing_decision`, `biomedical_training_stratum`, and
  `domain_coverage_report`.

- [ ] **Step 1: Write failing schema tests**

```python
def test_biomedical_context_requires_human_health_domain(self) -> None:
    context = biomedical_context_fixture()
    validate_document(context, "biomedical_context")
    context["application_domain"] = "veterinary"
    with self.assertRaises(SchemaValidationError):
        validate_document(context, "biomedical_context")

def test_domain_pack_cannot_claim_method_override(self) -> None:
    pack = domain_pack_fixture()
    validate_document(pack, "domain_pack_manifest")
    pack["constraints"]["may_override_protocol"] = True
    with self.assertRaises(SchemaValidationError):
        validate_document(pack, "domain_pack_manifest")
```

- [ ] **Step 2: Run the new tests and verify missing-schema failures**

Run:

```powershell
python -m unittest tests.test_biomedical_application_contract -v
```

Expected: FAIL because the five schemas and pack fixtures do not exist.

- [ ] **Step 3: Implement the schemas with closed objects**

Use these exact top-level contracts:

```json
{
  "biomedical_context": [
    "schema_version", "context_id", "application_domain", "status",
    "review_family", "primary_specialty", "secondary_specialties",
    "question_framework", "terminology_releases", "source_classes",
    "languages", "geographies", "ood_assessment", "created_at_utc",
    "updated_at_utc"
  ],
  "domain_pack_manifest": [
    "schema_version", "pack_id", "pack_type", "version", "status",
    "application_domain", "supported_review_families", "specialties",
    "capabilities", "terminology_releases", "authority_sources",
    "dependencies", "constraints", "validation", "content_sha256"
  ],
  "domain_routing_decision": [
    "schema_version", "decision_id", "context_id", "task_type",
    "risk_class", "candidate_pack_ids", "selected_pack_ids", "status",
    "confidence", "evidence", "reason_codes", "fallback",
    "created_at_utc"
  ],
  "biomedical_training_stratum": [
    "schema_version", "primary_specialty", "secondary_specialties",
    "question_type", "study_designs", "synthesis_routes", "languages",
    "document_modalities", "challenge_tags", "sampling_key",
    "label_status", "evidence"
  ],
  "domain_coverage_report": [
    "schema_version", "report_id", "registry_sha256", "generated_at_utc",
    "application_domain", "profiles", "specialties", "issues", "valid"
  ]
}
```

Set `application_domain` to the constant
`human_health_clinical_translational_biomedicine`. Set every schema to
`additionalProperties: false`. Pack constraints must contain five `false`
constants: `may_override_protocol`, `may_override_authority`,
`may_override_estimand`, `may_grant_tool_permissions`, and
`may_promote_model_output_to_gold`.

- [ ] **Step 4: Add minimal governed pack manifests**

The foundation pack supports every existing review family and only declares
terminology normalization, source selection, OOD detection, and domain routing.
Profile packs declare their matching review family and point to the existing
methodology source registry. The specialty registry defines stable IDs and weak
title terms for at least general medicine, oncology, cardiovascular medicine,
neurology, infectious disease, mental health, maternal-child health, public
health, drug safety, diagnostics, imaging, and clinical omics.

- [ ] **Step 5: Run schema and existing control-plane tests**

Run:

```powershell
python -m unittest tests.test_biomedical_application_contract tests.test_ai_control_plane -v
```

Expected: PASS.

- [ ] **Step 6: Commit the contracts**

```powershell
git add metawingman/schemas metawingman/references/domain-packs tests/test_biomedical_application_contract.py
git commit -m "feat: add biomedical domain contracts"
```

### Task 2: Implement Deterministic Domain Resolution and Pack Routing

**Files:**
- Create: `metawingman/scripts/metawingman_core/biomedical_domain.py`
- Create: `metawingman/scripts/resolve_biomedical_context.py`
- Create: `metawingman/scripts/route_domain_packs.py`
- Modify: `metawingman/scripts/metawingman_core/__init__.py`
- Modify: `tests/test_biomedical_application_contract.py`

**Interfaces:**
- Consumes: domain pack manifests and a draft `biomedical_context`.
- Produces:
  `resolve_context(seed: dict, packs: list[dict], now: str) -> dict` and
  `route_domain_packs(context: dict, packs: list[dict], task_type: str,
  risk_class: str, now: str) -> dict`.

- [ ] **Step 1: Add resolver and router failure tests**

```python
def test_resolver_preserves_source_text_and_unresolved_terms(self) -> None:
    result = resolve_context({
        "context_id": "ctx-1", "review_family": "intervention",
        "source_text": "Adults with an unmapped syndrome receiving aspirin",
        "declared_specialties": ["cardiovascular-medicine"],
    }, load_packs(), TIMESTAMP)
    self.assertEqual(result["question_framework"]["source_text"],
                     "Adults with an unmapped syndrome receiving aspirin")
    self.assertIn("unmapped syndrome",
                  result["question_framework"]["unresolved_terms"])

def test_high_risk_route_abstains_without_validated_profile_pack(self) -> None:
    result = route_domain_packs(context_fixture("diagnostic"),
                                [foundation_pack()], "appraisal", "high",
                                TIMESTAMP)
    self.assertEqual(result["status"], "abstained")
    self.assertIn("missing_profile_pack", result["reason_codes"])
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
python -m unittest tests.test_biomedical_application_contract -v
```

Expected: FAIL with an import error for `biomedical_domain`.

- [ ] **Step 3: Implement resolution without hidden clinical inference**

```python
def resolve_context(seed, packs, now):
    declared = tuple(dict.fromkeys(seed.get("declared_specialties", [])))
    primary = declared[0] if declared else "general-medicine"
    unresolved = _unresolved_source_terms(seed.get("source_text", ""), packs)
    context = {
        "schema_version": "1.0",
        "context_id": seed["context_id"],
        "application_domain":
            "human_health_clinical_translational_biomedicine",
        "status": "draft",
        "review_family": seed["review_family"],
        "primary_specialty": primary,
        "secondary_specialties": list(declared[1:]),
        "question_framework": {
            "framework": seed.get("framework", "profile_specific"),
            "source_text": seed.get("source_text", ""),
            "normalized_concepts": [],
            "unresolved_terms": unresolved,
        },
        "terminology_releases": [],
        "source_classes": [],
        "languages": seed.get("languages", ["en"]),
        "geographies": seed.get("geographies", []),
        "ood_assessment": {
            "status": "in_scope" if declared else "uncertain",
            "reason_codes": [] if declared else ["specialty_not_declared"],
        },
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    validate_document(context, "biomedical_context")
    return context
```

Do not map a source phrase unless a pack term matches a normalized token span.
Store the matched phrase and pack ID in each normalized concept.

- [ ] **Step 4: Implement fail-closed routing**

Select the biomedical foundation first, then one compatible profile pack, then
zero or more specialty packs. Reject retired packs, hash mismatches, unsupported
review families, and dependency gaps. High-risk routes require a profile pack
whose validation status is at least `fixture_tested`; otherwise return
`abstained`. Never resolve conflicts by majority vote.

- [ ] **Step 5: Add CLI JSON input/output and validate both boundaries**

Both CLIs read UTF-8 JSON, validate inputs, write atomic UTF-8 JSON, and return
exit code 2 for an abstained route. They never access the network.

- [ ] **Step 6: Run focused tests and commit**

```powershell
python -m unittest tests.test_biomedical_application_contract -v
git add metawingman/scripts tests/test_biomedical_application_contract.py
git commit -m "feat: route biomedical domain packs"
```

### Task 3: Add Biomedical Context to New and Existing Review Projects

**Files:**
- Modify: `metawingman/scripts/init_review.py`
- Create: `metawingman/scripts/migrate_biomedical_context.py`
- Modify: `metawingman/scripts/validate_project.py`
- Modify: `tests/test_ai_control_plane.py`
- Modify: `tests/test_biomedical_application_contract.py`

**Interfaces:**
- Consumes: `--specialty <id>` and existing `--profile` values.
- Produces: `01_protocol/biomedical_context.json` and explicit migration output.

- [ ] **Step 1: Add scaffold and migration tests**

```python
def test_init_review_writes_biomedical_context(self) -> None:
    result = run_init("--profile", "diagnostic", "--specialty", "diagnostics")
    context = json.loads((result / "01_protocol/biomedical_context.json")
                         .read_text(encoding="utf-8"))
    validate_document(context, "biomedical_context")
    self.assertEqual(context["primary_specialty"], "diagnostics")

def test_migration_requires_explicit_specialty(self) -> None:
    completed = run_migration(existing_project())
    self.assertEqual(completed.returncode, 2)
    self.assertIn("--specialty is required", completed.stderr)
```

- [ ] **Step 2: Verify focused tests fail**

Run:

```powershell
python -m unittest tests.test_ai_control_plane tests.test_biomedical_application_contract -v
```

Expected: FAIL because the scaffold has no biomedical context.

- [ ] **Step 3: Extend `init_review.py`**

Add repeatable `--specialty`; default to `general-medicine` only for a new draft.
Write a validated draft context whose source text is empty and whose OOD status
is `uncertain`. Do not infer specialty from the project title or folder name.

- [ ] **Step 4: Implement explicit migration**

The migration validates the existing project, refuses to overwrite an existing
context, requires at least one `--specialty`, hashes the current profile, writes
the context atomically, and records an event with action
`biomedical_context_migrated`. `--dry-run` prints the proposed JSON without
writing.

- [ ] **Step 5: Make project validation version-aware**

Newly initialized projects require the biomedical context. Legacy projects
without it report `migration_required` and remain readable; they do not pass the
biomedical readiness gate.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m unittest tests.test_ai_control_plane tests.test_adversarial_boundaries tests.test_biomedical_application_contract -v
git add metawingman/scripts tests
git commit -m "feat: scaffold biomedical review context"
```

### Task 4: Add Medical Strata to the Reproducible Corpus Planner

**Files:**
- Modify: `metawingman/schemas/training_corpus_plan.schema.json`
- Modify: `metawingman/scripts/metawingman_core/training_corpus.py`
- Modify: `metawingman/scripts/plan_training_corpus.py`
- Modify: `tests/test_reproducible_training_corpus.py`
- Create during execution: `research/training-corpus-plan-biomedical-v2.json`

**Interfaces:**
- Consumes: current top-journal corpus, family registry, and specialty registry.
- Produces:
  `classify_biomedical_stratum(record: dict, registry: dict) -> dict` and a
  schema-version 1.1 training plan with `biomedical_stratum` on each record.

- [ ] **Step 1: Write deterministic strata and no-journal-feature tests**

```python
def test_medical_strata_are_source_anchored_and_ignore_journal(self) -> None:
    left = corpus_record(1)
    left["title"] = "Cancer immunotherapy adverse events: systematic review"
    right = dict(left, journal="Unrelated Journal")
    self.assertEqual(classify_biomedical_stratum(left, registry_fixture()),
                     classify_biomedical_stratum(right, registry_fixture()))
    result = classify_biomedical_stratum(left, registry_fixture())
    self.assertEqual(result["primary_specialty"], "oncology")
    self.assertEqual(result["question_type"], "harms")
    self.assertTrue(result["evidence"])

def test_plan_balances_composite_strata_before_repeating_them(self) -> None:
    plan = fixture_medical_plan(maximum_records=12)
    keys = [item["biomedical_stratum"]["sampling_key"]
            for item in plan["records"]]
    self.assertGreaterEqual(len(set(keys)), 4)
```

- [ ] **Step 2: Verify the tests fail**

```powershell
python -m unittest tests.test_reproducible_training_corpus -v
```

- [ ] **Step 3: Add schema 1.0 read compatibility and 1.1 output**

Use a schema conditional: version 1.0 accepts current plans unchanged; version
1.1 requires `domain_policy`, `strata_summary`, and each record's validated
`biomedical_stratum`. New plans emit 1.1. Existing v1 artifacts stay auditable.

- [ ] **Step 4: Implement weak, evidence-bearing classification**

Normalize title and publication types only. Match the longest specialty and
question terms from the registry. Record every matched source phrase. Use
`general-medicine` and `unresolved` when no specialty term matches. Set
`label_status` to `deterministic_weak_candidate`, never `verified`.

- [ ] **Step 5: Replace journal round-robin with coverage-first selection**

Group eligible records by the composite key of primary specialty, question
type, study design, and synthesis route. Select one deterministic record from
the least-covered group each round. Use journal stratum only for reporting and
tie diversity; never include it in exported model input.

- [ ] **Step 6: Generate a large metadata-only server plan**

Run:

```powershell
python .\metawingman\scripts\plan_training_corpus.py `
  --corpus .\research\top-journal-training-corpus.json `
  --families .\research\top-journal-review-family-registry.json `
  --specialty-registry .\metawingman\references\domain-packs\specialty-registry.json `
  --out .\research\training-corpus-plan-biomedical-v2.json `
  --maximum-records 2048 --seed 20260815 `
  --created-at-utc 2026-08-15T00:00:00Z
```

This command performs no full-text download. If fewer than 2,048 records remain
eligible, record the exact eligible count and select all of them.

- [ ] **Step 7: Run tests, audit the plan, and commit**

```powershell
python -m unittest tests.test_reproducible_training_corpus -v
python -c "import json; from pathlib import Path; from sys import path; path.insert(0, 'metawingman/scripts'); from metawingman_core.schema_guard import validate_document; validate_document(json.loads(Path('research/training-corpus-plan-biomedical-v2.json').read_text(encoding='utf-8')), 'training_corpus_plan'); print('valid')"
git add metawingman/schemas/training_corpus_plan.schema.json metawingman/scripts research/training-corpus-plan-biomedical-v2.json tests/test_reproducible_training_corpus.py
git commit -m "feat: stratify biomedical training corpus"
```

### Task 5: Export Hard Negatives and Freeze Component Training Jobs

**Files:**
- Create: `metawingman/schemas/training_pair.schema.json`
- Create: `metawingman/schemas/component_training_job.schema.json`
- Modify: `metawingman/schemas/training_run_plan.schema.json`
- Modify: `metawingman/scripts/metawingman_core/training_corpus.py`
- Modify: `metawingman/scripts/export_training_splits.py`
- Create: `metawingman/scripts/prepare_component_training.py`
- Create: `metawingman/scripts/preflight_component_training.py`
- Create: `metawingman/scripts/run_component_training.py`
- Create: `metawingman/references/dependencies/python-training.lock.txt`
- Modify: `tests/test_reproducible_training_corpus.py`

**Interfaces:**
- Produces:
  `build_retrieval_pairs(examples: list[dict], strata_by_record: dict,
  seed: int) -> list[dict]`,
  `build_component_training_job(run_plan: dict, component: str,
  model: dict, optimization: dict, resources: dict, now: str) -> dict`, and
  `preflight_component_training(job: dict, root: Path) -> dict`.

- [ ] **Step 1: Write pair and preflight tests**

```python
def test_hard_negative_never_crosses_split_or_reuses_family(self) -> None:
    pairs = build_retrieval_pairs(example_fixture(), strata_fixture(), seed=11)
    for pair in pairs:
        self.assertEqual(pair["query_split"], pair["document_split"])
        if pair["label"] == 0:
            self.assertNotEqual(pair["query_family_id"],
                                pair["document_family_id"])
            self.assertTrue(pair["shared_medical_neighborhood"])

def test_preflight_blocks_mutable_model_revision(self) -> None:
    job = component_job_fixture()
    job["model"]["revision"] = "main"
    report = preflight_component_training(job, fixture_root())
    self.assertFalse(report["ready"])
    self.assertIn("model_revision_not_immutable", report["reason_codes"])

def test_training_runner_validate_only_never_imports_ml_runtime(self) -> None:
    with patch.dict(sys.modules, {"torch": None, "transformers": None}):
        report = validate_training_job(component_job_fixture(), fixture_root())
    self.assertTrue(report["manifest_valid"])
    self.assertFalse(report["training_started"])
```

- [ ] **Step 2: Verify tests fail**

```powershell
python -m unittest tests.test_reproducible_training_corpus -v
```

- [ ] **Step 3: Implement contrastive pair export**

Create one positive pair per anchored example. Select up to three negatives from
the same split and same primary specialty or question type, excluding the same
record, family, exact source span, and likely companion reports. Order candidates
by deterministic token overlap and a seeded hash. Mark every negative
`candidate_hard_negative_not_gold`.

- [ ] **Step 4: Extend the model-neutral run plan**

Schema version 1.1 adds dataset pair path/hash/counts, biomedical strata counts,
and supported objective readiness. Version 1.0 remains readable. A component may
enter `ready_for_server_preflight` only when all paths, hashes, family isolation,
license policy, and non-gold label states validate.

- [ ] **Step 5: Implement the frozen component job**

The first two jobs are `section_role_classification` and `evidence_retrieval`.
Each job records an immutable Hugging Face model revision, model-card URL,
declared license, tokenizer revision, dataset hashes, seed, epochs, batch size,
learning rate, weight decay, warmup ratio, precision policy, checkpoint cadence,
selection metric, output path, requested CPU/RAM/GPU/storage, and command argv.
The builder accepts explicit values and never chooses a remote model silently.

Audit `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext` from its
official model card and Hub metadata as the first bounded-task candidate. Resolve
and record an immutable commit SHA. If the declared model or dataset license is
missing or incompatible with the intended release, keep the job blocked and
record `model_license_unresolved`; do not substitute another model silently.

- [ ] **Step 6: Implement offline preflight**

Preflight validates schemas, hashes, split isolation, output containment,
checkpoint policy, immutable revisions, non-empty development data, and estimated
disk budget. It prints `ready: false` with reason codes when server hardware,
CUDA, or exact package versions remain unverified. It never imports Torch,
contacts a model hub, downloads a model, or starts training.

- [ ] **Step 7: Implement the optional server runner**

`--validate-only` validates the job and exits before importing ML packages.
Normal execution rechecks hashes and server preflight, sets Python, NumPy,
Torch, and trainer seeds, then dispatches by component. Section-role training
uses `AutoModelForSequenceClassification` and `Trainer`; retrieval training uses
a tied encoder with in-batch negatives and cosine similarity. Both write
checkpoint hashes, metrics JSON, package versions, accelerator details, elapsed
time, and the final execution state. The runner refuses an output directory
outside the job's declared root and never resumes a checkpoint whose hash is
absent from the job ledger.

Pin the Python training packages in `python-training.lock.txt` after resolving
current official package releases and compatibility. Do not install them on the
workstation during this task. The server preflight compares installed versions
to the lock before importing the training runtime.

- [ ] **Step 8: Run tests and commit**

```powershell
python -m unittest tests.test_reproducible_training_corpus -v
git add metawingman/schemas metawingman/scripts tests/test_reproducible_training_corpus.py
git commit -m "feat: prepare biomedical component training jobs"
```

### Task 6: Add Four-Level Biomedical AI-Only Evaluation and Coverage Audit

**Files:**
- Modify: `metawingman/schemas/ai_only_evaluation_plan.schema.json`
- Modify: `metawingman/references/ai-only-evaluation-plan.template.json`
- Modify: `metawingman/schemas/system_capability_matrix.schema.json`
- Modify: `metawingman/references/system-capability-matrix.json`
- Create: `metawingman/scripts/audit_biomedical_coverage.py`
- Modify: `metawingman/scripts/metawingman_core/coverage_audit.py`
- Modify: `metawingman/scripts/metawingman_core/living_update.py`
- Modify: `tests/test_ai_only_evaluator.py`
- Modify: `tests/test_system_coverage_and_acquisition.py`
- Modify: `tests/test_biomedical_application_contract.py`
- Modify: `tests/test_p3_living_benchmark.py`

**Interfaces:**
- Consumes: pack manifests, system capability matrix, and the AI-only plan.
- Produces: validated four-configuration evaluation plan and
  `audit_biomedical_coverage(pack_root, capability_matrix) -> dict`.

- [ ] **Step 1: Write evaluation and claim-boundary tests**

```python
def test_ai_only_template_has_four_biomedical_configurations(self) -> None:
    plan = load_ai_only_template()
    self.assertEqual([item["configuration_id"] for item in
                      plan["configurations"]], [
        "general-model-baseline", "biomedical-schema",
        "biomedical-routing", "full-biomedical-stack",
    ])
    validate_document(plan, "ai_only_evaluation_plan")

def test_coverage_does_not_promote_fixture_to_validated(self) -> None:
    report = audit_biomedical_coverage(pack_root(), capability_matrix())
    diagnostic = find_profile(report, "diagnostic")
    self.assertNotEqual(diagnostic["validation_level"],
                        "externally_validated")

def test_domain_pack_drift_requires_explicit_living_migration(self) -> None:
    result = plan_living_update(snapshot_with_pack_hash("1" * 64),
                                current_pack_hash="2" * 64)
    self.assertEqual(result["status"], "blocked_pending_domain_migration")
    self.assertIn("domain_pack_hash_changed", result["reason_codes"])
```

- [ ] **Step 2: Verify focused tests fail**

```powershell
python -m unittest tests.test_ai_only_evaluator tests.test_system_coverage_and_acquisition tests.test_biomedical_application_contract -v
```

- [ ] **Step 3: Add the frozen four-level ablation design**

Use exactly these IDs: `general-model-baseline`, `biomedical-schema`,
`biomedical-routing`, and `full-biomedical-stack`. Extend secondary metrics with
`anchor_accuracy`, `lineage_precision`, `lineage_recall`,
`exact_recomputation_rate`, `selective_coverage`, and `abstention_quality`.
Keep aggregation by review family and human-comparison claims disabled.

- [ ] **Step 4: Implement domain coverage auditing**

Audit pack hashes, dependency closure, profile/specialty IDs, terminology and
authority versions, capability evidence paths, and validation levels. Report
unsupported combinations explicitly. Shared lifecycle support cannot raise a
profile above `implemented_not_scientifically_validated`.

- [ ] **Step 5: Propagate pack drift into living updates**

Store active pack IDs, versions, terminology releases, and hashes in living
snapshots. A changed pack or terminology release produces a blocked delta that
lists affected evidence and claims. Only an explicit migration event may resume
the living run; a model response cannot clear this block.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m unittest tests.test_ai_only_evaluator tests.test_system_coverage_and_acquisition tests.test_biomedical_application_contract tests.test_p3_living_benchmark -v
git add metawingman/schemas metawingman/references metawingman/scripts tests
git commit -m "feat: audit biomedical evaluation coverage"
```

### Task 7: Produce the Local-to-Server Handoff Bundle

**Files:**
- Create: `metawingman/schemas/server_training_handoff.schema.json`
- Create: `metawingman/scripts/build_server_training_handoff.py`
- Create: `docs/architecture/server-training-runbook.md`
- Modify: `docs/architecture/reproducible-training-corpus.md`
- Modify: `tests/test_reproducible_training_corpus.py`

**Interfaces:**
- Consumes: biomedical v2 corpus plan, component job manifests, local preflight
  reports, and dependency locks.
- Produces: a metadata-only handoff directory with hashes and exact commands.

- [ ] **Step 1: Write handoff safety tests**

```python
def test_handoff_excludes_full_text_secrets_and_checkpoints(self) -> None:
    result = build_server_handoff(handoff_fixture())
    members = set(result["members"])
    self.assertFalse(any(name.endswith((".pdf", ".xml", ".env", ".pt",
                                         ".safetensors"))
                         for name in members))
    self.assertTrue(result["commands"]["download"][0].endswith(
        "fetch_training_corpus.py"))

def test_handoff_refuses_scientific_preflight_failure(self) -> None:
    fixture = handoff_fixture()
    fixture["preflight"]["ready"] = False
    fixture["preflight"]["blocking_reasons"] = ["dataset_hash_mismatch"]
    with self.assertRaises(TrainingCorpusError):
        build_server_handoff(fixture)
```

- [ ] **Step 2: Verify tests fail**

```powershell
python -m unittest tests.test_reproducible_training_corpus -v
```

- [ ] **Step 3: Implement the metadata-only handoff**

Include plan, schemas, component jobs, dependency locks, preflight reports,
expected output paths, storage estimate, hashes, and argv arrays for download,
freeze, audit, export, train, and benchmark. Reject secret-like content,
absolute author paths, raw full text, and checkpoint suffixes. Use deterministic
file ordering and canonical JSON. Scientific/data failures block the handoff.
Hardware, CUDA, and server package checks may remain in a separate
`server_only_pending` list; in that state the handoff status is
`local_ready_pending_server_preflight`, never `server_ready`.

- [ ] **Step 4: Write the server runbook**

Document read-only preflight, explicit authorization, upload destination,
environment creation, resume behavior, checksums, log paths, resource monitoring,
failure recovery, and result retrieval. State that this plan does not execute
the runbook.

- [ ] **Step 5: Build and verify the local handoff**

Generate under ignored `validation-output/server-training-handoff/`. The build
must stop if component model revisions, licenses, or local data hashes are not
frozen. Server-only hardware checks may remain pending. Do not weaken a failed
scientific or integrity gate to produce a nominally ready bundle.

- [ ] **Step 6: Run tests and commit source files**

```powershell
python -m unittest tests.test_reproducible_training_corpus -v
git add metawingman/schemas metawingman/scripts docs/architecture tests/test_reproducible_training_corpus.py
git commit -m "feat: build server training handoff"
```

### Task 8: Integrate the Skill, Documentation, and Release Bundle

**Files:**
- Modify: `metawingman/SKILL.md`
- Modify: `metawingman/references/review-types.md`
- Modify: `metawingman/references/search-retrieval-and-apis.md`
- Modify: `README.md`
- Modify: `docs/architecture/release-checklist.md`
- Generated: `.agents/skills/metawingman/**`
- Generated: `plugins/metawingman/skills/metawingman/**`
- Modify: `tests/test_skill_distribution.py`

**Interfaces:**
- Consumes: canonical schemas, scripts, packs, and docs from Tasks 1-7.
- Produces: identical standalone and plugin skills with biomedical scope visible
  and provider runtime still excluded from the standalone skill.

- [ ] **Step 1: Add distribution assertions**

```python
def test_bundle_declares_biomedical_scope_and_contains_domain_contracts(self):
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory) / "metawingman"
        manifest = _stage(ROOT, bundle)
        self.assertTrue((bundle / "schemas/biomedical_context.schema.json").is_file())
        self.assertTrue((bundle / "references/domain-packs/biomedical-foundation.json").is_file())
        self.assertIn("biomedical evidence synthesis",
                      (bundle / "SKILL.md").read_text(encoding="utf-8").casefold())
        self.assertEqual(manifest["requirements"]["direct_model_api"],
                         "not bundled")
```

- [ ] **Step 2: Verify the new assertion fails**

```powershell
python -m unittest tests.test_skill_distribution -v
```

- [ ] **Step 3: Update canonical instructions and research entry points**

State that biomedical scope is required, domain selection is typed, pack output
cannot override methods, and unresolved/OOD concepts trigger fallback or
abstention. Add commands for v2 planning, domain coverage audit, component
preflight, and handoff build. Do not claim trained or validated performance.

- [ ] **Step 4: Rebuild and verify both generated skills**

```powershell
python .\scripts\build_skill_bundle.py
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_skill_bundle.py .\plugins\metawingman\skills\metawingman
```

- [ ] **Step 5: Run distribution tests and commit**

```powershell
python -m unittest tests.test_skill_distribution -v
git add README.md docs/architecture metawingman .agents/skills/metawingman plugins/metawingman/skills/metawingman tests/test_skill_distribution.py
git commit -m "docs: publish biomedical MetaWingman workflow"
```

### Task 9: Run the Full Local Gate and Stop Before Server Execution

**Files:**
- Modify only when a verification failure requires a scoped fix.
- Generate under ignored `validation-output/` only.

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: a verified local readiness report or explicit blocking reason codes.

- [ ] **Step 1: Run all Python tests**

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run R adapter validation**

```powershell
python .\metawingman\scripts\test_r_adapters.py
```

Expected: all available deterministic R adapters PASS; unavailable optional
packages must be reported, not silently skipped as success.

- [ ] **Step 3: Audit coverage, corpus, and dependencies**

```powershell
python .\metawingman\scripts\audit_system_coverage.py
python .\metawingman\scripts\audit_biomedical_coverage.py
python .\scripts\verify_dependency_locks.py
```

Expected: schema and implementation coverage valid; scientific validation levels
remain bounded to their actual evidence.

- [ ] **Step 4: Rebuild, package, and verify release artifacts**

```powershell
python .\scripts\build_skill_bundle.py
python .\scripts\package_skill_release.py
python .\scripts\generate_release_metadata.py
```

Record tree hash, archive hash, file count, and secret-scan result.

- [ ] **Step 5: Build the local server handoff and inspect its gate**

Run the handoff builder only against the frozen biomedical v2 plan and concrete
component jobs. A report that still needs server hardware/CUDA confirmation is
acceptable only when it says so explicitly; the package must not claim the
server is ready.

- [ ] **Step 6: Inspect final Git state**

```powershell
git status --short --branch
git log --oneline --decorate -12
git diff --check
```

Confirm no unrelated user work, raw full text, credentials, checkpoints, or
server output entered a commit.

- [ ] **Step 7: Stop at the authorization boundary**

Report local test results, generated plan and handoff paths, hashes, estimated
storage/compute, exact remaining server blockers, and the first server command.
Do not connect, upload, install, download full text, or train on any server until
the user explicitly authorizes that run.
