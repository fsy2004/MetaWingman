# Question-Synthesis Server Mainline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a provider-neutral MetaWingman runtime that jointly
designs clinically useful review questions and synthesis methods, then carries
the selected design through one source-grounded full-review state on a server.

**Architecture:** Extend the current temporal topic engine with closed schemas,
a deterministic method registry, evidence-constrained tree search, and typed
proposal/opposition/judge roles. Connect its selected state to the existing
event ledger, provenance graph, document state, appraisal workbench, R adapters,
and living-update modules; train only bounded ranker, verifier, and routing
components from frozen reconstruction data.

**Tech Stack:** Python 3.12, JSON Schema 2020-12, `jsonschema`, standard-library
CLIs, `unittest`, existing provider-neutral `ModelProvider`, PyTorch and
Transformers for bounded encoders, scikit-learn for calibrated routing, R and
the existing MetaWingman analysis adapters, Linux/NVIDIA server runtime.

**Spec:** `docs/architecture/clinical-question-synthesis-co-design.md`

## Global Constraints

- Keep `metawingman/` as the canonical skill source and generate distributed
  skill copies only with the existing build script.
- Keep model providers outside the standalone skill and read credentials only
  through the existing secret boundary.
- Preserve the current topic schemas and CLIs; introduce explicit versioned
  joint-design contracts instead of changing historical records in place.
- Use closed JSON objects with `additionalProperties: false`.
- Never use a model-emitted scalar as scientific truth or production stopping
  authority.
- Every scientific field must carry evidence anchors, an explicit unavailable
  state, or an abstention reason.
- Keep `no_pooling` and SWiM as valid outcomes, not failures.
- Freeze retrospective cases by review family and time; seal target identity,
  descendants, final included studies, and post-cutoff evidence.
- Treat published review decisions as `published_reference`, not infallible
  gold labels.
- Use one AI-only execution arm; do not introduce contemporaneous human workflow
  arms into the benchmark.
- Do not commit raw full text, credentials, provider response content,
  checkpoints, or server run output.
- Require an external source or executable tool observation before reflection
  can change consequential state.
- Keep final protocol, high-risk unresolved judgments, irreversible actions,
  and conclusion responsibility human-overseen in production use.

## File Map

- `metawingman/schemas/clinical_decision_context.schema.json`: clinical intent
  and implementation context.
- `metawingman/schemas/question_synthesis_candidate.schema.json`: one joint
  question/review-family/estimand/method state.
- `metawingman/schemas/method_route_decision.schema.json`: compatible analysis
  routes, assumptions, failures, and fallback.
- `metawingman/schemas/question_synthesis_search.schema.json`: search tree,
  budget, observations, and selected portfolio.
- `metawingman/references/question-synthesis-methods.json`: deterministic method
  compatibility registry.
- `metawingman/scripts/metawingman_core/clinical_question.py`: context compiler.
- `metawingman/scripts/metawingman_core/synthesis_method_router.py`: method
  enumeration and hard compatibility checks.
- `metawingman/scripts/metawingman_core/question_synthesis_search.py`: search
  state, expansion, frontier allocation, and portfolio selection.
- `metawingman/scripts/metawingman_core/question_synthesis_agents.py`: typed
  proposer, opposition, judge, and evolution calls.
- `metawingman/scripts/metawingman_core/question_synthesis_verifier.py`: source,
  overlap, route, assumption, and lineage observations.
- `metawingman/scripts/design_review_question.py`: end-to-end joint-design CLI.
- `metawingman/schemas/question_synthesis_benchmark_case.schema.json`: sealed
  retrospective/prospective case.
- `metawingman/scripts/metawingman_core/question_synthesis_evaluator.py`: direct
  metrics, risk-coverage, repeated-run, and ablation evaluation.
- `metawingman/scripts/evaluate_question_synthesis.py`: benchmark CLI.
- `metawingman/schemas/review_case_state.schema.json`: persistent full-review
  operating state.
- `metawingman/schemas/scientific_reflection.schema.json`: proposed assertion,
  external tests, observations, and disposition.
- `metawingman/scripts/metawingman_core/review_case.py`: atomic case transitions.
- `metawingman/scripts/metawingman_core/reflection_engine.py`: external-feedback
  reflection loop.
- `metawingman/schemas/question_synthesis_training_example.schema.json`: frozen
  pairwise and verifier training items.
- `metawingman/scripts/prepare_question_synthesis_training.py`: family/time-safe
  export and component-job builder.
- `scripts/server/preflight_mainline.py`: server hardware, runtime, storage, and
  bundle preflight.
- `docs/architecture/server-mainline-runbook.md`: server data layout and command
  order.
- `tests/test_question_synthesis_contracts.py`: schemas and method registry.
- `tests/test_question_synthesis_engine.py`: context, routing, search, agents,
  and verifiers.
