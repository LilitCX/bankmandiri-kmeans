"""
config/settings.py
Centralized configuration — semua konstanta, credential, path ada di sini.
"""
import os

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
    "Gelora, Tanah Abang, Jakarta Pusat"
)
COMPANY_WEBSITE: str = "www.bankmandiri.co.id"
SIGNER_NAME: str = "Rahmad Supandi"
SIGNER_TITLE: str = "Direktur"
LOGO_PATH: str = os.path.join(STATIC_FOLDER, "logo.png")

# ── Pipeline ──────────────────────────────────────────────────────────────────
DEFAULT_K: int = 4
MIN_KATA_RAW: int = 3
MIN_KATA_BERSIH: int = 2
MAX_TFIDF_FEATURES: int = 500
LSA_COMPONENTS: int = 60
KMEANS_MAX_ITER: int = 500
KMEANS_N_INIT_DEFAULT: int = 15
TSNE_N_ITER: int = 1000
TOPIC_FEATURE_WEIGHT: float = 8.0
