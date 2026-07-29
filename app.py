"""
app.py — Entry point Flask.
Clean architecture: semua logika bisnis ada di services/, config ada di config/.
"""
import io
import os
import uuid

import pandas as pd
from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from config.settings import (
    DEBUG,
    RESULTS_FOLDER,
    SCRAPING_FOLDER,
    SECRET_KEY,
    UPLOAD_FOLDER,
    USERS,
    DEFAULT_K,
)
from services.dataset_service import apply_metadata, load_dataset, try_restore_latest
from services.state import STATE, reset_messages, set_error, set_message
from services.storage import save_upload, ensure_result_dir
from services.db import save_clustering_result, delete_old_clustering_results
from utils.pipeline import TextPreprocessor, run_clustering

import functools

# ── App factory ───────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SCRAPING_FOLDER"] = SCRAPING_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB upload limit

# Buat folder hanya jika tidak di environment serverless (Vercel)
if not os.environ.get("VERCEL"):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(SCRAPING_FOLDER, exist_ok=True)
    os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Preprocessor singleton — lazy init untuk menghindari timeout di Vercel
_PREPROCESSOR = None

def get_preprocessor():
    """Lazy loading: init Sastrawi hanya saat pertama kali dipanggil."""
    global _PREPROCESSOR
    if _PREPROCESSOR is None:
        _PREPROCESSOR = TextPreprocessor()
    return _PREPROCESSOR


# ── Template context: tanggal Indonesia ──────────────────────────────────────

from datetime import datetime as _dt

@app.context_processor
def inject_tanggal():
    """Sediakan variabel `tanggal_laporan` di semua template."""
    _hari  = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    _bulan = ["Januari","Februari","Maret","April","Mei","Juni",
              "Juli","Agustus","September","Oktober","November","Desember"]
    now = _dt.now()
    tgl = f"Jakarta, {_hari[now.weekday()]} {now.day:02d} {_bulan[now.month-1]} {now.year}"
    return {"tanggal_laporan": tgl}


# ── Auth decorator ────────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def _inner(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return _inner


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if USERS.get(username) == password:
            # Reset seluruh state kalkulasi setiap kali login
            from services.state import STATE, _empty
            STATE.update(_empty())
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session["fresh_login"] = True   # flag: jangan restore sesi lama
            return redirect(url_for("dashboard"))
        error = "Username atau password salah. Silakan coba lagi."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    from services.state import STATE, _empty
    STATE.update(_empty())
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    # Hanya restore jika session bukan "fresh login" (bukan sesi yang baru dibuat)
    if not session.get("fresh_login"):
        try_restore_latest(username=session.get("username"))
    else:
        # Hapus flag fresh_login setelah satu kali kunjungan dashboard
        session.pop("fresh_login", None)
    return render_template(
        "dashboard.html",
        state=STATE,
        username=session.get("username", ""),
    )


# ── Dataset ───────────────────────────────────────────────────────────────────

@app.route("/dataset", methods=["GET", "POST"])
@login_required
def dataset():
    reset_messages()

    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or not file.filename:
            set_error("File CSV belum dipilih.")
            return redirect(url_for("dataset"))
        if not file.filename.lower().endswith(".csv"):
            set_error("Hanya file berekstensi .csv yang diizinkan.")
            return redirect(url_for("dataset"))

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        try:
            filepath = save_upload(file, file.filename, UPLOAD_FOLDER)
        except Exception as exc:
            set_error(f"File gagal disimpan: {exc}")
            return redirect(url_for("dataset"))

        try:
            filter_type = "all"
            load_dataset(filepath, "Dataset berhasil diunggah.", filter_type=filter_type)
        except Exception as exc:
            set_error(f"File gagal dibaca: {exc}")
            return redirect(url_for("dataset"))

        return redirect(url_for("dataset"))

    raw_preview = None
    if STATE["raw_df"] is not None:
        raw_preview = STATE["raw_df"].head(20).to_dict(orient="records")

    return render_template("dataset.html", state=STATE, raw_preview=raw_preview)


# ── Scraping ──────────────────────────────────────────────────────────────────