- `tests/test_question_synthesis_benchmark.py`: sealing and metrics.
- `tests/test_review_case_loop.py`: full-loop state and reflection.
- `tests/test_question_synthesis_training.py`: export, split, and job checks.

---

### Task 1: Add Joint-Design Contracts and Method Registry

**Files:**
- Create: `metawingman/schemas/clinical_decision_context.schema.json`
- Create: `metawingman/schemas/question_synthesis_candidate.schema.json`
- Create: `metawingman/schemas/method_route_decision.schema.json`
- Create: `metawingman/schemas/question_synthesis_search.schema.json`
- Create: `metawingman/references/question-synthesis-methods.json`
- Create: `tests/test_question_synthesis_contracts.py`

**Interfaces:**
- Consumes: `validate_document(document, schema_name)` from
  `metawingman_core.schema_guard`.
- Produces: schema names `clinical_decision_context`,
  `question_synthesis_candidate`, `method_route_decision`, and
  `question_synthesis_search`; registry entries keyed by `route_id`.

- [ ] **Step 1: Write failing contract tests**

```python
def test_candidate_requires_clinical_estimand_and_method(self) -> None:
    candidate = question_synthesis_candidate_fixture()
    validate_document(candidate, "question_synthesis_candidate")
    del candidate["estimand"]
    with self.assertRaises(SchemaValidationError):
        validate_document(candidate, "question_synthesis_candidate")

def test_registry_contains_no_pooling_route(self) -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    routes = payload["routes"]
    self.assertIn("no_pooling", {item["route_id"] for item in routes})
```

- [ ] **Step 2: Run the tests and confirm missing-contract failures**

Run:

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_contracts.py" -v
```

Expected: FAIL because the schemas, loader, and registry do not exist.

- [ ] **Step 3: Implement closed schemas with these exact top-level fields**

```json
{
  "clinical_decision_context": [
    "schema_version", "context_id", "stakeholders", "setting",
    "decision_problem", "candidate_actions", "time_horizon",
    "patient_important_outcomes", "subgroups", "equity_factors",
    "implementation_constraints", "source_anchors", "status",
    "created_at_utc"
  ],
  "question_synthesis_candidate": [
    "schema_version", "candidate_id", "context_id", "parent_candidate_id",
    "mutation", "question_framework", "review_family", "estimand",
    "synthesis_route", "data_requirements", "evidence_anchor_ids",
    "assumption_checks", "feasibility", "overlap", "uncertainty",
    "disposition", "created_at_utc"
  ],
  "method_route_decision": [
    "schema_version", "decision_id", "candidate_id", "compatible_routes",
    "rejected_routes", "selected_route_id", "fallback_route_id",
    "required_checks", "evidence_anchor_ids", "status", "created_at_utc"
  ],
  "question_synthesis_search": [
    "schema_version", "search_id", "landscape_id", "context_id", "policy",
    "budget", "nodes", "edges", "observations", "portfolio", "status",
    "created_at_utc", "updated_at_utc"
  ]
}
```

Use existing review-family enum values. Define synthesis routes as registry
identifiers rather than a second hard-coded enum. Define dispositions as
`frontier`, `selected`, `reserve`, `rejected`, and `abstained`.

- [ ] **Step 4: Create and validate the method registry**

```json
{
  "schema_version": "1.0",
  "routes": [
    {
      "route_id": "no_pooling",
      "review_families": ["intervention", "diagnostic", "prognostic", "harms", "other"],
      "required_fields": ["outcome", "study_design"],
      "effect_measures": [],
      "minimum_data_shape": {},
      "assumptions": [],
      "hard_failures": [],
      "r_adapter": null,
      "fallback_route_id": null
    }
  ]
}
```

Add explicit records for pairwise aggregate-data, network, bivariate/HSROC
diagnostic, prognostic factor, prediction-model performance, prevalence,
incidence, rare-event harms, dose-response, IPD, multilevel/multivariate/RVE,
umbrella, and SWiM routes. Each non-null `r_adapter` must match a current adapter
manifest; the test must fail on an unknown adapter.

- [ ] **Step 5: Run tests and commit the contracts**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_contracts.py" -v
git add metawingman/schemas metawingman/references/question-synthesis-methods.json tests/test_question_synthesis_contracts.py
git commit -m "feat: add clinical question synthesis contracts"
```

Expected: all tests in `tests.test_question_synthesis_contracts` pass.

---

### Task 2: Compile Clinical Context and Enumerate Valid Synthesis Routes

**Files:**
- Create: `metawingman/scripts/metawingman_core/clinical_question.py`
- Create: `metawingman/scripts/metawingman_core/synthesis_method_router.py`
- Create: `metawingman/scripts/compile_clinical_question.py`
- Create: `metawingman/scripts/route_synthesis_method.py`
- Create: `tests/test_question_synthesis_engine.py`
- Modify: `metawingman/scripts/metawingman_core/__init__.py`

