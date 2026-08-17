"""Validate model and tool outputs before they can alter review state."""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


class SchemaValidationError(ValueError):
    """Raised when a document does not satisfy a MetaWingman schema."""

    def __init__(self, schema_name: str, errors: list[str]):
        self.schema_name = schema_name
        self.errors = errors
        super().__init__(f"{schema_name} validation failed: " + "; ".join(errors))


@lru_cache(maxsize=None)
def load_schema(schema_name: str) -> dict[str, Any]:
    name = schema_name if schema_name.endswith(".schema.json") else f"{schema_name}.schema.json"
    path = SCHEMA_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Unknown MetaWingman schema: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _format_error(error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "$"
    return f"{location}: {error.message}"


def validate_document(document: Any, schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    if errors:
        raise SchemaValidationError(schema_name, [_format_error(error) for error in errors])


def validate_json_file(path: Path, schema_name: str) -> Any:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(schema_name, [f"cannot read JSON from {path}: {exc}"]) from exc
    validate_document(document, schema_name)
    return document


def validate_jsonl_file(path: Path, schema_name: str) -> list[Any]:
    documents: list[Any] = []
    if not path.exists():
        return documents
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            document = json.loads(line)
            validate_document(document, schema_name)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(schema_name, [f"line {line_number}: invalid JSON: {exc}"]) from exc
        except SchemaValidationError as exc:
            raise SchemaValidationError(schema_name, [f"line {line_number}: {message}" for message in exc.errors]) from exc
        documents.append(document)
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()
    try:
        if args.jsonl:
            documents = validate_jsonl_file(args.path, args.schema)
            result = {"valid": True, "records": len(documents), "schema": args.schema}
        else:
            validate_json_file(args.path, args.schema)
            result = {"valid": True, "schema": args.schema}
    except (FileNotFoundError, SchemaValidationError) as exc:
        result = {"valid": False, "schema": args.schema, "error": str(exc)}
        print(json.dumps(result, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
