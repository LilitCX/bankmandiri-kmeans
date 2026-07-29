"""
services/report_pdf.py
Generate 4 jenis laporan PDF terpisah menggunakan WeasyPrint / xhtml2pdf.
- generate_pdf_evaluasi   → Laporan Evaluasi Cluster
- generate_pdf_visualisasi→ Laporan Visualisasi Cluster
- generate_pdf_interpretasi→Laporan Interpretasi Cluster
- generate_pdf_hasil      → Laporan Hasil Clustering
- generate_pdf            → alias: laporan lengkap (semua bagian)
"""
from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any

from config.settings import (
    COMPANY_ADDRESS,
    COMPANY_NAME,
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
    ext = os.path.splitext(LOGO_PATH)[1].lstrip(".").lower()
    mime = "png" if ext == "png" else ("jpeg" if ext in ("jpg", "jpeg") else "png")
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
    return f"Jakarta, {hari[now.weekday()]} {now.day:02d} {bulan[now.month - 1]} {now.year}"

# ── Cluster color map ─────────────────────────────────────────────────────────
_CLUSTER_COLORS = [
    "#2E86DE","#F39C12","#10B981","#8B5CF6",
    "#EF4444","#EC4899","#14B8A6","#6366F1",
]

def _cluster_color(cid: int) -> str:
    return _CLUSTER_COLORS[int(cid) % len(_CLUSTER_COLORS)]


# ── Shared CSS ────────────────────────────────────────────────────────────────
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif;
       font-size: 11pt; color: #1E293B; background: #fff; }
.kop { display: flex; align-items: center; gap: 16px;
       padding: 14px 32px 12px; border-bottom: 3px solid #1D4ED8; margin-bottom: 0; }
.kop img { width: 56px; max-width: 56px; height: auto; flex-shrink: 0; }
.kop-text h1 { font-size: 22pt; font-weight: 800; color: #1D4ED8;
               letter-spacing: 1px; text-transform: uppercase; margin-bottom: 3px; }
.kop-text p  { font-size: 9pt; color: #475569; margin: 0; }
.report-title-block { text-align: center; padding: 22px 32px 14px;
                      border-bottom: 1px solid #E2E8F0; margin-bottom: 20px; }
.report-title-block h2 { font-size: 14pt; font-weight: 800; color: #1E293B;
                         text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
.report-title-block .subtitle { font-size: 10pt; color: #475569; }
.body-content { padding: 0 32px; }
.section { margin-bottom: 24px; }
.section-title { font-size: 11pt; font-weight: 800; color: #1D4ED8;
                 text-transform: uppercase; letter-spacing: .5px;
                 margin-bottom: 10px; padding-bottom: 5px;
                 border-bottom: 1.5px solid #BFDBFE; }
table { width: 100%; border-collapse: collapse; font-size: 10pt; margin-bottom: 8px; }
th { background: #1D4ED8; color: #fff; padding: 8px 10px;
     text-align: center; font-weight: 700; font-size: 9.5pt; }
td { padding: 7px 10px; border: 1px solid #E2E8F0; vertical-align: top; }
tr:nth-child(even) td { background: #F8FAFC; }
tr:nth-child(odd)  td { background: #fff; }
.td-center { text-align: center; }
.td-right  { text-align: right; }
.td-num    { font-family: monospace; font-size: 10pt; }
.metric-grid { display: grid; grid-template-columns: repeat(4,1fr);
               gap: 10px; margin-bottom: 18px; }
.metric-box  { background: #EFF6FF; border: 1.5px solid #BFDBFE;
               border-radius: 8px; padding: 12px 14px; text-align: center; }
.metric-box .label { font-size: 8.5pt; color: #3B82F6; font-weight: 700;
                     text-transform: uppercase; letter-spacing: .4px; margin-bottom: 5px; }
.metric-box .value { font-size: 16pt; font-weight: 800; color: #1E293B; }
.cluster-badge { display: inline-block; padding: 3px 9px; border-radius: 6px;
                 font-weight: 700; font-size: 9.5pt; color: #fff; }
.topword { display: inline-block; background: #F1F5F9; border: 1px solid #CBD5E1;
           border-radius: 4px; padding: 2px 7px; font-size: 8.5pt;
           margin: 2px; font-family: monospace; color: #334155; }
.signature-block { margin-top: 36px; padding-right: 48px; padding-bottom: 32px; }
.signature-block .city-date { font-size: 10pt; color: #475569; margin-bottom: 4px; text-align: right; }
.signature-block .greeting  { font-size: 10pt; color: #475569; margin-bottom: 52px; text-align: right; }
.signature-block .sig-line  { border-top: 1.5px solid #1E293B; width: 180px;
                               margin: 0 0 4px auto; }
.signature-block .sig-name  { font-size: 11pt; font-weight: 800; color: #1E293B; text-align: right; }
.signature-block .sig-title { font-size: 10pt; color: #475569; text-align: right; }
.page-break { page-break-before: always; }
@page { size: A4; margin: 14mm 14mm 18mm; }
"""

# ── Shared building blocks ────────────────────────────────────────────────────

def _kop(logo_b64: str) -> str:
    img = f'<img src="{logo_b64}" alt="Logo">' if logo_b64 else ""
    return f"""<div class="kop">{img}
    <div class="kop-text">
        <h1>{COMPANY_NAME}</h1>
        <p>{COMPANY_ADDRESS} | {COMPANY_WEBSITE}</p>
    </div></div>"""


def _title_block(judul: str, generated_at: str) -> str:
    return f"""<div class="report-title-block">
    <h2>{judul}</h2>
    <div class="subtitle">TF-IDF &bull; LSA/SVD &bull; K-Means Clustering &mdash; {generated_at}</div>
</div>"""


def _signature() -> str:
    return f"""<div class="signature-block">
    <p class="city-date">{_tanggal_indonesia()}</p>
    <p class="greeting">Mengetahui,</p>
    <div class="sig-line"></div>
    <p class="sig-name">{SIGNER_NAME}</p>
    <p class="sig-title">{SIGNER_TITLE}</p>
</div>"""


def _wrap_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html><html lang="id"><head>
<meta charset="UTF-8"><title>{title}</title>
<style>{_CSS}</style></head><body>{body}</body></html>"""


def _metrics_grid(m: dict) -> str:
    sil = _fmt_float(m.get("silhouette_score"), 4)
    return f"""<div class="metric-grid">
    <div class="metric-box"><div class="label">Total Data</div>
        <div class="value">{_fmt_int(m.get("total_data"))}</div></div>
    <div class="metric-box"><div class="label">Jumlah Cluster</div>
        <div class="value">{_fmt_int(m.get("jumlah_cluster"))}</div></div>
    <div class="metric-box"><div class="label">Silhouette Score</div>
        <div class="value" style="font-size:13pt;">{sil}</div></div>
</div>"""

# ── HTML builders per report type ─────────────────────────────────────────────

def _html_evaluasi(state: dict, logo_b64: str, now_str: str) -> str:
    m   = state.get("metrics") or {}
    pre = state.get("preprocessing_stats") or {}
    bk  = state.get("best_k") or {}
    cs  = state.get("cluster_summary") or []
    ss  = state.get("seed_summary") or {}

    # ── Metrik utama
    grid = _metrics_grid(m) if m else ""
    model_rows = ""
    if m:
        model_rows = f"""<table><thead><tr>
            <th>Parameter</th><th>Nilai</th><th>Parameter</th><th>Nilai</th>
        </tr></thead><tbody>
        <tr><td>Fitur TF-IDF</td>
            <td class="td-center td-num">{_fmt_int(m.get("jumlah_fitur_tfidf"))}</td>
            <td>Komponen LSA/SVD</td>
            <td class="td-center td-num">{_fmt_int(m.get("jumlah_komponen_lsa"))}</td></tr>
        <tr><td>Variansi LSA</td>
            <td class="td-center td-num">{_fmt_float(m.get("variansi_lsa"),4)}</td>
            <td>K Dipilih</td>
            <td class="td-center td-num">{_fmt_int(m.get("jumlah_cluster"))}</td></tr>
        </tbody></table>"""

    # ── Preprocessing
    prep_html = ""
    if pre:
        prep_html = f"""<div class="section">
        <div class="section-title">Statistik Preprocessing Teks</div>
        <table><thead><tr><th>Tahap</th><th>Jumlah Data</th></tr></thead><tbody>
        <tr><td>Data Awal</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_data_awal"))}</td></tr>
        <tr><td>Tidak Null</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_tidak_null"))}</td></tr>
        <tr><td>Lolos Filter Kata Mentah (&ge;3)</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_setelah_filter_raw"))}</td></tr>
        <tr><td>Lolos Minimal Kata Bersih (&ge;2)</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_setelah_min_kata_bersih"))}</td></tr>
        <tr><td>Duplikat Dihapus</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_duplikat_dihapus"))}</td></tr>
        <tr><td><strong>Data Final (Valid)</strong></td>
            <td class="td-center td-num"><strong>{_fmt_int(pre.get("jumlah_data_valid"))}</strong></td></tr>
        </tbody></table></div>"""

    # ── Best K
    bk_html = ""
    if bk:
        dip   = bk.get("dipilih", "-")
        sil_k = bk.get("silhouette", {}).get("k", "-")
        sil_v = _fmt_float(bk.get("silhouette", {}).get("nilai"), 4)
        bk_html = f"""<div class="section">
        <div class="section-title">Rekomendasi Nilai K</div>
        <table><thead><tr>
            <th>K Dipilih</th><th>K Terbaik Silhouette</th><th>Nilai Silhouette</th>
        </tr></thead><tbody><tr>
            <td class="td-center td-num">{dip}</td>
            <td class="td-center td-num">{sil_k}</td>
            <td class="td-center td-num">{sil_v}</td>
        </tr></tbody></table></div>"""

    # ── Tabel perbandingan k (Inertia & Silhouette untuk k=2..5)
    eval_html = ""
    evaluation = state.get("metadata", {}) or {}
    evaluation = evaluation.get("evaluation", {}) if isinstance(evaluation, dict) else {}
    # Fallback ke state langsung
    k_values  = evaluation.get("k_values",  state.get("eval_labels", []))
    inertia   = evaluation.get("inertia",   state.get("eval_sse", []))
    sil_vals  = evaluation.get("silhouette", state.get("eval_silhouette", []))
    # Normalkan k_values menjadi list int
    if k_values and isinstance(k_values[0], str):
        k_vals_int = [int(x.replace("K=","")) for x in k_values]
    else:
        k_vals_int = [int(x) for x in k_values]

    if k_vals_int and inertia and sil_vals and len(k_vals_int)==len(inertia)==len(sil_vals):
        best_sil_k = k_vals_int[sil_vals.index(max(sil_vals))] if sil_vals else None
        chosen_k   = int(state.get("k", bk.get("dipilih", 0)))
        rows_eval  = ""
        for ki, ine, sil in zip(k_vals_int, inertia, sil_vals):
            is_ch  = (ki == chosen_k)
            is_bs  = (ki == best_sil_k)
            remark = (" — K dipilih &amp; silhouette terbaik" if is_ch and is_bs
                      else " — K yang digunakan" if is_ch
                      else " — Silhouette tertinggi" if is_bs
                      else "")
            style  = " style='background:#EFF6FF;font-weight:700;'" if is_ch else ""
            rows_eval += (f"<tr{style}>"
                          f"<td class='td-center td-num'>K={ki}</td>"
                          f"<td class='td-center td-num'>{_fmt_float(ine,4)}</td>"
                          f"<td class='td-center td-num'>{_fmt_float(sil,4)}</td>"
                          f"<td class='td-center' style='font-size:9pt;color:#475569;'>{remark}</td>"
                          f"</tr>")
        eval_html = f"""<div class="section">
        <div class="section-title">Perbandingan Nilai k (Elbow &amp; Silhouette)</div>
        <table><thead><tr>
            <th>Jumlah Cluster (k)</th>
            <th>Inertia / SSE</th>
            <th>Silhouette Score</th>
            <th>Keterangan</th>
        </tr></thead><tbody>{rows_eval}</tbody></table>
        <p style='font-size:9pt;color:#64748B;margin-top:6px;'>
            Elbow: cari titik di mana penurunan Inertia mulai melambat.
            Silhouette: nilai lebih tinggi = cluster lebih kompak dan terpisah.
        </p></div>"""

    # ── Kualitas per cluster
    cq_html = ""
    if cs:
        rows = ""
        for item in cs:
            cid   = int(item.get("cluster", 0))
            color = _cluster_color(cid)
            persen = item.get("persen", 0)
            rows += f"""<tr>
                <td class="td-center"><span class="cluster-badge" style="background:{color};">C{cid}</span></td>
                <td><strong>{item.get("label","-")}</strong></td>
                <td class="td-center td-num">{_fmt_int(item.get("jumlah"))}</td>
                <td class="td-center td-num">{persen:.2f}%</td>
                <td class="td-center td-num">{_fmt_float(item.get("silhouette_rata2"),4)}</td>
                <td class="td-center td-num">{_fmt_float(item.get("silhouette_min"),4)}</td>
                <td class="td-center td-num">{_fmt_float(item.get("silhouette_max"),4)}</td>
            </tr>"""
        cq_html = f"""<div class="section">
        <div class="section-title">Kualitas per Cluster</div>
        <table><thead><tr>
            <th>Cluster</th><th>Label Topik</th><th>Jumlah</th><th>%</th>
            <th>Sil. Rata-rata</th><th>Sil. Min</th><th>Sil. Max</th>
        </tr></thead><tbody>{rows}</tbody></table></div>"""

    # ── Seed validation
    seed_html = ""
    if ss:
        rows = "".join(f"<tr><td>{k}</td><td class='td-center td-num'>{_fmt_int(v)}</td></tr>"
                       for k, v in ss.items())
        seed_html = f"""<div class="section">
        <div class="section-title">Validasi Seed Topic</div>
        <table><thead><tr><th>Kategori</th><th>Jumlah</th></tr></thead>
        <tbody>{rows}</tbody></table></div>"""

    body = (f"{_kop(logo_b64)}{_title_block('Laporan Evaluasi Cluster', now_str)}"
            f"<div class='body-content'>"
            f"<div class='section'><div class='section-title'>Metrik Utama Model</div>"
            f"{grid}{model_rows}</div>"
            f"{prep_html}{bk_html}{eval_html}{cq_html}{seed_html}"
            f"<p style='font-size:9pt;color:#64748B;margin-top:8px;'>"
            f"Silhouette mendekati 1 = cluster sangat kompak dan terpisah baik. "
            f"Elbow ditandai penurunan Inertia yang mulai melambat.</p>"
            f"{_signature()}</div>")
    return _wrap_html("Laporan Evaluasi Cluster", body)

def _html_visualisasi(state: dict, logo_b64: str, now_str: str) -> str:
    m  = state.get("metrics") or {}
    cs = state.get("cluster_summary") or []

    grid = _metrics_grid(m) if m else ""

    # Distribusi tabel
    dist_rows = ""
    for item in cs:
        cid   = int(item.get("cluster", 0))
        color = _cluster_color(cid)
        words = " ".join(f'<span class="topword">{w}</span>'
                         for w in item.get("top_words", [])[:6])
        dist_rows += f"""<tr>
            <td class="td-center"><span class="cluster-badge" style="background:{color};">C{cid}</span></td>
            <td><strong>{item.get("label","-")}</strong></td>
            <td class="td-center td-num">{_fmt_int(item.get("jumlah"))}</td>
            <td class="td-center td-num">{item.get("persen",0):.1f}%</td>
            <td>{words}</td>
        </tr>"""

    dist_html = f"""<div class="section">
    <div class="section-title">Distribusi Komentar per Cluster</div>
    <table><thead><tr>
        <th style="width:8%">Cluster</th><th style="width:28%">Label Topik</th>
        <th style="width:12%">Jumlah</th><th style="width:10%">%</th>
        <th>Kata Kunci Utama</th>
    </tr></thead><tbody>{dist_rows}</tbody></table>
    <p style="font-size:9pt;color:#64748B;margin-top:6px;">
        Distribusi menunjukkan proporsi komentar yang masuk ke setiap kelompok topik.
    </p></div>""" if dist_rows else ""

    # Catatan scatter & wordcloud
    note_html = """<div class="section">
    <div class="section-title">Scatter Plot t-SNE</div>
    <p style="font-size:10pt;color:#475569;line-height:1.7;">
        Proyeksi t-SNE memperlihatkan sebaran komentar dalam ruang 2D. Setiap titik mewakili
        satu komentar. Titik-titik yang berdekatan memiliki kemiripan konteks teks yang lebih tinggi.
        Warna membedakan antar cluster. Visualisasi ini bersifat perkiraan — gunakan sebagai
        gambaran umum keterpisahan cluster, bukan ukuran jarak absolut.
    </p></div>
    <div class="section">
    <div class="section-title">Wordcloud per Cluster</div>
    <p style="font-size:10pt;color:#475569;line-height:1.7;">
        Wordcloud menampilkan kata-kata paling dominan berdasarkan bobot TF-IDF di setiap cluster.
        Ukuran kata mencerminkan frekuensi dan relevansi terhadap topik cluster tersebut.
        Kata kunci utama setiap cluster ditampilkan pada tabel distribusi di atas.
    </p></div>"""

    body = (f"{_kop(logo_b64)}{_title_block('Laporan Visualisasi Cluster', now_str)}"
            f"<div class='body-content'>"
            f"<div class='section'><div class='section-title'>Ringkasan Metrik</div>{grid}</div>"
            f"{dist_html}{note_html}{_signature()}</div>")
    return _wrap_html("Laporan Visualisasi Cluster", body)


def _html_interpretasi(state: dict, logo_b64: str, now_str: str) -> str:
    m        = state.get("metrics") or {}
    cs       = state.get("cluster_summary") or []
    text_col = state.get("text_column") or "komentar"

    grid = _metrics_grid(m) if m else ""

    # Ringkasan tabel
    sum_rows = ""
    for item in cs:
        cid   = int(item.get("cluster", 0))
        color = _cluster_color(cid)
        words = " ".join(f'<span class="topword">{w}</span>'
                         for w in item.get("top_words", [])[:5])
        sum_rows += f"""<tr>
            <td class="td-center"><span class="cluster-badge" style="background:{color};">C{cid}</span></td>
            <td><strong>{item.get("label","-")}</strong></td>
            <td class="td-center td-num">{_fmt_int(item.get("jumlah"))}</td>
            <td class="td-center td-num">{item.get("persen",0):.1f}%</td>
            <td class="td-center td-num">{_fmt_float(item.get("silhouette_rata2"),4)}</td>
            <td>{words}</td>
        </tr>"""
    summary_html = f"""<div class="section">
    <div class="section-title">Ringkasan Topik Semua Cluster</div>
    <table><thead><tr>
        <th>Cluster</th><th>Label Topik</th><th>Jumlah</th><th>%</th>
        <th>Sil. Rata-rata</th><th>Kata Kunci Utama</th>
    </tr></thead><tbody>{sum_rows}</tbody></table></div>""" if sum_rows else ""

    # Detail per cluster
    detail_blocks = ""
    for item in cs:
        cid   = int(item.get("cluster", 0))
        color = _cluster_color(cid)
        label = item.get("label", f"Cluster {cid}")
        words = " ".join(f'<span class="topword">{w}</span>'
                         for w in item.get("top_words", []))
        sample_rows = ""
        for i, s in enumerate(item.get("samples", [])[:5], 1):
            raw   = s.get(text_col) or s.get("komentar", "-")
            clean = s.get("komentar_bersih", "-")
            sv    = _fmt_float(s.get("silhouette_sample"), 4)
            sc    = "#10B981" if (s.get("silhouette_sample") or 0) >= 0 else "#EF4444"
            sample_rows += f"""<tr>
                <td class="td-center">{i}</td>
                <td>{raw}</td>
                <td style="font-family:monospace;font-size:9pt;color:#475569;">{clean}</td>
                <td class="td-center td-num" style="color:{sc};font-weight:700;">{sv}</td>
            </tr>"""
        detail_blocks += f"""
<div style="margin-bottom:22px;border-left:4px solid {color};padding-left:14px;">
    <h3 style="font-size:12pt;font-weight:800;color:#1E293B;margin-bottom:4px;">
        C{cid} &mdash; {label}</h3>
    <p style="font-size:9.5pt;color:#64748B;margin-bottom:8px;">
        {_fmt_int(item.get("jumlah"))} komentar ({item.get("persen",0):.1f}%)
        &bull; Silhouette rata-rata: <strong>{_fmt_float(item.get("silhouette_rata2"),4)}</strong>
        &nbsp;|&nbsp; Min: {_fmt_float(item.get("silhouette_min"),4)}
        &nbsp;|&nbsp; Max: {_fmt_float(item.get("silhouette_max"),4)}</p>
    <p style="font-size:9pt;font-weight:700;color:#94A3B8;margin-bottom:5px;">KATA KUNCI REPRESENTATIF</p>
    <div style="margin-bottom:10px;">{words}</div>
    <p style="font-size:9pt;font-weight:700;color:#94A3B8;margin-bottom:5px;">SAMPEL KOMENTAR TERTINGGI</p>
    <table><thead><tr>
        <th style="width:4%">No</th><th style="width:38%">Komentar Asli</th>
        <th style="width:46%">Token Preprocessing</th><th style="width:12%">Silhouette</th>
    </tr></thead><tbody>{sample_rows}</tbody></table>
</div>"""

    detail_html = (f"<div class='section page-break'>"
                   f"<div class='section-title'>Detail Interpretasi per Cluster</div>"
                   f"{detail_blocks}</div>") if detail_blocks else ""

    body = (f"{_kop(logo_b64)}{_title_block('Laporan Interpretasi Cluster', now_str)}"
            f"<div class='body-content'>"
            f"<div class='section'><div class='section-title'>Ringkasan Metrik</div>{grid}</div>"
            f"{summary_html}{detail_html}{_signature()}</div>")
    return _wrap_html("Laporan Interpretasi Cluster", body)

def _html_hasil(state: dict, logo_b64: str, now_str: str,
                result_df=None, cluster_filter: str = "all",
                search_query: str = "") -> str:
    import pandas as pd
    m        = state.get("metrics") or {}
    cs       = state.get("cluster_summary") or []
    text_col = state.get("text_column") or "komentar"

    grid = _metrics_grid(m) if m else ""

    # Distribusi singkat
    dist_rows = ""
    for item in cs:
        cid   = int(item.get("cluster", 0))
        color = _cluster_color(cid)
        dist_rows += f"""<tr>
            <td class="td-center"><span class="cluster-badge" style="background:{color};">C{cid}</span></td>
            <td><strong>{item.get("label","-")}</strong></td>
            <td class="td-center td-num">{_fmt_int(item.get("jumlah"))}</td>
            <td class="td-center td-num">{item.get("persen",0):.1f}%</td>
        </tr>"""
    dist_html = f"""<div class="section">
    <div class="section-title">Distribusi Cluster</div>
    <table><thead><tr>
        <th>Cluster</th><th>Label Topik</th><th>Jumlah</th><th>%</th>
    </tr></thead><tbody>{dist_rows}</tbody></table></div>""" if dist_rows else ""

    # Data tabel hasil
    data_html = ""
    if result_df is not None:
        df = result_df.copy()
        df = df.dropna(subset=["cluster"])
        df["cluster"] = df["cluster"].astype(int)
        if cluster_filter != "all":
            try:
                df = df[df["cluster"] == int(cluster_filter)]
            except Exception:
                pass
        if search_query:
            q_low   = search_query.lower()
            tcols   = [c for c in [text_col, "komentar", "komentar_bersih", "label_cluster"]
                       if c in df.columns]
            if tcols:
                mask = pd.Series(False, index=df.index)
                for col in tcols:
                    mask |= df[col].fillna("").astype(str).str.lower().str.contains(q_low, regex=False)
                df = df[mask]

        df_show  = df.head(200)
        col_map  = {"no":"No","tanggal":"Tanggal","username":"Username",
                    "komentar":"Komentar Asli","komentar_bersih":"Komentar Bersih",
                    "cluster":"Cluster","label_cluster":"Topik",
                    "silhouette_sample":"Silhouette","seed_match":"Kesesuaian"}
        show_cols = [c for c in df_show.columns
                     if c in col_map or c in (text_col,)]
        if not show_cols:
            show_cols = list(df_show.columns)

        header = "".join(f"<th>{col_map.get(c, c.capitalize())}</th>" for c in show_cols)
        rows   = ""
        for _, row in df_show.iterrows():
            cells = ""
            for c in show_cols:
                val = row.get(c, "")
                if c == "cluster":
                    color = _cluster_color(int(val))
                    cells += f'<td class="td-center"><span class="cluster-badge" style="background:{color};">C{int(val)}</span></td>'
                elif c == "silhouette_sample":
                    col_v = "#10B981" if (val or 0) >= 0 else "#EF4444"
                    cells += f'<td class="td-center td-num" style="color:{col_v};font-weight:700;">{_fmt_float(val,4)}</td>'
                elif c == "komentar_bersih":
                    cells += f'<td style="font-family:monospace;font-size:9pt;color:#475569;">{val}</td>'
                else:
                    cells += f"<td>{val}</td>"
            rows += f"<tr>{cells}</tr>"

        filter_note = ""
        if cluster_filter != "all":
            filter_note += f" | Filter: C{cluster_filter}"
        if search_query:
            filter_note += f" | Cari: \"{search_query}\""
        total_note = f"Menampilkan {len(df_show)} dari {len(df)} data{filter_note}."
        if len(df) > 200:
            total_note += " (maksimum 200 baris dalam PDF; unduh CSV untuk data lengkap)"

        data_html = f"""<div class="section page-break">
        <div class="section-title">Data Hasil Clustering</div>
        <p style="font-size:9pt;color:#64748B;margin-bottom:8px;">{total_note}</p>
        <table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>
        </div>"""

    body = (f"{_kop(logo_b64)}{_title_block('Laporan Hasil Clustering', now_str)}"
            f"<div class='body-content'>"
            f"<div class='section'><div class='section-title'>Ringkasan Metrik</div>{grid}</div>"
            f"{dist_html}{data_html}{_signature()}</div>")
    return _wrap_html("Laporan Hasil Clustering", body)


def _html_lengkap(state: dict, logo_b64: str, now_str: str) -> str:
    """Laporan gabungan semua bagian (untuk /download_laporan)."""
    text_col = state.get("text_column") or "komentar"
    m   = state.get("metrics") or {}
    pre = state.get("preprocessing_stats") or {}
    bk  = state.get("best_k") or {}
    cs  = state.get("cluster_summary") or []
    ss  = state.get("seed_summary") or {}
    grid = _metrics_grid(m) if m else ""

    # reuse evaluasi content (without kop/title/sig)
    eval_html   = _html_evaluasi(state, logo_b64, now_str)
    interp_html = _html_interpretasi(state, logo_b64, now_str)
    # Full combined: just build inline sections
    body = (f"{_kop(logo_b64)}{_title_block('Laporan Analisis Clustering Komentar', now_str)}"
            f"<div class='body-content'>"
            + _build_all_sections(state, text_col)
            + f"{_signature()}</div>")
    return _wrap_html(f"Laporan Clustering — {COMPANY_NAME}", body)


def _build_all_sections(state: dict, text_col: str) -> str:
    """All sections for the combined report."""
    m   = state.get("metrics") or {}
    pre = state.get("preprocessing_stats") or {}
    bk  = state.get("best_k") or {}
    cs  = state.get("cluster_summary") or []
    ss  = state.get("seed_summary") or {}
    eL  = state.get("eval_labels", [])
    eS  = state.get("eval_sse", [])
    eSil= state.get("eval_silhouette", [])

    sections = ""

    # Metrik
    if m:
        sil = _fmt_float(m.get("silhouette_score"), 4)
        sections += f"""<div class="section">
        <div class="section-title">Ringkasan Model</div>
        {_metrics_grid(m)}
        <table><thead><tr><th>Parameter</th><th>Nilai</th><th>Parameter</th><th>Nilai</th></tr></thead>
        <tbody>
        <tr><td>Fitur TF-IDF</td><td class="td-center td-num">{_fmt_int(m.get("jumlah_fitur_tfidf"))}</td>
            <td>Komponen LSA</td><td class="td-center td-num">{_fmt_int(m.get("jumlah_komponen_lsa"))}</td></tr>
        <tr><td>Variansi LSA</td><td class="td-center td-num">{_fmt_float(m.get("variansi_lsa"),4)}</td>
            <td>Silhouette Score</td><td class="td-center td-num">{sil}</td></tr>
        </tbody></table></div>"""

    # Preprocessing
    if pre:
        sections += f"""<div class="section">
        <div class="section-title">Statistik Preprocessing</div>
        <table><thead><tr><th>Tahap</th><th>Jumlah</th></tr></thead><tbody>
        <tr><td>Data Awal</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_data_awal"))}</td></tr>
        <tr><td>Tidak Null</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_tidak_null"))}</td></tr>
        <tr><td>Lolos Filter Mentah</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_setelah_filter_raw"))}</td></tr>
        <tr><td>Lolos Kata Bersih</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_setelah_min_kata_bersih"))}</td></tr>
        <tr><td>Duplikat Dihapus</td><td class="td-center td-num">{_fmt_int(pre.get("jumlah_duplikat_dihapus"))}</td></tr>
        <tr><td><strong>Data Valid Final</strong></td><td class="td-center td-num"><strong>{_fmt_int(pre.get("jumlah_data_valid"))}</strong></td></tr>
        </tbody></table></div>"""

    # Cluster summary
    if cs:
        rows = ""
        for item in cs:
            cid = int(item.get("cluster", 0))
            color = _cluster_color(cid)
            words = " ".join(f'<span class="topword">{w}</span>' for w in item.get("top_words", [])[:6])
            rows += f"""<tr>
                <td class="td-center"><span class="cluster-badge" style="background:{color};">C{cid}</span></td>
                <td><strong>{item.get("label","-")}</strong></td>
                <td class="td-center td-num">{_fmt_int(item.get("jumlah"))}</td>
                <td class="td-center td-num">{item.get("persen",0):.1f}%</td>
                <td class="td-center td-num">{_fmt_float(item.get("silhouette_rata2"),4)}</td>
                <td>{words}</td></tr>"""
        sections += f"""<div class="section">
        <div class="section-title">Ringkasan Cluster</div>
        <table><thead><tr>
            <th>Cluster</th><th>Topik</th><th>Jumlah</th><th>%</th><th>Silhouette</th><th>Kata Kunci</th>
        </tr></thead><tbody>{rows}</tbody></table></div>"""

    # Cluster detail
    if cs:
        blocks = ""
        for item in cs:
            cid = int(item.get("cluster", 0))
            color = _cluster_color(cid)
            words = " ".join(f'<span class="topword">{w}</span>' for w in item.get("top_words", []))
            srows = ""
            for i, s in enumerate(item.get("samples", [])[:5], 1):
                raw   = s.get(text_col) or s.get("komentar", "-")
                clean = s.get("komentar_bersih", "-")
                sv    = _fmt_float(s.get("silhouette_sample"), 4)
                sc    = "#10B981" if (s.get("silhouette_sample") or 0) >= 0 else "#EF4444"
                srows += f"""<tr>
                    <td class="td-center">{i}</td><td>{raw}</td>
                    <td style="font-family:monospace;font-size:9pt;color:#475569;">{clean}</td>
                    <td class="td-center td-num" style="color:{sc};font-weight:700;">{sv}</td></tr>"""
            blocks += f"""<div style="margin-bottom:20px;border-left:4px solid {color};padding-left:14px;">
            <h3 style="font-size:12pt;font-weight:800;color:#1E293B;margin-bottom:4px;">C{cid} &mdash; {item.get("label","")}</h3>
            <p style="font-size:9.5pt;color:#64748B;margin-bottom:8px;">{_fmt_int(item.get("jumlah"))} komentar
               ({item.get("persen",0):.1f}%) &bull; Silhouette: {_fmt_float(item.get("silhouette_rata2"),4)}</p>
            <p style="font-size:9pt;font-weight:700;color:#94A3B8;margin-bottom:4px;">KATA KUNCI</p>
            <div style="margin-bottom:8px;">{words}</div>
            <p style="font-size:9pt;font-weight:700;color:#94A3B8;margin-bottom:4px;">SAMPEL KOMENTAR</p>
            <table><thead><tr><th>No</th><th>Komentar Asli</th><th>Komentar Bersih</th><th>Silhouette</th></tr></thead>
            <tbody>{srows}</tbody></table></div>"""
        sections += f"""<div class="section page-break">
        <div class="section-title">Detail per Cluster</div>{blocks}</div>"""

    return sections

# ── PDF engine ────────────────────────────────────────────────────────────────

def _try_add_gtk_path() -> None:
    candidates = [
        r"C:\Program Files\GTK3-Runtime Win64\bin",
        r"C:\Program Files\GTK3-Runtime\bin",
        r"C:\GTK\bin",
        r"C:\msys64\mingw64\bin",
    ]
    current = os.environ.get("PATH", "")
    additions = [p for p in candidates if os.path.isdir(p) and p not in current]
    if additions:
        os.environ["PATH"] = ";".join(additions) + ";" + current


def _to_pdf(html_str: str) -> bytes:
    try:
        _try_add_gtk_path()
        from weasyprint import HTML
        return HTML(string=html_str, base_url=None).write_pdf()
    except (ImportError, OSError):
        pass
    try:
        import io
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        result = pisa.CreatePDF(html_str.encode("utf-8"), dest=buf, encoding="utf-8")
        if result.err:
            raise RuntimeError(f"xhtml2pdf error: {result.err}")
        buf.seek(0)
        return buf.read()
    except ImportError:
        raise RuntimeError(
            "Tidak ada PDF backend. Install WeasyPrint atau xhtml2pdf."
        )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pdf_evaluasi(state: dict) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_evaluasi(state, _logo_b64(), now_str))


def generate_pdf_visualisasi(state: dict) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_visualisasi(state, _logo_b64(), now_str))


def generate_pdf_interpretasi(state: dict) -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_interpretasi(state, _logo_b64(), now_str))


def generate_pdf_hasil(state: dict, result_df=None,
                       cluster_filter: str = "all",
                       search_query: str = "") -> bytes:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_hasil(state, _logo_b64(), now_str,
                               result_df=result_df,
                               cluster_filter=cluster_filter,
                               search_query=search_query))


def generate_pdf(state: dict) -> bytes:
    """Laporan lengkap (semua bagian). Alias untuk backward compat."""
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _to_pdf(_html_lengkap(state, _logo_b64(), now_str))


# backward compat alias
def build_html(state: dict) -> str:
    now_str = datetime.now().strftime("%d %B %Y %H:%M")
    return _html_lengkap(state, _logo_b64(), now_str)