**Interfaces:**
- Consumes: Task 1 schemas and method registry.
- Produces:
  `compile_clinical_decision_context(raw: dict, *, created_at_utc: str) -> dict`,
  `load_method_registry(path: Path) -> list[dict]`, and
  `enumerate_synthesis_routes(context: dict, candidate: dict, routes: list[dict], *, created_at_utc: str) -> dict`.

- [ ] **Step 1: Write failing compiler and routing tests**

```python
def test_compiler_preserves_raw_wording_and_marks_missing_decision(self) -> None:
    context = compile_clinical_decision_context(
        {"population": "adults with resistant hypertension"},
        created_at_utc=TIMESTAMP,
    )
    self.assertEqual(context["status"], "incomplete")
    self.assertEqual(context["source_anchors"][0]["verbatim"],
                     "adults with resistant hypertension")

def test_router_rejects_network_route_without_connected_comparators(self) -> None:
    decision = enumerate_synthesis_routes(
        context_fixture(), disconnected_network_candidate(), registry(),
        created_at_utc=TIMESTAMP,
    )
    rejected = {item["route_id"]: item for item in decision["rejected_routes"]}
    self.assertIn("network_random_effects", rejected)
    self.assertIn("network_connectivity", rejected["network_random_effects"]["failed_checks"])
```

- [ ] **Step 2: Run the focused tests and verify import failures**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_engine.py" -v
```

Expected: FAIL because `clinical_question` and `synthesis_method_router` are
missing.

- [ ] **Step 3: Implement the context compiler**

```python
class ClinicalQuestionError(ValueError):
    pass

def compile_clinical_decision_context(
    raw: dict[str, object], *, created_at_utc: str
) -> dict[str, object]:
    context = {
        "schema_version": "1.0",
        "context_id": stable_id("clinical-context", raw),
        "stakeholders": string_list(raw.get("stakeholders")),
        "setting": string_list(raw.get("setting")),
        "decision_problem": string_or_empty(raw.get("decision_problem")),
        "candidate_actions": string_list(raw.get("candidate_actions")),
        "time_horizon": string_or_empty(raw.get("time_horizon")),
        "patient_important_outcomes": outcome_list(raw.get("outcomes")),
        "subgroups": string_list(raw.get("subgroups")),
        "equity_factors": string_list(raw.get("equity_factors")),
        "implementation_constraints": string_list(raw.get("constraints")),
        "source_anchors": verbatim_anchors(raw),
        "status": "complete" if required_context_present(raw) else "incomplete",
        "created_at_utc": created_at_utc,
    }
    validate_document(context, "clinical_decision_context")
    return context
```

Normalization must retain the original wording in `source_anchors`; it may not
invent a clinical action or patient-important outcome.

- [ ] **Step 4: Implement deterministic route enumeration**

```python
def enumerate_synthesis_routes(
    context: dict[str, object],
    candidate: dict[str, object],
    routes: list[dict[str, object]],
    *,
    created_at_utc: str,
) -> dict[str, object]:
    compatible, rejected = [], []
    for route in sorted(routes, key=lambda item: str(item["route_id"])):
        failed = run_required_checks(context, candidate, route)
        target = compatible if not failed else rejected
        target.append(route_record(route, failed))
    selected = compatible[0]["route_id"] if len(compatible) == 1 else None
    decision = build_route_decision(candidate, compatible, rejected, selected,
                                    created_at_utc)
    validate_document(decision, "method_route_decision")
    return decision
```

The router enumerates compatibility; it does not choose between several
scientifically plausible routes by arbitrary ordering. Zero compatible routes
must return `status: abstained` with `fallback_route_id: no_pooling` when that
route is admissible.

- [ ] **Step 5: Add JSON-in/JSON-out CLIs, run tests, and commit**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_engine.py" -v
python .\metawingman\scripts\compile_clinical_question.py --help
python .\metawingman\scripts\route_synthesis_method.py --help
git add metawingman/scripts tests/test_question_synthesis_engine.py
git commit -m "feat: compile clinical context and synthesis routes"
```

Expected: focused tests pass and both CLIs exit zero for `--help`.

---

### Task 3: Implement Evidence-Constrained Joint Tree Search

**Files:**
- Create: `metawingman/scripts/metawingman_core/question_synthesis_search.py`
- Modify: `tests/test_question_synthesis_engine.py`
- Modify: `metawingman/scripts/metawingman_core/__init__.py`

**Interfaces:**
- Consumes: clinical context, temporal evidence landscape, Task 2 method-route
  decisions, and existing `topic_opportunity` evidence identifiers.