@app.route("/scraping", methods=["GET", "POST"])
@login_required
def scraping():
    reset_messages()

    if request.method == "POST":
        url = request.form.get("tiktok_url", "").strip()
        if not url.startswith("http"):
            set_error("URL TikTok tidak valid.")
            return redirect(url_for("scraping"))

        def _int(key, default, lo, hi):
            try:
                return max(lo, min(int(request.form.get(key, default)), hi))
            except (ValueError, TypeError):
                return default

        def _float(key, default, lo, hi):
            try:
                return max(lo, min(float(request.form.get(key, default)), hi))
            except (ValueError, TypeError):
                return default

        manual_wait    = _int("manual_wait", 20, 5, 180)
        max_comments   = _int("max_comments", 300, 10, 2000)
        max_empty      = _int("max_empty_scroll", 8, 3, 30)
        delay          = _float("delay", 2.0, 0.5, 8.0)

        try:
            from utils.tiktok_web_scraper import scrape_tiktok_for_web
            profile_dir = os.path.join(os.getcwd(), "profil_tiktok_web")
            result = scrape_tiktok_for_web(
                url=url,
                output_dir=SCRAPING_FOLDER,
                profile_dir=profile_dir,
                manual_wait=manual_wait,
                max_comments=max_comments,
                max_empty_scroll=max_empty,
                delay=delay,
                headless=False,
            )
            if not result.get("csv_path"):
                STATE["scraping_result"] = result
                set_error("Scraping selesai, tetapi komentar belum berhasil diambil.")
                return redirect(url_for("scraping"))

            load_dataset(
                result["csv_path"],
                f"Scraping berhasil: {result['total_comments']} komentar dimuat.",
            )
            STATE["scraping_result"] = result
            return redirect(url_for("dataset"))
        except ModuleNotFoundError:
            set_error("Dependency scraping belum terpasang. Jalankan: pip install -r requirements.txt")
        except Exception as exc:
            set_error(f"Scraping gagal: {exc}")
        return redirect(url_for("scraping"))

    return render_template("scraping.html", state=STATE)


# ── Preprocessing ─────────────────────────────────────────────────────────────

@app.route("/preprocessing", methods=["GET", "POST"])
@login_required
def preprocessing():
    reset_messages()

    if STATE["raw_df"] is None:
        set_error("Upload dataset terlebih dahulu.")
        return redirect(url_for("dataset"))

    if request.method == "POST":
        text_col = request.form.get("text_column", "")
        if not text_col or text_col not in STATE["raw_df"].columns:
            set_error("Kolom komentar tidak valid.")
            return redirect(url_for("preprocessing"))

        df = STATE["raw_df"].copy()
        df[text_col] = df[text_col].fillna("").astype(str)

        jumlah_data_awal            = len(df)
        jumlah_tidak_null           = int(STATE["raw_df"][text_col].notna().sum())

        df = df[df[text_col].str.split().str.len() >= 3].copy()
        jumlah_setelah_filter_raw   = len(df)

        df["komentar_bersih"] = df[text_col].apply(get_preprocessor().preprocess)
        df = df[df["komentar_bersih"].str.strip() != ""].reset_index(drop=True)
        jumlah_setelah_clean        = len(df)

        df = df[df["komentar_bersih"].str.split().str.len() >= 2].copy()
        jumlah_setelah_min          = len(df)

        before_dedup                = len(df)
        df = df.drop_duplicates(subset=["komentar_bersih"]).reset_index(drop=True)
        jumlah_duplikat             = before_dedup - len(df)

        if len(df) == 0:
            set_error("Tidak ada data valid setelah preprocessing. Coba kolom lain atau periksa isi dataset.")
            return redirect(url_for("preprocessing"))

        STATE["processed_df"]       = df
        STATE["result_df"]          = None
        STATE["text_column"]        = text_col
        STATE["preprocessing_stats"] = {
            "jumlah_data_awal":                int(jumlah_data_awal),
            "jumlah_tidak_null":               jumlah_tidak_null,
            "jumlah_setelah_filter_raw":       int(jumlah_setelah_filter_raw),
            "jumlah_setelah_clean_nonempty":   int(jumlah_setelah_clean),
            "jumlah_setelah_min_kata_bersih":  int(jumlah_setelah_min),
            "jumlah_duplikat_dihapus":         int(jumlah_duplikat),
            "jumlah_data_valid":               int(len(df)),
        }
        set_message("Preprocessing berhasil dilakukan.")
        return redirect(url_for("preprocessing"))

    preview = None
    if STATE["processed_df"] is not None:
        cols = [c for c in [STATE["text_column"], "komentar_bersih"]
                if c in STATE["processed_df"].columns]
        preview = STATE["processed_df"][cols].head(30).to_dict(orient="records")

    return render_template("preprocessing.html", state=STATE, preview=preview)


# ── Clustering ────────────────────────────────────────────────────────────────

