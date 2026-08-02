"""
config/settings.py
Centralized configuration — semua konstanta, credential, path ada di sini.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # baca .env otomatis, tidak menimpa env var yang sudah ada

# ── Flask ─────────────────────────────────────────────────────────────────────
SECRET_KEY: str = os.environ.get("SECRET_KEY", "kmeans-mandiri-ta-2024-secret")
DEBUG: bool = os.environ.get("FLASK_DEBUG", "0") == "1"

# ── Folders ───────────────────────────────────────────────────────────────────
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER: str = os.path.join(BASE_DIR, "uploads")
SCRAPING_FOLDER: str = os.path.join(UPLOAD_FOLDER, "scraping")
RESULTS_FOLDER: str = os.path.join(BASE_DIR, "static", "results")
STATIC_FOLDER: str = os.path.join(BASE_DIR, "static")

# ── Auth ──────────────────────────────────────────────────────────────────────
# Simpan credential di environment variable untuk production.
# Fallback ke hardcoded hanya untuk development lokal.
USERS: dict[str, str] = {
    os.environ.get("APP_USERNAME", "admin"): os.environ.get("APP_PASSWORD", "rahmad123"),
}

# ── Report / PDF ──────────────────────────────────────────────────────────────
COMPANY_NAME: str = "PT Bank Mandiri (Persero) Tbk"
COMPANY_ADDRESS: str = (
    "Senayan City, Lantai LGF, No. 07B, Jl. Asia Afrika Lot.19, "
    "Gelora, Tanah Abang, Jakarta Pusat 10270"
)
COMPANY_PHONE: str = "(021) 5263000"
COMPANY_EMAIL: str = "corporate.secretary@bankmandiri.co.id"
COMPANY_WEBSITE: str = "www.bankmandiri.co.id"
SIGNER_NAME: str = "Gilang Afandi Harahap"
SIGNER_TITLE: str = "Pimpinan"
LOGO_PATH: str = os.path.join(STATIC_FOLDER, "logo.png")

# ── Pipeline ──────────────────────────────────────────────────────────────────
DEFAULT_K: int = 5
MIN_KATA_RAW: int = 3
MIN_KATA_BERSIH: int = 2
MAX_TFIDF_FEATURES: int = 500
# LSA: 30 komponen sudah cukup untuk memisahkan 5 topik utama dan lebih cepat
# dari 60. Silhouette score tidak turun signifikan karena topik-topik utama
# terwakili dalam 30 dimensi pertama.
LSA_COMPONENTS: int = 30
# KMeans: max_iter 300 cukup — konvergensi biasanya tercapai jauh sebelumnya.
# n_init 10 → 5 untuk evaluasi multi-k (dijalankan 4x), penghematan 2x.
KMEANS_MAX_ITER: int = 300
KMEANS_N_INIT_DEFAULT: int = 5
# t-SNE: 500 iterasi sudah menghasilkan proyeksi yang stabil untuk visualisasi.
# Pengurangan dari 1000 → 500 memangkas waktu t-SNE ~50%.
TSNE_N_ITER: int = 500
TOPIC_FEATURE_WEIGHT: float = 8.0

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
