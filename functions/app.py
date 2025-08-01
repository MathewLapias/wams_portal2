# app.py
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
from datetime import datetime
from functools import wraps
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from calendar import monthrange
import os
import random
import string
from collections import Counter
from sqlalchemy import func
import json
import pytz
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import io
from flask import Response
from calendar import monthrange
import pandas as pd
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder='../templates', static_folder='../public')

# Konfigurasi default (akan ditimpa oleh main.py saat deploy)
app.config.setdefault('SECRET_KEY', 'default-secret-key')
app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///default.db')
app.config.setdefault('GCP_CREDS_DICT', None)

# Inisialisasi Ekstensi
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@app.template_filter('to_wita')
def to_wita_filter(utc_dt):
    """Mengubah datetime UTC ke WITA dan memformatnya."""
    if utc_dt is None:
        return ""
    wita_tz = pytz.timezone('Asia/Makassar')
    wita_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(wita_tz)
    return wita_dt.strftime('%Y-%m-%d %H:%M:%S')

# --- DECORATOR & MODEL ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Anda tidak memiliki izin untuk mengakses halaman ini.", "danger")
            return redirect(url_for('portal_page'))
        return f(*args, **kwargs)
    return decorated_function

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<Log {self.timestamp}: {self.username} - {self.action}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- FORM ---
class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Buat Akun")

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError("Username sudah terdaftar. Silakan gunakan username lain.")

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Login")

# --- KONFIGURASI & DATA ---
KPPN_LIST = {
    "manado": "KPPN Manado", "tahuna": "KPPN Tahuna", "kotamobagu": "KPPN Kotamobagu", "bitung": "KPPN Bitung"
}
MODUL_LIST = {
    "sp2d": "Durasi SP2D", "adk": "ADK Kontraktual", "pmrt": "Penolakan PMRT", "karwas": "Karwas UP/TUP", "lainnya": "Modul Lainnya"
}
FILE_MAPPING = {
    "sp2d": "Durasi SP2D", "adk": "ADK Kontraktual", "pmrt": "Penolakan PMRT", "karwas": "Karwas UP_TUP", "lainnya": "Modul Lainnya"
}
MONTH_MAP = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4, "Mei": 5, "Juni": 6,
    "Juli": 7, "Agustus": 8, "September": 9, "Oktober": 10, "November": 11, "Desember": 12
}

# --- FUNGSI HELPER & PEMROSESAN ---
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        'https://www.googleapis.com/auth/spreadsheets',
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_dict = app.config.get('GCP_CREDS_DICT')
    
    if creds_dict:
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    else:
        print("PERINGATAN: GCP_CREDS_DICT tidak ditemukan. Mencoba fallback dari file credentials.json.")
        try:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"Gagal memuat credentials.json lokal: {e}")
            return None

def get_data_from_sheet(client, file_name, sheet_name):
    try:
        spreadsheet = client.open(file_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        df = pd.DataFrame(worksheet.get_all_records())
        df.replace('', 0, inplace=True)
        numeric_cols = [col for col in df.columns if col not in ['Bulan', 'Minggu', 'Tanggal Awal', 'Tanggal Akhir']]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Tanggal Awal' in df.columns and 'Tanggal Akhir' in df.columns:
            df['start_dt'] = pd.to_datetime(df['Tanggal Awal'], format='%d-%b-%Y', errors='coerce')
            df['end_dt'] = pd.to_datetime(df['Tanggal Akhir'], format='%d-%b-%Y', errors='coerce')
        
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"FATAL ERROR: Spreadsheet '{file_name}' tidak ditemukan.")
        return None
    except gspread.exceptions.WorksheetNotFound:
        print(f"FATAL ERROR: Sheet '{sheet_name}' tidak ditemukan di spreadsheet '{file_name}'.")
        return None
    except Exception as e:
        print(f"Error pada get_data_from_sheet (file: {file_name}, sheet: {sheet_name}): {e}")
        return None