@app.route("/clustering", methods=["GET", "POST"])
@login_required
def clustering():
    reset_messages()

    if STATE["processed_df"] is None:
        set_error("Lakukan preprocessing terlebih dahulu.")
        return redirect(url_for("preprocessing"))

    if request.method == "POST":
        try:
            k = int(request.form.get("jumlah_cluster", DEFAULT_K))
        except (ValueError, TypeError):
            k = DEFAULT_K

        # Batasi hanya 2, 3, 4, 5
        if k not in (2, 3, 4, 5):
            k = DEFAULT_K

        n = len(STATE["processed_df"])
        if n < 3:
            set_error("Data terlalu sedikit untuk clustering (minimal 3 baris).")
            return redirect(url_for("clustering"))

        k = max(2, min(k, n - 1))
        STATE["k"] = k

        try:
            result_id  = uuid.uuid4().hex[:8]
            result_dir = ensure_result_dir(os.path.join(RESULTS_FOLDER, result_id))
            metadata   = run_clustering(
                csv_path          = STATE["upload_path"],
                result_dir        = result_dir,
                komentar_col      = STATE["text_column"],
                jumlah_cluster    = k,
                min_kata_raw      = 3,
                processed_df      = STATE["processed_df"],
                preprocessing_stats = STATE["preprocessing_stats"],
            )
            apply_metadata(metadata, result_dir)
            # Simpan ke Supabase agar persisten lintas restart.
            # Isi CSV di-encode base64 dan disimpan di kolom csv_content
            # sehingga bisa di-restore setelah server restart tanpa file lokal.
            save_clustering_result(
                result_id=result_id,
                metadata=metadata,
                username=session.get("username", "unknown"),
                csv_path=STATE.get("upload_path"),
            )
            # Bersihkan hasil lama (simpan 5 terakhir per user)
            delete_old_clustering_results(
                keep_last=5,
                username=session.get("username", "unknown"),
            )
        except Exception as exc:
            set_error(f"Clustering gagal: {exc}")
            return redirect(url_for("clustering"))

        set_message("Clustering berhasil dilakukan.")
        return redirect(url_for("visualisasi"))

    return render_template("clustering.html", state=STATE)


# ── Read-only result routes ───────────────────────────────────────────────────

def _require_result():
    """Kembalikan True jika result sudah ada / berhasil di-restore."""
    if STATE["result_df"] is not None:
        return True
    from flask import session as _session
    return try_restore_latest(username=_session.get("username"))


@app.route("/visualisasi")
@login_required
def visualisasi():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))
    return render_template("visualisasi.html", state=STATE)


@app.route("/evaluasi")
@login_required
def evaluasi():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))
    return render_template("evaluasi.html", state=STATE)


@app.route("/interpretasi")
@login_required
def interpretasi():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))
    return render_template("interpretasi.html", state=STATE)


# ── Laporan pages (report views) ─────────────────────────────────────────────

@app.route("/laporan/evaluasi")
@login_required
def laporan_evaluasi():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))
    return render_template("laporan_evaluasi.html", state=STATE)


@app.route("/laporan/visualisasi")
@login_required
def laporan_visualisasi():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))
    return render_template("laporan_visualisasi.html", state=STATE)


@app.route("/laporan/interpretasi")
@login_required
def laporan_interpretasi():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))
    return render_template("laporan_interpretasi.html", state=STATE)


@app.route("/laporan/hasil")
@login_required
def laporan_hasil():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))

    cluster_filter  = request.args.get("cluster", "all")
    search_query    = request.args.get("q", "").strip()

    df = STATE["result_df"].copy()
    df = df.dropna(subset=["cluster"])
    df["cluster"] = df["cluster"].astype(int)

    if cluster_filter != "all":
        try:
            df = df[df["cluster"] == int(cluster_filter)]
        except (ValueError, TypeError):
            cluster_filter = "all"

    if search_query:
        q_low = search_query.lower()
        text_cols = [c for c in [STATE["text_column"], "komentar", "komentar_bersih", "label_cluster"]
                     if c in df.columns]
        if text_cols:
            mask = pd.Series(False, index=df.index)
            for col in text_cols:
                mask |= df[col].fillna("").astype(str).str.lower().str.contains(q_low, regex=False)
            df = df[mask]

    clean_result    = STATE["result_df"].dropna(subset=["cluster"])
    cluster_options = sorted(clean_result["cluster"].astype(int).unique().tolist())
    preview         = df.to_dict(orient="records")

    return render_template(
        "laporan_hasil.html",
        state           = STATE,
        preview         = preview,
        cluster_options = cluster_options,
        cluster_filter  = cluster_filter,
        search_query    = search_query,
        total_filtered  = len(df),
    )


