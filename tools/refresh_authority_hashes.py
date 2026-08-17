"""Refresh domain-pack hashes end to end.

Updates, iteratively until stable:
1. authority_sources[].content_sha256 (LF-normalized file bytes, so the
   value is identical on CRLF/Windows and LF/Linux working trees);
2. dependencies[].version / content_sha256 references between packs;
3. each pack's top-level content_sha256.

Run after editing any authority source file or any pack manifest.

Usage: python tools/refresh_authority_hashes.py
"""
import glob
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "metawingman" / "scripts"))

from metawingman_core.biomedical_domain import pack_content_sha256  # noqa: E402

SKILL_ROOT = pathlib.Path("metawingman")


def lf_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> None:
    paths = [pathlib.Path(p) for p in glob.glob("metawingman/references/domain-packs/*.json")]
    packs = {p: json.loads(p.read_text(encoding="utf-8")) for p in paths}
    by_id = {data["pack_id"]: data for data in packs.values()}
    dirty: set[pathlib.Path] = set()

    for _round in range(6):
        changed_any = False
        for path, data in packs.items():
            changed = False
            for authority in data.get("authority_sources", []):
                target = (SKILL_ROOT / authority["path"]).resolve()
                expected = lf_hash(target)
                if authority.get("content_sha256") != expected:
                    authority["content_sha256"] = expected
                    changed = True
                    print(f"{path.name}: authority {authority['source_id']} -> {expected}")
            for dependency in data.get("dependencies", []):
                target = by_id.get(dependency["pack_id"])
                if target is None:
                    continue
                if dependency.get("version") != target["version"]:
                    dependency["version"] = target["version"]
                    changed = True
                if dependency.get("content_sha256") != target["content_sha256"]:
                    dependency["content_sha256"] = target["content_sha256"]
                    changed = True
                    print(f"{path.name}: dependency {dependency['pack_id']} -> {target['content_sha256']}")
            top_hash = pack_content_sha256(data)
            if data.get("content_sha256") != top_hash:
                data["content_sha256"] = top_hash
                changed = True
                print(f"{path.name}: pack content_sha256 -> {top_hash}")
            if changed:
                dirty.add(path)
                changed_any = True
        if not changed_any:
            break

    for path in dirty:
        path.write_text(json.dumps(packs[path], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"refreshed {len(dirty)} pack file(s)")

    # Sync the frozen capability matrix inventory with the live packs.
    matrix_path = pathlib.Path("metawingman/references/system-capability-matrix.json")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    inventory = matrix["biomedical_coverage"]["pack_inventory"]
    live_by_id = {data["pack_id"]: data for data in packs.values()}
    matrix_changed = False
    for entry in inventory:
        live = live_by_id.get(entry["pack_id"])
        if live is None:
            continue
        if entry.get("version") != live["version"]:
            entry["version"] = live["version"]
            matrix_changed = True
        if entry.get("content_sha256") != live["content_sha256"]:
            entry["content_sha256"] = live["content_sha256"]
            matrix_changed = True
        frozen_authorities = [
            {
                "source_id": item["source_id"],
                "version": item["version"],
                "content_sha256": item["content_sha256"],
            }
            for item in live["authority_sources"]
        ]
        if entry.get("authority_versions") != frozen_authorities:
            entry["authority_versions"] = frozen_authorities
            matrix_changed = True
        if matrix_changed:
            print(f"matrix: synced inventory entry {entry['pack_id']}")
    if matrix_changed:
        matrix_path.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("matrix refreshed")


if __name__ == "__main__":
    main()
