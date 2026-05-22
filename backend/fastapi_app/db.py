import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "db.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  workflow_id TEXT PRIMARY KEY,
  ticker      TEXT NOT NULL,
  started_at  TEXT NOT NULL,
  status      TEXT NOT NULL,
  last_phase  TEXT,
  params_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
  key            TEXT PRIMARY KEY,
  workflow_id    TEXT NOT NULL,
  action         TEXT NOT NULL,
  response_json  TEXT,
  created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chaos_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id  TEXT NOT NULL,
  kind         TEXT NOT NULL,
  payload_json TEXT,
  ts           TEXT NOT NULL
);
"""


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_run(workflow_id: str, ticker: str, params: dict[str, Any]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO runs(workflow_id,ticker,started_at,status,last_phase,params_json) VALUES (?,?,?,?,?,?)",
            (workflow_id, ticker, datetime.utcnow().isoformat(), "RUNNING", "SYNTHESIZING", json.dumps(params)),
        )
        conn.commit()
    finally:
        conn.close()


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_chaos(workflow_id: str, kind: str, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO chaos_events(workflow_id,kind,payload_json,ts) VALUES (?,?,?,?)",
            (workflow_id, kind, json.dumps(payload), datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
