import os
import re
import json
import string
from functools import lru_cache
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scipy.sparse import hstack, csr_matrix
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

try:
    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
    from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    SASTRAWI_OK = True
except Exception:
    StemmerFactory = None
    StopWordRemoverFactory = None
    SASTRAWI_OK = False

try:
    from wordcloud import WordCloud
    WORDCLOUD_OK = True
except Exception:
    WORDCLOUD_OK = False

# =========================
# Kamus normalisasi dari notebook
# =========================
KAMUS_NORM = {
    "ga":"tidak","gak":"tidak","ngak":"tidak","ngga":"tidak","nggak":"tidak","gk":"tidak",
    "tdk":"tidak","ndak":"tidak","nda":"tidak","enggak":"tidak","engga":"tidak","gaa":"tidak",
    "kagak":"tidak","gaada":"tidak","gada":"tidak","gakada":"tidak_ada","gkada":"tidak_ada",
    "gabisa":"tidak_bisa","gakbisa":"tidak_bisa","gbisa":"tidak_bisa","gbs":"tidak_bisa",
    "gabisaa":"tidak_bisa","nggabisa":"tidak_bisa","ndabisa":"tidak_bisa","tdkbisa":"tidak_bisa",
    "yg":"yang","dgn":"dengan","dg":"dengan","utk":"untuk","krn":"karena","karna":"karena",
    "jg":"juga","jga":"juga","tp":"tapi","tpi":"tapi","bs":"bisa","bsa":"bisa",
    "udh":"sudah","sdh":"sudah","blm":"belum","belom":"belum","lom":"belum",
    "skrg":"sekarang","skrng":"sekarang","skrang":"sekarang","kmrn":"kemarin","dlu":"dulu",
    "lg":"lagi","msh":"masih","masi":"masih","hrs":"harus","hrus":"harus",
    "lbh":"lebih","truz":"terus","trs":"terus","trus":"terus",
    "dpt":"dapat","dapet":"dapat","nyampe":"sampai","sampe":"sampai",
    "kalo":"kalau","klw":"kalau","kl":"kalau","klo":"kalau","klu":"kalau",
    "gimana":"bagaimana","gmna":"bagaimana","gmn":"bagaimana",
    "knpa":"kenapa","knp":"kenapa",
    "emang":"memang","emg":"memang",
    "pake":"pakai","pke":"pakai","dipake":"pakai","make":"pakai","bikin":"buat","nanya":"tanya",
    "mau":"ingin","pengen":"ingin","pingin":"ingin","pgn":"ingin",
    "livin":"livin","living":"livin","livinn":"livin","livinandiri":"livin","livin_mandiri":"livin",
    "eror":"error","errorr":"error","loadingg":"loading",
    "nomer":"nomor","no":"nomor","nomornya":"nomor",
    "trf":"transfer","tf":"transfer","transferan":"transfer",
    "rek":"rekening","rekeningnya":"rekening",
    "atem":"atm",
    "pijaman":"pinjaman","pinjem":"pinjam","minjem":"pinjam","kredt":"kredit",
    "notif":"notifikasi","topup":"isi_ulang","top_up":"isi_ulang",
    "ngajukan":"ajukan",
    "mantaf":"mantap","mantapp":"mantap","kren":"keren",
    "byar":"bayar","byr":"bayar","bayarin":"bayar","bwat":"buat","sya":"saya","sy":"saya",
    "saldonya":"saldo","tokennya":"token","kartunya":"kartu","akunnya":"akun",
    "aq":"aku","gw":"saya","gue":"saya","gua":"saya",
    "aptivasi":"aktivasi","aktivkanya":"aktivasi",
    "sih":"","dong":"","deh":"","nih":"","tuh":"","lah":"","kan":"",
    "loh":"","nah":"","eh":"","ih":"","ya":"","iya":"","yap":"",
    "kok":"","ko":"","woi":"","aduh":"","wah":"","yah":"","bang":"",
    "bgt":"","banget":"","bngt":"","bgtt":"",
    "kak":"","kakk":"","kakak":"","ka":"","mbak":"","mba":"","mas":"",
    "sis":"","gan":"","sob":"","pak":"","bu":"","ibu":"","bapak":"","bos":"",
    "min":"","admin":"","kk":"","bro":"",
    "wkwk":"","wkwkwk":"","wkwkwkwk":"","haha":"","hehe":"","hihi":"",
    "terimakasih":"","makasih":"","thanks":"","thank":"","thx":"","tks":"",
    "alhamdulillah":"","mudahan":"","moga":"","semoga":"","aamiin":"","amiin":"",
    "bismillah":"","selamat":"","semangat":"",
    "bln":"","org":"","rmh":"","jta":"","jt":"","ktnya":"","tdgkan":"","bsh":"",
    "onlien":"","prett":"","lipin":"","naya":"","hadrun":"","mualaikum":"",
    "assalamu":"","waalaikum":"","nlvon":"","wwwrb":"","gimn":"","gimnaa":"",
    "gmanacaray":"","yeyy":"","weyy":"","hahahah":"","hadecchh":"","sll":"",
    "swt":"","dpn":"","salfok":"","itupun":"","donk":"","kira2":"","joss":"",
    "php":"","okeh":"","haii":"","haiii":"","nyh":"","kawa":"","lanos":"",
    "humpang":"","cgp":"","hee":"","tdi":"","tilfun":"","sarulla":"",
    "tapanuli":"","mandri":"","minn":"","pina":"","boro":"","umr":"",
    "istana":"","pemirsa":"",
    "mndiri":"mandiri","mdiri":"mandiri","mandri":"mandiri","dibank":"bank",
    "tetep":"tetap","gampang":"mudah","dipotong":"terpotong",
    "bsah":"bisa","bisah":"bisa","blum":"belum","sdgkan":"sedangkan",
    "vitur":"fitur","solosinya":"solusi","bner":"benar",
    "spaylater":"paylater","paylateer":"paylater","paylattre":"paylater",
    "kepotong":"terpotong","diptong":"terpotong","terlallu":"terlalu",
    "syaratpemotongan":"syarat","dihistori":"riwayat","pamodal":"modal",
    "livinga":"livin","livin_a":"livin","mandri":"mandiri",
}

