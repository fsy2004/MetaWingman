"""Ingest lawful local documents into a checksummed multimodal state manifest."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


INGESTOR_VERSION = "1.0"
DEFAULT_MAX_DOCUMENT_BYTES = 250 * 1024 * 1024
DEFAULT_MAX_PAGES = 5000
DEFAULT_MAX_RENDER_PIXELS = 500_000_000


class DocumentIngestError(ValueError):
    """Raised when a document cannot be ingested without provenance loss."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise DocumentIngestError(f"Artifact path escapes project root: {path}") from exc


def _write_immutable(path: Path, body: bytes) -> None:
    if path.exists():
        if hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(body).digest():
            return
        raise DocumentIngestError(f"Refusing to overwrite a different artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _parser(name: str, version: str, configuration: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "version": version,
        "configuration_sha256": sha256_json(configuration),
    }


def ingest_document(
    artifact: Path,
    project_root: Path,
    *,
    document_id: str,
    report_id: str,
    source_type: str,
    access_route: str,
    license_name: str,
    origin_url: str | None = None,
    parent_document_id: str | None = None,
    extract_text: bool = True,
    render_pages: bool = False,
    page_dpi: int = 144,
    max_document_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_render_pixels: int = DEFAULT_MAX_RENDER_PIXELS,
    retrieved_at_utc: str | None = None,
) -> dict[str, Any]:
    artifact = artifact.expanduser().resolve()
    root = project_root.expanduser().resolve()
    if not artifact.is_file():
        raise DocumentIngestError(f"Document does not exist: {artifact}")
    if max_document_bytes < 1 or artifact.stat().st_size > max_document_bytes:
        raise DocumentIngestError(
            f"Document exceeds byte limit {max_document_bytes}: {artifact.stat().st_size}"
        )
    if max_pages < 1 or max_render_pixels < 1:
        raise DocumentIngestError("max_pages and max_render_pixels must be positive")
    if not document_id or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-" for character in document_id):
        raise DocumentIngestError("document_id must contain only letters, numbers, dot, underscore, or hyphen")
    if not license_name.strip():
        raise DocumentIngestError("License or access-rights statement is required")
    if page_dpi < 72 or page_dpi > 600:
        raise DocumentIngestError("page_dpi must be between 72 and 600")

    store = root / "02_search" / "retrieval" / "documents" / document_id
    original = store / "original" / artifact.name
    original.parent.mkdir(parents=True, exist_ok=True)
    if original.exists():
        if _hash_file(original) != _hash_file(artifact):
            raise DocumentIngestError(f"Document ID already points to a different original: {document_id}")
    else:
        shutil.copy2(artifact, original)
    original_hash = _hash_file(original)
    media_type = mimetypes.guess_type(original.name)[0] or "application/octet-stream"
    if original.suffix.casefold() == ".pdf":
        media_type = "application/pdf"

    now = retrieved_at_utc or datetime.now(timezone.utc).isoformat()
    representations: list[dict[str, Any]] = []
    parse_status = "not_started"
    active_parse_id: str | None = None

    if original.suffix.casefold() == ".pdf" and (extract_text or render_pages):
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise DocumentIngestError("PyMuPDF is required for PDF text/page extraction") from exc
        try:
            pdf = fitz.open(original)
        except Exception as exc:
            raise DocumentIngestError(f"Cannot open PDF: {exc}") from exc
        try:
            if pdf.needs_pass:
                raise DocumentIngestError(
                    "Password-protected PDF requires user-authorized decryption before ingestion"
                )
            page_count = pdf.page_count
            if page_count < 1:
                raise DocumentIngestError("PDF has no readable pages")
            if page_count > max_pages:
                raise DocumentIngestError(
                    f"PDF exceeds page limit {max_pages}: {page_count}"
                )
            if extract_text:
                chunks = [page.get_text("text") for page in pdf]
                text_body = "\n\f\n".join(chunks).encode("utf-8")
                text_path = store / "representations" / "native_text.txt"
                _write_immutable(text_path, text_body)
                text_id = f"{document_id}.native-text"
                warnings = [] if text_body.strip() else ["native_text_layer_empty"]
                representations.append({
                    "representation_id": text_id,
                    "type": "native_text",
                    "artifact_path": _relative(text_path, root),
                    "sha256": _hash_file(text_path),
                    "parser": _parser("PyMuPDF", getattr(fitz, "VersionBind", "unknown"), {"method": "page.get_text", "mode": "text"}),
                    "derived_from": [document_id],
                    "pages": {"first": 1, "last": page_count} if page_count else None,
                    "status": "active" if text_body.strip() else "candidate",
                    "quality": {"score": None, "warnings": warnings},
                })
                if text_body.strip():
                    active_parse_id = text_id
                    parse_status = "ready"
                else:
                    parse_status = "partial"
            if render_pages:
                zoom = page_dpi / 72.0
                estimated_pixels = sum(
                    int(page.rect.width * zoom) * int(page.rect.height * zoom)
                    for page in pdf
                )
                if estimated_pixels > max_render_pixels:
                    raise DocumentIngestError(
                        f"PDF render exceeds pixel budget {max_render_pixels}: {estimated_pixels}"
                    )
                for page_index, page in enumerate(pdf, start=1):
                    image_path = store / "representations" / "pages" / f"page-{page_index:04d}.png"
                    if not image_path.exists():
                        image_path.parent.mkdir(parents=True, exist_ok=True)
                        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(image_path)
                    representation_id = f"{document_id}.page-{page_index:04d}"
                    representations.append({
                        "representation_id": representation_id,
                        "type": "page_image",
                        "artifact_path": _relative(image_path, root),
                        "sha256": _hash_file(image_path),
                        "parser": _parser("PyMuPDF", getattr(fitz, "VersionBind", "unknown"), {"dpi": page_dpi, "alpha": False}),
                        "derived_from": [document_id],
                        "pages": {"first": page_index, "last": page_index},
                        "status": "active",
                        "quality": {"score": None, "warnings": []},
                    })
                if representations and active_parse_id is None:
                    active_parse_id = representations[0]["representation_id"]
                    parse_status = "partial"
        except DocumentIngestError:
            raise
        except Exception as exc:
            raise DocumentIngestError(f"Cannot process PDF: {exc}") from exc
        finally:
            pdf.close()
    elif extract_text and media_type.startswith("text/"):
        raw = original.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentIngestError("Text input must be UTF-8 or be pre-converted with a declared parser") from exc
        text_path = store / "representations" / "native_text.txt"
        _write_immutable(text_path, text.encode("utf-8"))
        active_parse_id = f"{document_id}.native-text"
        representations.append({
            "representation_id": active_parse_id,
            "type": "native_text",
            "artifact_path": _relative(text_path, root),
            "sha256": _hash_file(text_path),
            "parser": _parser("utf8-text-ingestor", INGESTOR_VERSION, {"encoding": "utf-8"}),
            "derived_from": [document_id],
            "pages": None,
            "status": "active",
            "quality": {"score": 1.0, "warnings": []},
        })
        parse_status = "ready"

    state = {
        "schema_version": "1.0",
        "document_id": document_id,
        "report_id": report_id,
        "parent_document_id": parent_document_id,
        "source": {
            "artifact_path": _relative(original, root),
            "sha256": original_hash,
            "media_type": media_type,
            "source_type": source_type,
            "origin_url": origin_url,
            "access_route": access_route,
            "license": license_name,
            "retrieved_at_utc": now,
        },
        "representations": representations,
        "parse_status": parse_status,
        "active_parse_id": active_parse_id,
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    try:
        validate_document(state, "document_state")
    except SchemaValidationError as exc:
        raise DocumentIngestError(str(exc)) from exc
    return state
