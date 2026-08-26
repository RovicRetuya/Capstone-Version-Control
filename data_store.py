"""Small centralized SQLite store for analyzed data and research results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path(__file__).resolve().parent / "defaketive.db"


@contextmanager
def _connect(path: str | Path = DEFAULT_DB):
    connection = sqlite3.connect(Path(path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
        CREATE TABLE IF NOT EXISTS products (
            link TEXT PRIMARY KEY, name TEXT NOT NULL, platform TEXT NOT NULL,
            category TEXT, price TEXT, rating REAL, review_count INTEGER NOT NULL,
            risk_score REAL, reliability_score REAL, source TEXT, raw_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            review_key TEXT PRIMARY KEY, product_link TEXT NOT NULL,
            author TEXT, rating INTEGER, reviewed_at TEXT, content TEXT,
            sentiment TEXT, risk_detected INTEGER NOT NULL, raw_json TEXT NOT NULL,
            FOREIGN KEY(product_link) REFERENCES products(link) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, submitted_at TEXT NOT NULL,
            shopping_frequency TEXT, sus_score REAL NOT NULL, umux_score REAL NOT NULL,
            responses_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT NOT NULL,
            source_name TEXT, sample_count INTEGER NOT NULL, accuracy REAL NOT NULL,
            precision REAL NOT NULL, recall REAL NOT NULL, f1 REAL NOT NULL,
            labels_json TEXT NOT NULL, matrix_json TEXT NOT NULL
        );
            """
        )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_products(products: list[dict[str, Any]], source: str = "", path: str | Path = DEFAULT_DB) -> None:
    from dashboard_utils import platform_name, product_reliability

    now = datetime.now(timezone.utc).isoformat()
    with _connect(path) as connection:
        for product in products:
            link = str(product.get("link") or "").strip()
            if not link:
                continue
            summary = product.get("sentiment_summary") or {}
            comments = [item for item in product.get("comments") or [] if isinstance(item, dict)]
            connection.execute(
                """INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link) DO UPDATE SET name=excluded.name, platform=excluded.platform,
                category=excluded.category, price=excluded.price, rating=excluded.rating,
                review_count=excluded.review_count, risk_score=excluded.risk_score,
                reliability_score=excluded.reliability_score, source=excluded.source,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at""",
                (link, str(product.get("name") or "Unnamed product"), platform_name(product),
                 str(product.get("category") or ""), str(product.get("price") or ""),
                 product.get("rating"), len(comments), summary.get("risk_score"),
                 product_reliability(product), source, json.dumps(product, ensure_ascii=False), now),
            )
            for review in comments:
                identity = "\x1f".join((link, str(review.get("author") or ""), str(review.get("time") or ""), str(review.get("content") or "")))
                key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
                analysis = review.get("sentiment_analysis") or {}
                connection.execute(
                    """INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(review_key) DO UPDATE SET sentiment=excluded.sentiment,
                    risk_detected=excluded.risk_detected, raw_json=excluded.raw_json""",
                    (key, link, review.get("author"), review.get("rating"), review.get("time"),
                     review.get("content"), analysis.get("label"),
                     int(bool((analysis.get("risk") or {}).get("detected"))),
                     json.dumps(review, ensure_ascii=False)),
                )


def database_counts(path: str | Path = DEFAULT_DB) -> dict[str, int]:
    with _connect(path) as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("products", "reviews", "survey_responses", "evaluation_runs")
        }


def load_saved_products(path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    """Load the latest analyzed product payloads for local recommendations."""
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT raw_json FROM products ORDER BY updated_at DESC"
        ).fetchall()
    products = []
    for (payload,) in rows:
        try:
            product = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(product, dict):
            products.append(product)
    return products


def save_survey_response(frequency: str, sus: list[int], umux: list[int], sus_score: float,
                         umux_score: float, path: str | Path = DEFAULT_DB) -> None:
    payload = json.dumps({"sus": sus, "umux": umux}, ensure_ascii=False)
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO survey_responses(submitted_at, shopping_frequency, sus_score, umux_score, responses_json) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), frequency, sus_score, umux_score, payload),
        )


def save_evaluation_run(source_name: str, result: dict, path: str | Path = DEFAULT_DB) -> None:
    with _connect(path) as connection:
        connection.execute(
            """INSERT INTO evaluation_runs(run_at, source_name, sample_count, accuracy, precision,
            recall, f1, labels_json, matrix_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), source_name, result["sample_count"],
             result["accuracy"], result["precision"], result["recall"], result["f1"],
             json.dumps(result["labels"]), json.dumps(result["matrix"])),
        )
