# Reproducible Training Corpus and Training Paradigm

Status: local v2 biomedical planning, pair export, component jobs, and metadata-only server handoff implemented; model training and scientific validation have not started.
Last checked: 2026-08-15

## Purpose

MetaWingman needs trainable components, but the Agent is not reduced to one fine-tuned model. Training is reserved for bounded capabilities such as section-role classification, evidence retrieval, screening candidates, structured extraction, routing, and critique. Protocol gates, evidence lineage, deterministic calculations, provenance, abstention, and final scientific responsibility remain explicit system controls.

The first corpus is a reproducible development dataset, not a held-out benchmark. Top-journal publication is a sampling stratum, not a quality label or model feature. Published text supplies source evidence; deterministic or model-generated labels remain weak supervision until independently verified.

## Immutable Layers

1. `T0 intake`: the Europe PMC metadata corpus and provisional review-family registry, each bound by SHA-256.
2. `T1 plan`: deterministic journal-balanced sampling with a fixed seed and review-family-level train/development assignment. Held-out assignment is disabled.
3. `T2 source`: article-level license and retraction checks, then OA PDF and JATS XML retrieval over public HTTPS with final URLs, sizes, and hashes.
4. `T3 deterministic weak labels`: section-heading rules create evidence-anchored classification and retrieval candidates. These are explicitly not gold labels.
5. `T4 model candidates`: DeepSeek or another provider may propose richer labels through the external schema-gated batch runtime. Provider output remains candidate-only and cannot replace `T3` or create accepted labels by itself.
6. `T5 verified labels`: future independently checked examples may support model selection or a sealed benchmark. Review-family and temporal contamination audits are required before promotion.

PMC's OA Web Service is used for article-level license and retraction status. Europe PMC REST supplies OA PDF links and JATS XML. The implementation follows the official [PMC OA Web Service](https://pmc.ncbi.nlm.nih.gov/tools/oa-service/) and [Europe PMC REST API](https://europepmc.org/RestfulWebService). Availability is checked at execution time because OA locations and distribution infrastructure can change.

An existing artifact is reused only when the plan hash, record/family/split identity, byte count, and SHA-256 all match the local manifest. Use `fetch_training_corpus.py --refresh` to ignore this content-addressed cache and recheck current remote license and source state.

## Reproducible Commands

```powershell
# 1. Freeze a family-isolated training/development plan.
python .\metawingman\scripts\plan_training_corpus.py `
  --corpus .\research\top-journal-training-corpus.json `
  --families .\research\top-journal-review-family-registry.json `
  --out .\research\training-corpus-plan-v1.json `
  --maximum-records 24 --seed 20260815 `
  --created-at-utc 2026-08-15T00:00:00Z

# 2. Retrieve OA PDF/XML and produce an immutable document manifest.
python .\metawingman\scripts\fetch_training_corpus.py `
  .\research\training-corpus-plan-v1.json `
  --out .\validation-output\training-corpus\documents `
  --max-file-bytes 41943040 --max-total-bytes 524288000

# 3. Build source-anchored examples and freeze the model-neutral run plan.
python .\metawingman\scripts\freeze_training_dataset.py `
  .\validation-output\training-corpus\documents\training-document-manifest.json `
  --artifact-root .\validation-output\training-corpus\documents `
  --examples-out .\validation-output\training-corpus\training-examples.jsonl `
  --run-plan-out .\validation-output\training-corpus\training-run-plan.json

# 4. Audit files, hashes, family isolation, anchors, and counts.
python .\metawingman\scripts\audit_training_dataset.py `
  --plan .\research\training-corpus-plan-v1.json `
  --manifest .\validation-output\training-corpus\documents\training-document-manifest.json `
  --examples .\validation-output\training-corpus\training-examples.jsonl `
  --run-plan .\validation-output\training-corpus\training-run-plan.json `
  --artifact-root .\validation-output\training-corpus\documents

# 5. Export provider-neutral training files.
python .\metawingman\scripts\export_training_splits.py `
  .\validation-output\training-corpus\training-examples.jsonl `
  --out .\validation-output\training-corpus\exports
```

## Current Pilot

The frozen v1 plan selects 24 provisional families from 2,331 eligible OA development records across 16 journals: 19 train and 5 development records. The first live retrieval produced 16 PDF+XML documents, 7 XML-only documents, and one rejected record whose current article-level license was `none`. The 39 accepted source artifacts contain 219 PDF pages, about 1.04 million native-PDF characters, and about 1.51 million JATS characters.

Deterministic section labeling produced 172 weak-supervision examples from 19 documents: 160 train and 12 development examples. The development set is too small for a performance claim. It is adequate for pipeline debugging, schema calibration, and estimating the cost of the next scale-up.

A three-document DeepSeek annotation pilot tested the optional `T4` layer. On the second frozen replay, all three tasks returned schema-valid candidates in four provider calls using 10,254 observed tokens. Six of eight proposed annotations contained an exact source excerpt; two paraphrased the source and were rejected by `verify_training_annotations.py`. This is development evidence for the abstention and verifier boundary, not annotation-accuracy evidence. None of the model candidates is gold or admitted to the frozen SFT export.

The biomedical v2 metadata plan selects 2,048 of 2,331 eligible OA records with 2,040 review families, 12 title-resolved primary specialties, and 108 composite sampling strata. No family crosses train/development. About 69% fall back to `general-medicine`, which is an explicit limitation of title-only weak classification, not evidence of specialty resolution accuracy.

The local 172-example pilot produced 331 retrieval pairs: 86 source-anchored positives and 245 candidate hard negatives from the same split and medical neighborhood but a different report and review family. Both component jobs bind the model, tokenizer, input data, pair set, runtime lock, output path, and checkpoint policy. Output and checkpoint hashes are created only by the execution receipt after a real run. Offline preflight has no scientific or data-integrity blocker; server hardware, CUDA, and exact package compatibility remain pending.

The current metadata-only handoff is generated under `validation-output/server-training-handoff-v2/`; see [server-training-runbook.md](server-training-runbook.md). A strict member allowlist, whole-manifest secret scan, and member/hash semantic validator exclude raw full text, credentials, archives, private-key material, databases, and checkpoints. The handoff does not authorize server execution.

## Training Sequence

1. Start with a small encoder or LoRA adapter for section-role classification and evidence retrieval. Do not train a foundation model from scratch.
2. Mine hard negatives only within the same frozen split, excluding the same report, review family, exact source span, and likely companion reports. The v2 export keeps these as candidate negatives rather than gold labels.
3. Add schema-constrained SFT for protocol, screening, extraction, and appraisal candidates only after independently checked labels and abstention examples exist.
4. Use preference optimization only with versioned, independently verified proposal-opposition pairs. Model self-preference is not a valid label.
5. Select checkpoints on development families and aggregate uncertainty by review family. Never tune on sealed reconstruction families.
6. Evaluate trained components inside the full Agent against direct prompting, generic RAG, and full MetaWingman ablations. Component accuracy does not establish end-to-end scientific validity.

## Promotion Gates

- No training run starts until the base model, revision, tokenizer, model license, document-license use, and redistribution policy are recorded.
- No weak label becomes gold because DeepSeek or another model agrees with it.
- No held-out set is created from the provisional family registry. Identifier, update-lineage, correction/retraction, and temporal audits must pass first.
- Journal, citation count, and venue prestige cannot enter model inputs or targets.
- Raw copyrighted or restricted text is never committed to Git or shipped in the standalone skill.
- A trained model must preserve evidence anchors, abstention, deterministic verification, and workflow gates; it cannot directly mutate accepted scientific state.