NEGATION_PHRASES = {
    ("tidak", "bisa"): "tidak_bisa",
    ("belum", "bisa"): "belum_bisa",
    ("tidak", "ada"): "tidak_ada",
    ("belum", "ada"): "belum_ada",
    ("tidak", "masuk"): "tidak_masuk",
    ("belum", "masuk"): "belum_masuk",
    ("tidak", "muncul"): "tidak_muncul",
    ("belum", "muncul"): "belum_muncul",
    ("tidak", "terkirim"): "tidak_terkirim",
    ("belum", "terkirim"): "belum_terkirim",
    ("tidak", "berubah"): "tidak_berubah",
    ("tidak", "jelas"): "tidak_jelas",
}


def normalize_compound_phrases(text):
    text = str(text).lower()

    for keyword in [
        "token", "saldo", "rekening", "aplikasi", "kartu", "pinjaman",
        "nomor", "kode", "notifikasi", "tagihan", "tabungan", "transaksi",
        "layanan", "pelayanan", "asuransi", "cicilan",
    ]:
        text = re.sub(rf"\b{keyword}(?:nya)?\b", keyword, text)

    text = re.sub(r"\b(ga|gak|ngga|nggak|ngak|tdk|tidak|tak|enggak|kagak)\s+bisa\b", "tidak_bisa", text)
    text = re.sub(r"\b(gabisa|gakbisa|gbisa|gbs|tdkbisa)\b", "tidak_bisa", text)
    text = re.sub(r"\b(ga|gak|ngga|nggak|ngak|tdk|tidak|tak)\s+ada\b", "tidak_ada", text)
    text = re.sub(r"\b(ga|gak|ngga|nggak|ngak|tdk|tidak|tak)\s+masuk\b", "tidak_masuk", text)
    text = re.sub(r"\b(ga|gak|ngga|nggak|ngak|tdk|tidak|tak)\s+muncul\b", "tidak_muncul", text)
    text = re.sub(r"\bbelum\s+bisa\b", "belum_bisa", text)
    text = re.sub(r"\bbelum\s+masuk\b", "belum_masuk", text)
    text = re.sub(r"\bbelum\s+muncul\b", "belum_muncul", text)

    text = re.sub(r"\btop[\s\-]?up\b", "isi_ulang", text)
    text = re.sub(r"\bcustomer[\s\-]?service\b", "customer_service", text)
    text = re.sub(r"\bcall[\s\-]?center\b", "call_center", text)
    text = re.sub(r"\blupa\s+pin\b", "lupa_pin", text)
    text = re.sub(r"\blupa\s+(password|kata\s+sandi)\b", "lupa_password", text)
    text = re.sub(r"\b(saldo|uang|dana)\s+(hilang|berkurang|terkurang|raib)\b", "saldo_hilang", text)
    text = re.sub(r"\b(kartu|atm)\s+(tertelan|nyangkut|tertelon)\b", "atm_tertelan", text)
    text = re.sub(r"\b(kode|nomor|no\.?|nomer)\s+token\b", "kode_token", text)
    text = re.sub(r"\bbiaya\s+admin(?:istrasi)?\b", "biaya_admin", text)
    text = re.sub(r"\bpengajuan\s+(kredit|pinjaman|kur|kpr)\b", r"pengajuan_\1", text)
    text = re.sub(r"\bbunga\s+(tinggi|besar|mahal|gedhe)\b", "bunga_tinggi", text)
    text = re.sub(r"\bs[\s\-]?paylater\b", "paylater", text)

    return text