- Produces:
  `start_question_synthesis_search(...) -> dict`,
  `apply_candidate_mutation(search, mutation, observation, *, updated_at_utc) -> dict`,
  `select_frontier_node(search) -> str`, and
  `finalize_question_portfolio(search, *, updated_at_utc) -> dict`.

- [ ] **Step 1: Write failing deterministic-search tests**

```python
def test_frontier_selection_is_order_invariant(self) -> None:
    first = start_question_synthesis_search(
        landscape(), context_fixture(), list(reversed(seed_candidates())),
        budget_fixture(), created_at_utc=TIMESTAMP,
    )
    second = start_question_synthesis_search(
        landscape(), context_fixture(), seed_candidates(), budget_fixture(),
        created_at_utc=TIMESTAMP,
    )
    self.assertEqual(select_frontier_node(first), select_frontier_node(second))

def test_mutation_cannot_reference_unknown_evidence(self) -> None:
    with self.assertRaises(QuestionSynthesisSearchError):
        apply_candidate_mutation(
            search_fixture(), mutation_fixture(),
            {"evidence_anchor_ids": ["missing-node"]},
            updated_at_utc=TIMESTAMP,
        )
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_engine.py" -v
```

Expected: FAIL on import of `question_synthesis_search`.

- [ ] **Step 3: Implement immutable-style state transitions**

```python
@dataclass(frozen=True)
class SearchBudget:
    max_nodes: int
    max_model_calls: int
    max_verifier_calls: int
    max_rounds: int

ALLOWED_MUTATIONS = {
    "narrow_scope", "broaden_scope", "split_question", "change_comparator",
    "change_outcome", "change_time_horizon", "change_design",
    "switch_review_family", "switch_synthesis_route", "request_evidence",
    "reject_duplicate", "abstain_no_pooling",
}

def apply_candidate_mutation(search, mutation, observation, *, updated_at_utc):
    candidate = copy.deepcopy(search)
    assert_budget_available(candidate)
    assert_known_evidence(candidate, observation["evidence_anchor_ids"])
    assert_allowed_mutation(mutation["type"])
    append_node_and_edge(candidate, mutation, observation)
    candidate["updated_at_utc"] = updated_at_utc
    validate_document(candidate, "question_synthesis_search")
    return candidate
```

Every edge stores parent, child, mutation type, actor capability, provider/model
receipt identifier, verifier observations, and reason for retention or pruning.

- [ ] **Step 4: Implement risk-adaptive frontier allocation**

```python
def frontier_priority(node: dict[str, object], parent_visits: int,
                      exploration_weight: float) -> tuple[float, str]:
    verified_value = float(node["verified_objective_sum"])
    impact = float(node["downstream_impact"])
    uncertainty = float(node["uncertainty"])
    visits = int(node["visits"])
    exploration = exploration_weight * uncertainty * math.sqrt(parent_visits + 1) / (visits + 1)
    return (verified_value + impact + exploration, str(node["candidate_id"]))
```

Use the candidate identifier only as a deterministic tie-break. Hard-failed or
leakage-failed nodes are never selected, regardless of model preference.

- [ ] **Step 5: Run tests and commit the search kernel**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_engine.py" -v
git add metawingman/scripts/metawingman_core tests/test_question_synthesis_engine.py
git commit -m "feat: add evidence constrained question search"
```

Expected: all joint-search invariance, budget, leakage, and abstention tests pass.

---

### Task 4: Add Typed Proposer, Opposition, Judge, and External Verifiers

**Files:**
- Create: `metawingman/scripts/metawingman_core/question_synthesis_agents.py`
- Create: `metawingman/scripts/metawingman_core/question_synthesis_verifier.py`
- Create: `metawingman/scripts/design_review_question.py`
- Modify: `tests/test_question_synthesis_engine.py`
- Modify: `metawingman/scripts/metawingman_core/__init__.py`

**Interfaces:**
- Consumes: `ModelProvider.chat(...) -> ProviderResult`, Task 3 search state,
  existing temporal landscape, existing schema guard, and Task 2 method router.
- Produces:
  `run_question_role(provider, role, payload, *, model, max_tokens) -> dict`,
  `verify_question_candidate(candidate, landscape, route_decision) -> list[dict]`,
  and `design_review_question(...) -> dict`.

- [ ] **Step 1: Write failing mock-provider and verifier tests**

```python
def test_model_self_score_is_discarded(self) -> None:
    provider = FixtureProvider({"candidate": candidate_payload(), "score": 0.99})
    result = run_question_role(provider, "proposer", proposer_input(),
                               model="fixture", max_tokens=800)
    self.assertNotIn("score", result)

def test_judge_cannot_select_candidate_with_failed_route(self) -> None:
    with self.assertRaises(QuestionSynthesisVerificationError):
        design_review_question(
            provider=judge_fixture_provider(), landscape=landscape(),
            context=context_fixture(), routes=registry(),
            budget=budget_fixture(), created_at_utc=TIMESTAMP,
        )
