"""
services/report_pdf.py
Generate 4 laporan PDF terpisah + laporan lengkap.
Engine: xhtml2pdf (fallback WeasyPrint).
Orientasi: A4 Landscape. Tabel rapi dengan word-wrap. Grafik + wordcloud hi-res.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime
from typing import Any

from config.settings import (
    COMPANY_ADDRESS,
    COMPANY_EMAIL,
    COMPANY_NAME,
    COMPANY_PHONE,
    COMPANY_WEBSITE,
    LOGO_PATH,
    SIGNER_NAME,
    SIGNER_TITLE,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _logo_b64() -> str:
    if not os.path.exists(LOGO_PATH):
        return ""
    with open(LOGO_PATH, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext  = os.path.splitext(LOGO_PATH)[1].lstrip(".").lower()
    mime = "png" if ext == "png" else ("jpeg" if ext in ("jpg","jpeg") else "png")
    return f"data:image/{mime};base64,{data}"


def _fmt_float(val: Any, decimals: int = 4) -> str:
    if val is None:
        return "-"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_int(val: Any) -> str:
    if val is None:
        return "-"
    try:
        return f"{int(val):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(val)


def _tanggal_indonesia() -> str:
    hari  = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    bulan = ["Januari","Februari","Maret","April","Mei","Juni",
             "Juli","Agustus","September","Oktober","November","Desember"]
    now = datetime.now()
    return f"Jakarta, {hari[now.weekday()]} {now.day:02d} {bulan[now.month-1]} {now.year}"

_CLUSTER_COLORS = [
    "#2E86DE","#F39C12","#10B981","#8B5CF6",
    "#EF4444","#EC4899","#14B8A6","#6366F1",
]

def _cluster_color(cid: int) -> str:
    return _CLUSTER_COLORS[int(cid) % len(_CLUSTER_COLORS)]


# ─────────────────────────────────────────────────────────────────────────────
# CSS  — xhtml2pdf subset, A4 Landscape (297×210mm), margin 14mm semua sisi
# Area cetak: ±269×182mm
# Aturan kritis:
#   • word-wrap/overflow-wrap di td mencegah teks keluar sel
#   • thead { display:table-header-group } mengulang header di setiap halaman
#   • tr { page-break-inside:avoid } mencegah baris terpotong
#   • float + clear:both untuk layout 2-kolom (gambar berdampingan)
#   • table-layout:fixed hanya pada tabel yang lebar kolomnya eksplisit
#   • .chart-block { page-break-inside:avoid } menjaga judul+deskripsi+gambar
#     selalu satu halaman
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

@page {
    size: A4 landscape;
    margin: 14mm 16mm 16mm 16mm;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 8.5pt;
    color: #1E293B;
    background: #ffffff;
    line-height: 1.55;
}

/* ══════════════════════════════════════════════════════
   KOP SURAT PROFESIONAL
   Layout: logo float-left | teks identitas perusahaan
   Garis bawah tebal memisahkan kop dari judul laporan
   ══════════════════════════════════════════════════════ */
.kop {
    overflow: hidden;
    padding-bottom: 10px;
    margin-bottom: 0;
}
.kop-logo-wrap {
    float: left;
    width: 58px;
    margin-right: 14px;
    padding-top: 2px;
}
.kop-logo-wrap img {
    width: 58px;
    height: auto;
    display: block;
}
/* Placeholder kotak abu jika logo tidak ada */
.kop-logo-placeholder {
    width: 58px; height: 58px;
    background: #E2E8F0;
    border: 1px solid #CBD5E1;
    display: block;
}
.kop-identity { overflow: hidden; }
.kop-company-name {
    font-size: 14pt;
    font-weight: 800;
    color: #1D4ED8;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 3px;
    line-height: 1.2;
}
.kop-detail {
    font-size: 7.5pt;
    color: #475569;
    line-height: 1.65;
    margin: 0;
}
.kop-detail span.kop-label {
    font-weight: 700;
    color: #334155;
    display: inline;
}
.kop-clear { clear: both; }

/* Garis pemisah kop dari judul laporan */
.kop-divider {
    border: none;
    border-top: 3px double #1D4ED8;
    margin: 8px 0 0 0;
    padding: 0;
}

/* ── Judul Laporan ── */
.report-title-block {
    text-align: center;
    padding: 9px 0 7px 0;
    border-bottom: 1px solid #E2E8F0;
    margin-bottom: 12px;
}
.report-title-block h2 {
    font-size: 11.5pt; font-weight: 800; color: #1E293B;
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px;
}
.report-title-block .subtitle { font-size: 7.5pt; color: #64748B; }
.report-title-block .print-meta {
    font-size: 7pt; color: #94A3B8; margin-top: 3px;
}

/* ── Section ── */
.section { margin-bottom: 14px; }
.section-title {
    font-size: 9pt; font-weight: 800; color: #1D4ED8;
    text-transform: uppercase; letter-spacing: 0.3px;
    margin-bottom: 6px; padding-bottom: 3px;
    border-bottom: 1.5px solid #BFDBFE;
}

/* ══════════════════════════════════════════════════════
   TABEL UMUM
   word-wrap + overflow-wrap di td mencegah teks keluar sel.
   thead display:table-header-group mengulang header.
   tr page-break-inside:avoid mencegah baris terpotong.
   ══════════════════════════════════════════════════════ */
table {
    border-collapse: collapse;
    width: 100%;
    font-size: 7.5pt;
    margin-bottom: 8px;
}
thead { display: table-header-group; }
th {
    background: #1D4ED8;
    color: #ffffff;
    padding: 5px 6px;
    text-align: center;
    font-weight: 700;
    font-size: 7pt;
    border: 1px solid #1D4ED8;
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: normal;
}
td {
    padding: 4px 6px;
    border: 1px solid #CBD5E1;
    vertical-align: top;
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: normal;
    font-size: 7.5pt;
    line-height: 1.5;
}
tr { page-break-inside: avoid; }
tr:nth-child(even) td { background: #F8FAFC; }
tr:nth-child(odd)  td { background: #ffffff;  }

/* Tabel dengan lebar kolom tetap — gunakan class .tbl-fixed */
.tbl-fixed { table-layout: fixed; }

.td-center { text-align: center; }
.td-right  { text-align: right; }
.td-num    { font-family: monospace; font-size: 7.5pt; text-align: center; white-space: normal; }
.td-mono   { font-family: monospace; font-size: 7pt; color: #475569; white-space: normal; }
.td-wrap   { word-wrap: break-word; overflow-wrap: break-word; white-space: normal; }
/* Kolom keterangan — izinkan wrap penuh agar tidak overflow */
.td-ket    {
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: normal;
    font-size: 7pt;
    color: #475569;
    line-height: 1.5;
}

/* ── Metric tiles (float layout) ── */
.metric-row { overflow: hidden; margin-bottom: 10px; }
.metric-box {
    float: left; width: 31%; margin-right: 2.5%;
    background: #EFF6FF; border: 1.5px solid #BFDBFE;
    border-radius: 4px; padding: 7px 9px;
    text-align: center; margin-bottom: 6px;
}
.metric-box:nth-child(3n) { margin-right: 0; }
.metric-clear { clear: both; }
.metric-box .lbl {
    font-size: 6.5pt; color: #3B82F6; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 3px;
}
.metric-box .val { font-size: 12pt; font-weight: 800; color: #1E293B; }

/* ══════════════════════════════════════════════════════
   CHART BLOCK — judul + deskripsi + gambar + caption
   selalu satu blok, tidak terpisah halaman.
   Gunakan page-break-before:auto agar blok pindah ke
   halaman baru hanya jika tidak muat di halaman sekarang.
   ══════════════════════════════════════════════════════ */
.chart-block {
    page-break-inside: avoid;
    margin-bottom: 12px;
}
.chart-block-title {
    font-size: 8.5pt; font-weight: 800; color: #1D4ED8;
    margin-bottom: 3px;
}
.chart-block-desc {
    font-size: 7pt; color: #475569;
    margin-bottom: 5px; line-height: 1.55;
}
.chart-block-caption {
    font-size: 6.5pt; color: #64748B;
    text-align: center; margin-top: 4px; font-style: italic;
}

/* ── Gambar (grafik / wordcloud) ── */
.chart-img {
    width: 100%; max-width: 100%; height: auto;
    border: 1px solid #E2E8F0; border-radius: 4px;
    display: block;
}
.chart-label {
    font-size: 8pt; font-weight: 700; color: #1D4ED8;
    text-align: center; margin-bottom: 4px;
}
.chart-note {
    font-size: 6.5pt; color: #64748B;
    text-align: center; margin-top: 3px;
}

/* Layout 2 gambar berdampingan — float */
.img-left  { float: left;  width: 48%; margin-right: 4%; page-break-inside: avoid; }
.img-right { float: left;  width: 48%; page-break-inside: avoid; }
.img-clear { clear: both; }

/* Layout wordcloud 2-per-baris — float */
.wc-left  { float: left; width: 48%; margin-right: 4%;
            margin-bottom: 8px; page-break-inside: avoid; }
.wc-right { float: left; width: 48%;
            margin-bottom: 8px; page-break-inside: avoid; }
.wc-row-clear { clear: both; }
.wc-title {
    font-size: 8pt; font-weight: 700; color: #1D4ED8;
    text-align: center; margin-bottom: 4px;
}
.wc-img {
    width: 100%; height: auto;
    border: 1px solid #E2E8F0; border-radius: 4px;
    display: block;
}
.wc-card {
    border: 1px solid #E2E8F0; padding: 6px;
    border-radius: 4px; background: #FAFAFA;
    page-break-inside: avoid;
}

/* ── Cluster card (interpretasi) ── */
.cluster-card {
    margin-bottom: 12px;
    border-left: 3px solid #CBD5E1;
    padding-left: 10px;
    page-break-inside: avoid;
}
.cluster-card h3 {
    font-size: 9.5pt; font-weight: 800; color: #1E293B; margin-bottom: 2px;
}
.cluster-card .meta {
    font-size: 7.5pt; color: #64748B; margin-bottom: 5px;
}
.cluster-card .words-label {
    font-size: 7pt; font-weight: 700; color: #94A3B8;
    margin-bottom: 3px; text-transform: uppercase;
}

/* ── Badge ── */
.badge {
    display: inline; padding: 1px 5px;
    border-radius: 3px; font-weight: 700;
    font-size: 7.5pt; color: #ffffff;
}

/* ── Top-word chip ── */
.topword {
    display: inline; background: #F1F5F9;
    border: 1px solid #CBD5E1; border-radius: 2px;
    padding: 0 4px; font-size: 6.5pt;
    font-family: monospace; color: #334155; margin: 1px;
}

/* ── Catatan kecil ── */
.note {
    font-size: 7pt; color: #64748B;
    margin-top: 4px; line-height: 1.5;
}

/* ── Tanda tangan ── */
.signature-block {
    margin-top: 24px; padding-bottom: 12px; text-align: right;
    page-break-inside: avoid;
}
.signature-block .city-date { font-size: 8pt; color: #475569; margin-bottom: 2px; }
.signature-block .greeting  { font-size: 8pt; color: #475569; margin-bottom: 38px; }
.signature-block .sig-line  {
    border-top: 1.5px solid #1E293B;
    width: 140px; margin: 0 0 2px auto;
}
.signature-block .sig-name  { font-size: 9pt; font-weight: 800; color: #1E293B; }
.signature-block .sig-title { font-size: 8pt; color: #475569; }

/* ── Page break ── */
.page-break { page-break-before: always; }
.no-break   { page-break-inside: avoid; }
"""

