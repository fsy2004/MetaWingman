#!/usr/bin/env python3
"""Generate deterministic SPDX SBOM and unsigned in-toto provenance for a skill ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _python_packages(bundle: Path) -> list[dict[str, str]]:
    packages: dict[str, str] = {}
    dependency_dir = bundle / "references/dependencies"
    for lock in sorted(dependency_dir.glob("python-*.lock.txt")):
        for line_number, raw in enumerate(lock.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = PIN.fullmatch(line)
            if not match:
                raise ValueError(f"{lock}:{line_number}: invalid exact dependency pin")
            name, version = match.groups()
            key = name.casefold().replace("_", "-")
            if key in packages and packages[key] != version:
                raise ValueError(f"conflicting Python dependency pin: {name}")
            packages[key] = version
    return [{"name": name, "version": packages[name], "ecosystem": "pypi"} for name in sorted(packages)]


def _r_packages(bundle: Path) -> list[dict[str, str]]:
    lock = json.loads((bundle / "references/dependencies/r-packages.lock.json").read_text(encoding="utf-8"))
    return [
        {"name": name, "version": version, "ecosystem": "cran"}
        for name, version in sorted(lock["packages"].items(), key=lambda item: item[0].casefold())
    ]


def generate_metadata(bundle: Path, archive: Path, output_dir: Path) -> dict[str, Any]:
    bundle = bundle.resolve()
    archive = archive.resolve()
    output_dir = output_dir.resolve()
    manifest = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    archive_sha = sha256(archive)
    version = str(manifest["bundle_version"])
    expected_archive = f"metawingman-skill-{version}.zip"
    if archive.name != expected_archive:
        raise ValueError(f"archive name must match bundle version: {expected_archive}")
    with zipfile.ZipFile(archive) as handle:
        members = sorted(item.filename for item in handle.infolist() if not item.is_dir())
    expected_members = sorted(f"metawingman/{item['path']}" for item in manifest["files"])
    expected_members.extend(["metawingman/.metawingman-generated", "metawingman/release-manifest.json"])
    if members != sorted(expected_members):
        raise ValueError("archive members do not match release manifest plus generated control files")

    dependencies = _python_packages(bundle) + _r_packages(bundle)
    package_entries = []
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package-MetaWingman"}]
    for index, dependency in enumerate(dependencies, start=1):
        spdx_id = f"SPDXRef-Dependency-{index:03d}"
        package_entries.append({
            "SPDXID": spdx_id,
            "name": dependency["name"],
            "versionInfo": dependency["version"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "externalRefs": [{
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:{dependency['ecosystem']}/{dependency['name']}@{dependency['version']}",
            }],
        })
        relationships.append({
            "spdxElementId": "SPDXRef-Package-MetaWingman",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": spdx_id,
        })
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": archive.name,
        "documentNamespace": f"https://metawingman.local/spdx/{archive_sha}",
        "creationInfo": {
            "creators": ["Tool: MetaWingman-generate_release_metadata.py-1.0"],
            "created": "2020-01-01T00:00:00Z",
            "comment": "Deterministic timestamp; artifact SHA-256 is the release identity.",
        },
        "packages": [{
            "SPDXID": "SPDXRef-Package-MetaWingman",
            "name": "metawingman-skill",
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "checksums": [{"algorithm": "SHA256", "checksumValue": archive_sha}],
        }] + package_entries,
        "relationships": relationships,
    }
    predicate = {
        "buildDefinition": {
            "buildType": "https://metawingman.local/build-types/deterministic-skill-zip/v1",
            "externalParameters": {
                "bundle_version": version,
                "source_tree_sha256": manifest["source_tree_sha256"],
            },
            "internalParameters": {},
            "resolvedDependencies": [],
        },
        "runDetails": {
            "builder": {"id": "https://metawingman.local/builders/package-skill-release/v1"},
            "metadata": {"invocationId": f"local-unsigned-{archive_sha}"},
        },
    }
    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": archive.name, "digest": {"sha256": archive_sha}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": predicate,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    sbom_path = output_dir / f"{archive.name}.spdx.json"
    provenance_path = output_dir / f"{archive.name}.unsigned.intoto.jsonl"
    sbom_path.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    provenance_path.write_text(json.dumps(provenance, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return {
        "generated": True,
        "archive_sha256": archive_sha,
        "sbom": str(sbom_path),
        "unsigned_provenance": str(provenance_path),
        "dependencies": len(dependencies),
        "publisher_authenticated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / ".agents/skills/metawingman")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--outdir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    manifest = json.loads((args.bundle / "release-manifest.json").read_text(encoding="utf-8"))
    archive = args.archive or args.outdir / f"metawingman-skill-{manifest['bundle_version']}.zip"
    try:
        result = generate_metadata(args.bundle, archive, args.outdir)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"generated": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