STOPWORD_EXTRA = {
    "aku","saya","kita","kami","mereka","dia","anda","gue","gw","gua","aq","sy",
    "ini","itu","beliau","kalian",
    "buat","ada","jadi","sama","sudah","udah","lagi","nya","yang",
    "keluar","lihat","liat","kasih","beli","jual","tanya",
    "bilang","kata","coba","pergi","datang","tunggu","nunggu",
    "kirim","terima","minta","tolong","bantu","buka","tutup",
    "ganti","ubah","tambah","hapus","cari","pilih",
    "sekarang","kemarin","besok","hari","bulan","tahun","kali",
    "tadi","nanti","dulu","lalu","setelah","sebelum","saat","waktu",
    "malem","malam","pagi","siang","sore","tanggal",
    "semua","banyak","sedikit","lama","baru","baik","selalu","sering",
    "jarang","kadang","pernah","mungkin","ternyata","justru","hampir",
    "sekali","terus","langsung","segera","lewat","kayaknya",
    "sepertinya","rasanya","katanya",
    "bagaimana","kenapa","mengapa","dimana","kemana","kapan",
    "siapa","apa","apakah","mana","kalau","jika","karena","supaya",
    "agar","maka","tetapi","tapi","namun","atau","dan","dengan",
    "untuk","dari","ke","di","pada","oleh","dalam","luar","atas",
    "bawah","depan","belakang","melalui","sekitar","antara",
    "seperti","kayak","biar","hampir","sebab",
    "video","konten","fyp","live","komen","tiktok","share","upload",
    "posting","post",
    "and","the","for","with","this","that","not","just","also","ya",
    "cara","caranya","hal","orang","tempat","nama","angka",
    "saja","hanya","sangat","pun","per","demi","tau","tahu",
    "gitu","begitu","gini","begini","sini","situ","sana","juga",
    "aja","aj","ajah","ajaa","yaa","yah","kah","masa","dah","dongg","nihh",
    "sma","sby","smg","semoga",
    "ingin","mau","pakai","punya","dapat","harus","sampai","padahal",
    "masih","lebih","pas","memang","malah","lain","sendiri","setiap",
    "tiap","cuma","benar","bener","pakaii","pake","pke","make",
    "bisa","nomor","kode","no","top","berapa","mohon",
    "tidak","belum","bukan","tanpa",
    "uang","duit","dana","masuk","ambil","anak","juta","ribu","online",
    "habis","tetap","kembali","pertama","terakhir","satu","jawab","perlu",
    "bank","mandiri","mandirinya","mandiriku","livin","living","livinku",
    "mobile","banking","bri","bca","bni","btn",
    "hj","pt","po","ksp","surya","titi","tirta","kencana","wiliam",
    "william","hasanah","jihan","iskandar","cina","unda","gajih",
    "surabaya","indonesia","motor","mobil","maju",
    "mama","papa","ayah","suami","istri","paman","kakek","nenek",
    "walet","istana","lipin","naya","hadrun","sarulla","tapanuli",
    "astah","pamodal","pemirsa","brobok","axxa","lanos","kawa","cgp",
    "humpang","dmna","pina","minn","mandri","livinga","livin_a",
    "utara","selatan","timur","barat","sumatra","lampung","medan",
    "manado","kota","kabupaten","provinsi","daerah","pulau","jawa",
    "sulawesi","papua","kalimantan","bandung","jakarta","makassar",
    "yogyakarta","semarang","palembang","cikande","cikampek",
    "allah","akhirat","rejeki","rezeki","amiinn","bismilah",
    "subhanallah","allahuakbar","masyaallah","insyaallah","insya",
    "assalamualaikum","assalamu","waalaikum","mualaikum","alhamdulillah",
    "alhamdulilah","mudahan","moga","bersyukur","syukur","tabur",
    "yatim","doa","niat","amal","surga","kubur","dosa",
    "love","bahagia","forever","amazing","mantul","judes","merinding",
    "mumet","berisik","boro","pain","betulan","ketulan","manis",
    "indah","cantik","ganteng","kece","drop","break","bangkrut",
    "saham","reksadana","obligasi","investasi","investas",
    "wifi","internet","provider","indihome","telkom",
    "emas","logam","mulia","perhiasan","pendidikan","sekolah",
    "kampus","kuliah","guru","ilmu","sawit","pertanian","kebun",
    "tanah","lahan","tambang","gopay","ovo","linkaja","jenius",
    "grab","gojek","tokopedia","shopee","lazada",
    "paling","cukup","jalan","soalnya","itupun","donk","reguler",
    "program","terbaru","modern","cetak","bawa","kira","masing",
    "mulai","sisa","beda","php","nyesel","kos","paham","izin",
    "loker","pekerja","penggerak","kolektif","rupiah","ratus",
    "keluarga","dua","tiga","empat","lima","enam","tujuh","delapan",
    "sembilan","sepuluh","separuh","setengah","sepertiga","kedua","ketiga",
    "bln","rmh","jta","jt","ktnya","salfok","dpn","sll","swt","bsah",
    "onlien","prett","bsh","sdgkan","nlvon","wwwrb","gimn","hadecchh",
    "weyy","yeyy","hahahah","hee","tdi","tilfun","ndk","galbay",
    "kerja","gaji","pajak","pensiun","dibank","hrus",
    "makan","masak","minum","tidur","pulang","belanja","main","nonton","baca",
    "tulis","sukses","mudah","mantap","keren","enak","sayang",
    "darurat","solusi","boleh","maaf","bangsa","rakyat","besar",
    "utang","tinggal","gedung","sebulan","untung","tetep","jangan",
    "joss","okeh","oke","dihistori","solosinya","gimnaa",
    "iku","praturan","bantal","rama","offline","story","pre",
}