def log_activity(action, user=None):
    if user is None:
        user = current_user
    if user.is_authenticated:
        log = ActivityLog(user_id=user.id, username=user.username, action=action)
        db.session.add(log)
        db.session.commit()
        
def sort_worksheet_by_date(worksheet):
    """
    Membaca semua data dari worksheet, mengurutkannya berdasarkan Tanggal Awal,
    lalu menulis kembali data yang sudah terurut ke sheet.
    """
    try:
        print(f"Mulai proses pengurutan untuk sheet: {worksheet.title}")
        all_values = worksheet.get_all_values()
        
        # Jika data kurang dari 2 baris (hanya header), tidak perlu diurutkan
        if len(all_values) < 2:
            print("Pengurutan dibatalkan: tidak ada data untuk diurutkan.")
            return

        header = all_values[0]
        data = all_values[1:]

        # Pastikan kolom 'Tanggal Awal' ada
        if 'Tanggal Awal' not in header:
            print("Pengurutan dibatalkan: Kolom 'Tanggal Awal' tidak ditemukan.")
            return

        # Ubah ke DataFrame untuk kemudahan sorting
        df = pd.DataFrame(data, columns=header)
        
        # Konversi kolom tanggal dan urutkan
        # Membuat kolom baru untuk pengurutan agar tidak mengubah format asli
        df['sort_date'] = pd.to_datetime(df['Tanggal Awal'], format='%d-%b-%Y', errors='coerce')
        df_sorted = df.sort_values(by='sort_date', ascending=True).drop(columns=['sort_date'])
        
        # Hapus data lama dari sheet (mulai dari baris kedua)
        worksheet.delete_rows(2, len(all_values))

        # Tulis kembali data yang sudah terurut
        # Mengubah kembali NaN menjadi string kosong untuk menghindari error
        df_sorted = df_sorted.replace(np.nan, '', regex=True)
        sorted_list = df_sorted.values.tolist()
        worksheet.append_rows(sorted_list, value_input_option='USER_ENTERED')
        print(f"Sheet {worksheet.title} berhasil diurutkan.")

    except Exception as e:
        print(f"ERROR saat mengurutkan sheet {worksheet.title}: {e}")

def process_sp2d_analysis(data_row, period_str):
    table_rows, chart_labels, chart_totals, chart_lt1, chart_pct = [], [], [], [], []
    time_slots = ['08:00-08:59', '09:00-09:59', '10:00-10:59', '11:00-11:59']
    data_dict = data_row if isinstance(data_row, dict) else data_row.to_dict()
    for slot in time_slots:
        total = data_dict.get(slot, 0)
        lt1_key = next((key for key in data_dict if slot in key and "< 1" in key), None)
        lt1 = data_dict.get(lt1_key, 0)
        percentage = (lt1 / total * 100) if total > 0 else 0
        table_rows.append({"jam_upload": slot, "total": int(total), "kurang_1_jam": int(lt1), "persen": f"{percentage:.2f}%"})
        chart_labels.append(slot.split('-')[0])
        chart_totals.append(int(total))
        chart_lt1.append(int(lt1))
        chart_pct.append(round(percentage, 2))
    return {"period": period_str, "table_rows": table_rows, "chart_data": {"labels": chart_labels, "totals": chart_totals, "less_than_1_hour": chart_lt1, "percentage": chart_pct}}

def process_adk_analysis(data_row, period_str):
    data_dict = data_row if isinstance(data_row, dict) else data_row.to_dict()
    kpi_data = { "tepat_waktu": int(data_dict.get("Tepat Waktu", 0)), "terlambat": int(data_dict.get("Terlambat", 0)) }
    return {"period": period_str, "kpi": kpi_data}

def process_pmrt_analysis(data_row, period_str):
    data_dict = data_row if isinstance(data_row, dict) else data_row.to_dict()
    kpi_data = { "formal": int(data_dict.get("Penolakan Formal", 0)), "substantif": int(data_dict.get("Penolakan Substantif", 0)), "total": int(data_dict.get("Total", 0)) }
    return {"period": period_str, "kpi": kpi_data}

