"""
services/storage.py
Abstraksi untuk file storage — lokal atau Cloudinary (cloud).
File CSV upload disimpan ke Cloudinary agar persisten lintas restart.
"""
from __future__ import annotations
import os
import io
from typing import Optional

# ── Cloudinary setup ──────────────────────────────────────────────────────────
USE_CLOUDINARY = os.environ.get("USE_CLOUDINARY", "0") == "1"
CLOUDINARY_OK  = False

if USE_CLOUDINARY:
    try:
        import cloudinary
        import cloudinary.uploader
        import cloudinary.api
        from cloudinary.utils import cloudinary_url

        cloudinary.config(
            cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
            api_key    = os.environ.get("CLOUDINARY_API_KEY"),
            api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
            secure     = True,
        )
        CLOUDINARY_OK = True
    except ImportError:
        CLOUDINARY_OK  = False
        USE_CLOUDINARY = False


# ── File Upload ───────────────────────────────────────────────────────────────

def save_upload(file, filename: str, upload_folder: str) -> str:
    """
    Simpan file CSV upload.
    - Jika Cloudinary aktif → upload ke cloud, return secure_url
    - Jika tidak → simpan ke disk lokal (/tmp di Render)

    Parameters
    ----------
    file : FileStorage
        Objek file dari request.files.
    filename : str
        Nama file yang akan disimpan.
    upload_folder : str
        Folder lokal sebagai fallback.

    Returns
    -------
    str
        URL Cloudinary atau path lokal.
    """
    if USE_CLOUDINARY and CLOUDINARY_OK:
        # Baca isi file ke bytes lalu upload
        file_bytes = file.read()
        result = cloudinary.uploader.upload(
            io.BytesIO(file_bytes),
            resource_type = "raw",             # CSV bukan image
            public_id     = f"uploads/{os.path.splitext(filename)[0]}",
            format        = "csv",
            overwrite     = True,
            use_filename  = False,
        )
        return result["secure_url"]
    else:
        # Fallback: simpan ke disk
        folder = "/tmp/uploads" if (os.environ.get("RENDER") or os.environ.get("VERCEL")) else upload_folder
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return filepath


def get_file_path(identifier: str) -> Optional[str]:
    """
    Ambil path lokal dari identifier (URL atau path).
    Jika berupa Cloudinary URL → download ke /tmp terlebih dahulu.

    Parameters
    ----------
    identifier : str
        URL Cloudinary atau path file lokal.

    Returns
    -------
    Optional[str]
        Path lokal yang bisa dibaca pandas, atau None jika tidak ada.
    """
    if not identifier:
        return None

    if identifier.startswith("http"):
        import requests
        # Ambil nama file dari URL (tanpa query string)
        raw_name = identifier.split("/")[-1].split("?")[0]
        # Pastikan ekstensi .csv
        if not raw_name.endswith(".csv"):
            raw_name += ".csv"
        local_path = f"/tmp/{raw_name}"
        if not os.path.exists(local_path):
            try:
                response = requests.get(identifier, timeout=30)
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(response.content)
            except Exception as e:
                print(f"[ERROR] Gagal download file dari Cloudinary: {e}")
                return None
        return local_path
    else:
        return identifier if os.path.exists(identifier) else None


# ── Result Directory ──────────────────────────────────────────────────────────

def ensure_result_dir(result_dir: str) -> str:
    """
    Pastikan direktori untuk menyimpan hasil clustering ada dan writable.
    Di Render/Vercel (read-only fs), gunakan /tmp.

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
