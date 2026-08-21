# Repository scripts

Root-level scripts maintain the repository and its distributions. Scientific
workflow entry points live under `metawingman/scripts/`.

## Common commands

| Task | Command |
|---|---|
| Refresh README metrics | `python scripts/update_readme.py` |
| Check README drift and links | `python scripts/update_readme.py --check` |
| Build generated Skill bundles | `python scripts/build_skill_bundle.py` |
| Verify a generated bundle | `python scripts/verify_skill_bundle.py .agents/skills/metawingman` |
| Verify dependency locks | `python scripts/verify_dependency_locks.py` |
| Build a deterministic release | `python scripts/build_release.py` |

`scripts/server/` contains server inventory and real document-pilot entry
points. Run their validate-only or preflight path before any remote mutation.

Generated bundles under `.agents/skills/` and `plugins/` must be rebuilt from
the canonical `metawingman/` and `toolkit/` sources. Do not hand-edit generated
copies.
