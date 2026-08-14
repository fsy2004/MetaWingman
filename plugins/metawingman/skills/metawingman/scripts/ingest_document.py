#!/usr/bin/env python3
"""Ingest one local report or supplement and emit a document-state record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.document_ingestor import DocumentIngestError, ingest_document
from metawingman_core.state_store import StateStoreError, append_jsonl_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--source-type", choices=("article", "supplement", "registry", "appendix", "correction", "other"), required=True)
    parser.add_argument("--access-route", choices=("open_access", "user_provided", "licensed_user_export", "public_api", "credentialed_browser_handoff", "other"), required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--origin-url")
    parser.add_argument("--parent-document-id")
    parser.add_argument("--no-text", action="store_true")
    parser.add_argument("--render-pages", action="store_true")
    parser.add_argument("--page-dpi", type=int, default=144)
    parser.add_argument("--max-document-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--max-pages", type=int, default=5000)
    parser.add_argument("--max-render-pixels", type=int, default=500_000_000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--append-project-state", action="store_true")
    args = parser.parse_args()
    try:
        state = ingest_document(
            args.artifact,
            args.project,
            document_id=args.document_id,
            report_id=args.report_id,
            source_type=args.source_type,
            access_route=args.access_route,
            license_name=args.license,
            origin_url=args.origin_url,
            parent_document_id=args.parent_document_id,
            extract_text=not args.no_text,
            render_pages=args.render_pages,
            page_dpi=args.page_dpi,
            max_document_bytes=args.max_document_bytes,
            max_pages=args.max_pages,
            max_render_pixels=args.max_render_pixels,
        )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.append_project_state:
            stream = args.project.resolve() / "02_search/retrieval/document_state.jsonl"
            append_jsonl_record(
                stream,
                state,
                "document_state",
                unique_fields=("document_id",),
            )
    except (OSError, json.JSONDecodeError, DocumentIngestError, StateStoreError) as exc:
        print(json.dumps({"ingested": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ingested": True, "document_state": state}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
