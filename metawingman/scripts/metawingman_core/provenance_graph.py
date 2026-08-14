"""SQLite-backed immutable provenance graph for review evidence lineage."""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


GRAPH_SCHEMA_VERSION = "1"
Direction = Literal["in", "out", "both"]


class GraphError(ValueError):
    """Raised when a graph mutation or query violates the graph contract."""


@dataclass(frozen=True)
class GraphWriteResult:
    inserted: bool
    kind: str
    identifier: str


def _canonical_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ProvenanceGraph:
    """Store immutable typed nodes and edges with deterministic hashes."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def __enter__(self) -> "ProvenanceGraph":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nodes (
                    node_type TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    document_sha256 TEXT NOT NULL,
                    PRIMARY KEY (node_type, node_id)
                );
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    from_type TEXT NOT NULL,
                    from_id TEXT NOT NULL,
                    to_type TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    status TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    document_sha256 TEXT NOT NULL,
                    FOREIGN KEY (from_type, from_id) REFERENCES nodes(node_type, node_id),
                    FOREIGN KEY (to_type, to_id) REFERENCES nodes(node_type, node_id)
                );
                CREATE INDEX IF NOT EXISTS edges_from_idx
                    ON edges(from_type, from_id, status, relationship);
                CREATE INDEX IF NOT EXISTS edges_to_idx
                    ON edges(to_type, to_id, status, relationship);
                """
            )
            row = self.connection.execute(
                "SELECT value FROM graph_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                self.connection.execute(
                    "INSERT INTO graph_metadata(key, value) VALUES('schema_version', ?)",
                    (GRAPH_SCHEMA_VERSION,),
                )
            elif row["value"] != GRAPH_SCHEMA_VERSION:
                raise GraphError(
                    f"Unsupported graph schema version {row['value']}; expected {GRAPH_SCHEMA_VERSION}"
                )

    def add_node(self, document: dict[str, Any]) -> GraphWriteResult:
        try:
            validate_document(document, "provenance_node")
        except SchemaValidationError as exc:
            raise GraphError(str(exc)) from exc
        node_type = document["node_type"]
        node_id = document["node_id"]
        digest = sha256_json(document)
        existing = self.connection.execute(
            "SELECT document_sha256 FROM nodes WHERE node_type = ? AND node_id = ?",
            (node_type, node_id),
        ).fetchone()
        if existing:
            if existing["document_sha256"] == digest:
                return GraphWriteResult(False, "node", f"{node_type}:{node_id}")
            raise GraphError(
                f"Immutable node {node_type}:{node_id} already exists with different content; "
                "create a new node and a supersedes edge"
            )
        with self.connection:
            self.connection.execute(
                "INSERT INTO nodes(node_type, node_id, document_json, document_sha256) "
                "VALUES(?, ?, ?, ?)",
                (node_type, node_id, _canonical_text(document), digest),
            )
        return GraphWriteResult(True, "node", f"{node_type}:{node_id}")

    def add_edge(self, document: dict[str, Any]) -> GraphWriteResult:
        try:
            validate_document(document, "lineage_edge")
        except SchemaValidationError as exc:
            raise GraphError(str(exc)) from exc
        edge_id = document["edge_id"]
        digest = sha256_json(document)
        existing = self.connection.execute(
            "SELECT document_sha256 FROM edges WHERE edge_id = ?", (edge_id,)
        ).fetchone()
        if existing:
            if existing["document_sha256"] == digest:
                return GraphWriteResult(False, "edge", edge_id)
            raise GraphError(
                f"Immutable edge {edge_id} already exists with different content; "
                "create a replacement edge"
            )
        source = document["from_node"]
        target = document["to_node"]
        missing = [
            f"{node['type']}:{node['id']}"
            for node in (source, target)
            if self.get_node(node["type"], node["id"]) is None
        ]
        if missing:
            raise GraphError("Edge endpoints must exist before insertion: " + ", ".join(missing))
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO edges(
                        edge_id, from_type, from_id, to_type, to_id, relationship,
                        status, document_json, document_sha256
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        source["type"], source["id"], target["type"], target["id"],
                        document["relationship"], document["status"],
                        _canonical_text(document), digest,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise GraphError(str(exc)) from exc
        return GraphWriteResult(True, "edge", edge_id)

    def get_node(self, node_type: str, node_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT document_json FROM nodes WHERE node_type = ? AND node_id = ?",
            (node_type, node_id),
        ).fetchone()
        return json.loads(row["document_json"]) if row else None

    def _edge_rows(
        self,
        node_type: str,
        node_id: str,
        direction: Direction,
        statuses: Iterable[str],
        relationship: str | None = None,
    ) -> list[sqlite3.Row]:
        if direction not in {"in", "out", "both"}:
            raise GraphError(f"Unsupported direction: {direction}")
        status_list = tuple(dict.fromkeys(statuses))
        if not status_list:
            return []
        placeholders = ",".join("?" for _ in status_list)
        clauses: list[str] = []
        params: list[Any] = []
        if direction in {"out", "both"}:
            clauses.append("(from_type = ? AND from_id = ?)")
            params.extend((node_type, node_id))
        if direction in {"in", "both"}:
            clauses.append("(to_type = ? AND to_id = ?)")
            params.extend((node_type, node_id))
        query = f"SELECT * FROM edges WHERE ({' OR '.join(clauses)}) AND status IN ({placeholders})"
        params.extend(status_list)
        if relationship:
            query += " AND relationship = ?"
            params.append(relationship)
        query += " ORDER BY edge_id"
        return list(self.connection.execute(query, params))

    def neighbors(
        self,
        node_type: str,
        node_id: str,
        direction: Direction = "both",
        statuses: Iterable[str] = ("accepted",),
        relationship: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.get_node(node_type, node_id) is None:
            raise GraphError(f"Unknown node: {node_type}:{node_id}")
        output: list[dict[str, Any]] = []
        for row in self._edge_rows(node_type, node_id, direction, statuses, relationship):
            edge = json.loads(row["document_json"])
            if row["from_type"] == node_type and row["from_id"] == node_id:
                neighbor = {"type": row["to_type"], "id": row["to_id"]}
                orientation = "out"
            else:
                neighbor = {"type": row["from_type"], "id": row["from_id"]}
                orientation = "in"
            output.append({"orientation": orientation, "neighbor": neighbor, "edge": edge})
        return output

    def shortest_path(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        direction: Direction = "out",
        statuses: Iterable[str] = ("accepted",),
        max_depth: int = 20,
    ) -> dict[str, Any] | None:
        source = (source_type, source_id)
        target = (target_type, target_id)
        if self.get_node(*source) is None or self.get_node(*target) is None:
            raise GraphError("Both path endpoints must exist")
        queue: deque[tuple[tuple[str, str], list[dict[str, Any]]]] = deque([(source, [])])
        visited = {source}
        while queue:
            current, path = queue.popleft()
            if current == target:
                return {"source": {"type": source[0], "id": source[1]}, "target": {"type": target[0], "id": target[1]}, "steps": path}
            if len(path) >= max_depth:
                continue
            for item in self.neighbors(*current, direction=direction, statuses=statuses):
                neighbor = (item["neighbor"]["type"], item["neighbor"]["id"])
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                step = {
                    "edge_id": item["edge"]["edge_id"],
                    "relationship": item["edge"]["relationship"],
                    "orientation": item["orientation"],
                    "node": item["neighbor"],
                }
                queue.append((neighbor, path + [step]))
        return None

    def impact(
        self,
        node_type: str,
        node_id: str,
        max_depth: int = 20,
        statuses: Iterable[str] = ("accepted",),
    ) -> list[dict[str, Any]]:
        if self.get_node(node_type, node_id) is None:
            raise GraphError(f"Unknown node: {node_type}:{node_id}")
        queue: deque[tuple[tuple[str, str], int]] = deque([((node_type, node_id), 0)])
        visited = {(node_type, node_id)}
        affected: list[dict[str, Any]] = []
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for item in self.neighbors(*current, direction="out", statuses=statuses):
                neighbor = (item["neighbor"]["type"], item["neighbor"]["id"])
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                next_depth = depth + 1
                affected.append({
                    "node": item["neighbor"],
                    "depth": next_depth,
                    "via_edge_id": item["edge"]["edge_id"],
                    "relationship": item["edge"]["relationship"],
                })
                queue.append((neighbor, next_depth))
        return affected

    def statistics(self) -> dict[str, Any]:
        node_counts = {
            row["node_type"]: row["count"]
            for row in self.connection.execute(
                "SELECT node_type, COUNT(*) AS count FROM nodes GROUP BY node_type ORDER BY node_type"
            )
        }
        edge_counts = {
            row["relationship"]: row["count"]
            for row in self.connection.execute(
                "SELECT relationship, COUNT(*) AS count FROM edges GROUP BY relationship ORDER BY relationship"
            )
        }
        return {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "nodes": sum(node_counts.values()),
            "edges": sum(edge_counts.values()),
            "nodes_by_type": node_counts,
            "edges_by_relationship": edge_counts,
        }

    def verify(self) -> list[str]:
        issues: list[str] = []
        foreign_keys = self.connection.execute("PRAGMA foreign_key_check").fetchall()
        for row in foreign_keys:
            issues.append(f"foreign key violation in {row[0]} row {row[1]}")
        for row in self.connection.execute("SELECT * FROM nodes ORDER BY node_type, node_id"):
            try:
                document = json.loads(row["document_json"])
                validate_document(document, "provenance_node")
            except (json.JSONDecodeError, SchemaValidationError) as exc:
                issues.append(f"node {row['node_type']}:{row['node_id']}: {exc}")
                continue
            if document["node_type"] != row["node_type"] or document["node_id"] != row["node_id"]:
                issues.append(f"node {row['node_type']}:{row['node_id']}: indexed identity mismatch")
            if sha256_json(document) != row["document_sha256"]:
                issues.append(f"node {row['node_type']}:{row['node_id']}: hash mismatch")
        for row in self.connection.execute("SELECT * FROM edges ORDER BY edge_id"):
            try:
                document = json.loads(row["document_json"])
                validate_document(document, "lineage_edge")
            except (json.JSONDecodeError, SchemaValidationError) as exc:
                issues.append(f"edge {row['edge_id']}: {exc}")
                continue
            indexed = (
                row["from_type"], row["from_id"], row["to_type"], row["to_id"],
                row["relationship"], row["status"],
            )
            embedded = (
                document["from_node"]["type"], document["from_node"]["id"],
                document["to_node"]["type"], document["to_node"]["id"],
                document["relationship"], document["status"],
            )
            if indexed != embedded:
                issues.append(f"edge {row['edge_id']}: indexed fields mismatch")
            if sha256_json(document) != row["document_sha256"]:
                issues.append(f"edge {row['edge_id']}: hash mismatch")
        return issues
