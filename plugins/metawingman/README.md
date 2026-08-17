# MetaWingman plugin

This is the skills-only Codex plugin distribution of MetaWingman. Build its skill payload from the repository root with:

```powershell
python -X utf8 .\scripts\build_skill_bundle.py
```

The generated `skills/metawingman/release-manifest.json` pins every bundled file hash. Edit the canonical `metawingman/` and `toolkit/` sources, never the generated payload.

No model provider, credential, hosted service, or MCP server is enabled by the plugin itself. Database logins remain user-controlled handoffs and secrets never belong in the plugin or review project.
