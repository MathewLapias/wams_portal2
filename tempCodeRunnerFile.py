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
from oauth2client.service_account import ServiceAccountCredentials
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

app = Flask(__name__)

@app.template_filter('to_wita')
def to_wita_filter(utc_dt):
    """Mengubah datetime UTC ke WITA dan memformatnya."""
    if utc_dt is None:
        return ""
    wita_tz = pytz.timezone('Asia/Makassar')
    wita_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(wita_tz)
    return wita_dt.strftime('%Y-%m-%d %H:%M:%S')

# --- KONFIGURASI DATABASE, KUNCI RAHASIA, & LOGIN ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SECRET_KEY'] = 'ganti-dengan-kunci-rahasia-anda'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Anda harus login untuk mengakses halaman ini."
login_manager.login_message_category = "warning"

with app.app_context():
    db.create_all()

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
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

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
        flash("Akun berhasil dibuat! Silakan login.", "success")
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
    return render_template(
        'admin/admin_dashboard.html', 
        users=users,
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
            chart_data = df_chart.to_dict('list') if df_chart is not None else None
            weekly_reports = [process_lainnya_analysis(row, f"{row['start_dt'].strftime('%d %b %Y')} s.d. {row['end_dt'].strftime('%d %b %Y')}") for _, row in df_filtered.iterrows()]
            numeric_cols = df_filtered.select_dtypes(include=np.number).columns
            monthly_aggregated_data = df_filtered[numeric_cols].sum().to_dict()
            monthly_summary = process_lainnya_analysis(monthly_aggregated_data, f"Akumulasi {month_name} {year}")
            return jsonify({"weekly_reports": weekly_reports, "monthly_summary": monthly_summary, "chart_data": chart_data})

        return jsonify({"error": f"Logika untuk modul '{modul_id}' belum diimplementasikan."}), 501

    except Exception as e:
        print(f"!!! SERVER ERROR ({kppn_id}/{modul_id}): {e} !!!")
        return jsonify({"error": f"Terjadi kesalahan di server: {e}"}), 500

@app.cli.command("create-admin")
def create_admin_command():
    """Membuat user admin awal."""
    db.create_all()
    if User.query.filter_by(username='admin').first():
        print("User 'admin' sudah ada.")
        return
    hashed_password = bcrypt.generate_password_hash('adminpassword').decode('utf-8')
    admin_user = User(username='admin', password=hashed_password, role='admin')
    db.session.add(admin_user)
    db.session.commit()
    print("User 'admin' berhasil dibuat dengan password 'adminpassword'.")
    print("Segera ganti password ini setelah login!")

if __name__ == '__main__':
    app.run(debug=True, port=5001)