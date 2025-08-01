# functions/main.py
import os
import json
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, functions
from app import app

# --- INISIALISASI FIREBASE (HANYA DI SINI) ---
options.set_global_options(region=options.SupportedRegion.ASIA_SOUTHEAST1)
initialize_app()
config = functions.config()

# --- MENYUNTIKKAN KONFIGURASI KE APLIKASI FLASK ---
try:
    app.config['SQLALCHEMY_DATABASE_URI'] = config.wams.database_url
    app.config['SECRET_KEY'] = config.wams.secret_key
    app.config['GCP_CREDS_DICT'] = json.loads(config.wams.gcp_credentials)
except Exception:
    print("PERINGATAN: Gagal memuat config Firebase. Menggunakan konfigurasi lokal.")
    # Konfigurasi fallback untuk development lokal
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SECRET_KEY'] = 'kunci-rahasia-lokal-anda'
    app.config['GCP_CREDS_DICT'] = None

# --- ENTRY POINT UNTUK CLOUD FUNCTION ---
@https_fn.on_request()
def wams_app(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()