def process_karwas_analysis(data_row, period_str):
    data_dict = data_row if isinstance(data_row, dict) else data_row.to_dict()
    kpi_data = { "up": { "jatuh_tempo_1_2": int(data_dict.get("Jatuh tempo 1-2 hari", 0)), "jatuh_tempo_gt_2": int(data_dict.get("Jatuh tempo >2 hari", 0)), "total": int(data_dict.get("Total UP", 0)) }, "tup": { "terlambat_1_2": int(data_dict.get("Terlambat 1-2 hari", 0)), "terlambat_gt_2": int(data_dict.get("Terlambat >2 hari", 0)), "total": int(data_dict.get("Total TUP", 0)) } }
    return {"period": period_str, "kpi": kpi_data}

def process_lainnya_analysis(data_row, period_str):
    data_dict = data_row if isinstance(data_row, dict) else data_row.to_dict()
    
    total_retur = int(data_dict.get("Total Retur", 0))
    tepat_waktu_retur = int(data_dict.get("≤8 hari", 0))
    persen_tepat_waktu = (tepat_waktu_retur / total_retur * 100) if total_retur > 0 else 0
    
    kpi_data = {
        "penerimaan": {
            "salah_satker_akun": int(data_dict.get("Monitoring PFK Salah Satker/Akun", 0)),
            "salah_potong": int(data_dict.get("Monitoring PFK Salah Potong", 0)),
            "salah_pecahan": int(data_dict.get("Monitoring PFK Salah Pecahan", 0))
        },
        "suspend": {
            "pengembalian_belanja": int(data_dict.get("Suspend Pengembalian Belanja", 0)),
            "satker_belum_koreksi": int(data_dict.get("Suspend Satker penerimaan yang belum dikoreksi", 0)),
            "akun_belum_koreksi": int(data_dict.get("Suspend akun yang belum dikoreksi", 0))
        },
        "bank": {
            "total_retur": int(data_dict.get("Total Retur", 0)),
            "tepat_waktu_retur": int(data_dict.get("≤8 hari", 0)),
            "belum_diproses": int(data_dict.get("Monitoring retur yang belum diproses", 0)),
            "sp2d_void": int(data_dict.get("SP2D Void(dibatalkan)", 0)),
            "sp2d_backdate": int(data_dict.get("SP2D Backdate", 0))
        },
        "renkas": {
            "deviasi_rpd_harian": int(data_dict.get("Tingkat Deviasi RPD Harian", 0)),
            "dispensasi_spm": int(data_dict.get("Pemberian dispensasi atas SPM tanpa RPD harian", 0))
        },
        "sbsn": { "deviasi_rpd_sbsn": int(data_dict.get("Tingkat Deviasi RPD SBSN", 0)) }
    }
    return {"period": period_str, "kpi": kpi_data}

# --- ROUTING OTENTIKASI ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm() 
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            log_activity(f"User '{user.username}' berhasil login.")
            return redirect(url_for('portal_page'))
        else:
            flash("Username atau password salah.", "danger")
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash("Akun Anda telah berhasil dibuat! Silakan login.", "success-popup")
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Anda telah berhasil logout.", "info")
    return redirect(url_for('login'))

# --- ROUTING ADMIN ---
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    # Ambil 5 log aktivitas terbaru
    latest_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(5).all()
    
    # Ambil data untuk modul populer (kode ini sudah ada)
    module_logs = ActivityLog.query.filter(ActivityLog.action.like('Melihat data:%')).all()
    module_views = [log.action.split(':')[1].strip().split(' untuk')[0] for log in module_logs]
    popular_modules = Counter(module_views).most_common(1) # Cukup ambil 1 teratas

    return render_template(
        'admin/admin_dashboard.html', 
        users=users,
        latest_logs=latest_logs,
        popular_modules=popular_modules,
        kppn_list=KPPN_LIST,
        modul_list=MODUL_LIST
    )

