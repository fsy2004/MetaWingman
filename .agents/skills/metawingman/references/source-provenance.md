# Bundled source provenance

The bundled R toolkit and executable adapters were migrated before retiring the former desktop applications.

| Component | Source project at migration | Source commit | Included path |
|---|---|---|---|
| Core and extended R modules | Meta Wingman `toolkit/R` | Meta Wingman `d826b61ceaa1f5f9d762f9b428ac7f43ce026183` | repository `toolkit/R` |
| Canonical method documentation and examples | `meta-analysis-toolkit` | `3af629d67be43b6010f364f5eb80ef9905d3cab1` | repository `toolkit/docs`, `toolkit/examples` |
| Command-line analysis adapters and example data | Meta Wingman `adapters/meta` | Meta Wingman `d826b61ceaa1f5f9d762f9b428ac7f43ce026183` | `scripts/r/adapters` |
| Legacy method manifests and input schemas | Meta Wingman `manifests` | Meta Wingman `d826b61ceaa1f5f9d762f9b428ac7f43ce026183` | `scripts/r/manifests` |

The former GUI, theme, installer, and desktop-launcher code was intentionally not migrated. The analysis source is MIT licensed; statistical packages and appraisal instruments retain their own licenses. Cite the packages and methods actually used.

Legacy manifests are discovery aids, not scientific authority. Some contain historical text-encoding damage. Validate the executable adapter, input schema, package availability, and output on representative data before calling a method turnkey.

Migration validation ran all 61 manifests against their declared example inputs. The first pass found four Windows-specific failures; this skill fixes UTF-8 CSV reading without locale translation and replaces unsupported plotmath Unicode labels in the E-value figure. Targeted reruns passed all four. Use `scripts/test_r_adapters.py` after R/package changes to refresh the evidence.
