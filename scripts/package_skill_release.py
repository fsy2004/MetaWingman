#!/usr/bin/env python3
"""Create a deterministic standalone MetaWingman skill archive and checksum."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

try:
    from .verify_skill_bundle import verify_bundle
except ImportError:  # Direct script execution.
    from verify_skill_bundle import verify_bundle


ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_skill(bundle_path: Path, output_dir: Path) -> dict[str, object]:
    bundle = bundle_path.expanduser().resolve()
    validation = verify_bundle(bundle)
    manifest = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    version = str(manifest["bundle_version"])
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"metawingman-skill-{version}.zip"
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as handle:
        for path in sorted(
            (item for item in bundle.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(bundle).as_posix(),
        ):
            relative = Path("metawingman") / path.relative_to(bundle)
            info = zipfile.ZipInfo(relative.as_posix(), ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, path.read_bytes())
    checksum = _sha256(archive)
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    return {
        "packaged": True,
        "archive": str(archive),
        "sha256": checksum,
        "checksum_file": str(checksum_path),
        "bundle_files": validation["files"],
        "source_tree_sha256": validation["source_tree_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bundle",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".agents/skills/metawingman",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "dist",
    )
    args = parser.parse_args()
    try:
        result = package_skill(args.bundle, args.outdir)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"packaged": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
