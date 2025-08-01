# functions/main.py
from firebase_functions import https_fn
from firebase_admin import initialize_app

initialize_app()

@https_fn.on_request()
def wams_app(req: https_fn.Request):
    # Impor aplikasi Flask DI DALAM fungsi
    # Ini memastikan kode Flask hanya berjalan saat ada permintaan
    from app import app
    with app.request_context(req.environ):
        return app.full_dispatch_request()