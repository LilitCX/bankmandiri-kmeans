# Dashboard K-Means Komentar TikTok Bank Mandiri

Aplikasi web sederhana berbasis Flask + Bootstrap untuk pengelompokan opini publik pada komentar TikTok Bank Mandiri menggunakan preprocessing teks, TF-IDF, fitur topik manual, LSA/SVD, dan K-Means.

## Fitur

- Upload dataset CSV
- Preview data mentah
- Pemilihan kolom komentar
- Preprocessing komentar
- TF-IDF + fitur topik manual
- LSA/SVD
- K-Means clustering
- Evaluasi cluster: Silhouette Score dan Davies-Bouldin Index
- Grafik distribusi cluster
- Grafik evaluasi K
- Top words per cluster
- Sampel komentar per cluster
- Wordcloud per cluster
- Download hasil CSV dan Excel

## Cara Menjalankan

```bash
cd bankmandiri_dashboard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Buka browser:

```text
http://127.0.0.1:5000
```

## Format CSV yang Disarankan

Minimal memiliki kolom:

```text
komentar
```

Lebih baik jika memiliki kolom:

```text
no,tanggal,username,komentar,is_banking
```

## Catatan Akademis

Penamaan cluster tetap sebaiknya ditinjau manual oleh peneliti berdasarkan top words dan sampel komentar setiap cluster. Dashboard ini menyediakan label awal sesuai pipeline notebook, tetapi label tersebut dapat disesuaikan dalam pembahasan tugas akhir.