```

- [ ] **Step 2: Run tests and confirm missing-module failures**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_engine.py" -v
```

Expected: FAIL because agent and verifier modules do not exist.

- [ ] **Step 3: Implement one schema-gated role runner**

```python
ROLE_OUTPUT_SCHEMA = {
    "proposer": "question_synthesis_candidate",
    "opposition": "scientific_action",
    "judge": "scientific_action",
    "evolver": "question_synthesis_candidate",
}

def run_question_role(provider, role, payload, *, model, max_tokens):
    result = provider.chat(
        role_messages(role, payload), model=model, max_tokens=max_tokens,
        json_output=True,
    )
    document = parse_single_json_object(result.content)
    document.pop("score", None)
    validate_document(document, ROLE_OUTPUT_SCHEMA[role])
    return {"document": document, "provider_receipt": result.audit_record()}
```

Permit one bounded schema-repair call through the existing structured-candidate
pattern. A second failure returns an abstention; it does not accept malformed
output.

- [ ] **Step 4: Implement verifier observations and orchestration**

```python
VERIFIERS = (
    verify_evidence_anchor_identity,
    verify_temporal_cutoff,
    verify_review_family_compatibility,
    verify_estimand_completeness,
    verify_synthesis_route,
    verify_overlap_and_active_protocols,
    verify_access_and_extractability,
)

def verify_question_candidate(candidate, landscape, route_decision):
    observations = [fn(candidate, landscape, route_decision) for fn in VERIFIERS]
    return sorted(observations, key=lambda item: item["verifier_id"])
```

`design_review_question` runs proposer, verifier, opposition, verifier, and judge
rounds under the search budget. The judge may retain only candidates whose hard
checks pass; unresolved high-impact disagreement produces `abstained` or
`reserve`, never silent acceptance.

- [ ] **Step 5: Add CLI tests, run focused tests, and commit**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_engine.py" -v
python .\metawingman\scripts\design_review_question.py --help
git add metawingman/scripts tests/test_question_synthesis_engine.py
git commit -m "feat: orchestrate evidence grounded question design"
```

Expected: fixture-provider runs are deterministic, receipts omit credentials and
response content, and failed verifiers block selection.

---

### Task 5: Build the Sealed AI-Only Benchmark and Open-Rubric Metrics

**Files:**
- Create: `metawingman/schemas/question_synthesis_benchmark_case.schema.json`
- Create: `metawingman/scripts/metawingman_core/question_synthesis_evaluator.py`
- Create: `metawingman/scripts/evaluate_question_synthesis.py`
- Create: `tests/test_question_synthesis_benchmark.py`
- Modify: `metawingman/scripts/metawingman_core/__init__.py`

**Interfaces:**
- Consumes: frozen benchmark material manifests, Task 4 portfolio output, and
  existing topic leakage checks.
- Produces:
  `validate_benchmark_case(case: dict) -> None`,
  `evaluate_question_portfolio(case: dict, run: dict, rubric: dict) -> dict`, and
  `aggregate_question_benchmark(reports: list[dict]) -> dict`.

- [ ] **Step 1: Write failing sealing and metric tests**

```python
def test_case_rejects_target_identifier_in_visible_material(self) -> None:
    case = benchmark_case_fixture()
    case["visible_material"][0]["text"] += " " + case["sealed_target"]["doi"]
    with self.assertRaises(QuestionSynthesisBenchmarkError):
        validate_benchmark_case(case)

def test_critical_error_scores_below_abstention(self) -> None:
    rubric = {"correct": 1.0, "abstain": 0.4, "critical_error": -2.0}
    wrong = score_open_rubric("critical_error", rubric)
    abstain = score_open_rubric("abstain", rubric)
    self.assertLess(wrong, abstain)
```

- [ ] **Step 2: Run tests and verify missing benchmark contracts**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_benchmark.py" -v
```

Expected: FAIL because schema and evaluator are missing.

- [ ] **Step 3: Implement the sealed benchmark case**

```json
{
  "required": [
    "schema_version", "case_id", "review_family_id", "cutoff_at_utc",
    "visible_material", "sealed_target", "published_reference",
    "leakage_patterns", "loss_rubric", "split", "status"
  ],
  "split_enum": ["development", "calibration", "held_out", "prospective"],
  "status_enum": ["draft", "sealed", "invalidated"]
}
```

`validate_benchmark_case` scans visible text, identifiers, filenames, graph
nodes, source-family links, and descendants. It rejects post-cutoff timestamps
and any held-out case whose family intersects development or calibration.

- [ ] **Step 4: Implement direct and selective metrics**

