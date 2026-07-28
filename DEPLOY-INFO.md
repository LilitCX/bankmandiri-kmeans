# Informasi Deploy Aplikasi Dashboard Bank Mandiri

## ❌ VERCEL TIDAK COCOK untuk aplikasi ini

### Mengapa?

Aplikasi ini menggunakan:
- **scikit-learn** (110 MB)
- **pandas** (60 MB)  
- **scipy** (110 MB)
- **matplotlib** (27 MB)
- **numpy** (30 MB)
- **Total dependencies: ~415 MB**

**Limit Vercel Python Serverless: 50 MB compressed (~100 MB uncompressed)**

Aplikasi machine learning dengan TF-IDF + SVD + K-Means tidak bisa berjalan di Vercel karena ukuran dependencies jauh melampaui batas.

---

## ✅ ALTERNATIF DEPLOYMENT YANG REALISTIS

### 1. **Render.com** (Gratis + Cocok untuk ML)
Platform terbaik untuk Python ML apps. Tidak ada batasan ukuran package ketat seperti Vercel.

**Cara deploy:**
```bash
# 1. Buat file render.yaml
# 2. Push ke GitHub
# 3. Connect ke Render.com
# 4. Deploy otomatis
```

**Kelebihan:**
- ✅ Free tier tersedia
- ✅ Support full scikit-learn, pandas, scipy
- ✅ Persistent storage (untuk uploads)
- ✅ Otomatis rebuild dari GitHub
- ✅ HTTPS gratis

**Kekurangan:**
- ⚠️ Cold start ~30 detik jika tidak ada traffic
- ⚠️ Free tier sleep setelah 15 menit tidak digunakan

---

### 2. **Railway.app** (Gratis $5/bulan credit)
Modern platform dengan UX bagus, cocok untuk demo skripsi.

**Cara deploy:**
```bash
# 1. railway login
# 2. railway init
# 3. railway up
```

**Kelebihan:**
- ✅ $5/bulan gratis kredit (cukup untuk demo ringan)
- ✅ Deploy dari GitHub otomatis
- ✅ Support environment variables
- ✅ Database addon gratis (jika butuh DB nanti)

**Kekurangan:**
- ⚠️ Setelah kredit habis, harus bayar

---

### 3. **Heroku** (Masih bisa, tapi berbayar)
Platform klasik, reliable, tapi tidak ada free tier lagi sejak 2022.

**Cara deploy:**
```bash
# 1. heroku login
# 2. heroku create nama-app
# 3. git push heroku main
```

**Kelebihan:**
- ✅ Dokumentasi lengkap
- ✅ Stabil dan mature
- ✅ Add-on ecosystem bagus

**Kekurangan:**
- ❌ Tidak ada free tier (mulai $7/bulan)
- ⚠️ Cold start jika pakai dyno murah

---

### 4. **PythonAnywhere** (Gratis dengan batasan)
Hosting khusus Python, cocok untuk presentasi/demo singkat.

**Kelebihan:**
- ✅ Free tier ada
- ✅ Setup mudah via web UI
- ✅ Persistent storage

**Kekurangan:**
- ⚠️ CPU limit ketat (bisa timeout saat clustering data besar)
- ⚠️ Tidak bisa otomatis deploy dari Git di free tier

---

### 5. **Replit** (Gratis untuk demo singkat)
Platform coding online dengan deployment built-in.

**Kelebihan:**
- ✅ Gratis untuk demo
- ✅ Setup sangat mudah
- ✅ Editor online (bisa coding langsung di browser)

**Kekurangan:**
- ⚠️ Performance terbatas di free tier
- ⚠️ URL public akan mati jika tidak ada activity

---

## 🚀 REKOMENDASI: Gunakan **Render.com**

Render adalah pilihan terbaik untuk **aplikasi Flask + scikit-learn**:
1. Gratis
2. Tidak ada batasan ukuran package
3. Setup mudah
4. Cocok untuk presentasi skripsi

---

## Tutorial Deploy ke Render (Step by Step)

### Step 1 — Buat file `render.yaml` di root project

```yaml
services:
  - type: web
    name: bankmandiri-dashboard
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn app:app --bind 0.0.0.0:$PORT"
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: FLASK_DEBUG
        value: "0"
      - key: APP_USERNAME
        sync: false
      - key: APP_PASSWORD
        sync: false
```

### Step 2 — Tambahkan `gunicorn` ke `requirements.txt`

```
gunicorn==21.2.0
```

### Step 3 — Push ke GitHub

```powershell
git add .
git commit -m "ready for Render deployment"
git push
```

### Step 4 — Deploy di Render.com

1. Buka [render.com](https://render.com) → Sign up/Login dengan GitHub
2. Klik **"New +"** → **"Blueprint"**
3. Connect repository GitHub kamu
4. Render akan detect `render.yaml` otomatis
5. Set environment variables:
   - `APP_USERNAME` → username login kamu
   - `APP_PASSWORD` → password login kamu
6. Klik **"Apply"**

Render akan build & deploy otomatis (~5-10 menit pertama kali).

### Step 5 — Akses aplikasi

Setelah deploy selesai, Render akan berikan URL:
```
https://bankmandiri-dashboard.onrender.com
```

---

## Catatan Penting

### Persistent Storage di Render
Render free tier tidak punya persistent disk. File upload akan **hilang setelah redeploy/restart**.

**Solusi:**
1. Untuk demo/presentasi: tidak perlu storage permanen
2. Untuk production: upgrade ke paid tier ($7/bulan) atau pakai S3/Cloudinary untuk file storage

### Cold Start
App akan "tidur" setelah 15 menit tidak ada traffic. Akses pertama setelah sleep butuh ~30 detik untuk bangun.

**Solusi:**
- Akses URL 5 menit sebelum presentasi
- Atau upgrade ke paid tier untuk always-on

---

## Environment Variables yang Dibutuhkan

| Variable | Value | Keterangan |
|---|---|---|
| `SECRET_KEY` | (auto-generated di Render) | Flask secret key |
| `APP_USERNAME` | `admin` | Username login dashboard |
| `APP_PASSWORD` | `password_kamu` | Password login dashboard |
| `FLASK_DEBUG` | `0` | Production mode |

---

## File yang Sudah Disiapkan

✅ `.env` — untuk development lokal  
✅ `.env.example` — template untuk tim  
✅ `.gitignore` — exclude file sensitif  
✅ `requirements.txt` — semua dependency (tanpa WeasyPrint)  
✅ `app.py` — entry point Flask  
✅ `api/index.py` — ~~Vercel~~ (tidak dipakai, file ini untuk Vercel)  
✅ `vercel.json` — ~~Vercel~~ (tidak dipakai)

---

## Rangkuman

| Platform | Gratis? | ML Support | Setup | Rekomendasi |
|---|---|---|---|---|
| **Vercel** | ✅ | ❌ (limit 50MB) | Mudah | ❌ Tidak cocok |
| **Render** | ✅ | ✅ | Mudah | ✅ **Terbaik** |
| **Railway** | ✅ ($5 credit) | ✅ | Mudah | ✅ Alternatif bagus |
| **Heroku** | ❌ ($7/bulan) | ✅ | Mudah | ⚠️ Kalau budget ada |
| **PythonAnywhere** | ✅ | ⚠️ (CPU limit) | Sedang | ⚠️ Untuk demo ringan |
| **Replit** | ✅ | ⚠️ (lambat) | Sangat mudah | ⚠️ Testing cepat |

**Gunakan Render.com untuk hasil terbaik!**
