# functions/main.py
import os
import json
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, functions

# Inisialisasi Firebase HANYA SEKALI di sini
initialize_app()

@https_fn.on_request(region="asia-southeast1")
def wams_app(req: https_fn.Request) -> https_fn.Response:
    # --- Lazy Import ---
    # Impor aplikasi Flask DI DALAM fungsi.
    # Ini memastikan kode Flask (termasuk gspread) hanya berjalan saat ada permintaan,
    # bukan saat proses build/analisis.
    from app import app, db

    # --- Menyuntikkan Konfigurasi ---
    # Konfigurasi disuntikkan setiap kali fungsi dipanggil
    config = functions.config()
    try:
        app.config['SQLALCHEMY_DATABASE_URI'] = config.wams.database_url
        app.config['SECRET_KEY'] = config.wams.secret_key
        app.config['GCP_CREDS_DICT'] = json.loads(config.wams.gcp_credentials)
    except Exception as e:
        print(f"PERINGATAN: Gagal memuat config Firebase: {e}. Menggunakan konfigurasi lokal.")
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../database.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
        app.config['SECRET_KEY'] = 'kunci-rahasia-lokal-anda'
        app.config['GCP_CREDS_DICT'] = None

    # --- Menjalankan Aplikasi Flask ---
    with app.request_context(req.environ):
        return app.full_dispatch_request()