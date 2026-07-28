"""
services/dataset_service.py
Logika loading dataset dari file CSV ke STATE.
"""
from __future__ import annotations

import os
import base64
import io
import json

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from wordcloud import WordCloud
    _WORDCLOUD_OK = True
except Exception:
    _WORDCLOUD_OK = False

from services.state import STATE
from config.settings import RESULTS_FOLDER


# ── CSV loader ────────────────────────────────────────────────────────────────

def _read_csv_robust(filepath: str) -> pd.DataFrame:
    """Coba berbagai encoding agar CSV dari Windows/Excel tidak gagal dibaca."""
    for enc in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
        try:
            return pd.read_csv(filepath, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Tidak dapat membaca file CSV: {filepath}")


def load_dataset(filepath: str, source_message: str, filter_type: str = "all") -> pd.DataFrame:
    """
    Load CSV → STATE. Mengembalikan DataFrame yang dimuat.

    Parameters
    ----------
    filepath : str
        Path absolut atau relatif ke file CSV.
    source_message : str
        Pesan sukses yang akan disimpan di STATE["message"].
    filter_type : str
        "all" → semua data; "bank_only" → filter kolom is_banking == True.
    """
    df = _read_csv_robust(filepath)

    if filter_type == "bank_only" and "is_banking" in df.columns:
        df = df[
            df["is_banking"].astype(str).str.lower().isin(["true", "1", "yes", "t"])
        ].copy()
        if len(df) == 0:
            STATE["error"] = (
                "Filter 'Hanya Data Bank' aktif, tetapi tidak ada baris yang memenuhi kriteria."
            )

    df.reset_index(drop=True, inplace=True)

    # Reset semua state hasil pipeline
    STATE.update({
        "raw_df": df,
        "processed_df": None,
        "result_df": None,
        "upload_path": filepath,
        "result_dir": None,
        "output_cols": [],
        "metadata": None,
        "preprocessing_stats": None,
        "cluster_summary": [],
        "cluster_quality": [],
        "seed_summary": {},
        "best_k": None,
        "columns": df.columns.tolist(),
        "text_column": "komentar" if "komentar" in df.columns else None,
        "message": source_message,
    })
    return df


# ── Wordcloud helper ──────────────────────────────────────────────────────────

def make_wordcloud_b64(text: str) -> str | None:
    """Buat wordcloud dari teks dan kembalikan sebagai base64 PNG string."""
    if not text or not str(text).strip():
        return None
    if not _WORDCLOUD_OK:
        return None
    try:
        wc = (
            WordCloud(width=900, height=450, background_color="white",
                      collocations=False, max_words=100)
            .generate(str(text))
        )
        buf = io.BytesIO()
        plt.figure(figsize=(9, 4.5))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.tight_layout(pad=0)
        plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        plt.close()
        return None


def _load_wordcloud_from_disk(result_dir: str, filename: str | None) -> str | None:
    if not filename or not result_dir:
        return None
    path = os.path.join(result_dir, filename)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Metadata → STATE ──────────────────────────────────────────────────────────

def apply_metadata(metadata: dict, result_dir: str) -> None:
    """Terapkan metadata hasil pipeline clustering ke STATE global."""
    csv_name = metadata.get("files", {}).get("csv")
    csv_path = os.path.join(result_dir, csv_name) if csv_name else None

    if csv_path and os.path.exists(csv_path):
        try:
            result_df = pd.read_csv(csv_path)
        except Exception:
            result_df = pd.DataFrame(metadata.get("preview_result", []))
    else:
        result_df = pd.DataFrame(metadata.get("preview_result", []))

    summary = metadata.get("summary", [])
    evaluation = metadata.get("evaluation", {})
    k_values = evaluation.get("k_values", [])
    wc_files = metadata.get("files", {}).get("wordclouds", {})

    wordclouds: dict = {}
    top_words: dict = {}

    for item in summary:
        cid = int(item["cluster"])
        top_words[cid] = item.get("top_words", [])
        wordclouds[cid] = _load_wordcloud_from_disk(result_dir, wc_files.get(str(cid)))

    if result_df is not None and not result_df.empty and "komentar_bersih" in result_df.columns:
        valid_df = result_df.dropna(subset=["cluster"])
        for cid in sorted(valid_df["cluster"].astype(int).unique()):
            if cid not in wordclouds or wordclouds[cid] is None:
                text = " ".join(
                    valid_df.loc[valid_df["cluster"].astype(int) == cid, "komentar_bersih"]
                    .astype(str)
                    .tolist()
                )
                wordclouds[cid] = make_wordcloud_b64(text)
            top_words.setdefault(cid, [])

    STATE.update({
        "result_df": result_df,
        "result_dir": result_dir,
        "metadata": metadata,
        "output_cols": metadata.get("output_cols", []),
        "k": int(metadata.get("jumlah_cluster", STATE["k"])),
        "preprocessing_stats": {
            "jumlah_data_awal": int(metadata.get("jumlah_data_awal", 0)),
            "jumlah_tidak_null": int(metadata.get("jumlah_tidak_null", 0)),
            "jumlah_setelah_filter_raw": int(metadata.get("jumlah_setelah_filter_raw", 0)),
            "jumlah_setelah_clean_nonempty": int(
                metadata.get("jumlah_setelah_clean_nonempty", metadata.get("jumlah_data_valid", 0))
            ),
            "jumlah_setelah_min_kata_bersih": int(
                metadata.get("jumlah_setelah_min_kata_bersih", metadata.get("jumlah_data_valid", 0))
            ),
            "jumlah_duplikat_dihapus": int(metadata.get("jumlah_duplikat_dihapus", 0)),
            "jumlah_data_valid": int(metadata.get("jumlah_data_valid", len(result_df))),
        },
        "metrics": {
            "total_data": int(metadata.get("jumlah_data_valid", len(result_df))),
            "jumlah_cluster": int(metadata.get("jumlah_cluster", STATE["k"])),
            "jumlah_fitur_tfidf": int(metadata.get("tfidf_shape", [0, 0])[1]),
            "jumlah_komponen_lsa": int(metadata.get("lsa_shape", [0, 0])[1]),
            "variansi_lsa": metadata.get("variansi_lsa"),
            "silhouette_score": metadata.get("silhouette"),
        },
        "cluster_summary": summary,
        "cluster_quality": metadata.get("cluster_quality", []),
        "seed_summary": metadata.get("seed_summary", {}),
        "best_k": evaluation.get("rekomendasi_k"),
        "bar_labels": [f"C{item['cluster']}" for item in summary],
        "bar_values": [int(item["jumlah"]) for item in summary],
        "scatter_data": metadata.get("scatter_data", []),
        "wordclouds": wordclouds,
        "top_words": top_words,
        "eval_labels": [f"K={k}" for k in k_values],
        "eval_sse": [round(float(x), 4) for x in evaluation.get("inertia", [])],
        "eval_silhouette": [round(float(x), 4) for x in evaluation.get("silhouette", [])],
    })


def try_restore_latest() -> bool:
    """Muat ulang hasil clustering terakhir dari disk jika STATE kosong."""
    if STATE["result_df"] is not None:
        return True
    if not os.path.isdir(RESULTS_FOLDER):
        return False

    candidates = [
        os.path.join(RESULTS_FOLDER, name, "metadata.json")
        for name in os.listdir(RESULTS_FOLDER)
        if os.path.exists(os.path.join(RESULTS_FOLDER, name, "metadata.json"))
    ]
    if not candidates:
        return False

    latest = max(candidates, key=os.path.getmtime)
    try:
        with open(latest, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        apply_metadata(metadata, os.path.dirname(latest))
        STATE["message"] = "Hasil clustering terakhir berhasil dimuat ulang."
        return True
    except Exception:
        return False
