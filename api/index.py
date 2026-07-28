"""
api/index.py — Vercel entrypoint.
Import app dari root module.
"""
import sys
import os

# Tambahkan root directory ke sys.path agar bisa import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel expects variable named 'app' or 'handler'
# Flask app sudah compatible dengan WSGI interface Vercel