```python
def score_open_rubric(outcome: str, rubric: dict[str, float]) -> float:
    return float(rubric[outcome])

def selective_curve(rows: list[dict[str, object]]) -> list[dict[str, float]]:
    ordered = sorted(rows, key=lambda row: (-float(row["confidence"]), str(row["case_id"])))
    return [coverage_risk_prefix(ordered, end) for end in range(1, len(ordered) + 1)]
```

Report top-K coherent opportunity recovery, route validity, critical false
exclusion, unsupported anchors/values/lineage/claims, abstention, repeated-run
pass rate, first-divergence stage, wall time, tokens, provider cost, CPU/GPU
time, peak memory, and storage growth. Match ablations by case set and declared
budget.

- [ ] **Step 5: Add CLI, run tests, and commit**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_benchmark.py" -v
python .\metawingman\scripts\evaluate_question_synthesis.py --help
git add metawingman/schemas metawingman/scripts tests/test_question_synthesis_benchmark.py
git commit -m "feat: add sealed question synthesis benchmark"
```

Expected: all leakage fixtures fail closed and all metric fixtures pass.

---

### Task 6: Connect the Selected Design to One Persistent Review Case State

**Files:**
- Create: `metawingman/schemas/review_case_state.schema.json`
- Create: `metawingman/schemas/scientific_reflection.schema.json`
- Create: `metawingman/scripts/metawingman_core/review_case.py`
- Create: `metawingman/scripts/metawingman_core/reflection_engine.py`
- Create: `tests/test_review_case_loop.py`
- Modify: `metawingman/scripts/init_review.py`
- Modify: `metawingman/scripts/metawingman_core/__init__.py`

**Interfaces:**
- Consumes: selected Task 4 candidate, existing `EventLedger`,
  `atomic_write_json`, provenance nodes/edges, document state, appraisal,
  analysis, claim, and living-update records.
- Produces:
  `initialize_review_case(project: Path, candidate: dict, *, created_at_utc: str) -> dict`,
  `transition_review_case(project: Path, action: dict, observation: dict, *, updated_at_utc: str) -> dict`, and
  `reflect_on_assertion(project: Path, reflection: dict, verifiers: dict[str, Callable]) -> dict`.

- [ ] **Step 1: Write failing transition and reflection tests**

```python
def test_case_cannot_skip_protocol_gate(self) -> None:
    with self.assertRaises(ReviewCaseError):
        transition_review_case(
            project_fixture(), analysis_action(), verified_observation(),
            updated_at_utc=TIMESTAMP,
        )

def test_reflection_without_external_observation_cannot_change_state(self) -> None:
    report = reflect_on_assertion(
        project_fixture(), reflection_fixture(external_tests=[]), {},
    )
    self.assertEqual(report["disposition"], "abstained")
    self.assertFalse(report["state_changed"])
```

- [ ] **Step 2: Run tests and verify missing state modules**

```powershell
python -m unittest discover -s tests -p "test_review_case_loop.py" -v
```

Expected: FAIL because review-case schemas and modules do not exist.

- [ ] **Step 3: Implement the persistent case contract and transitions**

```python
STAGE_ORDER = (
    "topic", "protocol", "search", "screening", "documents", "extraction",
    "appraisal", "analysis", "certainty", "writing", "review", "living",
)

def transition_review_case(project, action, observation, *, updated_at_utc):
    state = read_case_state(project)
    require_current_revision(action, state)
    require_stage_gate(state, action["stage"])
    require_valid_observation(action, observation)
    next_state = apply_observation(copy.deepcopy(state), action, observation)
    next_state["revision"] += 1
    next_state["updated_at_utc"] = updated_at_utc
    validate_document(next_state, "review_case_state")
    atomic_write_json(case_path(project), next_state, "review_case_state")
    append_case_event(project, state, next_state, action, observation)
    return next_state
```

The schema must hold active stage/gate, selected joint design, protocol hash,
record-report-study-arm-result-estimand-synthesis-certainty-claim node IDs,
unresolved conflicts, abstentions, pending permissions, budget, and revision.

- [ ] **Step 4: Implement source/tool reflection**

```python
def reflect_on_assertion(project, reflection, verifiers):
    observations = []
    for test in reflection["external_tests"]:
        verifier = verifiers.get(test["verifier_id"])
        if verifier is None:
            return abstained_reflection(reflection, "verifier_unavailable")
        observations.append(verifier(test))
    disposition = decide_reflection_disposition(reflection, observations)
    return persist_reflection(project, reflection, observations, disposition)