PROTECTED = {
    "gagal","tidak_ada","tidak_bisa","belum_bisa","belum_ada",
    "tidak_masuk","belum_masuk","tidak_muncul","belum_muncul",
    "tidak_terkirim","belum_terkirim","tidak_berubah","tidak_jelas",
    "error","kecewa","kesal","buruk","ribet","susah","blokir",
    "kacau","parah","lambat","hilang","salah","mahal","rugi","hack",
    "kapok","boros","menipu","tipu",
    "berhasil","puas","bagus","mudah","aman","sukses","praktis",
    "keren","mantap","cepat","canggih","gratis","senang","nyaman",
    "transfer","saldo","rekening","atm","kredit","pinjaman",
    "tabungan","deposito","kur","kpr","cicilan","bunga","biaya",
    "tagihan","token","listrik","pln","pdam","kartu","debit","tapcash",
    "transaksi","pembayaran","setor","aktivasi","verifikasi","notifikasi",
    "blokir","limit","pin","otp","isi_ulang","paylater","asuransi",
    "mobile","banking","nasabah","cabang","teller","cs","customer",
    "service","pengajuan","investasi","reksadana","obligasi","saham",
    "ajukan","pinjam","daftar","bayar","cek","isi","cairkan",
    "angsuran","cicil","agunan","jaminan",
    "saldo_hilang","atm_tertelan","lupa_pin","lupa_password",
    "kode_token","biaya_admin","bunga_tinggi","customer_service",
    "call_center","pengajuan_kredit","pengajuan_pinjaman",
    "pengajuan_kur","pengajuan_kpr",
}

RULES = {
    "C0_APP_MASALAH": {
        "livin", "aktivasi", "otp", "pin", "login", "daftar",
        "aplikasi", "error", "gagal", "tidak_bisa", "blokir",
        "password", "pasword", "fitur", "update", "verifikasi",
        "notifikasi", "loading", "lambat", "hang", "lupa_pin",
        "lupa_password", "call_center"
    },
    "C1_TRANSAKSI": {
        "saldo", "transfer", "rekening", "atm", "kartu", "debit",
        "setor", "tarik", "bayar", "tagihan", "transaksi",
        "tabungan", "potong", "debet", "mutasi", "riwayat",
        "limit", "biaya", "admin", "mahal", "gratis",
        "saldo_hilang", "atm_tertelan", "biaya_admin"
    },
    "C2_TOKEN_UTILITAS": {
        "token", "listrik", "pln", "pdam", "pulsa", "isi_ulang",
        "meteran", "kwh", "bayar_listrik", "tagihan_listrik",
        "nomor_token", "kode_token", "tapcash", "top"
    },
    "C3_PINJAMAN": {
        "pinjaman", "kredit", "kur", "kpr", "cicilan", "bunga",
        "pinjam", "ajukan", "angsuran", "agunan", "jaminan",
        "modal", "usaha", "umkm", "cair", "pengajuan",
        "paylater", "hutang", "tenor", "pengajuan_kredit",
        "pengajuan_pinjaman", "pengajuan_kur", "pengajuan_kpr",
        "bunga_tinggi"
    },
    "C4_KELUHAN_UMUM": {
        "kecewa", "kesal", "buruk", "kapok", "mending", "parah", "kacau",
        "asuransi", "tipu", "menipu", "rugi", "boros", "pelayanan",
        "customer", "service", "customer_service", "cs", "teller", "cabang", "antri",
        "pegawai", "karyawan", "hack", "diretas", "penipuan",
        "susah", "ribet", "lambat"
    },
}

DEFAULT_CLUSTER_LABELS = {
    0: "Masalah Aplikasi, Akun & Login",
    1: "Masalah Saldo, Transaksi & ATM",
    2: "Pembelian Token Listrik & Utilitas",
    3: "Pertanyaan & Pengajuan Pinjaman/KUR",
    4: "Keluhan Pelayanan & Pengalaman Negatif",
}

