"""
services/storage.py
File storage lokal — CSV disimpan ke disk.
Di server cloud (Render/Vercel) menggunakan /tmp karena hanya folder itu yang writable.
Persistensi lintas restart ditangani sepenuhnya oleh Supabase (db.py).
"""
from __future__ import annotations
import os
from typing import Optional


# ── File Upload ───────────────────────────────────────────────────────────────

def save_upload(file, filename: str, upload_folder: str) -> str:
    """
    Simpan file CSV upload ke disk lokal.
    Di server cloud (Render/Vercel) file ditulis ke /tmp/uploads.

    Parameters
    ----------
    file : FileStorage
        Objek file dari request.files.
    filename : str
        Nama file yang akan disimpan.
    upload_folder : str
        Folder lokal target.

    Returns
    -------
    str
        Path lokal file yang sudah disimpan.
    """
    # Di environment cloud gunakan /tmp (writable)
    if os.environ.get("RENDER") or os.environ.get("VERCEL"):
        folder = "/tmp/uploads"
    else:
        folder = upload_folder

    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    file.save(filepath)
    return filepath


def get_file_path(identifier: str) -> Optional[str]:
    """
    Kembalikan path lokal jika file ada di disk.

    Parameters
    ----------
    identifier : str
        Path lokal ke file CSV.

    Returns
    -------
    Optional[str]
        Path jika file ada di disk, None jika tidak ditemukan.
    """
    if not identifier:
        return None

    # Tolak identifier berupa URL — hanya path lokal yang didukung.
    if identifier.startswith("http"):
        return None

    return identifier if os.path.exists(identifier) else None


# ── Result Directory ──────────────────────────────────────────────────────────

def ensure_result_dir(result_dir: str) -> str:
    """
    Pastikan direktori untuk menyimpan hasil clustering ada dan writable.
    Di Render/Vercel gunakan /tmp.

    Parameters
    ----------
    result_dir : str
        Path direktori yang diinginkan.

    Returns
    -------
    str
        Path direktori yang sudah pasti bisa ditulis.
    """
    if os.environ.get("VERCEL") or os.environ.get("RENDER"):
        result_dir = os.path.join("/tmp", "results", os.path.basename(result_dir))
    os.makedirs(result_dir, exist_ok=True)
    return result_dir