```

Initial verifiers wrap identifier/source resolution, evidence-span recovery,
schema validation, report-study-result lineage, effect recalculation, R adapter
execution, and authority/profile checks. Model agreement alone cannot satisfy an
external test.

- [ ] **Step 5: Extend scaffolding, run tests, and commit**

```powershell
python -m unittest discover -s tests -p "test_review_case_loop.py" -v
python -m unittest discover -s tests -v
git add metawingman tests/test_review_case_loop.py
git commit -m "feat: add persistent evidence grounded review case"
```

Expected: old workflow fixtures still pass and the new case cannot skip gates or
mutate state through unsupported reflection.

---

### Task 7: Export and Train Bounded Ranker, Verifier, and Routing Components

**Files:**
- Create: `metawingman/schemas/question_synthesis_training_example.schema.json`
- Create: `metawingman/scripts/prepare_question_synthesis_training.py`
- Create: `metawingman/scripts/train_question_synthesis_component.py`
- Create: `tests/test_question_synthesis_training.py`
- Modify: `metawingman/scripts/metawingman_core/training_corpus.py`
- Modify: `metawingman/schemas/component_training_job.schema.json`
- Modify: `metawingman/references/dependencies/python-training.lock.txt`

**Interfaces:**
- Consumes: sealed Task 5 cases, Task 4 trajectories, Task 6 verifier
  observations, current training-document manifests, and family registry.
- Produces:
  `export_question_synthesis_examples(...) -> dict`,
  component job types `question_method_ranker`, `source_support_verifier`, and
  `risk_cost_router`, and content-addressed metrics/checkpoint receipts.

- [ ] **Step 1: Write failing family/time split and label tests**

```python
def test_export_rejects_family_cross_split(self) -> None:
    with self.assertRaises(TrainingCorpusError):
        export_question_synthesis_examples(
            cases=[development_case("family-a"), heldout_case("family-a")],
            trajectories=trajectory_fixtures(), created_at_utc=TIMESTAMP,
        )

def test_published_decision_is_not_named_gold(self) -> None:
    manifest = export_question_synthesis_examples(
        cases=[development_case("family-a")],
        trajectories=trajectory_fixtures(), created_at_utc=TIMESTAMP,
    )
    self.assertEqual({row["label_authority"] for row in manifest["examples"]},
                     {"published_reference"})
```

- [ ] **Step 2: Run tests and verify missing export failures**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_training.py" -v
```

Expected: FAIL because the schema and exporter do not exist.

- [ ] **Step 3: Implement frozen training examples and hard negatives**

```python
COMPONENT_TASKS = {
    "question_method_ranker": "pairwise_preference",
    "source_support_verifier": "binary_with_abstention",
    "risk_cost_router": "bounded_loss_policy",
}

def export_question_synthesis_examples(cases, trajectories, *, created_at_utc):
    assert_family_and_temporal_isolation(cases)
    examples = build_published_reference_positives(cases, trajectories)
    examples += build_profile_estimand_method_hard_negatives(cases)
    examples += build_unsupported_anchor_negatives(trajectories)
    return freeze_training_export(examples, created_at_utc)
```

Hard negatives must identify the violated rule: wrong review family, incompatible
effect measure, unidentifiable estimand, disconnected network, threshold/time
mismatch, duplicate topic, unsupported source span, or report-study-result
lineage break. Do not create negatives by random label flipping.

- [ ] **Step 4: Implement validate-only component jobs before training**

```python
def build_component(job, model, tokenizer, train_rows, eval_rows):
    if job["component_type"] == "risk_cost_router":
        return build_calibrated_sklearn_router(job, train_rows, eval_rows)
    return build_transformer_cross_encoder(job, model, tokenizer,
                                           train_rows, eval_rows)
```

Use the existing immutable model revision and training locks for the two
cross-encoders unless a separately frozen job changes them. The router consumes
task/profile/risk/uncertainty/cost features and selects a bounded action budget;
it cannot emit a scientific decision.

- [ ] **Step 5: Run validate-only jobs, tests, and commit**

```powershell
python -m unittest discover -s tests -p "test_question_synthesis_training.py" -v
python .\metawingman\scripts\prepare_question_synthesis_training.py --help
python .\metawingman\scripts\train_question_synthesis_component.py --help
git add metawingman tests/test_question_synthesis_training.py
git commit -m "feat: prepare bounded question synthesis training"
```

Expected: fixture jobs validate without downloading a model, all split/hash
checks pass, and normal training remains blocked until server preflight is ready.

---

### Task 8: Make the Server Runtime Reproducible and Run the First Matched-Cost Pilot

**Files:**
- Create: `scripts/server/preflight_mainline.py`
- Modify: `docs/architecture/server-mainline-runbook.md`
- Modify: `docs/architecture/compute-and-deployment-budget.md`
- Modify: `docs/architecture/server-training-runbook.md`
- Modify: `metawingman/SKILL.md`
- Modify: `README.md`
- Modify: `tests/test_skill_distribution.py`
- Modify: `tests/test_system_coverage_and_acquisition.py`