# Nama ramah untuk setiap kategori RULES
RULES_LABEL_MAP = {
    "C0_APP_MASALAH": "Masalah Aplikasi, Akun & Login",
    "C1_TRANSAKSI": "Masalah Saldo, Transaksi & ATM",
    "C2_TOKEN_UTILITAS": "Pembelian Token Listrik & Utilitas",
    "C3_PINJAMAN": "Pertanyaan & Pengajuan Pinjaman/KUR",
    "C4_KELUHAN_UMUM": "Keluhan Pelayanan & Pengalaman Negatif",
}


def generate_cluster_label(cluster_id, top_words, jumlah_cluster):
    """Generate nama cluster secara dinamis berdasarkan top_words dan RULES.
    Bekerja untuk sembarang nilai k."""
    # Jika k=5 dan cluster_id ada di DEFAULT, gunakan label default
    if jumlah_cluster == 5 and cluster_id in DEFAULT_CLUSTER_LABELS:
        return DEFAULT_CLUSTER_LABELS[cluster_id]

    # Hitung overlap antara top_words dengan setiap kategori RULES
    top_set = set(str(w).lower() for w in top_words)
    scores = {}
    for rule_key, keywords in RULES.items():
        overlap = len(top_set & keywords)
        if overlap > 0:
            scores[rule_key] = overlap

    if scores:
        best_rule = max(scores, key=scores.get)
        return RULES_LABEL_MAP.get(best_rule, f"Topik {best_rule}")

    # Fallback: gunakan 3 kata teratas sebagai nama
    preview = ", ".join(str(w) for w in top_words[:3]) if top_words else "Umum"
    return f"Cluster Topik: {preview}"


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


@lru_cache(maxsize=10000)
def cached_stem(word):
    if _GLOBAL_STEMMER is None:
        return word
    return _GLOBAL_STEMMER.stem(word)

_GLOBAL_STEMMER = None

def merge_negation_phrases(tokens):
    merged = []
    i = 0
    while i < len(tokens):
        pair = tuple(tokens[i:i + 2])
        if len(pair) == 2 and pair in NEGATION_PHRASES:
            merged.append(NEGATION_PHRASES[pair])
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    return merged

class TextPreprocessor:
    def __init__(self):
        if SASTRAWI_OK:
            self.stemmer = StemmerFactory().create_stemmer()
            global _GLOBAL_STEMMER
            _GLOBAL_STEMMER = self.stemmer
            self.stopwords = set(StopWordRemoverFactory().get_stop_words()).union(STOPWORD_EXTRA)
        else:
            self.stemmer = None
            self.stopwords = set(STOPWORD_EXTRA)

    def preprocess(self, text):
        text = normalize_compound_phrases(text)
        text = re.sub(r"http\S+|www\S+|@\w+|#\w+", " ", text)
        text = re.sub(r"\d+", " ", text)
        text = re.sub(r"[^\x00-\x7F]+", " ", text)
        punctuation_without_underscore = string.punctuation.replace("_", "")
        text = re.sub(r"[" + re.escape(punctuation_without_underscore) + "]", " ", text)
        text = re.sub(r"(.)\1{2,}", r"\1\1", text)
        text = re.sub(r"\s+", " ", text).strip()

        tokens = text.split()
        tokens = [KAMUS_NORM.get(w, w) for w in tokens]
        tokens = [t for t in tokens if t.strip()]
        tokens = merge_negation_phrases(tokens)
        tokens = [w for w in tokens if w not in self.stopwords and len(w) >= 3]

        hasil = []
        for word in tokens:
            if "_" in word or word in PROTECTED:
                hasil.append(word)
            elif self.stemmer and SASTRAWI_OK:
                hasil.append(cached_stem(word))
            else:
                hasil.append(word)
        return " ".join(hasil)


def detect_topic(text_clean):
    tokens = set(str(text_clean).split())
    scores = {}
    for topic, keywords in RULES.items():
        score = len(tokens & keywords)
        if score > 0:
            scores[topic] = score
    if not scores:
        return -1
    topic_map = {
        "C0_APP_MASALAH": 0,
        "C1_TRANSAKSI": 1,
        "C2_TOKEN_UTILITAS": 2,
        "C3_PINJAMAN": 3,
        "C4_KELUHAN_UMUM": 4,
    }
    return topic_map[max(scores, key=scores.get)]


def fitur_topik(text):
    tokens = set(str(text).split())
    return [
        len(tokens & RULES["C0_APP_MASALAH"]),
        len(tokens & RULES["C1_TRANSAKSI"]),
        len(tokens & RULES["C2_TOKEN_UTILITAS"]),
        len(tokens & RULES["C3_PINJAMAN"]),
        len(tokens & RULES["C4_KELUHAN_UMUM"]),
    ]


