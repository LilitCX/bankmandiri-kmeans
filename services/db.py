"""
services/db.py
Persistent storage menggunakan Supabase (PostgreSQL).
Menyimpan metadata hasil clustering agar tidak hilang saat restart.
"""
from __future__ import annotations
import os
import json
from typing import Optional
from datetime import datetime

# Cek apakah Supabase diaktifkan
USE_SUPABASE = os.environ.get("USE_SUPABASE", "0") == "1"

if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
        
        if SUPABASE_URL and SUPABASE_KEY:
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            SUPABASE_OK = True
        else:
            SUPABASE_OK = False
            USE_SUPABASE = False
    except ImportError:
        SUPABASE_OK = False
        USE_SUPABASE = False
else:
    SUPABASE_OK = False


# ── Table Schema ──────────────────────────────────────────────────────────────
# Tabel: clustering_results
# Columns:
#   - id (uuid, primary key, auto-generated)
#   - created_at (timestamp, auto)
#   - metadata (jsonb) — semua hasil clustering
#   - result_id (text) — identifier unik untuk sesi clustering
#   - username (text) — siapa yang jalankan clustering


def save_clustering_result(result_id: str, metadata: dict, username: str = "unknown") -> bool:
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
    
    Returns
    -------
    bool
        True jika berhasil, False jika gagal atau Supabase tidak aktif.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return False
    
    try:
        data = {
            "result_id": result_id,
            "metadata": metadata,
            "username": username,
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("clustering_results").insert(data).execute()
        return True
    except Exception as e:
        print(f"[ERROR] Gagal save ke Supabase: {e}")
        return False


def get_latest_clustering_result(username: Optional[str] = None) -> Optional[dict]:
    """
    Ambil hasil clustering terakhir dari Supabase.
    
    Parameters
    ----------
    username : Optional[str]
        Filter berdasarkan username. Jika None, ambil yang paling baru dari semua user.
    
    Returns
    -------
    Optional[dict]
        Metadata dict jika ada, None jika tidak ada atau Supabase tidak aktif.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return None
    
    try:
        query = supabase.table("clustering_results").select("*")
        
        if username:
            query = query.eq("username", username)
        
        response = query.order("created_at", desc=True).limit(1).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]["metadata"]
        return None
    except Exception as e:
        print(f"[ERROR] Gagal baca dari Supabase: {e}")
        return None


def get_all_clustering_results(username: Optional[str] = None, limit: int = 10) -> list[dict]:
    """
    Ambil semua hasil clustering (untuk history/list).
    
    Parameters
    ----------
    username : Optional[str]
        Filter berdasarkan username.
    limit : int
        Jumlah maksimal hasil yang dikembalikan.
    
    Returns
    -------
    list[dict]
        List metadata dict.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return []
    
    try:
        query = supabase.table("clustering_results").select("*")
        
        if username:
            query = query.eq("username", username)
        
        response = query.order("created_at", desc=True).limit(limit).execute()
        
        return [row["metadata"] for row in response.data] if response.data else []
    except Exception as e:
        print(f"[ERROR] Gagal baca list dari Supabase: {e}")
        return []


def delete_old_clustering_results(keep_last: int = 5, username: Optional[str] = None) -> int:
    """
    Hapus hasil clustering lama, simpan hanya N terbaru.
    
    Parameters
    ----------
    keep_last : int
        Berapa hasil terakhir yang disimpan.
    username : Optional[str]
        Filter berdasarkan username.
    
    Returns
    -------
    int
        Jumlah row yang dihapus.
    """
    if not USE_SUPABASE or not SUPABASE_OK:
        return 0
    
    try:
        # Ambil semua row
        query = supabase.table("clustering_results").select("id,created_at")
        
        if username:
            query = query.eq("username", username)
        
        response = query.order("created_at", desc=True).execute()
        
        if not response.data or len(response.data) <= keep_last:
            return 0
        
        # Hapus yang lama
        to_delete = response.data[keep_last:]
        delete_ids = [row["id"] for row in to_delete]
        
        for id_to_del in delete_ids:
            supabase.table("clustering_results").delete().eq("id", id_to_del).execute()
        
        return len(delete_ids)
    except Exception as e:
        print(f"[ERROR] Gagal delete old results: {e}")
        return 0