@app.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    page = request.args.get('page', 1, type=int)
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=20)
    return render_template(
        'admin/logs.html',
        logs=logs,
        kppn_list=KPPN_LIST,
        modul_list=MODUL_LIST
    )

@app.route('/admin/stats')
@login_required
@admin_required
def admin_stats():
    total_users = User.query.count()
    module_logs = ActivityLog.query.filter(ActivityLog.action.like('Melihat data:%')).all()
    module_views = [log.action.split(':')[1].strip().split(' untuk')[0] for log in module_logs]
    popular_modules = Counter(module_views).most_common(5)
    login_logs = db.session.query(
        func.date(ActivityLog.timestamp).label('login_date'),
        func.count(ActivityLog.id).label('login_count')
    ).filter(ActivityLog.action.like('%berhasil login%')).group_by('login_date').order_by(func.date(ActivityLog.timestamp).desc()).limit(30).all()
    login_chart_data = {
        "labels": [datetime.strptime(log.login_date, '%Y-%m-%d').strftime('%d %b') for log in reversed(login_logs)],
        "data": [log.login_count for log in reversed(login_logs)]
    }
    return render_template(
        'admin/stats.html', 
        total_users=total_users, 
        popular_modules=popular_modules,
        login_chart_data=json.dumps(login_chart_data),
        kppn_list=KPPN_LIST,
        modul_list=MODUL_LIST
    )