def read_csv_smart(path):
    # Coba beberapa encoding yang umum pada CSV Windows/Excel.
    last_error = None
    for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_error = e
    raise last_error


def create_bar_chart(summary, output_path):
    labels = [f"C{row['cluster']}" for row in summary]
    counts = [row["jumlah"] for row in summary]
    plt.figure(figsize=(9, 5))
    bars = plt.bar(labels, counts)
    plt.title("Jumlah Komentar per Cluster")
    plt.xlabel("Cluster")
    plt.ylabel("Jumlah Komentar")
    for bar, count in zip(bars, counts):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), str(count), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close()


def create_eval_chart(k_values, inertia, sil, selected_k, output_path):
    # Dua grafik: Elbow/Inertia dan Silhouette Score
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    series = [
        (inertia, "Elbow / Inertia", "Inertia"),
        (sil,     "Silhouette Score", "Score"),
    ]
    for ax, (data, title, ylabel) in zip(axes, series):
        ax.plot(k_values, data, marker="o")
        ax.axvline(selected_k, linestyle="--")
        ax.set_title(title)
        ax.set_xlabel("Jumlah Cluster (k)")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close()


def create_wordclouds(df, result_dir, jumlah_cluster):
    paths = {}
    if not WORDCLOUD_OK:
        return paths
    for c in range(jumlah_cluster):
        text = " ".join(df.loc[df["cluster"] == c, "komentar_bersih"].astype(str).tolist()).strip()
        if not text:
            continue
        wc = WordCloud(width=900, height=450, background_color="white", collocations=False).generate(text)
        filename = f"wordcloud_cluster_{c}.png"
        output_path = os.path.join(result_dir, filename)
        plt.figure(figsize=(9, 4.5))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(output_path, dpi=140, bbox_inches="tight")
        plt.close()
        paths[str(c)] = filename
    return paths