# ─────────────────────────────────────────────────────────────────────────────
# SHARED BUILDING BLOCKS
# ─────────────────────────────────────────────────────────────────────────────

def _kop(logo_b64: str) -> str:
    """Kop surat profesional: logo kiri | nama perusahaan + detail kontak.
    Diikuti garis pemisah double-line, lalu judul laporan.
    """
    if logo_b64:
        logo_html = (
            f'<div class="kop-logo-wrap">'
            f'<img src="{logo_b64}" alt="Logo {COMPANY_NAME}">'
            f'</div>'
        )
    else:
        logo_html = '<div class="kop-logo-wrap"><div class="kop-logo-placeholder"></div></div>'

    return (
        f'<div class="kop">'
        f'{logo_html}'
        f'<div class="kop-identity">'
        f'<div class="kop-company-name">{COMPANY_NAME}</div>'
        f'<div class="kop-detail">'
        f'<span class="kop-label">Alamat&nbsp;:</span> {COMPANY_ADDRESS}<br>'
        f'<span class="kop-label">Telepon&nbsp;:</span> {COMPANY_PHONE}'
        f'&nbsp;&nbsp;&nbsp;'
        f'<span class="kop-label">Email&nbsp;:</span> {COMPANY_EMAIL}<br>'
        f'<span class="kop-label">Website&nbsp;:</span> {COMPANY_WEBSITE}'
        f'</div>'
        f'</div>'
        f'<div class="kop-clear"></div>'
        f'</div>'
        f'<hr class="kop-divider">'
    )


def _title_block(judul: str, generated_at: str) -> str:
    return (
        f'<div class="report-title-block">'
        f'<h2>{judul}</h2>'
        f'<div class="subtitle">'
        f'TF-IDF &bull; LSA/SVD &bull; K-Means Clustering'
        f'</div>'
        f'<div class="print-meta">Dicetak: {generated_at}</div>'
        f'</div>'
    )


def _signature() -> str:
    return (
        f'<div class="signature-block">'
        f'<p class="city-date">{_tanggal_indonesia()}</p>'
        f'<p class="greeting">Mengetahui,</p>'
        f'<div class="sig-line"></div>'
        f'<p class="sig-name">{SIGNER_NAME}</p>'
        f'<p class="sig-title">{SIGNER_TITLE}</p>'
        f'</div>'
    )


def _wrap_html(title: str, body: str) -> str:
    return (
        f'<!DOCTYPE html><html lang="id"><head>'
        f'<meta charset="UTF-8"><title>{title}</title>'
        f'<style>{_CSS}</style>'
        f'</head><body>{body}</body></html>'
    )


def _embed_img(b64: str, alt: str = "", extra_css: str = "") -> str:
    """Buat <img> dari base64 PNG. Kosong jika b64 kosong."""
    if not b64:
        return ""
    style = f' style="{extra_css}"' if extra_css else ""
    return f'<img src="data:image/png;base64,{b64}" class="chart-img"{style} alt="{alt}">'