@app.route('/admin/toggle_role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Anda tidak dapat mengubah peran Anda sendiri.", "warning")
        return redirect(url_for('admin_dashboard'))
    old_role = user.role
    user.role = 'admin' if user.role == 'user' else 'user'
    db.session.commit()
    log_activity(f"Mengubah peran user '{user.username}' dari '{old_role}' menjadi '{user.role}'.")
    flash(f"Peran untuk {user.username} berhasil diubah menjadi {user.role}.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Anda tidak dapat menghapus akun Anda sendiri.", "danger")
        return redirect(url_for('admin_dashboard'))
    username_deleted = user.username
    ActivityLog.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    log_activity(f"Menghapus user '{username_deleted}'.")
    flash(f"User {username_deleted} berhasil dihapus.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    log_activity(f"Mereset password untuk user '{user.username}'.")
    flash(f"Password untuk {user.username} telah direset menjadi: {new_password}", "info")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/manage_data/<kppn_id>/<modul_id>')
@login_required
@admin_required
def manage_data(kppn_id, modul_id):
    if kppn_id not in KPPN_LIST or modul_id not in MODUL_LIST:
        flash("KPPN atau Modul tidak valid.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        client = get_gspread_client()
        file_name = FILE_MAPPING.get(modul_id)
        sheet_name = kppn_id.capitalize()
        
        spreadsheet = client.open(file_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        all_values = worksheet.get_all_values()
        headers = all_values[0] if all_values else []
        records_data = all_values[1:] if len(all_values) > 1 else []

        records = []
        for i, row in enumerate(records_data, start=2):
            record_dict = {headers[j]: cell for j, cell in enumerate(row)}
            record_dict['row_index'] = i
            records.append(record_dict)

        # ==> LOGIKA PENTING UNTUK MEMPROSES DATA SP2D <==
        if modul_id == 'sp2d' and records:
            processed_records = []
            time_slots = ['08:00-08:59', '09:00-09:59', '10:00-10:59', '11:00-11:59']
            for record in records:
                processed_record = record.copy()
                processed_record['sp2d_summary'] = {}
                for slot in time_slots:
                    total_val = record.get(slot, '0')
                    lt1_val = record.get(f"{slot} < 1 Jam", '0')
                    gt1_val = record.get(f"{slot} > 1 Jam", '0')
                    
                    processed_record['sp2d_summary'][slot] = {
                        'total': total_val, 'lt1': lt1_val, 'gt1': gt1_val
                    }
                processed_records.append(processed_record)
            # Ganti records mentah dengan yang sudah diproses
            records = processed_records 
        
        return render_template(
            'admin/manage_data.html',
            records=records,
            headers=headers,
            kppn_name=KPPN_LIST[kppn_id],
            modul_name=MODUL_LIST[modul_id],
            kppn_id=kppn_id,
            modul_id=modul_id,
            kppn_list=KPPN_LIST,
            modul_list=MODUL_LIST
        )
    except Exception as e:
        flash(f"Gagal memuat data dari spreadsheet: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_row/<kppn_id>/<modul_id>/<int:row_index>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_row(kppn_id, modul_id, row_index):
    client = get_gspread_client()
    file_name = FILE_MAPPING.get(modul_id)
    sheet_name = kppn_id.capitalize()
    
    try:
        spreadsheet = client.open(file_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
    except Exception as e:
        flash(f"Gagal mengakses spreadsheet: {e}", "danger")
        return redirect(url_for('manage_data', kppn_id=kppn_id, modul_id=modul_id))

    if request.method == 'POST':
        # Ambil data dari form sesuai urutan header asli
        values = [request.form.get(header) for header in headers]
        try:
            if row_index == 0:
                worksheet.append_row(values, value_input_option='USER_ENTERED')
                log_activity(f"Menambah data baru di {modul_id}/{kppn_id}.")
                flash("Data berhasil ditambahkan!", "success")
            else:
                # Update baris menggunakan gspread. Worksheet.update menerima range dan list of lists.
                worksheet.update(f'A{row_index}', [values])
                log_activity(f"Mengedit data baris ke-{row_index} di {modul_id}/{kppn_id}.")
                flash("Data berhasil diperbarui!", "success")

            # --- PANGGIL FUNGSI SORTING DI SINI ---
            # Pengurutan hanya dijalankan jika ada kolom tanggal untuk efisiensi
            if 'Tanggal Awal' in headers:
                sort_worksheet_by_date(worksheet)
            
            return redirect(url_for('manage_data', kppn_id=kppn_id, modul_id=modul_id))
        except Exception as e:
            flash(f"Gagal menyimpan data ke spreadsheet: {e}", "danger")

    # Untuk request GET, siapkan data untuk ditampilkan di form
    row_data = {}
    if row_index > 0:
        # Ambil nilai baris dan pasangkan dengan headernya
        row_values = worksheet.row_values(row_index)
        # Pastikan row_values memiliki panjang yang sama dengan headers
        row_data = {headers[i]: (row_values[i] if i < len(row_values) else '') for i in range(len(headers))}

    # ==> LOGIKA BARU UNTUK MENGELOMPOKKAN FORM <==
    form_groups = {
        "periode": ["Bulan", "Minggu", "Tanggal Awal", "Tanggal Akhir"],
        "slots": {
            "08:00-08:59": ["08:00-08:59", "08:00-08:59 < 1 Jam", "08:00-08:59 > 1 Jam"],
            "09:00-09:59": ["09:00-09:59", "09:00-09:59 < 1 Jam", "09:00-09:59 > 1 Jam"],
            "10:00-10:59": ["10:00-10:59", "10:00-10:59 < 1 Jam", "10:00-10:59 > 1 Jam"],
            "11:00-11:59": ["11:00-11:59", "11:00-11:59 < 1 Jam", "11:00-11:59 > 1 Jam"]
        },
        "agregat": ["Total", "< 1 Jam", "> 1 Jam"]
    }
    # Hanya gunakan pengelompokan jika modulnya sp2d
    use_grouping = modul_id == 'sp2d'

    return render_template(
        'admin/edit_form.html',
        row_data=row_data,
        headers=headers,
        kppn_id=kppn_id,
        modul_id=modul_id,
        row_index=row_index,
        modul_name=MODUL_LIST[modul_id],
        kppn_list=KPPN_LIST,
        modul_list=MODUL_LIST,
        kppn_name=KPPN_LIST.get(kppn_id), # Menambahkan kppn_name
        form_groups=form_groups if use_grouping else None
    )
    
@app.route('/admin/delete_row/<kppn_id>/<modul_id>/<int:row_index>', methods=['POST'])
@login_required
@admin_required
def delete_row(kppn_id, modul_id, row_index):
    try:
        client = get_gspread_client()
        file_name = FILE_MAPPING.get(modul_id)
        sheet_name = kppn_id.capitalize()
        
        spreadsheet = client.open(file_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        worksheet.delete_rows(row_index)
        log_activity(f"Menghapus data baris ke-{row_index} di {modul_id}/{kppn_id}.")
        flash(f"Data baris ke-{row_index} berhasil dihapus.", "success")
        
    except Exception as e:
        flash(f"Gagal menghapus data dari spreadsheet: {e}", "danger")
        
    return redirect(url_for('manage_data', kppn_id=kppn_id, modul_id=modul_id))

# --- ROUTING UTAMA ---
@app.route('/')
@login_required
def portal_page():
    kppn_id = request.args.get('kppn')
    modul_id = request.args.get('modul')
    view_mode = "beranda"
    if kppn_id and kppn_id in KPPN_LIST:
        view_mode = "dashboard_kppn" 
        if modul_id and modul_id in MODUL_LIST:
            view_mode = "dashboard_modul"
    tahun_list = list(range(2023, 2026))
    bulan_list = list(MONTH_MAP.keys())
    return render_template(
        'portal.html', 
        view_mode=view_mode, kppn_list=KPPN_LIST, modul_list=MODUL_LIST,
        active_kppn=kppn_id, active_modul=modul_id,
        tahun_list=sorted(tahun_list, reverse=True), bulan_list=bulan_list
    )

@app.route('/export/excel/<kppn_id>/<modul_id>')
@login_required
def export_to_excel(kppn_id, modul_id):
    if kppn_id not in KPPN_LIST or modul_id not in MODUL_LIST:
        flash("KPPN atau Modul tidak valid.", "danger")
        return redirect(url_for('portal_page'))

    try:
        # Ambil parameter filter dari URL
        year = request.args.get('tahun', type=int, default=datetime.now().year)
        month_name = request.args.get('bulan', type=str, default=datetime.now().strftime('%B'))
        month = MONTH_MAP.get(month_name)
        if not month:
            flash("Nama bulan tidak valid.", "danger")
            return redirect(request.referrer)

        # Ambil data dari Google Sheet (logika yang sama dengan API)
        client = get_gspread_client()
        file_name = FILE_MAPPING.get(modul_id)
        kppn_name_capitalized = kppn_id.capitalize()

        df_main = get_data_from_sheet(client, file_name, kppn_name_capitalized)
        if df_main is None or 'start_dt' not in df_main.columns:
            flash("Gagal memuat data atau format spreadsheet salah.", "danger")
            return redirect(request.referrer)

        # Filter data berdasarkan periode
        _, num_days = monthrange(year, month)
        month_start = pd.Timestamp(year, month, 1)
        month_end = pd.Timestamp(year, month, num_days)
        df_filtered = df_main.dropna(subset=['start_dt', 'end_dt'])
        df_filtered = df_filtered[(df_filtered['start_dt'] <= month_end) & (df_filtered['end_dt'] >= month_start)].sort_values(by='start_dt')

        if df_filtered.empty:
            flash(f"Tidak ada data untuk diekspor pada periode {month_name} {year}.", "warning")
            return redirect(request.referrer or url_for('portal_page'))

        # Buang kolom tanggal internal sebelum ekspor
        df_to_export = df_filtered.drop(columns=['start_dt', 'end_dt'], errors='ignore')

        # Buat file Excel di memori
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Data {modul_id.upper()}"

        # Tulis DataFrame ke worksheet
        for r in dataframe_to_rows(df_to_export, index=False, header=True):
            ws.append(r)

        # Atur lebar kolom agar otomatis
        for column_cells in ws.columns:
            length = max(len(str(cell.value)) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = length + 2

        # Simpan workbook ke stream di memori
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Buat nama file dinamis
        excel_filename = f"Laporan_{modul_id.upper()}_{KPPN_LIST[kppn_id]}_{month_name}_{year}.xlsx"

        # Kirim response file ke pengguna
        return Response(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment;filename={excel_filename}'}
        )

    except Exception as e:
        print(f"Error saat ekspor ke Excel: {e}")
        flash(f"Terjadi kesalahan saat membuat file Excel: {e}", "danger")
        return redirect(request.referrer or url_for('portal_page'))

# --- API ENDPOINT ---
@app.route('/api/data/<kppn_id>/<modul_id>')
@login_required
def get_modul_data(kppn_id, modul_id):
    if kppn_id not in KPPN_LIST or modul_id not in MODUL_LIST:
        return jsonify({"error": "KPPN atau Modul tidak valid"}), 404
    
    log_activity(f"Melihat data: {MODUL_LIST.get(modul_id, 'N/A')} untuk {KPPN_LIST.get(kppn_id, 'N/A')}.")
    
    try:
        year = request.args.get('tahun', type=int)
        month_name = request.args.get('bulan', type=str)
        if not all([year, month_name]): return jsonify({"error": "Parameter tahun dan bulan dibutuhkan"}), 400
        month = MONTH_MAP.get(month_name)
        if not month: return jsonify({"error": "Nama bulan tidak valid"}), 400

        kppn_name_capitalized = kppn_id.capitalize()
        client = get_gspread_client()
        file_name = FILE_MAPPING.get(modul_id)
        if not file_name: return jsonify({"error": f"File untuk modul {modul_id} tidak terdaftar"}), 404

        df_main = get_data_from_sheet(client, file_name, kppn_name_capitalized)
        if df_main is None: return jsonify({"error": f"Data utama tidak dapat dimuat. Periksa nama Spreadsheet ('{file_name}') dan nama Sheet ('{kppn_name_capitalized}') serta hak akses."}), 404

        if 'start_dt' not in df_main.columns or 'end_dt' not in df_main.columns:
            return jsonify({"error": "Spreadsheet harus memiliki kolom 'Tanggal Awal' dan 'Tanggal Akhir' dengan format DD-Mon-YYYY."}), 404

        df_filtered = df_main.dropna(subset=['start_dt', 'end_dt'])
        _, num_days = monthrange(year, month)
        month_start = pd.Timestamp(year, month, 1)
        month_end = pd.Timestamp(year, month, num_days)
        df_filtered = df_filtered[(df_filtered['start_dt'] <= month_end) & (df_filtered['end_dt'] >= month_start)].sort_values(by='start_dt')
        
        if df_filtered.empty: return jsonify({"error": f"Tidak ada data untuk periode {month_name} {year}."}), 404
        
        # --- Logika pemrosesan berdasarkan modul ---
        
        if modul_id == 'sp2d':
            weekly_reports = [process_sp2d_analysis(row, f"{row['start_dt'].strftime('%d %b %Y')} s.d. {row['end_dt'].strftime('%d %b %Y')}") for _, row in df_filtered.iterrows()]
            numeric_cols = df_filtered.select_dtypes(include=np.number).columns
            monthly_aggregated_data = df_filtered[numeric_cols].sum().to_dict()
            monthly_summary = process_sp2d_analysis(monthly_aggregated_data, f"Akumulasi {month_name} {year}")
            return jsonify({"weekly_reports": weekly_reports, "monthly_summary": monthly_summary})

        elif modul_id == 'adk':
            df_chart = get_data_from_sheet(client, file_name, f"Kontrak {kppn_name_capitalized}")
            chart_data = df_chart.to_dict('list') if df_chart is not None else None
            weekly_reports = [process_adk_analysis(row, f"{row['start_dt'].strftime('%d %b %Y')} s.d. {row['end_dt'].strftime('%d %b %Y')}") for _, row in df_filtered.iterrows()]
            numeric_cols = df_filtered.select_dtypes(include=np.number).columns
            monthly_aggregated_data = df_filtered[numeric_cols].sum().to_dict()
            monthly_summary = process_adk_analysis(monthly_aggregated_data, f"Akumulasi {month_name} {year}")
            return jsonify({"weekly_reports": weekly_reports, "monthly_summary": monthly_summary, "chart_data": chart_data})

        elif modul_id == 'pmrt':
            df_chart = get_data_from_sheet(client, file_name, f"G.{kppn_name_capitalized}")
            chart_data = df_chart.to_dict('list') if df_chart is not None else None
            weekly_reports = [process_pmrt_analysis(row, f"{row['start_dt'].strftime('%d %b %Y')} s.d. {row['end_dt'].strftime('%d %b %Y')}") for _, row in df_filtered.iterrows()]
            numeric_cols = df_filtered.select_dtypes(include=np.number).columns
            monthly_aggregated_data = df_filtered[numeric_cols].sum().to_dict()
            monthly_summary = process_pmrt_analysis(monthly_aggregated_data, f"Akumulasi {month_name} {year}")
            return jsonify({"weekly_reports": weekly_reports, "monthly_summary": monthly_summary, "chart_data": chart_data})

        elif modul_id == 'karwas':
            chart_data = None
            weekly_reports = [process_karwas_analysis(row, f"{row['start_dt'].strftime('%d %b %Y')} s.d. {row['end_dt'].strftime('%d %b %Y')}") for _, row in df_filtered.iterrows()]
            numeric_cols = df_filtered.select_dtypes(include=np.number).columns
            monthly_aggregated_data = df_filtered[numeric_cols].sum().to_dict()
            monthly_summary = process_karwas_analysis(monthly_aggregated_data, f"Akumulasi {month_name} {year}")
            return jsonify({"weekly_reports": weekly_reports, "monthly_summary": monthly_summary, "chart_data": chart_data})

        elif modul_id == 'lainnya':
            df_chart = get_data_from_sheet(client, file_name, f"Retur {kppn_name_capitalized}")
            chart_data = None
            if df_chart is not None:
                # Memastikan semua kolom yang dibutuhkan ada dan diubah ke numerik
                required_cols = ['Total Retur', '≤8 hari']
                for col in required_cols:
                    if col in df_chart.columns:
                        df_chart[col] = pd.to_numeric(df_chart[col], errors='coerce').fillna(0)
                    else:
                        # Jika kolom tidak ada, buat kolom kosong agar tidak error
                        df_chart[col] = 0
                
                # Mengolah data untuk chart baru dengan nama kolom yang benar
                df_chart['Retur Terlambat (>8 Hari)'] = df_chart['Total Retur'] - df_chart['≤8 hari']
                df_chart['% Tepat Waktu'] = np.where(df_chart['Total Retur'] > 0, (df_chart['≤8 hari'] / df_chart['Total Retur']) * 100, 0)
                
                chart_data = {
                    "labels": df_chart['Bulan'].tolist(),
                    "tepat_waktu": df_chart['≤8 hari'].tolist(),
                    "terlambat": df_chart['Retur Terlambat (>8 Hari)'].tolist(),
                    "persentase": df_chart['% Tepat Waktu'].tolist()
                }

            weekly_reports = [process_lainnya_analysis(row, f"{row['start_dt'].strftime('%d %b %Y')} s.d. {row['end_dt'].strftime('%d %b %Y')}") for _, row in df_filtered.iterrows()]
            numeric_cols = df_filtered.select_dtypes(include=np.number).columns
            monthly_aggregated_data = df_filtered[numeric_cols].sum().to_dict()
            monthly_summary = process_lainnya_analysis(monthly_aggregated_data, f"Akumulasi {month_name} {year}")
            return jsonify({"weekly_reports": weekly_reports, "monthly_summary": monthly_summary, "chart_data": chart_data})

        return jsonify({"error": f"Logika untuk modul '{modul_id}' belum diimplementasikan."}), 501

    except Exception as e:
        print(f"!!! SERVER ERROR ({kppn_id}/{modul_id}): {e} !!!")
        return jsonify({"error": f"Terjadi kesalahan di server: {e}"}), 500