def run_clustering(
    csv_path,
    result_dir,
    komentar_col="komentar",
    jumlah_cluster=5,
    min_kata_raw=3,
    processed_df=None,
    preprocessing_stats=None,
):
    os.makedirs(result_dir, exist_ok=True)
    jumlah_cluster = _safe_int(jumlah_cluster, 5)
    min_kata_raw = _safe_int(min_kata_raw, 3)
    preprocessing_stats = preprocessing_stats or {}

    if processed_df is not None:
        df_raw = processed_df.copy()
        if komentar_col not in df_raw.columns:
            raise ValueError(f"Kolom komentar '{komentar_col}' tidak ditemukan. Kolom tersedia: {', '.join(df_raw.columns)}")
        if "komentar_bersih" not in df_raw.columns:
            raise ValueError("Data preprocessing belum memiliki kolom 'komentar_bersih'. Ulangi preprocessing.")

        df_raw[komentar_col] = df_raw[komentar_col].fillna("").astype(str)
        df_raw["komentar_bersih"] = df_raw["komentar_bersih"].fillna("").astype(str)
        if df_raw["komentar_bersih"].str.strip().eq("").any():
            raise ValueError("Data preprocessing masih memiliki komentar_bersih kosong. Ulangi preprocessing.")

        df = df_raw.reset_index(drop=True)
        jumlah_data_awal = int(preprocessing_stats.get("jumlah_data_awal", len(df_raw)))
        jumlah_tidak_null = int(preprocessing_stats.get("jumlah_tidak_null", df[komentar_col].notna().sum()))
        before_clean_filter = int(preprocessing_stats.get("jumlah_setelah_filter_raw", len(df)))
        after_nonempty = int(preprocessing_stats.get("jumlah_setelah_clean_nonempty", len(df)))
        after_min_clean_words = int(preprocessing_stats.get("jumlah_setelah_min_kata_bersih", len(df)))
        jumlah_duplikat = int(preprocessing_stats.get("jumlah_duplikat_dihapus", 0))
    else:
        df_raw = read_csv_smart(csv_path)
        if komentar_col not in df_raw.columns:
            raise ValueError(f"Kolom komentar '{komentar_col}' tidak ditemukan. Kolom tersedia: {', '.join(df_raw.columns)}")

        df_raw["len_kata"] = df_raw[komentar_col].astype(str).str.split().str.len()
        df = df_raw.copy()
        df = df[df[komentar_col].notna()].copy()
        jumlah_tidak_null = len(df)
        df = df[df[komentar_col].astype(str).str.split().str.len() >= min_kata_raw].copy()
        df = df.reset_index(drop=True)

        pre = TextPreprocessor()
        df["komentar_bersih"] = df[komentar_col].apply(pre.preprocess)
        before_clean_filter = len(df)
        df = df[df["komentar_bersih"].str.strip() != ""].copy()
        after_nonempty = len(df)
        df = df[df["komentar_bersih"].str.split().str.len() >= 2].copy()
        after_min_clean_words = len(df)
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["komentar_bersih"]).reset_index(drop=True)
        jumlah_duplikat = before_dedup - len(df)
        jumlah_data_awal = len(df_raw)

    if len(df) < jumlah_cluster:
        raise ValueError(f"Data valid hanya {len(df)} baris, lebih sedikit dari jumlah cluster k={jumlah_cluster}.")

    df["seed_label"] = df["komentar_bersih"].apply(detect_topic)

    max_features = min(500, max(50, len(df) * 2))
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2 if len(df) < 100 else 3,
        max_df=0.60,
        max_features=max_features,
        sublinear_tf=True,
    )
    X_tfidf = vectorizer.fit_transform(df["komentar_bersih"])

    bobot = 8.0
    X_fitur = csr_matrix(np.array([fitur_topik(t) for t in df["komentar_bersih"]]) * bobot)
    X_gabungan = hstack([X_tfidf, X_fitur])

    n_comp = min(60, X_gabungan.shape[1] - 1, len(df) - 1)
    n_comp = max(2, n_comp)
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    lsa = make_pipeline(svd, Normalizer(copy=False))
    X_lsa = lsa.fit_transform(X_gabungan)
    var_lsa = float(svd.explained_variance_ratio_.sum())

    # Seed initialization jika k=5, kalau bukan 5 pakai k-means++ agar aman.
    if jumlah_cluster == 5:
        initial_centroids = np.zeros((jumlah_cluster, X_lsa.shape[1]))
        rng = np.random.default_rng(42)
        for c in range(jumlah_cluster):
            mask = df["seed_label"] == c
            if mask.sum() > 0:
                initial_centroids[c] = X_lsa[mask.values].mean(axis=0)
            else:
                initial_centroids[c] = X_lsa[rng.integers(0, len(X_lsa))].copy()
        kmeans = KMeans(n_clusters=jumlah_cluster, init=initial_centroids, n_init=1, max_iter=500, random_state=42)
    else:
        kmeans = KMeans(n_clusters=jumlah_cluster, init="k-means++", n_init=15, max_iter=500, random_state=42)

    df["cluster"] = kmeans.fit_predict(X_lsa)
    df["x_lsa"] = X_lsa[:, 0]
    df["y_lsa"] = X_lsa[:, 1] if X_lsa.shape[1] > 1 else 0.0

    # Proyeksi t-SNE untuk scatter plot yang lebih baik
    try:
        perplexity_val = min(30, max(5, len(df) // 5))
        tsne = TSNE(
            n_components=2,
            perplexity=perplexity_val,
            random_state=42,
            n_iter=1000,
            learning_rate="auto",
            init="pca",
        )
        X_tsne = tsne.fit_transform(X_lsa)
        df["x_tsne"] = X_tsne[:, 0]
        df["y_tsne"] = X_tsne[:, 1]
        use_tsne = True
    except Exception:
        df["x_tsne"] = df["x_lsa"]
        df["y_tsne"] = df["y_lsa"]
        use_tsne = False
    final_sil = float(silhouette_score(X_lsa, df["cluster"]))
    df["silhouette_sample"] = silhouette_samples(X_lsa, df["cluster"])

    terms = vectorizer.get_feature_names_out()
    n_tfidf = X_tfidf.shape[1]
    centroids_full = svd.inverse_transform(kmeans.cluster_centers_)
    centroids_tfidf = centroids_full[:, :n_tfidf]

    # Buat label dinamis per cluster berdasarkan top_words & RULES
    labels = {}
    for c in range(jumlah_cluster):
        sub_tmp = df[df["cluster"] == c]
        top_idx_tmp = centroids_tfidf[c].argsort()[::-1][:15]
        top_words_tmp = [str(terms[j]) for j in top_idx_tmp]
        labels[c] = generate_cluster_label(c, top_words_tmp, jumlah_cluster)
    df["label_cluster"] = df["cluster"].map(labels)
    df["seed_match"] = df.apply(
        lambda r: "Tidak teridentifikasi" if r["seed_label"] == -1 else ("Cocok" if r["seed_label"] == r["cluster"] else "Beda dari seed"),
        axis=1,
    )

    summary = []
    for c in range(jumlah_cluster):
        sub = df[df["cluster"] == c]
        top_idx = centroids_tfidf[c].argsort()[::-1][:15]
        top_words = [str(terms[j]) for j in top_idx]
        sample_cols = [komentar_col, "komentar_bersih", "silhouette_sample"]
        samples = (
            sub.sort_values("silhouette_sample", ascending=False)[sample_cols]
            .head(5)
            .round({"silhouette_sample": 4})
            .to_dict(orient="records")
        )
        summary.append({
            "cluster": c,
            "label": labels[c],
            "jumlah": int(len(sub)),
            "persen": round((len(sub) / len(df)) * 100, 2),
            "silhouette_rata2": round(float(sub["silhouette_sample"].mean()), 4) if len(sub) else None,
            "silhouette_min": round(float(sub["silhouette_sample"].min()), 4) if len(sub) else None,
            "silhouette_max": round(float(sub["silhouette_sample"].max()), 4) if len(sub) else None,
            "top_words": top_words,
            "samples": samples,
        })

    k_values = list(range(2, min(8, len(df) - 1) + 1))
    inertia_list, sil_list = [], []
    for k in k_values:
        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        lbl = km.fit_predict(X_lsa)
        inertia_list.append(float(km.inertia_))
        sil_list.append(float(silhouette_score(X_lsa, lbl)))

    best_sil_idx = int(np.argmax(sil_list)) if sil_list else None
    rekomendasi_k = {
        "silhouette": {
            "k": int(k_values[best_sil_idx]) if best_sil_idx is not None else None,
            "nilai": round(float(sil_list[best_sil_idx]), 4) if best_sil_idx is not None else None,
        },
        "dipilih": int(jumlah_cluster),
    }

    chart_distribution = "distribusi_cluster.png"
    chart_evaluation = "evaluasi_cluster.png"
    create_bar_chart(summary, os.path.join(result_dir, chart_distribution))
    create_eval_chart(k_values, inertia_list, sil_list, jumlah_cluster, os.path.join(result_dir, chart_evaluation))
    wordclouds = create_wordclouds(df, result_dir, jumlah_cluster)

    output_cols = [col for col in ["no", "tanggal", "username", komentar_col, "komentar_bersih", "cluster", "label_cluster", "seed_label", "seed_match", "silhouette_sample"] if col in df.columns]
    csv_output = "hasil_clustering.csv"
    excel_output = "hasil_clustering.xlsx"
    df[output_cols].to_csv(os.path.join(result_dir, csv_output), index=False, encoding="utf-8-sig")
    df[output_cols].to_excel(os.path.join(result_dir, excel_output), index=False)

    metadata = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jumlah_data_awal": int(jumlah_data_awal),
        "jumlah_tidak_null": int(jumlah_tidak_null),
        "jumlah_setelah_filter_raw": int(before_clean_filter),
        "jumlah_setelah_clean_nonempty": int(after_nonempty),
        "jumlah_setelah_min_kata_bersih": int(after_min_clean_words),
        "jumlah_duplikat_dihapus": int(jumlah_duplikat),
        "jumlah_data_valid": int(len(df)),
        "jumlah_cluster": int(jumlah_cluster),
        "kolom_komentar": komentar_col,
        "min_kata_raw": int(min_kata_raw),
        "tfidf_shape": [int(X_tfidf.shape[0]), int(X_tfidf.shape[1])],
        "lsa_shape": [int(X_lsa.shape[0]), int(X_lsa.shape[1])],
        "variansi_lsa": round(var_lsa, 4),
        "silhouette": round(final_sil, 4),
        "sastrawi_ok": bool(SASTRAWI_OK),
        "wordcloud_ok": bool(WORDCLOUD_OK),
        "summary": summary,
        "seed_summary": df["seed_match"].value_counts().to_dict(),
        "cluster_quality": [
            {
                "cluster": item["cluster"],
                "label": item["label"],
                "jumlah": item["jumlah"],
                "silhouette_rata2": item["silhouette_rata2"],
                "silhouette_min": item["silhouette_min"],
                "silhouette_max": item["silhouette_max"],
            }
            for item in summary
        ],
        "evaluation": {
            "k_values": k_values,
            "inertia": [round(x, 4) for x in inertia_list],
            "silhouette": [round(x, 4) for x in sil_list],
            "rekomendasi_k": rekomendasi_k,
        },
        "files": {
            "csv": csv_output,
            "excel": excel_output,
            "chart_distribution": chart_distribution,
            "chart_evaluation": chart_evaluation,
            "wordclouds": wordclouds,
        },
        "preview_raw": df_raw.head(10).fillna("").to_dict(orient="records"),
        "preview_preprocessing": df[[komentar_col, "komentar_bersih"]].head(15).fillna("").to_dict(orient="records"),
        "preview_result": df[output_cols].head(100).fillna("").to_dict(orient="records"),
        "scatter_data": [
            {
                "x": round(float(row["x_tsne"]), 5),
                "y": round(float(row["y_tsne"]), 5),
                "cluster": int(row["cluster"]),
                "label": labels.get(int(row["cluster"]), f"Cluster {int(row['cluster'])}"),
                "komentar": str(row[komentar_col])[:120],
            }
            for _, row in df.iterrows()
        ],
        "use_tsne": use_tsne,
        "output_cols": output_cols,
    }
    with open(os.path.join(result_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return metadata
