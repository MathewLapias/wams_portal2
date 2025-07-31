# functions/app.py
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, Response
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

# Inisialisasi Aplikasi Flask dengan path yang benar
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

# --- PASTE SEMUA KODE ANDA YANG LAIN (MODEL, FORM, ROUTE) DI SINI ---
# Contoh:
@app.template_filter('to_wita')
def to_wita_filter(utc_dt):
    if utc_dt is None: return ""
    wita_tz = pytz.timezone('Asia/Makassar')
    wita_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(wita_tz)
    return wita_dt.strftime('%Y-%m-%d %H:%M:%S')

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)])
    submit = SubmitField("Buat Akun")
    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError("Username sudah terdaftar.")

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)])
    submit = SubmitField("Login")

# (lanjutkan paste sisa kode Anda seperti KPPN_LIST, MODUL_LIST, semua fungsi helper, dan semua @app.route)

# --- FUNGSI get_gspread_client YANG SUDAH DIPERBARUI ---
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

# --- RUTE SEMENTARA UNTUK INISIALISASI DATABASE ---
@app.route('/init-db-first-time')
def init_db():
    with app.app_context():
        db.create_all()
    return "Database tables created successfully!"