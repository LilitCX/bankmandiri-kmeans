"""
services/db.py
Persistent storage menggunakan Supabase (PostgreSQL).

Skema tabel `clustering_results`:
  - id          : uuid, primary key (auto)
  - created_at  : timestamptz (auto)
  - result_id   : text
  - username    : text
  - metadata    : jsonb   — semua hasil pipeline clustering
  - csv_content : text    — isi file CSV upload (base64) untuk restore lintas restart
"""
from __future__ import annotations
import os
import base64
import tempfile
from typing import Optional
from datetime import datetime

# ── Supabase setup ────────────────────────────────────────────────────────────
USE_SUPABASE = os.environ.get("USE_SUPABASE", "0") == "1"
SUPABASE_OK  = False

if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        _SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
        _SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

        if _SUPABASE_URL and _SUPABASE_KEY:
            supabase: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
            SUPABASE_OK = True
        else:
            USE_SUPABASE = False
    except ImportError:
        USE_SUPABASE = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode_csv(csv_path: str) -> Optional[str]:
    """Baca file CSV dan kembalikan sebagai string base64."""
    try:
        with open(csv_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[WARN] Gagal encode CSV ke base64: {e}")
        return None


def restore_csv_from_db(username: Optional[str] = None) -> Optional[str]:
    """
    Ambil isi CSV dari Supabase dan tulis ke file /tmp sementara.

    Returns
    -------
    Optional[str]
        Path file CSV sementara yang sudah ditulis ke disk,
        atau None jika data tidak tersedia / Supabase tidak aktif.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return None

    try:
        query = supabase.table("clustering_results").select("csv_content,result_id")
        if username:
            query = query.eq("username", username)
        response = query.order("created_at", desc=True).limit(1).execute()

        if not response.data:
            return None

        row = response.data[0]
        csv_b64 = row.get("csv_content")
        if not csv_b64:
            print("[WARN] Baris Supabase ditemukan tapi csv_content kosong.")
            return None

        csv_bytes = base64.b64decode(csv_b64)
        result_id = row.get("result_id", "restored")
        tmp_path  = os.path.join(tempfile.gettempdir(), f"csv_restored_{result_id}.csv")
        with open(tmp_path, "wb") as f:
            f.write(csv_bytes)
        print(f"[INFO] CSV berhasil di-restore ke {tmp_path}")
        return tmp_path
    except Exception as e:
        print(f"[ERROR] Gagal restore CSV dari Supabase: {e}")
        return None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def save_clustering_result(
    result_id: str,
    metadata:  dict,
    username:  str = "unknown",
    csv_path:  Optional[str] = None,
) -> bool:
    """
    Simpan hasil clustering ke Supabase.

    Parameters
    ----------
    result_id : str
        Identifier unik (uuid hex).
    metadata : dict
        Dict lengkap dari run_clustering().
    username : str
        Username yang menjalankan clustering.
    csv_path : Optional[str]
        Path lokal file CSV upload. Isinya di-encode base64 dan disimpan
        di kolom csv_content agar bisa di-restore tanpa file fisik.

    Returns
    -------
    bool
        True jika berhasil, False jika gagal atau Supabase tidak aktif.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return False

    try:
        # Buat salinan metadata tanpa menyertakan path lokal —
        # path lokal tidak valid di server lain / setelah restart.
        clean_metadata = {k: v for k, v in metadata.items() if k != "upload_path"}

        data: dict = {
            "result_id":  result_id,
            "metadata":   clean_metadata,
            "username":   username,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Simpan isi CSV sebagai base64 agar restore bisa dilakukan tanpa storage eksternal
        if csv_path and os.path.exists(csv_path):
            encoded = _encode_csv(csv_path)
            if encoded:
                data["csv_content"] = encoded
            else:
                print(f"[WARN] CSV ditemukan tapi gagal di-encode: {csv_path}")
        elif csv_path:
            print(f"[WARN] csv_path diberikan tapi file tidak ada: {csv_path}")

        supabase.table("clustering_results").insert(data).execute()
        print(f"[INFO] Hasil clustering {result_id} berhasil disimpan ke Supabase.")
        return True
    except Exception as e:
        print(f"[ERROR] Gagal save ke Supabase: {e}")
        return False


def get_latest_clustering_result(username: Optional[str] = None) -> Optional[dict]:
    """
    Ambil metadata hasil clustering terakhir dari Supabase.

    Parameters
    ----------
    username : Optional[str]
        Filter berdasarkan username. Jika None, ambil yang paling baru.

    Returns
    -------
    Optional[dict]
        Metadata dict jika ada, None jika tidak ada atau Supabase tidak aktif.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return None

    try:
        query = supabase.table("clustering_results").select("metadata")
        if username:
            query = query.eq("username", username)
        response = query.order("created_at", desc=True).limit(1).execute()

        if response.data:
            return response.data[0]["metadata"]
        return None
    except Exception as e:
        print(f"[ERROR] Gagal baca dari Supabase: {e}")
        return None


def get_all_clustering_results(
    username: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Ambil semua metadata hasil clustering (untuk history)."""
    if not USE_SUPABASE or not SUPABASE_OK:
        return []

    try:
        query = supabase.table("clustering_results").select("metadata")
        if username:
            query = query.eq("username", username)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return [row["metadata"] for row in response.data] if response.data else []
    except Exception as e:
        print(f"[ERROR] Gagal baca list dari Supabase: {e}")
        return []


def delete_old_clustering_results(
    keep_last: int = 5,
    username:  Optional[str] = None,
) -> int:
    """
    Hapus hasil clustering lama, simpan hanya `keep_last` terbaru per user.

    Returns
    -------
    int
        Jumlah baris yang dihapus.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return 0

    try:
        query = supabase.table("clustering_results").select("id,created_at")
        if username:
            query = query.eq("username", username)
        response = query.order("created_at", desc=True).execute()

        if not response.data or len(response.data) <= keep_last:
            return 0

        to_delete  = response.data[keep_last:]
        delete_ids = [row["id"] for row in to_delete]

        for row_id in delete_ids:
            supabase.table("clustering_results").delete().eq("id", row_id).execute()

        print(f"[INFO] Dihapus {len(delete_ids)} hasil clustering lama.")
        return len(delete_ids)
    except Exception as e:
        print(f"[ERROR] Gagal delete old results: {e}")
        return 0