@app.route("/hasil")
@login_required
def hasil():
    if not _require_result():
        set_error("Lakukan clustering terlebih dahulu.")
        return redirect(url_for("clustering"))

    cluster_filter = request.args.get("cluster", "all")
    search_query   = request.args.get("q", "").strip()

    df = STATE["result_df"].copy()
    df = df.dropna(subset=["cluster"])
    df["cluster"] = df["cluster"].astype(int)

    if cluster_filter != "all":
        try:
            df = df[df["cluster"] == int(cluster_filter)]
        except (ValueError, TypeError):
            cluster_filter = "all"

    if search_query:
        q_low = search_query.lower()
        text_cols = [c for c in [STATE["text_column"], "komentar", "komentar_bersih", "label_cluster"]
                     if c in df.columns]
        if text_cols:
            mask = pd.Series(False, index=df.index)
            for col in text_cols:
                mask |= df[col].fillna("").astype(str).str.lower().str.contains(q_low, regex=False)
            df = df[mask]

    clean_result   = STATE["result_df"].dropna(subset=["cluster"])
    cluster_options = sorted(clean_result["cluster"].astype(int).unique().tolist())
    preview        = df.to_dict(orient="records")

    return render_template(
        "hasil.html",
        state          = STATE,
        preview        = preview,
        cluster_options = cluster_options,
        cluster_filter = cluster_filter,
        search_query   = search_query,
        total_filtered = len(df),
    )


# ── Download routes ───────────────────────────────────────────────────────────

@app.route("/download")
@login_required
def download():
    if not _require_result():
        return "Belum ada hasil clustering.", 404

    buf = io.BytesIO()
    STATE["result_df"].to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return send_file(
        buf,
        mimetype     = "text/csv",
        as_attachment = True,
        download_name = "hasil_clustering_bank_mandiri.csv",
    )


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/download_laporan")
@login_required
def download_laporan():
    """Laporan PDF lengkap (semua bagian)."""
    if not _require_result():
        return "Belum ada hasil clustering.", 404
    try:
        from services.report_pdf import generate_pdf
        return _pdf_response(generate_pdf(STATE),
                             "laporan_clustering_bank_mandiri.pdf")
    except Exception as exc:
        return f"Gagal membuat PDF: {exc}", 500


@app.route("/download_laporan/evaluasi")
@login_required
def download_laporan_evaluasi():
    if not _require_result():
        return "Belum ada hasil clustering.", 404
    try:
        from services.report_pdf import generate_pdf_evaluasi
        return _pdf_response(generate_pdf_evaluasi(STATE),
                             "laporan_evaluasi_cluster.pdf")
    except Exception as exc:
        return f"Gagal membuat PDF: {exc}", 500


@app.route("/download_laporan/visualisasi")
@login_required
def download_laporan_visualisasi():
    if not _require_result():
        return "Belum ada hasil clustering.", 404
    try:
        from services.report_pdf import generate_pdf_visualisasi
        return _pdf_response(generate_pdf_visualisasi(STATE),
                             "laporan_visualisasi_cluster.pdf")
    except Exception as exc:
        return f"Gagal membuat PDF: {exc}", 500


@app.route("/download_laporan/interpretasi")
@login_required
def download_laporan_interpretasi():
    if not _require_result():
        return "Belum ada hasil clustering.", 404
    try:
        from services.report_pdf import generate_pdf_interpretasi
        return _pdf_response(generate_pdf_interpretasi(STATE),
                             "laporan_interpretasi_cluster.pdf")
    except Exception as exc:
        return f"Gagal membuat PDF: {exc}", 500


@app.route("/download_laporan/hasil")
@login_required
def download_laporan_hasil():
    if not _require_result():
        return "Belum ada hasil clustering.", 404
    cluster_filter = request.args.get("cluster", "all")
    search_query   = request.args.get("q", "").strip()
    try:
        from services.report_pdf import generate_pdf_hasil
        return _pdf_response(
            generate_pdf_hasil(STATE,
                               result_df=STATE["result_df"],
                               cluster_filter=cluster_filter,
                               search_query=search_query),
            "laporan_hasil_clustering.pdf",
        )
    except Exception as exc:
        return f"Gagal membuat PDF: {exc}", 500


if __name__ == "__main__":
    app.run(debug=DEBUG, port=4040)
