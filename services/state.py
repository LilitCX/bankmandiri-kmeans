"""
services/state.py
Global in-memory state manager.
Untuk single-process deployment (Vercel serverless / Gunicorn single worker).
"""
from __future__ import annotations
from typing import Any

import pandas as pd

# ── Initial state factory ─────────────────────────────────────────────────────

def _empty() -> dict[str, Any]:
    return {
        "raw_df": None,
        "processed_df": None,
        "result_df": None,
        "upload_path": None,
        "result_dir": None,
        "output_cols": [],
        "metadata": None,
        "preprocessing_stats": None,
        "cluster_summary": [],
        "cluster_quality": [],
        "seed_summary": {},
        "best_k": None,
        "scraping_result": None,
        "columns": [],
        "text_column": None,
        "k": 4,
        "metrics": None,
        "bar_labels": [],
        "bar_values": [],
        "scatter_data": [],
        "wordclouds": {},
        "top_words": {},
        "eval_labels": [],
        "eval_sse": [],
        "eval_silhouette": [],
        "message": None,
        "error": None,
    }


STATE: dict[str, Any] = _empty()


def reset_messages() -> None:
    STATE["message"] = None
    STATE["error"] = None


def set_error(msg: str) -> None:
    STATE["error"] = str(msg)


def set_message(msg: str) -> None:
    STATE["message"] = str(msg)


def reset_pipeline() -> None:
    """Reset semua state hasil pipeline (preprocessing & clustering)."""
    STATE.update({
        "processed_df": None,
        "result_df": None,
        "result_dir": None,
        "output_cols": [],
        "metadata": None,
        "preprocessing_stats": None,
        "cluster_summary": [],
        "cluster_quality": [],
        "seed_summary": {},
        "best_k": None,
        "k": 4,
        "metrics": None,
        "bar_labels": [],
        "bar_values": [],
        "scatter_data": [],
        "wordclouds": {},
        "top_words": {},
        "eval_labels": [],
        "eval_sse": [],
        "eval_silhouette": [],
    })