**Interfaces:**
- Consumes: verified source checkout, current `server-training-handoff-v3`, Tasks
  1-7 code, dependency locks, GPU/driver inspection, the validated
  `deepseek-v4-flash` provider config, and lawful source credentials. Codex is
  the interactive development and review host; it is not a required server API.
- Produces: `server-mainline-preflight.json`, content-addressed run directories,
  matched-cost benchmark reports, and rebuilt skill artifacts.

- [ ] **Step 1: Write failing preflight and distribution tests**

```python
def test_mainline_preflight_requires_separate_data_and_run_roots(self) -> None:
    report = inspect_mainline_server(server_fixture(shared_root=True))
    self.assertFalse(report["ready"])
    self.assertIn("data_run_root_collision", report["blocking_findings"])

def test_distributed_skill_mentions_joint_question_method_design(self) -> None:
    text = (ROOT / "metawingman" / "SKILL.md").read_text(encoding="utf-8")
    self.assertIn("clinical question", text.lower())
    self.assertIn("synthesis route", text.lower())
```

- [ ] **Step 2: Run focused tests and verify missing preflight failures**

```powershell
python -m unittest discover -s tests -p "test_skill_distribution.py" -v
python -m unittest discover -s tests -p "test_system_coverage_and_acquisition.py" -v
```

Expected: FAIL because the new preflight and skill behavior are absent.

- [ ] **Step 3: Implement fail-closed server inspection**

```python
REQUIRED_ROOTS = ("source_root", "corpus_root", "cache_root", "run_root",
                  "checkpoint_root", "receipt_root")

def inspect_mainline_server(config):
    findings = []
    findings += inspect_distinct_resolved_roots(config, REQUIRED_ROOTS)
    findings += inspect_free_space(config)
    findings += inspect_git_and_bundle_hashes(config)
    findings += inspect_python_r_and_packages(config)
    findings += inspect_nvidia_driver_and_gpus(config)
    findings += inspect_secret_capabilities_without_values(config)
    return build_preflight_report(config, findings)
```

The report records GPU model/count/VRAM, CPU count, RAM, free disk, driver/CUDA,
Python/R/package versions, bundle hashes, source-access capabilities, and
provider capability receipts. It never records secret values.

- [ ] **Step 4: Freeze server paths and execute the pilot in this order**

```bash
python scripts/server/preflight_mainline.py --config /srv/metawingman/config/mainline.json --output /srv/metawingman/receipts/preflight.json
python metawingman/scripts/preflight_component_training.py validation-output/server-training-handoff-v3/validation-output/training-corpus/jobs/section-role.json --root validation-output/server-training-handoff-v3 --inspect-server
python metawingman/scripts/preflight_component_training.py validation-output/server-training-handoff-v3/validation-output/training-corpus/jobs/evidence-retrieval.json --root validation-output/server-training-handoff-v3 --inspect-server
python -m unittest discover -s tests -v
python metawingman/scripts/test_r_adapters.py metawingman
python metawingman/scripts/design_review_question.py --config /srv/metawingman/config/pilot.json
python metawingman/scripts/evaluate_question_synthesis.py --plan /srv/metawingman/config/pilot-benchmark.json
```

Begin with the five matched-cost configurations defined by the spec. Run three
independent seeds per case for the development pilot, then freeze calibration
and held-out execution commands before inspecting held-out outputs. Start the
bounded training jobs only after their `--validate-only` checks and server
preflight both report ready.

- [ ] **Step 5: Rebuild the skill and run complete verification**

```powershell
python -m unittest discover -s .\tests -v
python .\metawingman\scripts\test_r_adapters.py .\metawingman
python .\scripts\build_skill_bundle.py
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_dependency_locks.py
git diff --check
git status --short --branch
```

Expected: all Python and R tests pass, canonical and distributed skill hashes
match, dependency locks validate, and Git contains only reviewed source and
documentation changes.

- [ ] **Step 6: Commit the server-ready vertical slice**

```powershell
git add scripts/server docs/architecture metawingman README.md tests
git commit -m "feat: complete question synthesis server vertical slice"
```

Do not push, publish checkpoints, upload raw full text, or change remote settings
without a separate explicit authorization.

---

## Program Gates After the First Pilot

- **P0 complete:** Tasks 1, 2, and 5 pass with at least one sealed development,
  calibration, and held-out fixture per implemented review family.
- **P1 complete:** Tasks 3 and 4 beat the direct-model and current topic-only
  baselines on the frozen joint-design loss without increasing critical errors.
- **P2 complete:** Task 6 replays a complete review case with source-linked
  lineage and deterministic R results, including a justified no-pooling case.
- **P3 complete:** Tasks 7 and 8 show matched-cost gains for at least one bounded
  learned component and preserve held-out selective risk under repeated runs.

Failure at a gate narrows the supported review-family capability matrix. It does
not trigger a broader autonomy claim or an unregistered metric change.