def _topwords(words: list, max_n: int = 10) -> str:
    return " ".join(
        f'<span class="topword">{w}</span>'
        for w in (words or [])[:max_n]
    )

def _metric_tiles(*pairs) -> str:
    """Buat metric tiles dari pasangan (label, value).
    pairs: urutan (label, value, label, value, ...)
    Maksimal 6 tile (3 per baris) untuk layout landscape yang rapi."""
    boxes = ""
    it = iter(pairs)
    for lbl, val in zip(it, it):
        boxes += (
            f'<div class="metric-box">'
            f'<div class="lbl">{lbl}</div>'
            f'<div class="val">{val}</div>'
            f'</div>'
        )
    return (
        f'<div class="metric-row">{boxes}'
        f'<div class="metric-clear"></div></div>'
    )


def _two_imgs(left_b64: str, left_lbl: str,
              right_b64: str, right_lbl: str,
              left_desc: str = "", right_desc: str = "",
              caption: str = "") -> str:
    """Dua grafik berdampingan menggunakan float div.
    Setiap sisi dibungkus .chart-block agar judul+deskripsi+gambar+caption
    tidak terpisah halaman (page-break-inside:avoid).
    """
    def _side(b64: str, lbl: str, desc: str) -> str:
        img = (_embed_img(b64, lbl, "width:100%;height:auto;")
               or '<p class="note" style="text-align:center;">Grafik tidak tersedia.</p>')
        desc_html = f'<p class="chart-block-desc">{desc}</p>' if desc else ""
        return (
            f'<div class="chart-block">'
            f'<p class="chart-block-title">{lbl}</p>'
            f'{desc_html}'
            f'{img}'
            f'</div>'
        )

    cap_html = (f'<p class="chart-block-caption">{caption}</p>' if caption else "")

    return (
        f'<div style="overflow:hidden;">'
        f'<div class="img-left">{_side(left_b64, left_lbl, left_desc)}</div>'
        f'<div class="img-right">{_side(right_b64, right_lbl, right_desc)}</div>'
        f'<div class="img-clear"></div>'
        f'</div>'
        f'{cap_html}'
    )


def _wc_grid(wc_items: list, cs: list) -> str:
    """Render wordcloud dalam grid 2-per-baris menggunakan float."""
    html = ""
    for i in range(0, len(wc_items), 2):
        pair = wc_items[i: i + 2]
        cells = ""
        sides = ["wc-left", "wc-right"]
        for idx, (cid_raw, img_b64) in enumerate(pair):
            cid   = int(cid_raw)
            color = _cluster_color(cid)
            label = next(
                (x.get("label","") for x in cs if int(x.get("cluster",-1)) == cid),
                f"Cluster {cid}",
            )
            img_tag = (
                f'<img src="data:image/png;base64,{img_b64}" class="wc-img" '
                f'alt="Wordcloud C{cid}">'
                if img_b64
                else f'<p class="note" style="text-align:center;padding:12px 0;">'
                     f'Tidak ada kata cukup.</p>'
            )
            cells += (
                f'<div class="{sides[idx]}">'
                f'<div class="wc-card">'
                f'<p class="wc-title" style="color:{color};">'
                f'C{cid} &mdash; {label}</p>'
                f'{img_tag}'
                f'</div></div>'
            )
        html += (
            f'<div style="overflow:hidden;">{cells}'
            f'<div class="wc-row-clear"></div></div>'
        )
    return html

# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN EVALUASI
# Isi: Metrik model, Preprocessing stats, Rekomendasi K,
#      Tabel perbandingan k, Grafik Elbow+Silhouette, Kualitas per cluster,
#      Seed validation, Catatan interpretasi.
# TIDAK ADA: wordcloud, scatter, daftar komentar
# ─────────────────────────────────────────────────────────────────────────────

def _html_evaluasi(state: dict, logo_b64: str, now_str: str) -> str:
    m   = state.get("metrics") or {}
    pre = state.get("preprocessing_stats") or {}
    bk  = state.get("best_k") or {}
    cs  = state.get("cluster_summary") or []

    # ── Metrik utama ──────────────────────────────────────────────────────
    metrics_html = ""
    if m:
        metrics_html = _metric_tiles(
            "Total Data",      _fmt_int(m.get("total_data")),
            "Jumlah Cluster",  _fmt_int(m.get("jumlah_cluster")),
            "Silhouette Score", _fmt_float(m.get("silhouette_score"), 4),
            "Fitur TF-IDF",    _fmt_int(m.get("jumlah_fitur_tfidf")),
            "Komponen LSA",    _fmt_int(m.get("jumlah_komponen_lsa")),
            "Variansi LSA",    _fmt_float(m.get("variansi_lsa"), 4),
        )

    # ── Statistik Preprocessing ───────────────────────────────────────────
    prep_html = ""
    if pre:
        rows = (
            f'<tr><td>Data Awal</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_data_awal"))}</td>'
            f'<td>Total baris dataset unggahan</td></tr>'
            f'<tr><td>Tidak Null</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_tidak_null"))}</td>'
            f'<td>Baris dengan nilai komentar terisi</td></tr>'
            f'<tr><td>Lolos Filter Mentah (&ge;3 kata)</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_setelah_filter_raw"))}</td>'
            f'<td>Minimal 3 kata sebelum preprocessing</td></tr>'
            f'<tr><td>Lolos Minimal Bersih (&ge;2 kata)</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_setelah_min_kata_bersih"))}</td>'
            f'<td>Setelah normalisasi &amp; stemming</td></tr>'
            f'<tr><td>Duplikat Dihapus</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_duplikat_dihapus"))}</td>'
            f'<td>Komentar bersih identik dihilangkan</td></tr>'
            f'<tr style="background:#EFF6FF;font-weight:700;">'
            f'<td>Data Final (Valid)</td>'
            f'<td class="td-num" style="color:#15803D;">'
            f'{_fmt_int(pre.get("jumlah_data_valid"))}</td>'
            f'<td>Digunakan untuk TF-IDF &rarr; LSA &rarr; K-Means</td></tr>'
        )
        prep_html = (
            f'<div class="section">'
            f'<div class="section-title">Statistik Preprocessing Teks</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:38%;"><col style="width:14%;"><col style="width:48%;">'
            f'</colgroup>'
            f'<thead><tr><th>Tahap</th><th>Jumlah Data</th><th>Keterangan</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )

    # ── Rekomendasi K ─────────────────────────────────────────────────────
    bk_html = ""
    if bk:
        dip   = bk.get("dipilih", "-")
        sil_k = bk.get("silhouette", {}).get("k", "-")
        sil_v = _fmt_float(bk.get("silhouette", {}).get("nilai"), 4)
        bk_html = (
            f'<div class="section">'
            f'<div class="section-title">Rekomendasi Nilai K</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:33%;"><col style="width:33%;"><col style="width:34%;">'
            f'</colgroup>'
            f'<thead><tr>'
            f'<th>K Dipilih</th>'
            f'<th>K Terbaik (Silhouette)</th>'
            f'<th>Nilai Silhouette</th>'
            f'</tr></thead>'
            f'<tbody><tr>'
            f'<td class="td-num">{dip}</td>'
            f'<td class="td-num">{sil_k}</td>'
            f'<td class="td-num">{sil_v}</td>'
            f'</tr></tbody></table></div>'
        )

    # ── Tabel Perbandingan K ──────────────────────────────────────────────
    eval_html = ""
    eval_labels = state.get("eval_labels", [])
    inertia     = state.get("eval_sse", [])
    sil_vals    = state.get("eval_silhouette", [])
    if eval_labels and isinstance(eval_labels[0], str):
        k_ints = [int(x.replace("K=", "")) for x in eval_labels]
    else:
        k_ints = [int(x) for x in eval_labels] if eval_labels else []

    if k_ints and inertia and sil_vals and len(k_ints) == len(inertia) == len(sil_vals):
        best_sil_k = k_ints[sil_vals.index(max(sil_vals))]
        chosen_k   = int(state.get("k") or (bk.get("dipilih") or 0))
        rows_k = ""
        for ki, ine, sil in zip(k_ints, inertia, sil_vals):
            is_ch = (ki == chosen_k)
            is_bs = (ki == best_sil_k)
            note  = ("K dipilih &amp; silhouette terbaik" if is_ch and is_bs
                     else "K yang digunakan" if is_ch
                     else "Silhouette tertinggi" if is_bs else "&mdash;")
            row_style = " style='background:#EFF6FF;font-weight:700;'" if is_ch else ""
            rows_k += (
                f"<tr{row_style}>"
                f"<td class='td-num'>K={ki}</td>"
                f"<td class='td-num'>{_fmt_float(ine, 2)}</td>"
                f"<td class='td-num'>{_fmt_float(sil, 4)}</td>"
                f"<td class='td-ket'>{note}</td>"
                f"</tr>"
            )
        eval_html = (
            f'<div class="section">'
            f'<div class="section-title">Perbandingan Nilai k &mdash; Elbow &amp; Silhouette</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:16%;"><col style="width:24%;"><col style="width:22%;">'
            f'<col style="width:38%;">'
            f'</colgroup>'
            f'<thead><tr>'
            f'<th>Jumlah Cluster (k)</th>'
            f'<th>Inertia / SSE</th>'
            f'<th>Silhouette Score</th>'
            f'<th>Keterangan</th>'
            f'</tr></thead>'
            f'<tbody>{rows_k}</tbody></table>'
            f'<p class="note">Elbow: pilih k di titik penurunan Inertia mulai melambat. '
            f'Silhouette lebih tinggi = cluster lebih kompak.</p>'
            f'</div>'
        )

    # ── Grafik Elbow & Silhouette ─────────────────────────────────────────
    charts_html = ""
    elbow_b64 = state.get("elbow_chart_b64") or ""
    sil_b64   = state.get("silhouette_chart_b64") or ""
    if elbow_b64 or sil_b64:
        charts_html = (
            f'<div class="section no-break">'
            f'<div class="section-title">Visualisasi Evaluasi &mdash; Elbow &amp; Silhouette</div>'
            + _two_imgs(
                elbow_b64, "Elbow Method (Inertia / SSE)",
                sil_b64,   "Silhouette Score per K",
                left_desc="Cari titik &ldquo;siku&rdquo; di mana penurunan Inertia mulai melambat.",
                right_desc="Nilai lebih tinggi = cluster lebih kompak dan terpisah.",
                caption="Titik merah = K yang dipilih pada proses clustering terakhir.",
            )
            + f'</div>'
        )

    # ── Kualitas per Cluster ──────────────────────────────────────────────
    cq_html = ""
    if cs:
        rows_cq = ""
        for item in cs:
            cid   = int(item.get("cluster", 0))
            color = _cluster_color(cid)
            sil_r = _fmt_float(item.get("silhouette_rata2"), 4)
            sil_c = ("#15803D" if (item.get("silhouette_rata2") or 0) >= 0.3
                     else "#D97706" if (item.get("silhouette_rata2") or 0) >= 0
                     else "#DC2626")
            rows_cq += (
                f'<tr>'
                f'<td class="td-center">'
                f'<b style="color:{color};">C{cid}</b></td>'
                f'<td class="td-wrap"><strong>{item.get("label","-")}</strong></td>'
                f'<td class="td-num">{_fmt_int(item.get("jumlah"))}</td>'
                f'<td class="td-num">{item.get("persen",0):.1f}%</td>'
                f'<td class="td-num" style="color:{sil_c};font-weight:700;">{sil_r}</td>'
                f'<td class="td-num">{_fmt_float(item.get("silhouette_min"),4)}</td>'
                f'<td class="td-num">{_fmt_float(item.get("silhouette_max"),4)}</td>'
                f'</tr>'
            )
        cq_html = (
            f'<div class="section">'
            f'<div class="section-title">Kualitas per Cluster</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:8%;"><col style="width:28%;"><col style="width:9%;">'
            f'<col style="width:7%;"><col style="width:16%;"><col style="width:16%;">'
            f'<col style="width:16%;">'
            f'</colgroup>'
            f'<thead><tr>'
            f'<th>Cluster</th><th>Label Topik</th>'
            f'<th>Jumlah</th><th>%</th>'
            f'<th>Sil. Rata-rata</th><th>Sil. Min</th><th>Sil. Max</th>'
            f'</tr></thead>'
            f'<tbody>{rows_cq}</tbody></table>'
            f'<p class="note">'
            f'<span style="color:#15803D;font-weight:700;">&ge;0.30</span> = Baik &nbsp;|&nbsp;'
            f'<span style="color:#D97706;font-weight:700;">0.00&ndash;0.29</span> = Cukup &nbsp;|&nbsp;'
            f'<span style="color:#DC2626;font-weight:700;">&lt;0.00</span> = Tumpang tindih</p>'
            f'</div>'
        )

    # ── Validasi Seed ─────────────────────────────────────────────────────
    seed_html = ""
    ss = state.get("seed_summary") or {}
    if ss:
        rows_s = "".join(
            f'<tr><td class="td-wrap">{k}</td>'
            f'<td class="td-num">{_fmt_int(v)}</td></tr>'
            for k, v in ss.items()
        )
        seed_html = (
            f'<div class="section">'
            f'<div class="section-title">Validasi Seed Topic</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup><col style="width:70%;"><col style="width:30%;"></colgroup>'
            f'<thead><tr><th>Kategori</th><th>Jumlah</th></tr></thead>'
            f'<tbody>{rows_s}</tbody></table></div>'
        )

    body = (
        f'{_kop(logo_b64)}'
        f'{_title_block("Laporan Evaluasi Cluster", now_str)}'
        f'<div class="section">'
        f'<div class="section-title">Metrik Utama Model</div>'
        f'{metrics_html}</div>'
        f'{prep_html}{bk_html}{eval_html}{charts_html}{cq_html}{seed_html}'
        f'<p class="note">Silhouette mendekati 1 = cluster sangat kompak dan terpisah. '
        f'Nilai 0.1&ndash;0.3 wajar untuk komentar pendek media sosial.</p>'
        f'{_signature()}'
    )
    return _wrap_html("Laporan Evaluasi Cluster", body)

# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN VISUALISASI
# Isi: Distribusi cluster (tabel + bar chart), Scatter t-SNE (catatan),
#      Wordcloud per cluster
# TIDAK ADA: Silhouette, Elbow, tabel komentar
# ─────────────────────────────────────────────────────────────────────────────

def _html_visualisasi(state: dict, logo_b64: str, now_str: str) -> str:
    m  = state.get("metrics") or {}
    cs = state.get("cluster_summary") or []
    wc = state.get("wordclouds") or {}

    # ── Info ringkas ──────────────────────────────────────────────────────
    info_html = ""
    if m:
        info_html = _metric_tiles(
            "Total Data",      _fmt_int(m.get("total_data")),
            "Jumlah Cluster",  _fmt_int(m.get("jumlah_cluster")),
            "K Dipilih",       _fmt_int(state.get("k") or m.get("jumlah_cluster")),
        )

    # ── Tabel distribusi cluster ──────────────────────────────────────────
    dist_html = ""
    if cs:
        rows_d = ""
        for item in cs:
            cid   = int(item.get("cluster", 0))
            color = _cluster_color(cid)
            words = _topwords(item.get("top_words", []), 8)
            rows_d += (
                f'<tr>'
                f'<td class="td-center">'
                f'<b style="color:{color};">C{cid}</b></td>'
                f'<td class="td-wrap"><strong>{item.get("label","-")}</strong></td>'
                f'<td class="td-num">{_fmt_int(item.get("jumlah"))}</td>'
                f'<td class="td-num">{item.get("persen",0):.1f}%</td>'
                f'<td class="td-wrap">{words}</td>'
                f'</tr>'
            )
        dist_html = (
            f'<div class="section">'
            f'<div class="section-title">Distribusi Komentar per Cluster</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:9%;"><col style="width:22%;"><col style="width:10%;">'
            f'<col style="width:9%;"><col style="width:50%;">'
            f'</colgroup>'
            f'<thead><tr>'
            f'<th>Cluster</th><th>Label Topik</th>'
            f'<th>Jumlah</th><th>%</th><th>Kata Kunci Utama (Top 8)</th>'
            f'</tr></thead>'
            f'<tbody>{rows_d}</tbody></table>'
            f'<p class="note">Distribusi menunjukkan proporsi komentar yang masuk '
            f'ke setiap kelompok topik.</p>'
            f'</div>'
        )

    # ── Scatter t-SNE (hanya catatan, tidak ada canvas di PDF) ───────────
    scatter_html = (
        f'<div class="section chart-block">'
        f'<div class="section-title">Scatter Plot t-SNE (Proyeksi 2D)</div>'
        f'<p class="chart-block-desc">'
        f'Proyeksi t-SNE menampilkan sebaran komentar dalam ruang 2-dimensi. '
        f'Setiap titik mewakili satu komentar; titik yang berdekatan memiliki '
        f'kemiripan konteks lebih tinggi. Visualisasi interaktif tersedia di '
        f'halaman Laporan Visualisasi pada aplikasi web.</p>'
        f'</div>'
    )

    # ── Wordcloud ─────────────────────────────────────────────────────────
    wc_html = ""
    wc_items = sorted(wc.items(), key=lambda x: int(x[0]))
    grid = _wc_grid(wc_items, cs)
    if grid:
        wc_html = (
            f'<div class="section page-break">'
            f'<div class="section-title">Wordcloud per Cluster</div>'
            f'<p class="note" style="margin-bottom:8px;">'
            f'Ukuran kata mencerminkan bobot TF-IDF &mdash; semakin besar, '
            f'semakin dominan dalam cluster tersebut.</p>'
            f'{grid}</div>'
        )

    body = (
        f'{_kop(logo_b64)}'
        f'{_title_block("Laporan Visualisasi Cluster", now_str)}'
        f'<div class="section">'
        f'<div class="section-title">Informasi Dataset</div>'
        f'{info_html}</div>'
        f'{dist_html}{scatter_html}{wc_html}'
        f'{_signature()}'
    )
    return _wrap_html("Laporan Visualisasi Cluster", body)

# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN INTERPRETASI
# Isi: Ringkasan topik, Detail per cluster (karakteristik, kata dominan,
#      sampel komentar representatif = komentar asli + token preprocessing)
# TIDAK ADA: grafik evaluasi, wordcloud mentah, daftar dokumen lengkap,
#            nilai silhouette (metrik evaluasi)
# ─────────────────────────────────────────────────────────────────────────────

def _html_interpretasi(state: dict, logo_b64: str, now_str: str) -> str:
    m        = state.get("metrics") or {}
    cs       = state.get("cluster_summary") or []
    text_col = state.get("text_column") or "komentar"

    # Info ringkas — tanpa Silhouette (itu ranah evaluasi)
    info_html = ""
    if m:
        info_html = _metric_tiles(
            "Total Data",     _fmt_int(m.get("total_data")),
            "Jumlah Cluster", _fmt_int(m.get("jumlah_cluster")),
            "K Dipilih",      _fmt_int(state.get("k") or m.get("jumlah_cluster")),
        )

    # ── Ringkasan semua cluster ───────────────────────────────────────────
    sum_html = ""
    if cs:
        rows_s = ""
        for item in cs:
            cid   = int(item.get("cluster", 0))
            color = _cluster_color(cid)
            words = _topwords(item.get("top_words", []), 6)
            rows_s += (
                f'<tr>'
                f'<td class="td-center">'
                f'<b style="color:{color};">C{cid}</b></td>'
                f'<td class="td-wrap"><strong>{item.get("label","-")}</strong></td>'
                f'<td class="td-num">{_fmt_int(item.get("jumlah"))}</td>'
                f'<td class="td-num">{item.get("persen",0):.1f}%</td>'
                f'<td class="td-wrap">{words}</td>'
                f'</tr>'
            )
        sum_html = (
            f'<div class="section">'
            f'<div class="section-title">Ringkasan Topik Semua Cluster</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:9%;"><col style="width:25%;"><col style="width:10%;">'
            f'<col style="width:8%;"><col style="width:48%;">'
            f'</colgroup>'
            f'<thead><tr>'
            f'<th>Cluster</th><th>Label Topik</th>'
            f'<th>Jumlah</th><th>%</th><th>Kata Kunci Utama</th>'
            f'</tr></thead>'
            f'<tbody>{rows_s}</tbody></table></div>'
        )

    # ── Detail per cluster ────────────────────────────────────────────────
    detail_html = ""
    blocks = ""
    for item in cs:
        cid   = int(item.get("cluster", 0))
        color = _cluster_color(cid)
        label = item.get("label", f"Cluster {cid}")
        words = _topwords(item.get("top_words", []), 15)

        # Sampel komentar — 2 kolom: komentar asli + token preprocessing
        # (tanpa kolom Silhouette — itu ranah evaluasi)
        sample_rows = ""
        for idx, s in enumerate(item.get("samples", [])[:6], 1):
            raw   = str(s.get(text_col) or s.get("komentar", "-"))[:200]
            clean = str(s.get("komentar_bersih", "-"))[:160]
            sample_rows += (
                f'<tr>'
                f'<td class="td-center" style="width:5%;">{idx}</td>'
                f'<td class="td-wrap" style="font-size:7pt;">{raw}</td>'
                f'<td class="td-mono td-wrap">{clean}</td>'
                f'</tr>'
            )

        sample_tbl = ""
        if sample_rows:
            sample_tbl = (
                f'<p class="cluster-card" style="font-size:7pt;font-weight:700;'
                f'color:#94A3B8;text-transform:uppercase;margin-bottom:3px;">'
                f'Sampel Komentar Representatif</p>'
                f'<table class="tbl-fixed">'
                f'<colgroup>'
                f'<col style="width:5%;"><col style="width:50%;"><col style="width:45%;">'
                f'</colgroup>'
                f'<thead><tr>'
                f'<th>No</th><th>Komentar Asli</th>'
                f'<th>Token Preprocessing</th>'
                f'</tr></thead>'
                f'<tbody>{sample_rows}</tbody></table>'
            )

        blocks += (
            f'<div class="cluster-card no-break" style="border-left-color:{color};">'
            f'<h3>C{cid} &mdash; {label}</h3>'
            f'<p class="meta">'
            f'{_fmt_int(item.get("jumlah"))} komentar '
            f'({item.get("persen",0):.1f}% dari total data)'
            f'</p>'
            f'<p class="words-label">Kata Kunci Representatif (TF-IDF Centroid)</p>'
            f'<div style="margin-bottom:7px;">{words}</div>'
            f'{sample_tbl}'
            f'</div>'
        )

    if blocks:
        detail_html = (
            f'<div class="section page-break">'
            f'<div class="section-title">Detail Interpretasi per Cluster</div>'
            f'{blocks}'
            f'<p class="note">'
            f'Kata kunci diekstrak dari centroid TF-IDF — mencerminkan inti tematik cluster. '
            f'Token preprocessing adalah hasil normalisasi dan stemming Sastrawi.</p>'
            f'</div>'
        )

    body = (
        f'{_kop(logo_b64)}'
        f'{_title_block("Laporan Interpretasi Cluster", now_str)}'
        f'<div class="section">'
        f'<div class="section-title">Informasi Dataset</div>'
        f'{info_html}</div>'
        f'{sum_html}{detail_html}'
        f'{_signature()}'
    )
    return _wrap_html("Laporan Interpretasi Cluster", body)

# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN HASIL
# Isi: Info hasil clustering, Filter aktif, Tabel data
#      (tanpa silhouette_sample dan komentar_bersih — sesuai audit template)
# TIDAK ADA: Elbow, Silhouette, Wordcloud, insight interpretasi
# ─────────────────────────────────────────────────────────────────────────────

# Kolom yang DIKECUALIKAN dari tabel Laporan Hasil
# (konsisten dengan exclude_cols di laporan_hasil.html)
_HASIL_EXCLUDE = {"silhouette_sample", "komentar_bersih"}

# Lebar kolom (%) untuk landscape A4 — total ±100%
_HASIL_COL_W: dict[str, str] = {
    "no":           "4%",
    "tanggal":      "10%",
    "username":     "10%",
    "komentar":     "38%",
    "cluster":      "6%",
    "label_cluster":"16%",
    "seed_match":   "8%",
    "seed_label":   "8%",
}

_HASIL_COL_LBL: dict[str, str] = {
    "no":           "No",
    "tanggal":      "Tanggal",
    "username":     "Username",
    "komentar":     "Komentar Asli",
    "cluster":      "Cluster",
    "label_cluster":"Topik",
    "seed_match":   "Kesesuaian",
    "seed_label":   "Seed",
}

# Truncate panjang teks per kolom agar tidak overflow
_HASIL_MAX_CHARS: dict[str, int] = {
    "komentar":     220,
    "label_cluster": 60,
    "username":      40,
}


def _html_hasil(
    state: dict,
    logo_b64: str,
    now_str: str,
    result_df=None,
    cluster_filter: str = "all",
    search_query: str = "",
) -> str:
    import pandas as pd

    m = state.get("metrics") or {}

    # Info ringkas — tanpa Silhouette (ranah evaluasi)
    info_html = ""
    if m:
        info_html = _metric_tiles(
            "Total Data Valid",  _fmt_int(m.get("total_data")),
            "Jumlah Cluster (K)", _fmt_int(m.get("jumlah_cluster")),
        )

    # ── Keterangan filter aktif ───────────────────────────────────────────
    filter_note = "Semua cluster"
    if cluster_filter != "all":
        filter_note = f"Filter: Cluster {cluster_filter}"
    if search_query:
        filter_note += f' &nbsp;|&nbsp; Kata kunci: &ldquo;{search_query}&rdquo;'

    # ── Tabel data hasil ──────────────────────────────────────────────────
    data_html = ""
    if result_df is not None:
        df = result_df.copy()
        df = df.dropna(subset=["cluster"])
        df["cluster"] = df["cluster"].astype(int)

        # Terapkan filter cluster
        if cluster_filter != "all":
            try:
                df = df[df["cluster"] == int(cluster_filter)]
            except Exception:
                pass

        # Terapkan filter pencarian
        text_col = state.get("text_column") or "komentar"
        if search_query:
            q_low = search_query.lower()
            tcols = [c for c in [text_col, "komentar", "label_cluster"]
                     if c in df.columns]
            if tcols:
                mask = pd.Series(False, index=df.index)
                for col in tcols:
                    mask |= (df[col].fillna("").astype(str)
                             .str.lower().str.contains(q_low, regex=False))
                df = df[mask]

        # Batasi 300 baris untuk PDF agar tidak terlalu besar
        df_show = df.head(300)
        total   = len(df)
        shown   = len(df_show)

        # Tentukan kolom yang akan ditampilkan (exclude silhouette_sample & komentar_bersih)
        preferred = [
            "no", "tanggal", "username", text_col,
            "cluster", "label_cluster", "seed_match", "seed_label",
        ]
        show_cols = [c for c in preferred
                     if c in df_show.columns and c not in _HASIL_EXCLUDE]
        # Fallback: kolom tersedia minus exclude
        if not show_cols:
            show_cols = [c for c in df_show.columns
                         if c not in _HASIL_EXCLUDE][:9]

        # Bangun colgroup untuk lebar proporsional
        colgroup = "".join(
            f'<col style="width:{_HASIL_COL_W.get(c, "auto")};">'
            for c in show_cols
        )

        # Header
        header = "".join(
            f'<th>{_HASIL_COL_LBL.get(c, c.capitalize())}</th>'
            for c in show_cols
        )

        # Baris data
        rows = ""
        for row_num, (_, row) in enumerate(df_show.iterrows(), 1):
            cells = ""
            for c in show_cols:
                val = row.get(c, "")
                if c == "no":
                    cells += f'<td class="td-center">{row_num}</td>'
                elif c == "cluster":
                    color = _cluster_color(int(val))
                    cells += (f'<td class="td-center">'
                               f'<b style="color:{color};">C{int(val)}</b></td>')
                elif c == "seed_label":
                    sv = "Tidak ada" if val == -1 else f"C{val}"
                    cells += f'<td class="td-center td-mono">{sv}</td>'
                else:
                    max_c = _HASIL_MAX_CHARS.get(c, 999)
                    txt   = str(val)[:max_c] if val is not None else "-"
                    cells += f'<td class="td-wrap">{txt}</td>'
            rows += f"<tr>{cells}</tr>"

        trunc_note = ""
        if total > 300:
            trunc_note = (f' (maks. 300 baris ditampilkan dalam PDF; '
                          f'unduh CSV untuk {total} data lengkap)')

        data_html = (
            f'<div class="section page-break">'
            f'<div class="section-title">Data Hasil Clustering</div>'
            f'<p class="note" style="margin-bottom:6px;">'
            f'Menampilkan {shown:,} dari {total:,} data. '
            f'{filter_note}{trunc_note}.</p>'
            f'<table class="tbl-fixed">'
            f'<colgroup>{colgroup}</colgroup>'
            f'<thead><tr>{header}</tr></thead>'
            f'<tbody>{rows}</tbody>'
            f'</table>'
            f'</div>'
        )

    body = (
        f'{_kop(logo_b64)}'
        f'{_title_block("Laporan Hasil Clustering", now_str)}'
        f'<div class="section">'
        f'<div class="section-title">Informasi Hasil Clustering</div>'
        f'{info_html}</div>'
        f'{data_html}'
        f'{_signature()}'
    )
    return _wrap_html("Laporan Hasil Clustering", body)

# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN LENGKAP (gabungan semua section)
# ─────────────────────────────────────────────────────────────────────────────

def _html_lengkap(state: dict, logo_b64: str, now_str: str) -> str:
    """Gabungkan semua section menjadi satu PDF laporan lengkap."""
    text_col = state.get("text_column") or "komentar"
    m   = state.get("metrics") or {}
    pre = state.get("preprocessing_stats") or {}
    bk  = state.get("best_k") or {}
    cs  = state.get("cluster_summary") or []
    ss  = state.get("seed_summary") or {}
    wc  = state.get("wordclouds") or {}

    sections = ""

    # ── 1. Ringkasan model ────────────────────────────────────────────────
    if m:
        sections += (
            f'<div class="section">'
            f'<div class="section-title">Ringkasan Model</div>'
            + _metric_tiles(
                "Total Data",       _fmt_int(m.get("total_data")),
                "Jumlah Cluster",   _fmt_int(m.get("jumlah_cluster")),
                "Silhouette Score", _fmt_float(m.get("silhouette_score"), 4),
                "Fitur TF-IDF",     _fmt_int(m.get("jumlah_fitur_tfidf")),
                "Komponen LSA",     _fmt_int(m.get("jumlah_komponen_lsa")),
                "Variansi LSA",     _fmt_float(m.get("variansi_lsa"), 4),
            )
            + f'</div>'
        )

    # ── 2. Preprocessing stats ────────────────────────────────────────────
    if pre:
        rows = (
            f'<tr><td>Data Awal</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_data_awal"))}</td></tr>'
            f'<tr><td>Tidak Null</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_tidak_null"))}</td></tr>'
            f'<tr><td>Lolos Filter Mentah (&ge;3 kata)</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_setelah_filter_raw"))}</td></tr>'
            f'<tr><td>Lolos Minimal Bersih (&ge;2 kata)</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_setelah_min_kata_bersih"))}</td></tr>'
            f'<tr><td>Duplikat Dihapus</td>'
            f'<td class="td-num">{_fmt_int(pre.get("jumlah_duplikat_dihapus"))}</td></tr>'
            f'<tr style="background:#EFF6FF;font-weight:700;">'
            f'<td>Data Final (Valid)</td>'
            f'<td class="td-num" style="color:#15803D;">'
            f'{_fmt_int(pre.get("jumlah_data_valid"))}</td></tr>'
        )
        sections += (
            f'<div class="section">'
            f'<div class="section-title">Statistik Preprocessing</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup><col style="width:70%;"><col style="width:30%;"></colgroup>'
            f'<thead><tr><th>Tahap</th><th>Jumlah Data</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )

    # ── 3. Rekomendasi K & tabel perbandingan ─────────────────────────────
    if bk:
        dip   = bk.get("dipilih", "-")
        sil_k = bk.get("silhouette", {}).get("k", "-")
        sil_v = _fmt_float(bk.get("silhouette", {}).get("nilai"), 4)
        sections += (
            f'<div class="section">'
            f'<div class="section-title">Rekomendasi Nilai K</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:33%;"><col style="width:33%;"><col style="width:34%;">'
            f'</colgroup>'
            f'<thead><tr>'
            f'<th>K Dipilih</th><th>K Terbaik (Silhouette)</th><th>Nilai Silhouette</th>'
            f'</tr></thead>'
            f'<tbody><tr>'
            f'<td class="td-num">{dip}</td>'
            f'<td class="td-num">{sil_k}</td>'
            f'<td class="td-num">{sil_v}</td>'
            f'</tr></tbody></table></div>'
        )

    eval_labels = state.get("eval_labels", [])
    inertia     = state.get("eval_sse", [])
    sil_vals    = state.get("eval_silhouette", [])
    k_ints = [int(x.replace("K=","")) if isinstance(x,str) else int(x)
              for x in eval_labels] if eval_labels else []
    if k_ints and inertia and sil_vals and len(k_ints)==len(inertia)==len(sil_vals):
        best_sil_k = k_ints[sil_vals.index(max(sil_vals))]
        chosen_k   = int(state.get("k") or bk.get("dipilih") or 0)
        rows_k = ""
        for ki, ine, sil in zip(k_ints, inertia, sil_vals):
            is_ch = ki == chosen_k; is_bs = ki == best_sil_k
            note  = ("K dipilih &amp; silhouette terbaik" if is_ch and is_bs
                     else "K yang digunakan" if is_ch
                     else "Silhouette tertinggi" if is_bs else "&mdash;")
            rs = " style='background:#EFF6FF;font-weight:700;'" if is_ch else ""
            rows_k += (f"<tr{rs}><td class='td-num'>K={ki}</td>"
                       f"<td class='td-num'>{_fmt_float(ine,2)}</td>"
                       f"<td class='td-num'>{_fmt_float(sil,4)}</td>"
                       f"<td class='td-ket'>{note}</td></tr>")
        sections += (
            f'<div class="section">'
            f'<div class="section-title">Perbandingan k &mdash; Elbow &amp; Silhouette</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:16%;"><col style="width:24%;">'
            f'<col style="width:22%;"><col style="width:38%;">'
            f'</colgroup>'
            f'<thead><tr><th>k</th><th>Inertia/SSE</th>'
            f'<th>Silhouette</th><th>Keterangan</th></tr></thead>'
            f'<tbody>{rows_k}</tbody></table></div>'
        )

    # ── 4. Grafik Elbow & Silhouette ──────────────────────────────────────
    elbow_b64 = state.get("elbow_chart_b64") or ""
    sil_b64   = state.get("silhouette_chart_b64") or ""
    if elbow_b64 or sil_b64:
        sections += (
            f'<div class="section no-break">'
            f'<div class="section-title">Grafik Evaluasi</div>'
            + _two_imgs(
                elbow_b64, "Elbow Method (Inertia/SSE)",
                sil_b64,   "Silhouette Score per K",
                left_desc="Cari titik &ldquo;siku&rdquo; di mana penurunan Inertia mulai melambat.",
                right_desc="Nilai lebih tinggi = cluster lebih kompak dan terpisah.",
                caption="Titik merah = K yang dipilih pada proses clustering terakhir.",
            )
            + f'</div>'
        )

    # ── 5. Distribusi cluster ─────────────────────────────────────────────
    if cs:
        rows_d = ""
        for item in cs:
            cid = int(item.get("cluster",0)); color = _cluster_color(cid)
            words = _topwords(item.get("top_words",[]), 6)
            rows_d += (
                f'<tr><td class="td-center"><b style="color:{color};">C{cid}</b></td>'
                f'<td class="td-wrap"><strong>{item.get("label","-")}</strong></td>'
                f'<td class="td-num">{_fmt_int(item.get("jumlah"))}</td>'
                f'<td class="td-num">{item.get("persen",0):.1f}%</td>'
                f'<td class="td-num">{_fmt_float(item.get("silhouette_rata2"),4)}</td>'
                f'<td class="td-wrap">{words}</td></tr>'
            )
        sections += (
            f'<div class="section">'
            f'<div class="section-title">Distribusi &amp; Kualitas Cluster</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup>'
            f'<col style="width:8%;"><col style="width:22%;"><col style="width:9%;">'
            f'<col style="width:7%;"><col style="width:14%;"><col style="width:40%;">'
            f'</colgroup>'
            f'<thead><tr><th>Cluster</th><th>Label</th><th>Jumlah</th>'
            f'<th>%</th><th>Sil. Rata-rata</th><th>Kata Kunci</th></tr></thead>'
            f'<tbody>{rows_d}</tbody></table></div>'
        )

    # ── 6. Wordcloud ──────────────────────────────────────────────────────
    wc_items = sorted(wc.items(), key=lambda x: int(x[0]))
    grid = _wc_grid(wc_items, cs)
    if grid:
        sections += (
            f'<div class="section page-break">'
            f'<div class="section-title">Wordcloud per Cluster</div>'
            f'<p class="note" style="margin-bottom:7px;">'
            f'Ukuran kata mencerminkan bobot TF-IDF.</p>'
            f'{grid}</div>'
        )

    # ── 7. Detail per cluster (interpretasi) ──────────────────────────────
    blocks = ""
    for item in cs:
        cid   = int(item.get("cluster",0)); color = _cluster_color(cid)
        label = item.get("label", f"Cluster {cid}")
        words = _topwords(item.get("top_words",[]), 15)
        srows = ""
        for idx, s in enumerate(item.get("samples",[])[:5], 1):
            raw   = str(s.get(text_col) or s.get("komentar","-"))[:200]
            clean = str(s.get("komentar_bersih","-"))[:160]
            srows += (f'<tr><td class="td-center">{idx}</td>'
                      f'<td class="td-wrap" style="font-size:7pt;">{raw}</td>'
                      f'<td class="td-mono td-wrap">{clean}</td></tr>')
        stbl = ""
        if srows:
            stbl = (
                f'<table class="tbl-fixed" style="margin-top:4px;">'
                f'<colgroup>'
                f'<col style="width:5%;"><col style="width:52%;"><col style="width:43%;">'
                f'</colgroup>'
                f'<thead><tr><th>No</th><th>Komentar Asli</th>'
                f'<th>Token Preprocessing</th></tr></thead>'
                f'<tbody>{srows}</tbody></table>'
            )
        blocks += (
            f'<div class="cluster-card no-break" style="border-left-color:{color};">'
            f'<h3>C{cid} &mdash; {label}</h3>'
            f'<p class="meta">{_fmt_int(item.get("jumlah"))} komentar '
            f'({item.get("persen",0):.1f}%)</p>'
            f'<p class="words-label">Kata Kunci</p>'
            f'<div style="margin-bottom:6px;">{words}</div>'
            f'<p class="words-label">Sampel Komentar</p>'
            f'{stbl}</div>'
        )
    if blocks:
        sections += (
            f'<div class="section page-break">'
            f'<div class="section-title">Detail per Cluster</div>'
            f'{blocks}</div>'
        )

    # ── 8. Seed summary ───────────────────────────────────────────────────
    if ss:
        rows_s = "".join(
            f'<tr><td class="td-wrap">{k}</td>'
            f'<td class="td-num">{_fmt_int(v)}</td></tr>'
            for k, v in ss.items()
        )
        sections += (
            f'<div class="section">'
            f'<div class="section-title">Validasi Seed Topic</div>'
            f'<table class="tbl-fixed">'
            f'<colgroup><col style="width:70%;"><col style="width:30%;"></colgroup>'
            f'<thead><tr><th>Kategori</th><th>Jumlah</th></tr></thead>'
            f'<tbody>{rows_s}</tbody></table></div>'
        )

    body = (
        f'{_kop(logo_b64)}'
        f'{_title_block("Laporan Analisis Clustering Komentar", now_str)}'
        f'{sections}'
        f'{_signature()}'
    )
    return _wrap_html(f"Laporan Clustering — {COMPANY_NAME}", body)

# ─────────────────────────────────────────────────────────────────────────────
# PDF ENGINE  — WeasyPrint (prioritas) → xhtml2pdf (fallback)
# WeasyPrint butuh GTK; jika tidak tersedia di lingkungan ini → xhtml2pdf.
# ─────────────────────────────────────────────────────────────────────────────

def _try_add_gtk_path() -> None:
    candidates = [
        r"C:\Program Files\GTK3-Runtime Win64\bin",
        r"C:\Program Files\GTK3-Runtime\bin",
        r"C:\GTK\bin",
        r"C:\msys64\mingw64\bin",
    ]
    cur = os.environ.get("PATH", "")
    add = [p for p in candidates if os.path.isdir(p) and p not in cur]
    if add:
        os.environ["PATH"] = ";".join(add) + ";" + cur


def _to_pdf(html_str: str) -> bytes:
    """HTML → PDF bytes. Coba WeasyPrint dulu, fallback ke xhtml2pdf."""
    # WeasyPrint (kualitas lebih baik, perlu GTK)
    try:
        _try_add_gtk_path()
        from weasyprint import HTML
        return HTML(string=html_str, base_url=None).write_pdf()
    except Exception:
        pass

    # xhtml2pdf (fallback ringan, tidak butuh GTK)
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        result = pisa.CreatePDF(
            html_str.encode("utf-8"),
            dest=buf,
            encoding="utf-8",
        )
        if result.err:
            raise RuntimeError(f"xhtml2pdf error: {result.err}")
        buf.seek(0)
        return buf.read()
    except ImportError:
        raise RuntimeError(
            "Tidak ada PDF backend. Instal WeasyPrint atau xhtml2pdf."
        )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_evaluasi(state: dict) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_evaluasi(state, _logo_b64(), now_str))


def generate_pdf_visualisasi(state: dict) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_visualisasi(state, _logo_b64(), now_str))


def generate_pdf_interpretasi(state: dict) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_interpretasi(state, _logo_b64(), now_str))


def generate_pdf_hasil(
    state: dict,
    result_df=None,
    cluster_filter: str = "all",
    search_query: str = "",
) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(
        _html_hasil(
            state, _logo_b64(), now_str,
            result_df=result_df,
            cluster_filter=cluster_filter,
            search_query=search_query,
        )
    )


def generate_pdf(state: dict) -> bytes:
    """Laporan lengkap — semua section dalam satu PDF."""
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_lengkap(state, _logo_b64(), now_str))


# Alias backward compat
def build_html(state: dict) -> str:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _html_lengkap(state, _logo_b64(), now_str)
