#!/usr/bin/env python3
"""
School Management System - Backend Server
Requires: Python 3.6+ (no external dependencies)
"""

import http.server
import json
import sqlite3
import hashlib
import hmac
import uuid
import os
import base64
import re
import mimetypes
import threading
import csv
import io
import shutil
import smtplib
import tempfile
import logging
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, parse_qs, quote
import urllib.request
import urllib.error
from datetime import datetime, timedelta

try:
    from weasyprint import HTML as WeasyHTML
except Exception:
    WeasyHTML = None


def load_dotenv(env_path=None, override=False):
    """Load simple KEY=VALUE pairs from a .env file without external deps."""
    env_path = env_path or os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return False

    def _strip_inline_comment(value):
        if not value or value[0] in ('"', "'"):
            return value
        if " #" in value:
            return value.split(" #", 1)[0].rstrip()
        return value

    with open(env_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_inline_comment(value.strip())
            if value[:1] == value[-1:] and value[:1] in ('"', "'"):
                value = value[1:-1]
            if not override and key in os.environ:
                continue
            os.environ[key] = value
    return True


load_dotenv()


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_text(name, default=""):
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def is_production_env(value):
    return (value or "").strip().lower() in ("production", "prod")

# Railway (and most cloud platforms) inject a PORT environment variable.
# Fall back to 8080 for local development.
PORT = int(env_text("PORT", "8080"))
_KNOWN_ENVS = {"production", "prod", "development", "dev", "test", "staging"}
_raw_env = env_text("ENVIRONMENT", "").lower() or env_text("ENV", "").lower()
ENVIRONMENT = _raw_env if _raw_env in _KNOWN_ENVS else "development"
LOG_LEVEL = env_text("LOG_LEVEL", "INFO").upper() or "INFO"

# CORS
ALLOWED_ORIGIN = env_text("ALLOWED_ORIGIN", "*")

# Email (SMTP) config
SMTP_HOST = env_text("SMTP_HOST", "")
SMTP_PORT = int(env_text("SMTP_PORT", "587"))
SMTP_USER = env_text("SMTP_USER", "")
SMTP_PASS = env_text("SMTP_PASS", "")
SMTP_FROM = env_text("SMTP_FROM", "")
APP_URL_RAW = env_text("APP_URL", "")
APP_URL = APP_URL_RAW.rstrip("/")
if not APP_URL and not is_production_env(ENVIRONMENT):
    APP_URL = f"http://localhost:{PORT}"

# Payment / messaging integrations
PAYSTACK_SECRET_KEY = env_text("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = env_text("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_CALLBACK_URL = env_text("PAYSTACK_CALLBACK_URL", "")

INITIAL_ADMIN_NAME = env_text("INITIAL_ADMIN_NAME", "School Admin")
INITIAL_ADMIN_EMAIL = env_text("INITIAL_ADMIN_EMAIL", "").lower()
INITIAL_ADMIN_PASSWORD = env_text("INITIAL_ADMIN_PASSWORD", "")
ALLOW_DEFAULT_ADMIN = env_flag("ALLOW_DEFAULT_ADMIN", default=False)
ALLOW_DESTRUCTIVE_MIGRATIONS = env_flag("ALLOW_DESTRUCTIVE_MIGRATIONS", default=not is_production_env(ENVIRONMENT))

WHATSAPP_PROVIDER = env_text("WHATSAPP_PROVIDER", "termii").lower()
TERMII_API_KEY = env_text("TERMII_API_KEY", "")
TERMII_SENDER = env_text("TERMII_SENDER", "GISL Schools")
TERMII_SMS_ENDPOINT = env_text("TERMII_SMS_ENDPOINT", "https://api.ng.termii.com/api/sms/send")
TERMII_WHATSAPP_ENDPOINT = env_text("TERMII_WHATSAPP_ENDPOINT", "")
META_WHATSAPP_ACCESS_TOKEN = env_text("META_WHATSAPP_ACCESS_TOKEN", "")
META_WHATSAPP_PHONE_NUMBER_ID = env_text("META_WHATSAPP_PHONE_NUMBER_ID", "")

# Login rate limiting
_login_attempts = {}
_login_lock = threading.Lock()

# On Railway, mount a persistent volume at /data and set DATA_DIR=/data
# so the database and uploads survive redeploys. Falls back to the app
# folder for local use.
_DATA_DIR = env_text("DATA_DIR", os.path.dirname(__file__))
DB_PATH    = os.path.join(_DATA_DIR, "school.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR = os.path.join(_DATA_DIR, "uploads")
BACKUP_DIR = os.path.join(_DATA_DIR, "backups")
LOG_PATH = os.path.join(_DATA_DIR, "app.log")
LEGACY_DEFAULT_ADMIN_PASSWORD = "admin123"

LOGGER = logging.getLogger("gisl_schools")
_BOOTSTRAP_STATUS = {"mode": "unknown", "message": ""}


def configure_logging():
    os.makedirs(_DATA_DIR, exist_ok=True)
    LOGGER.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    LOGGER.propagate = False
    if LOGGER.handlers:
        return LOGGER

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)

    try:
        file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
    except Exception:
        pass

    return LOGGER


def ensure_runtime_directories():
    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_database_backup(label="manual"):
    if not os.path.exists(DB_PATH):
        return None
    ensure_runtime_directories()
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_") or "backup"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"school_{safe_label}_{stamp}.db")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup_path


def list_database_backups(limit=20):
    ensure_runtime_directories()
    items = []
    for name in os.listdir(BACKUP_DIR):
        if not name.endswith(".db"):
            continue
        path = os.path.join(BACKUP_DIR, name)
        try:
            stat = os.stat(path)
            items.append({
                "filename": name,
                "path": path,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except Exception:
            continue
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return items[:limit]


def _dir_is_writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True, "Writable"
    except Exception as exc:
        return False, str(exc)


def _build_check(key, label, status, message, fatal=False):
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
        "fatal": fatal,
    }


def get_system_checks():
    checks = []
    prod = is_production_env(ENVIRONMENT)

    data_ok, data_msg = _dir_is_writable(_DATA_DIR)
    checks.append(_build_check(
        "data_dir",
        "Persistent data directory",
        "ok" if data_ok else "error",
        f"DATA_DIR={_DATA_DIR} ({data_msg})",
        fatal=not data_ok,
    ))

    backup_ok, backup_msg = _dir_is_writable(BACKUP_DIR)
    checks.append(_build_check(
        "backup_dir",
        "Backups directory",
        "ok" if backup_ok else "error",
        f"BACKUP_DIR={BACKUP_DIR} ({backup_msg})",
        fatal=not backup_ok,
    ))

    origin_locked = ALLOWED_ORIGIN not in ("", "*")
    checks.append(_build_check(
        "cors_origin",
        "CORS origin policy",
        "ok" if origin_locked or not prod else "error",
        f"ALLOWED_ORIGIN={ALLOWED_ORIGIN or '(empty)'}" if origin_locked or prod else "ALLOWED_ORIGIN=* allowed for local development",
        fatal=prod and not origin_locked,
    ))

    app_url_ok = bool(APP_URL)
    checks.append(_build_check(
        "app_url",
        "Public application URL",
        "ok" if app_url_ok else ("error" if prod else "warning"),
        APP_URL if APP_URL_RAW else (APP_URL or "APP_URL is not configured"),
        fatal=prod and not app_url_ok,
    ))

    if os.environ.get("RAILWAY_ENVIRONMENT"):
        railway_data_ok = os.path.abspath(_DATA_DIR) == "/data"
        checks.append(_build_check(
            "railway_volume",
            "Railway persistent volume",
            "ok" if railway_data_ok else "error",
            "DATA_DIR is mounted to /data" if railway_data_ok else f"DATA_DIR should be /data on Railway, got {_DATA_DIR}",
            fatal=not railway_data_ok,
        ))

    smtp_ready = all([SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM])
    smtp_partially_set = any([SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM])
    checks.append(_build_check(
        "smtp",
        "SMTP notifications",
        "ok" if smtp_ready else ("warning" if smtp_partially_set or prod else "ok"),
        "SMTP is configured" if smtp_ready else ("SMTP is disabled or incomplete" if smtp_partially_set or prod else "SMTP is disabled for local development"),
    ))

    paystack_ready = all([PAYSTACK_PUBLIC_KEY, PAYSTACK_SECRET_KEY, PAYSTACK_CALLBACK_URL])
    paystack_partial = any([PAYSTACK_PUBLIC_KEY, PAYSTACK_SECRET_KEY, PAYSTACK_CALLBACK_URL])
    checks.append(_build_check(
        "paystack",
        "Paystack payments",
        "ok" if paystack_ready else ("warning" if paystack_partial or prod else "ok"),
        "Paystack is configured" if paystack_ready else ("Paystack is disabled or incomplete" if paystack_partial or prod else "Paystack is disabled for local development"),
    ))

    whatsapp_ready = bool(TERMII_API_KEY or (META_WHATSAPP_ACCESS_TOKEN and META_WHATSAPP_PHONE_NUMBER_ID))
    checks.append(_build_check(
        "messaging",
        "SMS / WhatsApp messaging",
        "ok" if whatsapp_ready or not prod else "warning",
        "Messaging provider is configured" if whatsapp_ready else ("No messaging provider is fully configured" if prod else "Messaging is disabled for local development"),
    ))

    checks.append(_build_check(
        "pdf_generation",
        "PDF generation",
        "ok" if WeasyHTML or not prod else "warning",
        "WeasyPrint is available" if WeasyHTML else ("WeasyPrint is missing or missing system dependencies" if prod else "PDF generation is disabled in local development until WeasyPrint is installed"),
    ))

    admin_count = 0
    try:
        conn = get_db()
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
        conn.close()
    except Exception as exc:
        checks.append(_build_check("db_admin_lookup", "Admin account lookup", "error", str(exc), fatal=True))

    checks.append(_build_check(
        "admin_account",
        "Admin account bootstrap",
        "ok" if admin_count else "error",
        f"{admin_count} active admin account(s) found" if admin_count else "No active admin account exists",
        fatal=admin_count == 0,
    ))

    if prod and ALLOW_DEFAULT_ADMIN:
        checks.append(_build_check(
            "default_admin",
            "Default admin login",
            "warning",
            "ALLOW_DEFAULT_ADMIN is enabled in production. Disable it after first setup.",
        ))

    summary = {
        "ok": sum(1 for c in checks if c["status"] == "ok"),
        "warning": sum(1 for c in checks if c["status"] == "warning"),
        "error": sum(1 for c in checks if c["status"] == "error"),
    }

    return {
        "environment": ENVIRONMENT,
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "checks": checks,
    }


def enforce_production_readiness():
    report = get_system_checks()
    fatal_errors = [c for c in report["checks"] if c["status"] == "error" and c.get("fatal")]
    if is_production_env(ENVIRONMENT) and fatal_errors:
        joined = "; ".join(f"{c['label']}: {c['message']}" for c in fatal_errors)
        raise RuntimeError(f"Production readiness checks failed: {joined}")
    return report


def _create_admin_account(conn, name, email, password, must_change_password=1):
    admin_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO users (id, name, email, password_hash, role, must_change_password)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (admin_id, name.strip() or "School Admin", email.strip().lower(), hash_password(password), "admin", must_change_password)
    )
    return admin_id


def ensure_admin_bootstrap(conn):
    admin = conn.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 LIMIT 1").fetchone()
    if admin:
        _BOOTSTRAP_STATUS["mode"] = "existing_admin"
        _BOOTSTRAP_STATUS["message"] = "Using existing admin account."
        return

    if INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD:
        _create_admin_account(conn, INITIAL_ADMIN_NAME, INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_PASSWORD, 1)
        _BOOTSTRAP_STATUS["mode"] = "configured_admin"
        _BOOTSTRAP_STATUS["message"] = f"Initial admin created for {INITIAL_ADMIN_EMAIL}."
        LOGGER.warning("Created initial admin account from environment configuration for %s", INITIAL_ADMIN_EMAIL)
        return

    if not is_production_env(ENVIRONMENT) and ALLOW_DEFAULT_ADMIN:
        _create_admin_account(conn, "School Admin", "admin@school.com", LEGACY_DEFAULT_ADMIN_PASSWORD, 1)
        _BOOTSTRAP_STATUS["mode"] = "default_admin"
        _BOOTSTRAP_STATUS["message"] = "Development-only default admin created."
        LOGGER.warning("Created development default admin account. Change the password immediately.")
        return

    _BOOTSTRAP_STATUS["mode"] = "missing_admin"
    _BOOTSTRAP_STATUS["message"] = (
        "No admin account exists. Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD to bootstrap the first admin."
    )
    LOGGER.warning(_BOOTSTRAP_STATUS["message"])

# ─── DATABASE ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 30000")  # 30 s busy-wait before raising "locked"
    return conn


from contextlib import contextmanager

@contextmanager
def db_conn():
    """Context manager that guarantees the connection is closed even on exception.

    Usage:
        with db_conn() as conn:
            rows = conn.execute("SELECT …").fetchall()
            conn.commit()
    """
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = get_db()
    try:
        c = conn.cursor()

        # Schema compatibility check.
        # Legacy deployments may contain old INTEGER PK tables. In development you may
        # allow destructive repair, but in production this is blocked unless explicitly enabled.
        _old_schema_tables = ["users", "parent_accounts"]
        for tbl in _old_schema_tables:
            cols = {row[1]: row[2] for row in c.execute(f"PRAGMA table_info({tbl})").fetchall()}
            if not cols:
                continue
            # Old schema: INTEGER primary key OR missing expected TEXT columns
            if cols.get("id") == "INTEGER" or (tbl == "parent_accounts" and "email" not in cols):
                if not ALLOW_DESTRUCTIVE_MIGRATIONS:
                    raise RuntimeError(
                        "Legacy schema detected but destructive migrations are disabled. "
                        "Back up the database and migrate manually, or set ALLOW_DESTRUCTIVE_MIGRATIONS=true for a one-time controlled repair."
                    )
                backup_path = create_database_backup("before_destructive_migration")
                LOGGER.warning("Legacy schema detected in %s. Backup created at %s before destructive migration.", tbl, backup_path)
                stale = ["users", "classes", "pupils", "results", "parent_accounts",
                         "teachers", "conduct", "payments", "fees", "audit_log"]
                for t in stale:
                    c.execute(f"DROP TABLE IF EXISTS {t}")
                conn.commit()
                break

        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','teacher')),
            phone TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS classes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER NOT NULL,
            stream TEXT DEFAULT 'A',
            teacher_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS subjects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS terms (
            id TEXT PRIMARY KEY,
            academic_year TEXT NOT NULL,
            term_number INTEGER NOT NULL CHECK(term_number IN (1,2,3)),
            is_current INTEGER DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pupils (
            id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            other_name TEXT,
            admission_number TEXT UNIQUE,
            date_of_birth TEXT,
            gender TEXT CHECK(gender IN ('male','female')),
            class_id TEXT,
            blood_group TEXT,
            religion TEXT,
            photo TEXT,
            parent_name TEXT,
            parent_phone TEXT,
            parent_email TEXT,
            parent_address TEXT,
            parent_relationship TEXT,
            emergency_name TEXT,
            emergency_phone TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active','archived','graduated')),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS results (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            term_id TEXT NOT NULL,
            ca_score REAL DEFAULT 0,
            exam_score REAL DEFAULT 0,
            entered_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, subject_id, term_id)
        );

        CREATE TABLE IF NOT EXISTS conduct_ratings (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            term_id TEXT NOT NULL,
            punctuality TEXT DEFAULT '',
            honesty TEXT DEFAULT '',
            cleanliness TEXT DEFAULT '',
            leadership TEXT DEFAULT '',
            politeness TEXT DEFAULT '',
            attentiveness TEXT DEFAULT '',
            writing TEXT DEFAULT '',
            handwork TEXT DEFAULT '',
            verbal_fluency TEXT DEFAULT '',
            drama TEXT DEFAULT '',
            sports TEXT DEFAULT '',
            teacher_comment TEXT DEFAULT '',
            admin_comment TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, term_id)
        );

        CREATE TABLE IF NOT EXISTS parent_accounts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS parent_acknowledgments (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            term_id TEXT NOT NULL,
            parent_account_id TEXT,
            acknowledged_at TEXT DEFAULT (datetime('now')),
            parent_comment TEXT DEFAULT '',
            UNIQUE(pupil_id, term_id)
        );

        CREATE TABLE IF NOT EXISTS school_notices (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            posted_by TEXT NOT NULL,
            posted_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER DEFAULT 1,
            target TEXT DEFAULT 'all'
        );

        CREATE TABLE IF NOT EXISTS fee_structures (
            id TEXT PRIMARY KEY,
            class_id TEXT,
            academic_year TEXT NOT NULL,
            term_number INTEGER NOT NULL,
            fee_name TEXT NOT NULL,
            new_pupil_amount REAL DEFAULT 0,
            returning_pupil_amount REAL DEFAULT 0,
            is_optional INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS fee_payments (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            term_id TEXT NOT NULL,
            fee_structure_id TEXT NOT NULL,
            amount_paid REAL DEFAULT 0,
            payment_date TEXT,
            payment_reference TEXT,
            notes TEXT,
            recorded_by TEXT,
            is_parent_payment INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, term_id, fee_structure_id)
        );

        CREATE TABLE IF NOT EXISTS skill_assessments (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            term_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            grade TEXT DEFAULT '',
            teacher_comment TEXT DEFAULT '',
            admin_comment TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, term_id, skill_name)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            user_email TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id TEXT PRIMARY KEY,
            recipient_name TEXT,
            recipient_phone TEXT,
            recipient_email TEXT,
            channel TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            provider_response TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS online_payment_transactions (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            term_id TEXT NOT NULL,
            fee_structure_id TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'paystack',
            reference TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'initialized',
            access_code TEXT DEFAULT '',
            authorization_url TEXT DEFAULT '',
            metadata TEXT DEFAULT '',
            paid_at TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id TEXT PRIMARY KEY,
            pupil_id TEXT NOT NULL,
            class_id TEXT NOT NULL,
            term_id TEXT,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('present','absent','late')),
            notes TEXT DEFAULT '',
            marked_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, attendance_date)
        );

        CREATE TABLE IF NOT EXISTS homework_assignments (
            id TEXT PRIMARY KEY,
            class_id TEXT NOT NULL,
            subject_id TEXT,
            term_id TEXT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT,
            created_by TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS homework_completions (
            id TEXT PRIMARY KEY,
            assignment_id TEXT NOT NULL,
            pupil_id TEXT NOT NULL,
            is_done INTEGER DEFAULT 0,
            parent_note TEXT DEFAULT '',
            done_at TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(assignment_id, pupil_id)
        );

        CREATE TABLE IF NOT EXISTS school_events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            event_date TEXT NOT NULL,
            end_date TEXT DEFAULT '',
            event_type TEXT DEFAULT 'general',
            target TEXT DEFAULT 'all',
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS class_timetables (
            id TEXT PRIMARY KEY,
            class_id TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            period_name TEXT DEFAULT '',
            subject_id TEXT,
            start_time TEXT DEFAULT '',
            end_time TEXT DEFAULT '',
            teacher_name TEXT DEFAULT '',
            location TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payroll_entries (
            id TEXT PRIMARY KEY,
            staff_id TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            basic_salary REAL DEFAULT 0,
            allowances REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            net_pay REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(staff_id, month, year)
        );
        """)

        # Migrations
        # If a previous reworked schema created users.full_name instead of users.name, rename it
        try:
            cols = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
            if 'full_name' in cols and 'name' not in cols:
                c.execute("ALTER TABLE users RENAME COLUMN full_name TO name")
                conn.commit()
        except: pass

        try:
            c.execute("ALTER TABLE classes ADD COLUMN class_type TEXT DEFAULT 'primary'")
            conn.commit()
        except: pass

        try:
            c.execute("ALTER TABLE sessions ADD COLUMN user_type TEXT DEFAULT 'staff'")
            conn.commit()
        except: pass

        try:
            c.execute("ALTER TABLE fee_payments ADD COLUMN is_parent_payment INTEGER DEFAULT 0")
            conn.commit()
        except: pass

        try:
            c.execute("ALTER TABLE parent_acknowledgments ADD COLUMN parent_account_id TEXT")
            conn.commit()
        except: pass

        try:
            c.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
            conn.commit()
        except: pass

        for migration in (
            "ALTER TABLE pupils ADD COLUMN allergies TEXT DEFAULT ''",
            "ALTER TABLE pupils ADD COLUMN medical_conditions TEXT DEFAULT ''",
            "ALTER TABLE pupils ADD COLUMN doctor_name TEXT DEFAULT ''",
            "ALTER TABLE pupils ADD COLUMN doctor_phone TEXT DEFAULT ''",
        ):
            try:
                c.execute(migration)
                conn.commit()
            except:
                pass

        try:
            c.execute("ALTER TABLE parent_accounts ADD COLUMN must_change_password INTEGER DEFAULT 0")
            conn.commit()
        except: pass

        # Flag any existing admin still using the legacy default password as needing a change
        try:
            _legacy_default = hashlib.sha256(LEGACY_DEFAULT_ADMIN_PASSWORD.encode()).hexdigest()
            c.execute("""UPDATE users SET must_change_password=1
                         WHERE role='admin' AND password_hash=?""", (_legacy_default,))
            conn.commit()
        except: pass

        ensure_admin_bootstrap(conn)

        # Seed default classes
        existing_classes = c.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        if existing_classes == 0:
            lower_classes = [
                ("Playgroup", 0, "lower"),
                ("Kindergarten", 1, "lower"),
                ("Nursery 1", 2, "lower"),
                ("Nursery 2", 3, "lower"),
            ]
            for name, level, ctype in lower_classes:
                cid = str(uuid.uuid4())
                c.execute("INSERT INTO classes (id, name, level, stream, class_type) VALUES (?, ?, ?, ?, ?)",
                          (cid, name, level, "A", ctype))
            for level in range(1, 7):
                cid = str(uuid.uuid4())
                c.execute("INSERT INTO classes (id, name, level, stream, class_type) VALUES (?, ?, ?, ?, ?)",
                          (cid, f"Primary {level}", level, "A", "primary"))

        # Seed default subjects
        existing_subjects = c.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        if existing_subjects == 0:
            subjects = [
                "English Language", "Mathematics", "Basic Science",
                "Social Studies", "Civic Education", "Christian Religious Studies",
                "Nigerian Language", "Agricultural Science", "Computer Studies",
                "Creative Arts", "Physical & Health Education"
            ]
            for i, name in enumerate(subjects):
                sid = str(uuid.uuid4())
                c.execute("INSERT INTO subjects (id, name, sort_order) VALUES (?, ?, ?)",
                          (sid, name, i))

        # Seed current term
        existing_terms = c.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
        if existing_terms == 0:
            tid = str(uuid.uuid4())
            year = datetime.now().year
            academic_year = f"{year}/{year+1}"
            c.execute("""INSERT INTO terms (id, academic_year, term_number, is_current)
                         VALUES (?, ?, ?, 1)""", (tid, academic_year, 1))

        conn.commit()
        LOGGER.info("Database initialized")
    finally:
        conn.close()

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

def hash_password(password):
    """Hash using PBKDF2-HMAC-SHA256 with a random salt. Returns pbkdf2$<salt_hex>$<hash_hex>."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 260000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"

def check_password(password, stored_hash):
    """Check password against stored hash. Supports legacy SHA-256 (64-char hex) and new PBKDF2."""
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2$"):
        try:
            _, salt_hex, hash_hex = stored_hash.split("$")
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 260000)
            return hmac.compare_digest(dk.hex(), hash_hex)
        except Exception:
            return False
    else:
        # Legacy SHA-256 format (64-char hex)
        legacy = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy, stored_hash)

def get_client_ip(handler):
    forwarded = handler.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return handler.client_address[0]

def check_rate_limit(ip):
    """Returns (allowed: bool, wait_secs: int)."""
    with _login_lock:
        record = _login_attempts.get(ip)
        if not record:
            return True, 0
        if record.get("locked_until"):
            remaining = int(record["locked_until"] - datetime.now().timestamp())
            if remaining > 0:
                return False, remaining
            else:
                del _login_attempts[ip]
        return True, 0

def record_failed_attempt(ip):
    with _login_lock:
        record = _login_attempts.setdefault(ip, {"count": 0})
        record["count"] = record.get("count", 0) + 1
        if record["count"] >= 5:
            record["locked_until"] = datetime.now().timestamp() + 600

def clear_attempts(ip):
    with _login_lock:
        _login_attempts.pop(ip, None)

def cleanup_expired_sessions():
    try:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
        conn.commit()
        conn.close()
    except Exception:
        pass

def write_audit(user, action, target_type=None, target_id=None, details=None, ip=None):
    try:
        conn = get_db()
        uid = user["id"] if user else None
        uemail = user["email"] if user else None
        conn.execute("""INSERT INTO audit_log (id, user_id, user_email, action, target_type, target_id, details, ip_address)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (str(uuid.uuid4()), uid, uemail, action, target_type, target_id, details, ip))
        conn.commit()
        conn.close()
    except Exception:
        pass

def send_email_async(to_addr, subject, html_body):
    if not (SMTP_HOST and SMTP_USER):
        return
    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM or SMTP_USER
            msg["To"] = to_addr
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM or SMTP_USER, to_addr, msg.as_string())
        except Exception as e:
            print(f"Email send error: {e}")
    t = threading.Thread(target=_send, daemon=True)
    t.start()

def add_security_headers(handler):
    handler.send_header("X-Frame-Options", "SAMEORIGIN")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-XSS-Protection", "1; mode=block")
    handler.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
    handler.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)

def create_session(user_id, user_type="staff"):
    token = str(uuid.uuid4())
    expires = (datetime.now() + timedelta(hours=24)).isoformat()
    conn = get_db()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at, user_type) VALUES (?, ?, ?, ?)",
                 (token, user_id, expires, user_type))
    conn.commit()
    conn.close()
    return token

def get_current_user(handler):
    token = get_token_from_request(handler)
    if not token:
        return None
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE token = ? AND expires_at > datetime('now')", (token,)
    ).fetchone()
    if not session:
        conn.close()
        return None
    user_type = session["user_type"] if "user_type" in session.keys() else "staff"
    user_id = session["user_id"]
    if user_type == "parent":
        user = conn.execute("SELECT *, 'parent' as role FROM parent_accounts WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
    else:
        user = conn.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
    conn.close()
    return user

def get_token_from_request(handler):
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None

def get_teacher_class_id(conn, teacher_id):
    cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (teacher_id,)).fetchone()
    return cls["id"] if cls else None

def can_access_class(conn, user, class_id):
    if not class_id:
        return False
    if user["role"] == "admin":
        return True
    if user["role"] == "teacher":
        return get_teacher_class_id(conn, user["id"]) == class_id
    return False

def can_access_pupil(conn, user, pupil_row):
    if not pupil_row:
        return False
    if user["role"] == "admin":
        return True
    if user["role"] == "teacher":
        teacher_class_id = get_teacher_class_id(conn, user["id"])
        return bool(teacher_class_id and pupil_row["class_id"] == teacher_class_id)
    if user["role"] == "parent":
        return (pupil_row["parent_email"] or "").strip().lower() == (user["email"] or "").strip().lower()
    return False

# ─── RESPONSE HELPERS ─────────────────────────────────────────────────────────

def send_json(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    add_security_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)

def send_error(handler, message, status=400):
    if status >= 500:
        LOGGER.error("HTTP %s error: %s", status, message)
    send_json(handler, {"error": message}, status)

def read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except:
        return {}

def json_dumps(data):
    return json.dumps(data, default=str)

def today_iso():
    return datetime.now().date().isoformat()

def get_current_term(conn=None):
    own = False
    if conn is None:
        conn = get_db()
        own = True
    term = conn.execute("SELECT * FROM terms WHERE is_current=1 ORDER BY created_at DESC LIMIT 1").fetchone()
    if not term:
        term = conn.execute("SELECT * FROM terms ORDER BY academic_year DESC, term_number DESC LIMIT 1").fetchone()
    if own:
        conn.close()
    return term

def normalize_phone(phone):
    phone = (phone or "").strip()
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+"):
        return digits
    only = re.sub(r"\D", "", digits)
    if only.startswith("234"):
        return "+" + only
    if only.startswith("0") and len(only) >= 11:
        return "+234" + only[1:]
    if len(only) >= 10:
        return "+" + only
    return phone

def post_json(url, payload, headers=None):
    headers = headers or {}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as res:
        raw = res.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def get_json(url, headers=None):
    headers = headers or {}
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as res:
        raw = res.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def log_notification(recipient_name, recipient_phone, recipient_email, channel, event_type, message, status, provider_response=""):
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO notification_log
               (id, recipient_name, recipient_phone, recipient_email, channel, event_type, message, status, provider_response)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), recipient_name or "", recipient_phone or "", recipient_email or "",
             channel, event_type, message, status, provider_response[:4000])
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def send_sms(phone, message, recipient_name="", recipient_email="", event_type="general"):
    phone = normalize_phone(phone)
    if not phone:
        log_notification(recipient_name, phone, recipient_email, "sms", event_type, message, "skipped", "No phone number")
        return {"status": "skipped", "message": "No phone number"}
    if not TERMII_API_KEY:
        log_notification(recipient_name, phone, recipient_email, "sms", event_type, message, "skipped", "TERMII_API_KEY missing")
        return {"status": "skipped", "message": "SMS provider not configured"}
    try:
        payload = {
            "to": phone,
            "from": TERMII_SENDER,
            "sms": message,
            "type": "plain",
            "channel": "generic",
            "api_key": TERMII_API_KEY,
        }
        response = post_json(TERMII_SMS_ENDPOINT, payload)
        log_notification(recipient_name, phone, recipient_email, "sms", event_type, message, "sent", json_dumps(response))
        return {"status": "sent", "response": response}
    except Exception as e:
        log_notification(recipient_name, phone, recipient_email, "sms", event_type, message, "failed", str(e))
        return {"status": "failed", "message": str(e)}

def send_whatsapp(phone, message, recipient_name="", recipient_email="", event_type="general"):
    phone = normalize_phone(phone)
    if not phone:
        log_notification(recipient_name, phone, recipient_email, "whatsapp", event_type, message, "skipped", "No phone number")
        return {"status": "skipped", "message": "No phone number"}
    try:
        response = None
        if WHATSAPP_PROVIDER == "termii" and TERMII_API_KEY and TERMII_WHATSAPP_ENDPOINT:
            response = post_json(TERMII_WHATSAPP_ENDPOINT, {
                "api_key": TERMII_API_KEY,
                "to": phone,
                "from": TERMII_SENDER,
                "type": "text",
                "channel": "whatsapp",
                "message": message,
            })
        elif META_WHATSAPP_ACCESS_TOKEN and META_WHATSAPP_PHONE_NUMBER_ID:
            endpoint = f"https://graph.facebook.com/v18.0/{META_WHATSAPP_PHONE_NUMBER_ID}/messages"
            response = post_json(endpoint, {
                "messaging_product": "whatsapp",
                "to": phone.replace("+", ""),
                "type": "text",
                "text": {"body": message}
            }, headers={"Authorization": f"Bearer {META_WHATSAPP_ACCESS_TOKEN}"})
        else:
            log_notification(recipient_name, phone, recipient_email, "whatsapp", event_type, message, "skipped", "WhatsApp provider not configured")
            return {"status": "skipped", "message": "WhatsApp provider not configured"}
        log_notification(recipient_name, phone, recipient_email, "whatsapp", event_type, message, "sent", json_dumps(response))
        return {"status": "sent", "response": response}
    except Exception as e:
        log_notification(recipient_name, phone, recipient_email, "whatsapp", event_type, message, "failed", str(e))
        return {"status": "failed", "message": str(e)}

def notify_parent_channels(pupil_row, message, event_type="general", prefer_whatsapp=True, send_email=False):
    responses = []
    if prefer_whatsapp:
        responses.append(send_whatsapp(pupil_row.get("parent_phone"), message, pupil_row.get("parent_name"), pupil_row.get("parent_email"), event_type))
    responses.append(send_sms(pupil_row.get("parent_phone"), message, pupil_row.get("parent_name"), pupil_row.get("parent_email"), event_type))
    if send_email and pupil_row.get("parent_email"):
        send_email_async(pupil_row.get("parent_email"), f"GISL Schools Notification — {event_type.replace('_', ' ').title()}", f"<p>{message}</p>")
        log_notification(pupil_row.get("parent_name"), pupil_row.get("parent_phone"), pupil_row.get("parent_email"), "email", event_type, message, "sent", "SMTP async queued")
    return responses

def record_fee_payment_row(conn, actor_id, is_parent, pupil_id, term_id, fee_structure_id, amount, payment_date="", payment_reference="", notes=""):
    pid = str(uuid.uuid4())
    conn.execute("""INSERT INTO fee_payments
        (id, pupil_id, term_id, fee_structure_id, amount_paid, payment_date, payment_reference, notes, recorded_by, is_parent_payment)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(pupil_id, term_id, fee_structure_id) DO UPDATE SET
        amount_paid=amount_paid + excluded.amount_paid,
        payment_date=excluded.payment_date,
        payment_reference=excluded.payment_reference,
        notes=excluded.notes,
        recorded_by=excluded.recorded_by,
        is_parent_payment=excluded.is_parent_payment""",
        (pid, pupil_id, term_id, fee_structure_id, amount, payment_date, payment_reference, notes, actor_id, 1 if is_parent else 0))
    return pid

def calculate_attendance_summary(conn, pupil_id, term_id=None):
    args = [pupil_id]
    query = "SELECT status, attendance_date FROM attendance_records WHERE pupil_id=?"
    if term_id:
        query += " AND term_id=?"
        args.append(term_id)
    rows = conn.execute(query, args).fetchall()
    present = sum(1 for r in rows if r["status"] == "present")
    late = sum(1 for r in rows if r["status"] == "late")
    absent = sum(1 for r in rows if r["status"] == "absent")
    total = len(rows)
    effective_present = present + late
    percentage = round((effective_present / total) * 100, 2) if total else 0
    recent = conn.execute(
        "SELECT attendance_date, status FROM attendance_records WHERE pupil_id=? ORDER BY attendance_date DESC LIMIT 7",
        (pupil_id,)
    ).fetchall()
    return {
        "present": present,
        "late": late,
        "absent": absent,
        "total": total,
        "percentage": percentage,
        "recent": [dict(r) for r in recent]
    }

def render_pdf_bytes(html, base_url=None):
    if not WeasyHTML:
        return None, "WeasyPrint is not installed. Add it to requirements and install system dependencies."
    try:
        pdf = WeasyHTML(string=html, base_url=base_url or STATIC_DIR).write_pdf()
        return pdf, None
    except Exception as e:
        return None, str(e)

def send_pdf(handler, pdf_bytes, filename):
    handler.send_response(200)
    handler.send_header("Content-Type", "application/pdf")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(pdf_bytes)))
    add_security_headers(handler)
    handler.end_headers()
    handler.wfile.write(pdf_bytes)

# ─── API HANDLERS ─────────────────────────────────────────────────────────────

def handle_login(handler, body):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    if not email or not password:
        return send_error(handler, "Email and password required")

    ip = get_client_ip(handler)
    allowed, wait_secs = check_rate_limit(ip)
    if not allowed:
        return send_error(handler, f"Too many failed attempts. Try again in {wait_secs} seconds.", 429)

    conn = get_db()
    # Try staff first
    user = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
    if user and check_password(password, user["password_hash"]):
        # Transparently upgrade old SHA-256 hash to PBKDF2
        if not user["password_hash"].startswith("pbkdf2$"):
            new_hash = hash_password(password)
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user["id"]))
            conn.commit()
        conn.close()
        clear_attempts(ip)
        cleanup_expired_sessions()
        token = create_session(user["id"], "staff")
        write_audit(dict(user), "login", ip=ip)
        must_change = bool(user["must_change_password"]) if "must_change_password" in user.keys() else False
        return send_json(handler, {"token": token, "user": {
            "id": user["id"], "name": user["name"], "email": user["email"],
            "role": user["role"], "must_change_password": must_change
        }})
    # Try parent
    parent = conn.execute("SELECT * FROM parent_accounts WHERE email = ? AND is_active = 1", (email,)).fetchone()
    if parent and check_password(password, parent["password_hash"]):
        # Transparently upgrade old SHA-256 hash to PBKDF2
        if not parent["password_hash"].startswith("pbkdf2$"):
            new_hash = hash_password(password)
            conn.execute("UPDATE parent_accounts SET password_hash=? WHERE id=?", (new_hash, parent["id"]))
            conn.commit()
        conn.close()
        clear_attempts(ip)
        cleanup_expired_sessions()
        token = create_session(parent["id"], "parent")
        write_audit(dict(parent), "login", ip=ip)
        must_change = bool(parent["must_change_password"]) if "must_change_password" in parent.keys() else False
        return send_json(handler, {"token": token, "user": {
            "id": parent["id"], "name": parent["name"], "email": parent["email"],
            "role": "parent", "must_change_password": must_change
        }})
    conn.close()
    record_failed_attempt(ip)
    return send_error(handler, "Invalid email or password", 401)

def handle_logout(handler, user):
    token = get_token_from_request(handler)
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    write_audit(user, "logout", ip=get_client_ip(handler))
    send_json(handler, {"message": "Logged out"})

def handle_get_me(handler, user):
    result = {k: user[k] for k in ["id","name","email","role","phone"]}
    result["must_change_password"] = bool(user["must_change_password"]) if "must_change_password" in user.keys() else False
    if user["role"] == "teacher":
        conn = get_db()
        cls = conn.execute("SELECT * FROM classes WHERE teacher_id = ?", (user["id"],)).fetchone()
        conn.close()
        result["class"] = dict(cls) if cls else None
    send_json(handler, result)

# ── PUPILS ────────────────────────────────────────────────────────────────────

def handle_get_pupils(handler, user, params):
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    class_id = params.get("class_id", [None])[0]
    status = params.get("status", ["active"])[0]
    search = params.get("search", [None])[0]

    # Teachers only see their class
    if user["role"] == "teacher":
        conn = get_db()
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id = ?", (user["id"],)).fetchone()
        conn.close()
        if cls:
            class_id = cls["id"]
        else:
            return send_json(handler, [])

    conn = get_db()
    query = """
        SELECT p.*, c.name as class_name, c.level as class_level, c.class_type
        FROM pupils p
        LEFT JOIN classes c ON c.id = p.class_id
        WHERE 1=1
    """
    args = []
    if status:
        query += " AND p.status = ?"
        args.append(status)
    if class_id:
        query += " AND p.class_id = ?"
        args.append(class_id)
    if search:
        query += " AND (p.first_name LIKE ? OR p.last_name LIKE ? OR p.admission_number LIKE ?)"
        s = f"%{search}%"
        args.extend([s, s, s])
    query += " ORDER BY c.level, p.last_name, p.first_name"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_create_pupil(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    required = ["first_name", "last_name"]
    for f in required:
        if not body.get(f):
            return send_error(handler, f"{f} is required")

    if body.get("photo") and len(body["photo"]) > 2_000_000:
        return send_error(handler, "Photo must be under 1.5MB")

    pid = str(uuid.uuid4())
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM pupils").fetchone()[0]
    year = datetime.now().year
    admission = body.get("admission_number") or f"SCH/{year}/{str(count+1).zfill(4)}"

    conn.execute("""
        INSERT INTO pupils (id, first_name, last_name, other_name, admission_number,
            date_of_birth, gender, class_id, blood_group, religion, photo,
            parent_name, parent_phone, parent_email, parent_address, parent_relationship,
            emergency_name, emergency_phone, allergies, medical_conditions, doctor_name, doctor_phone)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        pid,
        body.get("first_name","").strip(),
        body.get("last_name","").strip(),
        body.get("other_name",""),
        admission,
        body.get("date_of_birth",""),
        body.get("gender",""),
        body.get("class_id",""),
        body.get("blood_group",""),
        body.get("religion",""),
        body.get("photo",""),
        body.get("parent_name",""),
        body.get("parent_phone",""),
        body.get("parent_email","").strip().lower(),
        body.get("parent_address",""),
        body.get("parent_relationship",""),
        body.get("emergency_name",""),
        body.get("emergency_phone",""),
        body.get("allergies", ""),
        body.get("medical_conditions", ""),
        body.get("doctor_name", ""),
        body.get("doctor_phone", ""),
    ))
    conn.commit()
    pupil = conn.execute("SELECT * FROM pupils WHERE id = ?", (pid,)).fetchone()
    conn.close()
    write_audit(user, "create_pupil", target_type="pupil", target_id=pid,
                details=f"{body.get('first_name','')} {body.get('last_name','')}", ip=get_client_ip(handler))
    send_json(handler, dict(pupil), 201)

def handle_get_pupil(handler, user, pupil_id):
    conn = get_db()
    pupil = conn.execute("""
        SELECT p.*, c.name as class_name, c.level as class_level, c.class_type
        FROM pupils p LEFT JOIN classes c ON c.id = p.class_id
        WHERE p.id = ?
    """, (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    conn.close()
    send_json(handler, dict(pupil))

def handle_update_pupil(handler, user, pupil_id, body):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Not authorized", 403)
    if body.get("photo") and len(body["photo"]) > 2_000_000:
        return send_error(handler, "Photo must be under 1.5MB")
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id = ?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    if user["role"] == "admin":
        fields = ["first_name","last_name","other_name","date_of_birth","gender",
                  "class_id","blood_group","religion","photo","parent_name","parent_phone",
                  "parent_email","parent_address","parent_relationship",
                  "emergency_name","emergency_phone","admission_number",
                  "allergies","medical_conditions","doctor_name","doctor_phone"]
    else:
        fields = ["first_name","last_name","other_name","date_of_birth","gender",
                  "blood_group","religion","photo","parent_name","parent_phone",
                  "parent_email","parent_address","parent_relationship",
                  "emergency_name","emergency_phone","allergies",
                  "medical_conditions","doctor_name","doctor_phone"]
    updates = []
    values = []
    for f in fields:
        if f in body:
            updates.append(f"{f} = ?")
            if f == "parent_email":
                values.append(body[f].strip().lower() if body[f] else "")
            else:
                values.append(body[f])
    if not updates:
        conn.close()
        return send_error(handler, "No fields to update")
    updates.append("updated_at = datetime('now')")
    values.append(pupil_id)
    conn.execute(f"UPDATE pupils SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    updated = conn.execute("SELECT * FROM pupils WHERE id = ?", (pupil_id,)).fetchone()
    conn.close()
    write_audit(user, "update_pupil", target_type="pupil", target_id=pupil_id, ip=get_client_ip(handler))
    send_json(handler, dict(updated))

def handle_archive_pupil(handler, user, pupil_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    conn.execute("UPDATE pupils SET status='archived', updated_at=datetime('now') WHERE id=?", (pupil_id,))
    conn.commit()
    conn.close()
    write_audit(user, "archive_pupil", target_type="pupil", target_id=pupil_id, ip=get_client_ip(handler))
    send_json(handler, {"message": "Pupil archived"})

def handle_restore_pupil(handler, user, pupil_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    conn.execute("UPDATE pupils SET status='active', updated_at=datetime('now') WHERE id=?", (pupil_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Pupil restored"})

def _get_promotion_targets(conn, class_row, pupil_ids=None):
    query = "SELECT id FROM pupils WHERE class_id=? AND status='active'"
    args = [class_row["id"]]
    if pupil_ids is not None:
        normalized = [str(pid) for pid in pupil_ids if pid]
        if not normalized:
            return [], []
        placeholders = ",".join("?" for _ in normalized)
        query += f" AND id IN ({placeholders})"
        args.extend(normalized)
    rows = conn.execute(query, args).fetchall()
    found_ids = [row["id"] for row in rows]
    missing_ids = []
    if pupil_ids is not None:
        requested_ids = [str(pid) for pid in pupil_ids if pid]
        missing_ids = [pid for pid in requested_ids if pid not in found_ids]
    return found_ids, missing_ids


def handle_promote_class(handler, user, class_id, body=None):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    body = body or {}
    conn = get_db()
    cls = conn.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
    if not cls:
        conn.close()
        return send_error(handler, "Class not found", 404)
    requested_pupil_ids = body.get("pupil_ids") if isinstance(body.get("pupil_ids"), list) else None
    target_pupil_ids, missing_pupil_ids = _get_promotion_targets(conn, cls, requested_pupil_ids)
    if missing_pupil_ids:
        conn.close()
        return send_error(handler, "Some selected pupils are invalid or no longer in this class", 400)
    if requested_pupil_ids is not None and not target_pupil_ids:
        conn.close()
        return send_error(handler, "No selected pupils are eligible for promotion", 400)
    level = cls["level"]
    class_type = cls["class_type"] or "primary"
    filter_clause = ""
    filter_args = [class_id]
    if target_pupil_ids:
        placeholders = ",".join("?" for _ in target_pupil_ids)
        filter_clause = f" AND id IN ({placeholders})"
        filter_args.extend(target_pupil_ids)

    # Primary 6 graduates
    if class_type == "primary" and level >= 6:
        conn.execute("""UPDATE pupils SET status='graduated', class_id=NULL, updated_at=datetime('now')
                        WHERE class_id=? AND status='active'""" + filter_clause, filter_args)
        count = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        conn.close()
        scope = "selected pupils" if requested_pupil_ids is not None else "pupils"
        return send_json(handler, {"message": f"{count} {scope} graduated from Primary 6", "count": count, "action": "graduated"})

    # Lower-school top class (Nursery 2, level 3) promotes to Primary 1
    if class_type == "lower" and level >= 3:
        next_cls = conn.execute(
            "SELECT * FROM classes WHERE class_type='primary' AND level=1"
        ).fetchone()
        if not next_cls:
            conn.close()
            return send_error(handler, "Primary 1 class not found")
        conn.execute("""UPDATE pupils SET class_id=?, updated_at=datetime('now')
                        WHERE class_id=? AND status='active'""" + filter_clause, [next_cls["id"], *filter_args])
        count = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        conn.close()
        return send_json(handler, {"message": f"{count} pupils promoted to {next_cls['name']}", "count": count, "target_class": next_cls["name"], "action": "promoted"})

    # Within the same class_type, find the next level
    next_cls = conn.execute(
        "SELECT * FROM classes WHERE class_type=? AND level=?", (class_type, level + 1)
    ).fetchone()
    if not next_cls:
        conn.close()
        return send_error(handler, "Next class not found")
    next_id = next_cls["id"]
    conn.execute("""UPDATE pupils SET class_id=?, updated_at=datetime('now')
                    WHERE class_id=? AND status='active'""" + filter_clause, [next_id, *filter_args])
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    send_json(handler, {"message": f"{count} pupils promoted to {next_cls['name']}", "count": count, "target_class": next_cls["name"], "action": "promoted"})

# ── TEACHERS ──────────────────────────────────────────────────────────────────

def handle_get_teachers(handler, user):
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    query = """
        SELECT u.*, c.name as class_name, c.id as class_id
        FROM users u
        LEFT JOIN classes c ON c.teacher_id = u.id
        WHERE u.role = 'teacher' AND u.is_active = 1
    """
    args = []
    if user["role"] == "teacher":
        query += " AND u.id = ?"
        args.append(user["id"])
    query += " ORDER BY u.name"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_create_teacher(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    required = ["name", "email", "password"]
    for f in required:
        if not body.get(f):
            return send_error(handler, f"{f} is required")
    if len(body["password"]) < 6:
        return send_error(handler, "Password must be at least 6 characters")
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email=?", (body["email"].lower(),)).fetchone()
    if existing:
        conn.close()
        return send_error(handler, "Email already registered")
    tid = str(uuid.uuid4())
    conn.execute("""INSERT INTO users (id, name, email, password_hash, role, phone)
                    VALUES (?,?,?,?,?,?)""",
                 (tid, body["name"], body["email"].lower(),
                  hash_password(body["password"]), "teacher", body.get("phone","")))
    if body.get("class_id"):
        conn.execute("UPDATE classes SET teacher_id=? WHERE id=?", (tid, body["class_id"]))
    conn.commit()
    teacher = conn.execute("SELECT id,name,email,role,phone FROM users WHERE id=?", (tid,)).fetchone()
    conn.close()
    write_audit(user, "create_teacher", target_type="teacher", target_id=tid,
                details=body["name"], ip=get_client_ip(handler))
    send_json(handler, dict(teacher), 201)

def handle_update_teacher(handler, user, teacher_id, body):
    is_self_update = str(user["id"]) == str(teacher_id)
    if not is_self_update and user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    updates = []
    values = []
    # Non-admin users may only change their own password, not name/phone/class
    if user["role"] == "admin":
        for f in ["name","phone"]:
            if f in body:
                updates.append(f"{f} = ?")
                values.append(body[f])
    if body.get("password"):
        if len(body["password"]) < 6:
            conn.close()
            return send_error(handler, "Password must be at least 6 characters")
        updates.append("password_hash = ?")
        values.append(hash_password(body["password"]))
    if updates:
        values.append(teacher_id)
        conn.execute(f"UPDATE users SET {','.join(updates)} WHERE id=?", values)
    if "class_id" in body and user["role"] == "admin":
        conn.execute("UPDATE classes SET teacher_id=NULL WHERE teacher_id=?", (teacher_id,))
        if body["class_id"]:
            conn.execute("UPDATE classes SET teacher_id=? WHERE id=?", (teacher_id, body["class_id"]))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Teacher updated"})

def handle_delete_teacher(handler, user, teacher_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    conn.execute("UPDATE users SET is_active=0 WHERE id=?", (teacher_id,))
    conn.execute("UPDATE classes SET teacher_id=NULL WHERE teacher_id=?", (teacher_id,))
    conn.commit()
    conn.close()
    write_audit(user, "delete_teacher", target_type="teacher", target_id=teacher_id, ip=get_client_ip(handler))
    send_json(handler, {"message": "Teacher removed"})

# ── CLASSES ───────────────────────────────────────────────────────────────────

def handle_get_classes(handler, user):
    conn = get_db()
    query = """
        SELECT c.*, u.name as teacher_name,
               (SELECT COUNT(*) FROM pupils p WHERE p.class_id=c.id AND p.status='active') as pupil_count
        FROM classes c
        LEFT JOIN users u ON u.id = c.teacher_id
    """
    args = []
    if user["role"] == "teacher":
        query += " WHERE c.teacher_id = ?"
        args.append(user["id"])
    query += " ORDER BY c.level"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_assign_teacher(handler, user, class_id, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    teacher_id = body.get("teacher_id")
    conn = get_db()
    if teacher_id:
        conn.execute("UPDATE classes SET teacher_id=NULL WHERE teacher_id=?", (teacher_id,))
    conn.execute("UPDATE classes SET teacher_id=? WHERE id=?", (teacher_id, class_id))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Teacher assigned"})

# ── SUBJECTS ──────────────────────────────────────────────────────────────────

def handle_get_subjects(handler):
    conn = get_db()
    rows = conn.execute("SELECT * FROM subjects WHERE is_active=1 ORDER BY sort_order").fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_create_subject(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    sid = str(uuid.uuid4())
    conn.execute("INSERT INTO subjects (id, name, sort_order) VALUES (?,?,?)",
                 (sid, body.get("name",""), count))
    conn.commit()
    conn.close()
    send_json(handler, {"id": sid, "name": body.get("name","")}, 201)

def handle_toggle_subject(handler, user, subject_id, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    active = 1 if body.get("is_active", True) else 0
    conn = get_db()
    conn.execute("UPDATE subjects SET is_active=? WHERE id=?", (active, subject_id))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Subject updated"})

# ── TERMS ─────────────────────────────────────────────────────────────────────

def handle_get_terms(handler):
    conn = get_db()
    rows = conn.execute("SELECT * FROM terms ORDER BY academic_year DESC, term_number").fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_create_term(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    academic_year = body.get("academic_year", "").strip()
    if not academic_year:
        return send_error(handler, "academic_year is required")
    try:
        term_number = int(body.get("term_number"))
        if term_number not in (1, 2, 3):
            raise ValueError()
    except (TypeError, ValueError):
        return send_error(handler, "term_number must be 1, 2, or 3")
    conn = get_db()
    existing = conn.execute("SELECT id FROM terms WHERE academic_year=? AND term_number=?",
                            (academic_year, term_number)).fetchone()
    if existing:
        conn.close()
        return send_error(handler, "Term already exists")
    tid = str(uuid.uuid4())
    conn.execute("""INSERT INTO terms (id, academic_year, term_number, start_date, end_date)
                    VALUES (?,?,?,?,?)""",
                 (tid, academic_year, term_number,
                  body.get("start_date",""), body.get("end_date","")))
    conn.commit()
    conn.close()
    send_json(handler, {"id": tid}, 201)

def handle_set_current_term(handler, user, term_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    conn.execute("UPDATE terms SET is_current=0")
    conn.execute("UPDATE terms SET is_current=1 WHERE id=?", (term_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Current term updated"})

# ── RESULTS ───────────────────────────────────────────────────────────────────

def handle_get_results(handler, user, params):
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    pupil_id = params.get("pupil_id", [None])[0]
    term_id = params.get("term_id", [None])[0]
    class_id = params.get("class_id", [None])[0]

    if user["role"] == "teacher":
        conn = get_db()
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if cls:
            class_id = cls["id"]
        conn.close()

    conn = get_db()
    query = """
        SELECT r.*, p.first_name, p.last_name, p.admission_number,
               s.name as subject_name, t.term_number, t.academic_year
        FROM results r
        JOIN pupils p ON p.id = r.pupil_id
        JOIN subjects s ON s.id = r.subject_id
        JOIN terms t ON t.id = r.term_id
        WHERE 1=1
    """
    args = []
    if pupil_id:
        query += " AND r.pupil_id = ?"
        args.append(pupil_id)
    if term_id:
        query += " AND r.term_id = ?"
        args.append(term_id)
    if class_id:
        query += " AND p.class_id = ?"
        args.append(class_id)
    query += " ORDER BY p.last_name, s.name"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_save_results_batch(handler, user, body):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Not authorized", 403)
    results = body.get("results", [])
    if not results:
        return send_error(handler, "No results provided")
    conn = get_db()
    # Teachers may only enter results for pupils in their assigned class
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if not cls:
            conn.close()
            return send_error(handler, "You are not assigned to any class", 403)
        teacher_class_id = cls["id"]
        class_pupil_ids = {
            row["id"] for row in conn.execute(
                "SELECT id FROM pupils WHERE class_id=? AND status='active'", (teacher_class_id,)
            ).fetchall()
        }
        for r in results:
            if r.get("pupil_id") not in class_pupil_ids:
                conn.close()
                return send_error(handler, "You can only enter results for pupils in your own class", 403)
    try:
        for r in results:
            existing = conn.execute(
                "SELECT id FROM results WHERE pupil_id=? AND subject_id=? AND term_id=?",
                (r["pupil_id"], r["subject_id"], r["term_id"])
            ).fetchone()
            ca = min(float(r.get("ca_score", 0)), 40)
            exam = min(float(r.get("exam_score", 0)), 60)
            if existing:
                conn.execute("""UPDATE results SET ca_score=?, exam_score=?, entered_by=?,
                                updated_at=datetime('now') WHERE id=?""",
                             (ca, exam, user["id"], existing["id"]))
            else:
                rid = str(uuid.uuid4())
                conn.execute("""INSERT INTO results (id, pupil_id, subject_id, term_id, ca_score, exam_score, entered_by)
                                VALUES (?,?,?,?,?,?,?)""",
                             (rid, r["pupil_id"], r["subject_id"], r["term_id"], ca, exam, user["id"]))
        conn.commit()
        conn.close()
        write_audit(user, "save_results", details=f"Saved {len(results)} results", ip=get_client_ip(handler))
        send_json(handler, {"message": f"Saved {len(results)} results"})
    except Exception as e:
        try: conn.rollback()
        except: pass
        conn.close()
        send_error(handler, f"Failed to save: {str(e)}", 500)

# ── STATS ─────────────────────────────────────────────────────────────────────

def handle_get_stats(handler, user):
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    teacher_class_id = None
    if user["role"] == "teacher":
        teacher_class_id = get_teacher_class_id(conn, user["id"])
        if not teacher_class_id:
            conn.close()
            return send_json(handler, {
                "total_pupils": 0,
                "total_teachers": 1,
                "total_classes": 0,
                "archived": 0,
                "graduated": 0,
                "current_term": None,
                "class_breakdown": [],
                "attendance_today": {},
                "fee_collection_today": 0,
                "active_homework": 0,
                "upcoming_events": 0
            })
    if teacher_class_id:
        total_pupils = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='active' AND class_id=?", (teacher_class_id,)).fetchone()[0]
        total_teachers = 1
        total_classes = 1
        archived = 0
        graduated = 0
    else:
        total_pupils = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='active'").fetchone()[0]
        total_teachers = conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher' AND is_active=1").fetchone()[0]
        total_classes = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        archived = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='archived'").fetchone()[0]
        graduated = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='graduated'").fetchone()[0]
    current_term = conn.execute("SELECT * FROM terms WHERE is_current=1").fetchone()
    today = today_iso()
    if teacher_class_id:
        attendance_today = conn.execute(
            "SELECT status, COUNT(*) as count FROM attendance_records WHERE attendance_date=? AND class_id=? GROUP BY status",
            (today, teacher_class_id)
        ).fetchall()
        fee_today = conn.execute(
            """SELECT COALESCE(SUM(fp.amount_paid),0)
               FROM fee_payments fp
               JOIN pupils p ON p.id = fp.pupil_id
               WHERE fp.payment_date=? AND p.class_id=?""",
            (today, teacher_class_id)
        ).fetchone()[0] or 0
        homework_active = conn.execute(
            "SELECT COUNT(*) FROM homework_assignments WHERE is_active=1 AND class_id=?",
            (teacher_class_id,)
        ).fetchone()[0]
    else:
        attendance_today = conn.execute(
            "SELECT status, COUNT(*) as count FROM attendance_records WHERE attendance_date=? GROUP BY status",
            (today,)
        ).fetchall()
        fee_today = conn.execute(
            "SELECT COALESCE(SUM(amount_paid),0) FROM fee_payments WHERE payment_date=?",
            (today,)
        ).fetchone()[0] or 0
        homework_active = conn.execute(
            "SELECT COUNT(*) FROM homework_assignments WHERE is_active=1"
        ).fetchone()[0]
    upcoming_events = conn.execute(
        "SELECT COUNT(*) FROM school_events WHERE event_date >= ?",
        (today,)
    ).fetchone()[0]

    class_query = """
        SELECT c.name, c.level,
               COUNT(p.id) as count,
               u.name as teacher_name
        FROM classes c
        LEFT JOIN pupils p ON p.class_id=c.id AND p.status='active'
        LEFT JOIN users u ON u.id=c.teacher_id
    """
    class_args = []
    if teacher_class_id:
        class_query += " WHERE c.id=?"
        class_args.append(teacher_class_id)
    class_query += " GROUP BY c.id ORDER BY c.level"
    class_counts = conn.execute(class_query, class_args).fetchall()
    conn.close()

    send_json(handler, {
        "total_pupils": total_pupils,
        "total_teachers": total_teachers,
        "total_classes": total_classes,
        "archived": archived,
        "graduated": graduated,
        "current_term": dict(current_term) if current_term else None,
        "class_breakdown": [dict(r) for r in class_counts],
        "attendance_today": {r["status"]: r["count"] for r in attendance_today},
        "fee_collection_today": round(float(fee_today), 2),
        "active_homework": homework_active,
        "upcoming_events": upcoming_events
    })

# ── REPORT CARD ───────────────────────────────────────────────────────────────

def handle_get_report(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("""
        SELECT p.*, c.name as class_name, c.level as class_level, c.id as class_id_ref, c.class_type
        FROM pupils p LEFT JOIN classes c ON c.id=p.class_id
        WHERE p.id=?
    """, (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)

    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()

    my_results = conn.execute("""
        SELECT r.ca_score, r.exam_score, (r.ca_score+r.exam_score) as total,
               s.name as subject_name, s.sort_order, s.id as subject_id
        FROM results r JOIN subjects s ON s.id=r.subject_id
        WHERE r.pupil_id=? AND r.term_id=?
        ORDER BY s.sort_order
    """, (pupil_id, term_id)).fetchall()

    class_id = pupil["class_id"]
    subject_class_scores = {}
    class_grand_totals = {}

    if class_id:
        all_class_results = conn.execute("""
            SELECT r.pupil_id, r.ca_score, r.exam_score, (r.ca_score+r.exam_score) as total,
                   s.id as subject_id
            FROM results r
            JOIN pupils p ON p.id=r.pupil_id
            JOIN subjects s ON s.id=r.subject_id
            WHERE r.term_id=? AND p.class_id=? AND p.status='active'
        """, (term_id, class_id)).fetchall()

        for row in all_class_results:
            sid = row["subject_id"]
            pid = row["pupil_id"]
            t = row["total"] or 0
            if sid not in subject_class_scores:
                subject_class_scores[sid] = []
            subject_class_scores[sid].append({"pupil_id": pid, "total": t})
            class_grand_totals[pid] = class_grand_totals.get(pid, 0) + t

    subject_results = []
    for r in my_results:
        sid = r["subject_id"]
        class_scores = subject_class_scores.get(sid, [])
        my_total = r["total"] or 0
        position_in_subject = sum(1 for s in class_scores if s["total"] > my_total) + 1
        class_avg = round(sum(s["total"] for s in class_scores) / len(class_scores), 2) if class_scores else 0
        subject_results.append({
            **dict(r),
            "position_in_subject": position_in_subject,
            "class_subject_average": class_avg,
            "class_size_for_subject": len(class_scores)
        })

    grand_total = sum(r["total"] or 0 for r in my_results)
    num_subjects = len(my_results)
    has_exam = any((r["exam_score"] or 0) > 0 for r in my_results)
    max_per_subject = 100 if has_exam else 40
    max_total = num_subjects * max_per_subject
    percentage = round(grand_total / max_total * 100, 2) if max_total else 0
    avg_per_subject = round(grand_total / num_subjects, 2) if num_subjects else 0

    total_in_class = len(class_grand_totals)
    class_position = sum(1 for t in class_grand_totals.values() if t > grand_total) + 1 if class_grand_totals else None

    class_avgs_per_subject = [round(v / num_subjects, 2) for v in class_grand_totals.values()] if class_grand_totals and num_subjects else []
    least_class_avg = round(min(class_grand_totals.values()) / num_subjects, 2) if class_grand_totals and num_subjects else None
    max_class_avg = round(max(class_grand_totals.values()) / num_subjects, 2) if class_grand_totals and num_subjects else None

    dob = pupil["date_of_birth"]
    age_str = ""
    if dob:
        try:
            from datetime import date
            b = date.fromisoformat(dob)
            today = date.today()
            years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
            months = (today.month - b.month) % 12
            age_str = f"{years} Years {months} Months" if months else f"{years} Years"
        except:
            pass

    conduct = conn.execute(
        "SELECT * FROM conduct_ratings WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)
    ).fetchone()

    # Get parent acknowledgment with parent name
    parent_ack = conn.execute("""
        SELECT pa.*, p.name as parent_name 
        FROM parent_acknowledgments pa
        LEFT JOIN parent_accounts p ON p.id = pa.parent_account_id
        WHERE pa.pupil_id=? AND pa.term_id=?
    """, (pupil_id, term_id)).fetchone()

    attendance_summary = calculate_attendance_summary(conn, pupil_id, term_id)
    progress_history_rows = conn.execute(
        """SELECT t.academic_year, t.term_number,
                  ROUND(SUM(r.ca_score + r.exam_score), 2) as total_score,
                  ROUND(AVG(r.ca_score + r.exam_score), 2) as average_score
           FROM results r
           JOIN terms t ON t.id = r.term_id
           WHERE r.pupil_id=?
           GROUP BY t.id
           ORDER BY t.academic_year DESC, t.term_number DESC
           LIMIT 3""",
        (pupil_id,)
    ).fetchall()
    progress_history = [dict(r) for r in reversed(progress_history_rows)]

    # For Term 3, pull Term 1 and Term 2 per-subject totals for the cumulative view
    prev_term_results = {}
    if term and term["term_number"] == 3:
        prev_terms = conn.execute(
            "SELECT * FROM terms WHERE academic_year=? AND term_number IN (1,2) ORDER BY term_number",
            (term["academic_year"],)
        ).fetchall()
        for pt in prev_terms:
            pt_rows = conn.execute(
                "SELECT (r.ca_score + r.exam_score) as total, s.id as subject_id "
                "FROM results r JOIN subjects s ON s.id=r.subject_id "
                "WHERE r.pupil_id=? AND r.term_id=?",
                (pupil_id, pt["id"])
            ).fetchall()
            prev_term_results[str(pt["term_number"])] = {r["subject_id"]: r["total"] for r in pt_rows}

    conn.close()
    send_json(handler, {
        "pupil": dict(pupil),
        "term": dict(term) if term else None,
        "results": subject_results,
        "grand_total": grand_total,
        "max_total": max_total,
        "max_per_subject": max_per_subject,
        "percentage": percentage,
        "avg_per_subject": avg_per_subject,
        "position": class_position,
        "total_in_class": total_in_class,
        "least_class_avg": least_class_avg,
        "max_class_avg": max_class_avg,
        "num_subjects": num_subjects,
        "age": age_str,
        "conduct": dict(conduct) if conduct else None,
        "parent_acknowledgment": dict(parent_ack) if parent_ack else None,
        "class_type": pupil["class_type"] if "class_type" in pupil.keys() else "primary",
        "attendance_summary": attendance_summary,
        "progress_history": progress_history,
        "prev_term_results": prev_term_results,
        "is_cumulative": bool(prev_term_results),
    })

# ── CONDUCT RATINGS ───────────────────────────────────────────────────────────

def handle_get_conduct(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    row = conn.execute(
        "SELECT * FROM conduct_ratings WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)
    ).fetchone()
    conn.close()
    send_json(handler, dict(row) if row else {})

def handle_save_conduct(handler, user, pupil_id, term_id, body):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    existing = conn.execute(
        "SELECT id FROM conduct_ratings WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)
    ).fetchone()
    fields = ["punctuality","honesty","cleanliness","leadership","politeness",
              "attentiveness","writing","handwork","verbal_fluency","drama",
              "sports","teacher_comment","admin_comment"]
    if existing:
        updates = [f"{f}=?" for f in fields if f in body]
        values = [body[f] for f in fields if f in body]
        if updates:
            updates.append("updated_at=datetime('now')")
            values.extend([pupil_id, term_id])
            conn.execute(f"UPDATE conduct_ratings SET {','.join(updates)} WHERE pupil_id=? AND term_id=?", values)
    else:
        rid = str(uuid.uuid4())
        vals = {f: body.get(f, "") for f in fields}
        conn.execute("""INSERT INTO conduct_ratings
            (id, pupil_id, term_id, punctuality, honesty, cleanliness, leadership, politeness,
             attentiveness, writing, handwork, verbal_fluency, drama, sports, teacher_comment, admin_comment)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, pupil_id, term_id,
             vals["punctuality"], vals["honesty"], vals["cleanliness"], vals["leadership"],
             vals["politeness"], vals["attentiveness"], vals["writing"], vals["handwork"],
             vals["verbal_fluency"], vals["drama"], vals["sports"],
             vals["teacher_comment"], vals["admin_comment"]))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Conduct saved"})

# ── FEE STRUCTURES ────────────────────────────────────────────────────────────

def handle_get_fee_structures(handler, user, params):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    class_id = params.get('class_id', [None])[0]
    year = params.get('year', params.get('academic_year', [None]))[0]
    conn = get_db()
    q = "SELECT * FROM fee_structures WHERE 1=1"
    args = []
    if class_id:
        q += " AND (class_id=? OR class_id IS NULL)"
        args.append(class_id)
    if year:
        q += " AND academic_year=?"
        args.append(year)
    q += " ORDER BY term_number, sort_order"
    rows = conn.execute(q, args).fetchall()
    conn.close()
    send_json(handler, {"fee_structures": [dict(r) for r in rows]})

def handle_save_fee_structure(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    fid = body.get('id') or str(uuid.uuid4())
    existing = conn.execute("SELECT id FROM fee_structures WHERE id=?", (fid,)).fetchone()
    if existing:
        conn.execute("""UPDATE fee_structures SET class_id=?, academic_year=?, term_number=?,
            fee_name=?, new_pupil_amount=?, returning_pupil_amount=?, is_optional=?, sort_order=?
            WHERE id=?""",
            (body.get('class_id'), body['academic_year'], body['term_number'],
             body['fee_name'], body.get('new_pupil_amount', 0), body.get('returning_pupil_amount', 0),
             1 if body.get('is_optional') else 0, body.get('sort_order', 0), fid))
    else:
        conn.execute("""INSERT INTO fee_structures
            (id, class_id, academic_year, term_number, fee_name, new_pupil_amount, returning_pupil_amount, is_optional, sort_order)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (fid, body.get('class_id'), body['academic_year'], body['term_number'],
             body['fee_name'], body.get('new_pupil_amount', 0), body.get('returning_pupil_amount', 0),
             1 if body.get('is_optional') else 0, body.get('sort_order', 0)))
    conn.commit()
    conn.close()
    send_json(handler, {"id": fid, "message": "Saved"})

def handle_delete_fee_structure(handler, user, fid):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    conn.execute("DELETE FROM fee_structures WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Deleted"})

def handle_get_fee_bill(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("""
        SELECT p.*, c.name as class_name, c.class_type
        FROM pupils p LEFT JOIN classes c ON c.id=p.class_id
        WHERE p.id=?""", (pupil_id,)).fetchone()
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    if not pupil or not term:
        conn.close()
        return send_error(handler, "Not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    structures = conn.execute("""
        SELECT * FROM fee_structures
        WHERE academic_year=? AND term_number=?
          AND (class_id=? OR class_id IS NULL)
        ORDER BY is_optional, sort_order""",
        (term['academic_year'], term['term_number'], pupil['class_id'])).fetchall()
    payments = conn.execute("""
        SELECT fp.*, fs.fee_name FROM fee_payments fp
        JOIN fee_structures fs ON fs.id=fp.fee_structure_id
        WHERE fp.pupil_id=? AND fp.term_id=?""",
        (pupil_id, term_id)).fetchall()
    prior_payments = conn.execute(
        "SELECT COUNT(*) FROM fee_payments WHERE pupil_id=?", (pupil_id,)
    ).fetchone()[0]
    is_new = prior_payments == 0
    conn.close()
    send_json(handler, {
        "pupil": dict(pupil),
        "term": dict(term),
        "fee_items": [dict(s) for s in structures],
        "payments": [dict(p) for p in payments],
        "is_new_pupil": is_new
    })

def handle_save_fee_payment(handler, user, body):
    # Validate required fields
    amount = body.get('amount_paid', 0)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return send_error(handler, "amount_paid must be a number", 400)
    if amount <= 0:
        return send_error(handler, "amount_paid must be greater than zero", 400)
    for required in ('pupil_id', 'term_id', 'fee_structure_id'):
        if not body.get(required):
            return send_error(handler, f"Missing required field: {required}", 400)

    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (body['pupil_id'],)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    is_parent = 1 if user["role"] == "parent" else 0
    record_fee_payment_row(
        conn, user['id'], bool(is_parent), body['pupil_id'], body['term_id'], body['fee_structure_id'],
        amount, body.get('payment_date', ''), body.get('payment_reference', ''), body.get('notes', '')
    )
    conn.commit()
    pupil_row = conn.execute("SELECT first_name, last_name, parent_email, parent_phone, parent_name FROM pupils WHERE id=?",
                             (body['pupil_id'],)).fetchone()
    # Send email to parent if staff recorded the payment and parent email is available
    if pupil_row:
        msg = f"Fee payment received: ₦{amount:,.2f} for {pupil_row['first_name']} {pupil_row['last_name']}. Ref: {body.get('payment_reference', 'N/A')}."
        notify_parent_channels(dict(pupil_row), msg, event_type="fee_receipt", prefer_whatsapp=True, send_email=not is_parent)
    conn.close()
    write_audit(user, "fee_payment", target_type="pupil", target_id=body['pupil_id'],
                details=f"₦{amount}", ip=get_client_ip(handler))
    send_json(handler, {"message": "Payment recorded", "amount": amount})

def handle_get_fee_payments_by_pupil(handler, user, pupil_id):
    # Only staff (admin/teachers) may view full payment history by pupil.
    # Parents must use the fee bill endpoint which is scoped to their child.
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    payments = conn.execute("""
        SELECT fp.*, fs.fee_name, t.academic_year, t.term_number,
               CASE WHEN fp.is_parent_payment = 1 THEN 'Parent' ELSE 'Staff' END as recorded_by_type
        FROM fee_payments fp
        JOIN fee_structures fs ON fs.id = fp.fee_structure_id
        JOIN terms t ON t.id = fp.term_id
        WHERE fp.pupil_id=?
        ORDER BY fp.created_at DESC
    """, (pupil_id,)).fetchall()
    conn.close()
    send_json(handler, [dict(p) for p in payments])

# ── SKILL ASSESSMENTS ─────────────────────────────────────────────────────────

def handle_get_skill_assessments(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    rows = conn.execute(
        "SELECT * FROM skill_assessments WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)).fetchall()
    conduct = conn.execute(
        "SELECT teacher_comment, admin_comment FROM conduct_ratings WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)).fetchone()
    conn.close()
    result = {r['skill_name']: r['grade'] for r in rows}
    if conduct:
        result['__teacher_comment'] = conduct['teacher_comment']
        result['__admin_comment'] = conduct['admin_comment']
    send_json(handler, result)

def handle_save_skill_assessments(handler, user, pupil_id, term_id, body):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    skills = {k: v for k, v in body.items() if not k.startswith('__')}
    for skill_name, grade in skills.items():
        sid = str(uuid.uuid4())
        conn.execute("""INSERT INTO skill_assessments (id, pupil_id, term_id, skill_name, grade)
            VALUES (?,?,?,?,?)
            ON CONFLICT(pupil_id, term_id, skill_name) DO UPDATE SET grade=excluded.grade, updated_at=datetime('now')""",
            (sid, pupil_id, term_id, skill_name, grade))
    tc = body.get('__teacher_comment', '')
    ac = body.get('__admin_comment', '')
    existing = conn.execute("SELECT id FROM conduct_ratings WHERE pupil_id=? AND term_id=?", (pupil_id, term_id)).fetchone()
    if existing:
        conn.execute("UPDATE conduct_ratings SET teacher_comment=?, admin_comment=? WHERE pupil_id=? AND term_id=?",
                     (tc, ac, pupil_id, term_id))
    else:
        cid = str(uuid.uuid4())
        conn.execute("INSERT INTO conduct_ratings (id, pupil_id, term_id, teacher_comment, admin_comment) VALUES (?,?,?,?,?)",
                     (cid, pupil_id, term_id, tc, ac))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Saved"})

def handle_get_lower_school_report(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("""
        SELECT p.*, c.name as class_name, c.class_type
        FROM pupils p LEFT JOIN classes c ON c.id=p.class_id
        WHERE p.id=?""", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    skills = conn.execute(
        "SELECT skill_name, grade FROM skill_assessments WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)).fetchall()
    conduct = conn.execute(
        "SELECT teacher_comment, admin_comment FROM conduct_ratings WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)).fetchone()
    
    parent_ack = conn.execute("""
        SELECT pa.*, p.name as parent_name 
        FROM parent_acknowledgments pa
        LEFT JOIN parent_accounts p ON p.id = pa.parent_account_id
        WHERE pa.pupil_id=? AND pa.term_id=?
    """, (pupil_id, term_id)).fetchone()

    dob = pupil["date_of_birth"] if pupil else None
    age_str = ""
    if dob:
        try:
            from datetime import date
            b = date.fromisoformat(dob)
            today = date.today()
            years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
            months = (today.month - b.month) % 12
            age_str = f"{years} Years {months} Months" if months else f"{years} Years"
        except: pass

    conn.close()
    send_json(handler, {
        "pupil": dict(pupil),
        "term": dict(term) if term else None,
        "skills": {r['skill_name']: r['grade'] for r in skills},
        "teacher_comment": conduct['teacher_comment'] if conduct else '',
        "admin_comment": conduct['admin_comment'] if conduct else '',
        "parent_acknowledgment": dict(parent_ack) if parent_ack else None,
        "age": age_str
    })

# ─── PARENT ACCOUNTS ──────────────────────────────────────────────────────────

def handle_get_parent_accounts(handler, user):
    if user["role"] not in ("admin",):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    parents = conn.execute("SELECT * FROM parent_accounts ORDER BY name").fetchall()
    result = []
    for p in parents:
        children = conn.execute("""
            SELECT id, first_name, last_name, admission_number, class_id,
                   (SELECT name FROM classes WHERE id=pupils.class_id) as class_name
            FROM pupils WHERE parent_email=? AND status='active'
        """, (p["email"],)).fetchall()
        d = dict(p)
        d.pop("password_hash", None)
        d["children"] = [dict(c) for c in children]
        result.append(d)
    conn.close()
    send_json(handler, result)

def handle_save_parent_account(handler, user, body, parent_id=None):
    if user["role"] not in ("admin",):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    if parent_id:
        existing = conn.execute("SELECT id FROM parent_accounts WHERE id=?", (parent_id,)).fetchone()
        if not existing:
            conn.close()
            return send_error(handler, "Not found", 404)
        updates = []
        values = []
        for f in ["name","phone","is_active"]:
            if f in body:
                updates.append(f"{f}=?")
                values.append(body[f])
        if "password" in body and body["password"]:
            if len(body["password"]) < 6:
                conn.close()
                return send_error(handler, "Password must be at least 6 characters")
            updates.append("password_hash=?")
            values.append(hash_password(body["password"]))
        if updates:
            values.append(parent_id)
            conn.execute(f"UPDATE parent_accounts SET {','.join(updates)} WHERE id=?", values)
        conn.commit()
        conn.close()
        send_json(handler, {"message": "Updated"})
    else:
        email = body.get("email", "").strip().lower()
        name = body.get("name", "").strip()
        password = body.get("password", "")
        if not email or not name or not password:
            conn.close()
            return send_error(handler, "Name, email and password required")
        if len(password) < 6:
            conn.close()
            return send_error(handler, "Password must be at least 6 characters")
        pid = str(uuid.uuid4())
        try:
            conn.execute("INSERT INTO parent_accounts (id,name,email,password_hash,phone) VALUES (?,?,?,?,?)",
                (pid, name, email, hash_password(password), body.get("phone","")))
            conn.commit()
            conn.close()
            write_audit(user, "create_parent_account", target_type="parent_account", target_id=pid,
                        details=email, ip=get_client_ip(handler))
            # Send welcome email with credentials
            app_url = APP_URL
            html = f"""<html><body>
<p>Dear {name},</p>
<p>Your parent portal account has been created for <strong>GISL Daycare Nursery &amp; Primary School</strong>.</p>
<p><strong>Login Details:</strong><br/>
Email: {email}<br/>
Password: {password}</p>
<p>Access the portal at: <a href="{app_url}">{app_url or 'Contact school for URL'}</a></p>
<p>Please change your password after first login.<br/>
Thank you.<br/>GISL Schools</p>
</body></html>"""
            send_email_async(email, "Your GISL Schools Parent Portal Access", html)
            send_json(handler, {"id": pid, "message": "Created"})
        except Exception as e:
            conn.close()
            send_error(handler, str(e))

def handle_delete_parent_account(handler, user, parent_id):
    if user["role"] not in ("admin",):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE user_id=?", (parent_id,))
    conn.execute("DELETE FROM parent_accounts WHERE id=?", (parent_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Deleted"})

# ─── PARENT PORTAL ────────────────────────────────────────────────────────────

def handle_get_parent_children(handler, user):
    if user["role"] != "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    children = conn.execute("""
        SELECT p.*, c.name as class_name, c.class_type
        FROM pupils p
        LEFT JOIN classes c ON c.id=p.class_id
        WHERE p.parent_email=? AND p.status='active'
        ORDER BY p.first_name
    """, (user["email"],)).fetchall()
    conn.close()
    send_json(handler, [dict(c) for c in children])

def handle_get_parent_child_results(handler, user, pupil_id, params):
    if user["role"] != "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=? AND parent_email=?", (pupil_id, user["email"])).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Not found", 404)
    term_id = params.get("term_id", [None])[0]
    if not term_id:
        conn.close()
        return send_error(handler, "term_id required")
    results = conn.execute("""
        SELECT r.*, s.name as subject_name
        FROM results r
        JOIN subjects s ON s.id=r.subject_id
        WHERE r.pupil_id=? AND r.term_id=?
        ORDER BY s.sort_order
    """, (pupil_id, term_id)).fetchall()
    ack = conn.execute("SELECT * FROM parent_acknowledgments WHERE pupil_id=? AND term_id=?", (pupil_id, term_id)).fetchone()
    conn.close()
    send_json(handler, {
        "results": [dict(r) for r in results],
        "acknowledgment": dict(ack) if ack else None
    })

def handle_get_parent_child_fees(handler, user, pupil_id, term_id):
    if user["role"] != "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=? AND parent_email=?", (pupil_id, user["email"])).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Not found", 404)
    conn.close()
    return handle_get_fee_bill(handler, user, pupil_id, term_id)

def handle_parent_acknowledge(handler, user, body):
    if user["role"] != "parent":
        return send_error(handler, "Forbidden", 403)
    pupil_id = body.get("pupil_id")
    term_id = body.get("term_id")
    comment = (body.get("comment") or "").strip()
    if len(comment) > 1000:
        return send_error(handler, "Comment must be 1000 characters or less", 400)
    if not pupil_id or not term_id:
        return send_error(handler, "pupil_id and term_id required")
    conn = get_db()
    pupil = conn.execute("SELECT id FROM pupils WHERE id=? AND parent_email=?", (pupil_id, user["email"])).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Not found", 404)
    aid = str(uuid.uuid4())
    conn.execute("""INSERT INTO parent_acknowledgments (id, pupil_id, term_id, parent_account_id, parent_comment)
        VALUES (?,?,?,?,?)
        ON CONFLICT(pupil_id,term_id) DO UPDATE SET
            parent_comment=excluded.parent_comment,
            parent_account_id=excluded.parent_account_id,
            acknowledged_at=datetime('now')""",
        (aid, pupil_id, term_id, user["id"], comment))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Acknowledged"})

# ─── SCHOOL NOTICES ───────────────────────────────────────────────────────────

def handle_get_notices(handler, user, params):
    conn = get_db()
    if user["role"] in ("admin","teacher"):
        notices = conn.execute("SELECT * FROM school_notices ORDER BY posted_at DESC").fetchall()
    else:
        notices = conn.execute(
            "SELECT * FROM school_notices WHERE is_active=1 AND (target='all' OR target='parents') ORDER BY posted_at DESC"
        ).fetchall()
    conn.close()
    send_json(handler, [dict(n) for n in notices])

def handle_save_notice(handler, user, body, notice_id=None):
    if user["role"] not in ("admin","teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    if notice_id:
        updates = []
        values = []
        for f in ["title","body","is_active","target"]:
            if f in body:
                updates.append(f"{f}=?")
                values.append(body[f])
        if updates:
            values.append(notice_id)
            conn.execute(f"UPDATE school_notices SET {','.join(updates)} WHERE id=?", values)
        conn.commit()
        conn.close()
        send_json(handler, {"message": "Updated"})
    else:
        nid = str(uuid.uuid4())
        conn.execute("INSERT INTO school_notices (id,title,body,posted_by,target) VALUES (?,?,?,?,?)",
            (nid, body.get("title",""), body.get("body",""), user["name"], body.get("target","all")))
        conn.commit()
        conn.close()
        send_json(handler, {"id": nid, "message": "Created"})

def handle_delete_notice(handler, user, notice_id):
    if user["role"] not in ("admin","teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    conn.execute("DELETE FROM school_notices WHERE id=?", (notice_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Deleted"})

def handle_get_parent_acknowledgments_for_admin(handler, user, params):
    if user["role"] not in ("admin","teacher"):
        return send_error(handler, "Forbidden", 403)
    pupil_id = params.get("pupil_id", [None])[0]
    term_id = params.get("term_id", [None])[0]
    conn = get_db()
    query = """SELECT pa.*, p.first_name, p.last_name, p.admission_number, 
                      t.academic_year, t.term_number,
                      par.name as parent_name, par.email as parent_email
               FROM parent_acknowledgments pa 
               JOIN pupils p ON p.id=pa.pupil_id
               JOIN terms t ON t.id=pa.term_id
               LEFT JOIN parent_accounts par ON par.id=pa.parent_account_id
               WHERE 1=1"""
    args = []
    if user["role"] == "teacher":
        teacher_class_id = get_teacher_class_id(conn, user["id"])
        if not teacher_class_id:
            conn.close()
            return send_json(handler, [])
        query += " AND p.class_id=?"
        args.append(teacher_class_id)
    if pupil_id:
        query += " AND pa.pupil_id=?"
        args.append(pupil_id)
    if term_id:
        query += " AND pa.term_id=?"
        args.append(term_id)
    query += " ORDER BY pa.acknowledged_at DESC"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

# ─── CHANGE PASSWORD ──────────────────────────────────────────────────────────

def handle_change_password(handler, user, body):
    new_password = body.get("new_password", "")
    if not new_password or len(new_password) < 6:
        return send_error(handler, "new_password must be at least 6 characters")
    new_hash = hash_password(new_password)
    conn = get_db()
    if user["role"] == "parent":
        conn.execute("UPDATE parent_accounts SET password_hash=?, must_change_password=0 WHERE id=?",
                     (new_hash, user["id"]))
    else:
        conn.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
                     (new_hash, user["id"]))
    conn.commit()
    conn.close()
    write_audit(user, "change_password", ip=get_client_ip(handler))
    send_json(handler, {"message": "Password updated"})

# ─── HEALTH ───────────────────────────────────────────────────────────────────

def handle_get_readiness_report(handler, user):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    report = get_system_checks()
    report["bootstrap"] = dict(_BOOTSTRAP_STATUS)
    send_json(handler, report)


def handle_list_backups(handler, user):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    backups = list_database_backups()
    send_json(handler, {"backups": backups, "count": len(backups)})


def handle_create_backup(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    label = (body.get("label") or "manual").strip()
    backup_path = create_database_backup(label)
    if not backup_path:
        return send_error(handler, "Database file does not exist yet", 404)
    write_audit(user, "create_backup", target_type="backup", target_id=os.path.basename(backup_path), ip=get_client_ip(handler))
    send_json(handler, {
        "message": "Backup created",
        "backup": {
            "filename": os.path.basename(backup_path),
            "path": backup_path,
        }
    }, 201)


def handle_download_backup(handler, user, filename):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".db"):
        return send_error(handler, "Invalid backup filename", 400)
    filepath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(filepath):
        return send_error(handler, "Backup not found", 404)
    try:
        with open(filepath, "rb") as f:
            content = f.read()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/octet-stream")
        handler.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        handler.send_header("Content-Length", str(len(content)))
        add_security_headers(handler)
        handler.end_headers()
        handler.wfile.write(content)
    except Exception as e:
        send_error(handler, str(e), 500)


def handle_restore_backup(handler, user, filename):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".db"):
        return send_error(handler, "Invalid backup filename", 400)
    src_path = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.isfile(src_path):
        return send_error(handler, "Backup not found", 404)
    try:
        test_conn = sqlite3.connect(src_path)
        test_conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        test_conn.close()
    except Exception:
        return send_error(handler, "File is not a valid SQLite database", 400)
    safety_path = create_database_backup("pre-restore")
    try:
        shutil.copy2(src_path, DB_PATH)
    except Exception as e:
        return send_error(handler, f"Restore failed: {e}", 500)
    write_audit(user, "restore_backup", target_type="backup", target_id=safe_name, ip=get_client_ip(handler))
    safety_name = os.path.basename(safety_path) if safety_path else "N/A"
    send_json(handler, {"message": f"Database restored from {safe_name}. Safety backup saved as {safety_name}."})


def handle_restore_upload(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    data_b64 = body.get("data", "")
    if not data_b64:
        return send_error(handler, "No file data provided")
    try:
        file_bytes = base64.b64decode(data_b64)
    except Exception:
        return send_error(handler, "Invalid file data (not valid base64)")
    if not file_bytes.startswith(b"SQLite format 3"):
        return send_error(handler, "Uploaded file is not a valid SQLite database")
    if len(file_bytes) > 100 * 1024 * 1024:
        return send_error(handler, "File too large (max 100 MB)")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_path = os.path.join(BACKUP_DIR, f"_upload_{stamp}.db")
    try:
        with open(tmp_path, "wb") as f:
            f.write(file_bytes)
        test_conn = sqlite3.connect(tmp_path)
        test_conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        test_conn.close()
    except Exception as e:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return send_error(handler, f"Invalid database file: {e}")
    safety_path = create_database_backup("pre-restore-upload")
    try:
        shutil.copy2(tmp_path, DB_PATH)
    except Exception as e:
        return send_error(handler, f"Restore failed: {e}", 500)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    write_audit(user, "restore_upload", target_type="backup", details="Restored from uploaded file", ip=get_client_ip(handler))
    safety_name = os.path.basename(safety_path) if safety_path else "N/A"
    send_json(handler, {"message": f"Database restored from uploaded file. Safety backup saved as {safety_name}."})


def handle_health(handler):
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        report = get_system_checks()
        report["bootstrap"] = dict(_BOOTSTRAP_STATUS)
        fatal_errors = [c for c in report["checks"] if c["status"] == "error" and c.get("fatal")]
        status = "ok" if not fatal_errors else "degraded"
        send_json(handler, {
            "status": status,
            "db": "connected",
            "version": "1.1.0",
            "environment": ENVIRONMENT,
            "summary": report["summary"],
            "bootstrap": report["bootstrap"],
        }, 200 if status == "ok" else 503)
    except Exception as exc:
        LOGGER.exception("Health check failed")
        send_json(handler, {"status": "degraded", "db": "error", "error": str(exc)}, 503)

# ─── CSV EXPORT ───────────────────────────────────────────────────────────────

def handle_export_pupils(handler, user):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    query = """
        SELECT p.admission_number, p.first_name, p.last_name, p.other_name,
               p.gender, p.date_of_birth, c.name as class_name, p.blood_group,
               p.religion, p.parent_name, p.parent_phone, p.parent_email, p.status
        FROM pupils p
        LEFT JOIN classes c ON c.id = p.class_id
        WHERE p.status = 'active'
    """
    args = []
    if user["role"] == "teacher":
        teacher_class_id = get_teacher_class_id(conn, user["id"])
        if not teacher_class_id:
            conn.close()
            return send_json(handler, [])
        query += " AND p.class_id = ?"
        args.append(teacher_class_id)
    query += " ORDER BY c.level, p.last_name, p.first_name"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Admission No", "First Name", "Last Name", "Other Name", "Gender",
                     "DOB", "Class", "Blood Group", "Religion",
                     "Parent Name", "Parent Phone", "Parent Email", "Status"])
    for r in rows:
        writer.writerow([r["admission_number"] or "", r["first_name"], r["last_name"],
                         r["other_name"] or "", r["gender"] or "", r["date_of_birth"] or "",
                         r["class_name"] or "", r["blood_group"] or "", r["religion"] or "",
                         r["parent_name"] or "", r["parent_phone"] or "",
                         r["parent_email"] or "", r["status"]])
    content = ("\ufeff" + output.getvalue()).encode("utf-8")
    date_str = datetime.now().strftime("%Y%m%d")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="pupils_{date_str}.csv"')
    handler.send_header("Content-Length", str(len(content)))
    add_security_headers(handler)
    handler.end_headers()
    handler.wfile.write(content)

def handle_export_results(handler, user, params):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    term_id = params.get("term_id", [None])[0]
    if not term_id:
        return send_error(handler, "term_id is required")
    conn = get_db()
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    if not term:
        conn.close()
        return send_error(handler, "Term not found", 404)
    query = """
        SELECT p.first_name, p.last_name, p.admission_number, c.name as class_name,
               s.name as subject_name, r.ca_score, r.exam_score,
               (r.ca_score + r.exam_score) as total
        FROM results r
        JOIN pupils p ON p.id = r.pupil_id
        JOIN subjects s ON s.id = r.subject_id
        LEFT JOIN classes c ON c.id = p.class_id
        WHERE r.term_id = ?
    """
    args = [term_id]
    if user["role"] == "teacher":
        teacher_class_id = get_teacher_class_id(conn, user["id"])
        if not teacher_class_id:
            conn.close()
            return send_json(handler, [])
        query += " AND p.class_id = ?"
        args.append(teacher_class_id)
    query += " ORDER BY p.last_name, p.first_name, s.sort_order"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["First Name", "Last Name", "Admission No", "Class", "Subject",
                     "CA Score", "Exam Score", "Total"])
    for r in rows:
        writer.writerow([r["first_name"], r["last_name"], r["admission_number"] or "",
                         r["class_name"] or "", r["subject_name"],
                         r["ca_score"] or 0, r["exam_score"] or 0, r["total"] or 0])
    content = ("\ufeff" + output.getvalue()).encode("utf-8")
    fname = f"results_{term['academic_year'].replace('/','-')}_term{term['term_number']}.csv"
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="{fname}"')
    handler.send_header("Content-Length", str(len(content)))
    add_security_headers(handler)
    handler.end_headers()
    handler.wfile.write(content)

def handle_export_fees(handler, user, params):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    term_id = params.get("term_id", [None])[0]
    if not term_id:
        return send_error(handler, "term_id is required")
    conn = get_db()
    rows = conn.execute("""
        SELECT p.first_name, p.last_name, p.admission_number, c.name as class_name,
               fs.fee_name, fp.amount_paid, fp.payment_date, fp.payment_reference,
               CASE WHEN fp.is_parent_payment=1 THEN 'Parent' ELSE 'Staff' END as recorded_by_type
        FROM fee_payments fp
        JOIN pupils p ON p.id = fp.pupil_id
        JOIN fee_structures fs ON fs.id = fp.fee_structure_id
        LEFT JOIN classes c ON c.id = p.class_id
        WHERE fp.term_id = ?
        ORDER BY p.last_name, p.first_name
    """, (term_id,)).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Pupil Name", "Admission No", "Class", "Fee Item",
                     "Amount Paid", "Payment Date", "Reference", "Recorded By"])
    for r in rows:
        writer.writerow([f"{r['first_name']} {r['last_name']}", r["admission_number"] or "",
                         r["class_name"] or "", r["fee_name"], r["amount_paid"] or 0,
                         r["payment_date"] or "", r["payment_reference"] or "",
                         r["recorded_by_type"]])
    content = ("\ufeff" + output.getvalue()).encode("utf-8")
    date_str = datetime.now().strftime("%Y%m%d")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="fees_{date_str}.csv"')
    handler.send_header("Content-Length", str(len(content)))
    add_security_headers(handler)
    handler.end_headers()
    handler.wfile.write(content)

def handle_get_audit_log(handler, user, params):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    action_filter = params.get("action", [None])[0]
    conn = get_db()
    if action_filter:
        rows = conn.execute("""SELECT * FROM audit_log WHERE action=?
                               ORDER BY created_at DESC LIMIT 200""", (action_filter,)).fetchall()
    else:
        rows = conn.execute("""SELECT * FROM audit_log
                               ORDER BY created_at DESC LIMIT 200""").fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def _get_fee_item_context(conn, pupil_id, term_id, fee_structure_id):
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    item = conn.execute("SELECT * FROM fee_structures WHERE id=?", (fee_structure_id,)).fetchone()
    if not pupil or not term or not item:
        return None, None, None, 0, 0, 0
    prior_payments = conn.execute("SELECT COUNT(*) FROM fee_payments WHERE pupil_id=?", (pupil_id,)).fetchone()[0]
    is_new = prior_payments == 0
    amount_due = float(item["new_pupil_amount"] if is_new else item["returning_pupil_amount"])
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount_paid),0) FROM fee_payments WHERE pupil_id=? AND term_id=? AND fee_structure_id=?",
        (pupil_id, term_id, fee_structure_id)
    ).fetchone()[0] or 0
    outstanding = max(0, amount_due - float(paid))
    return pupil, term, item, amount_due, float(paid), outstanding

def handle_initialize_online_payment(handler, user, body):
    pupil_id = body.get("pupil_id")
    term_id = body.get("term_id")
    fee_structure_id = body.get("fee_structure_id")
    if not pupil_id or not term_id or not fee_structure_id:
        return send_error(handler, "pupil_id, term_id and fee_structure_id are required")
    conn = get_db()
    pupil, term, item, amount_due, paid, outstanding = _get_fee_item_context(conn, pupil_id, term_id, fee_structure_id)
    if not pupil or not term or not item:
        conn.close()
        return send_error(handler, "Invalid pupil, term or fee item", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    if outstanding <= 0:
        conn.close()
        return send_error(handler, "This fee item has already been fully paid", 400)

    reference = f"GISL-{uuid.uuid4().hex[:12].upper()}"
    tx_id = str(uuid.uuid4())
    metadata = {
        "pupil_id": pupil_id,
        "term_id": term_id,
        "fee_structure_id": fee_structure_id,
        "pupil_name": f"{pupil['first_name']} {pupil['last_name']}",
        "fee_name": item["fee_name"],
        "source": "parent_portal"
    }
    authorization_url = ""
    access_code = ""
    status = "initialized"

    if PAYSTACK_SECRET_KEY:
        callback = PAYSTACK_CALLBACK_URL or f"{APP_URL}/index.html"
        try:
            paystack_resp = post_json(
                "https://api.paystack.co/transaction/initialize",
                {
                    "email": pupil["parent_email"] or user.get("email") or "parent@example.com",
                    "amount": int(round(outstanding * 100)),
                    "reference": reference,
                    "callback_url": callback,
                    "metadata": metadata,
                    "channels": ["card", "bank", "ussd", "bank_transfer"]
                },
                headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
            )
            if not paystack_resp.get("status"):
                raise Exception(paystack_resp.get("message") or "Unable to initialize Paystack transaction")
            pdata = paystack_resp.get("data") or {}
            authorization_url = pdata.get("authorization_url", "")
            access_code = pdata.get("access_code", "")
        except Exception as e:
            conn.close()
            return send_error(handler, f"Failed to initialize Paystack: {str(e)}", 502)
    else:
        status = "mock_initialized"

    conn.execute(
        """INSERT INTO online_payment_transactions
           (id, pupil_id, term_id, fee_structure_id, provider, reference, amount, status, access_code, authorization_url, metadata, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tx_id, pupil_id, term_id, fee_structure_id, "paystack", reference, outstanding, status,
         access_code, authorization_url, json_dumps(metadata), user["id"])
    )
    conn.commit()
    conn.close()
    send_json(handler, {
        "reference": reference,
        "amount": outstanding,
        "authorization_url": authorization_url,
        "access_code": access_code,
        "mock": not bool(PAYSTACK_SECRET_KEY),
        "fee_name": item["fee_name"],
        "pupil_name": metadata["pupil_name"]
    })

def handle_verify_online_payment(handler, user, body):
    reference = (body.get("reference") or "").strip()
    if not reference:
        return send_error(handler, "reference is required")
    conn = get_db()
    tx = conn.execute("SELECT * FROM online_payment_transactions WHERE reference=?", (reference,)).fetchone()
    if not tx:
        conn.close()
        return send_error(handler, "Transaction not found", 404)
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (tx["pupil_id"],)).fetchone()
    if not pupil or not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)

    payment_ok = False
    provider_payload = {}
    if PAYSTACK_SECRET_KEY:
        try:
            verify = get_json(f"https://api.paystack.co/transaction/verify/{quote(reference)}",
                              headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"})
            provider_payload = verify
            pdata = verify.get("data") or {}
            payment_ok = verify.get("status") and pdata.get("status") == "success"
        except Exception as e:
            conn.close()
            return send_error(handler, f"Failed to verify Paystack transaction: {str(e)}", 502)
    else:
        payment_ok = tx["status"] in ("initialized", "mock_initialized")
        provider_payload = {"mock": True, "message": "Local demo payment verified"}

    if not payment_ok:
        conn.execute("UPDATE online_payment_transactions SET status='failed', metadata=? WHERE id=?",
                     (json_dumps(provider_payload), tx["id"]))
        conn.commit()
        conn.close()
        return send_error(handler, "Payment not successful", 400)

    if tx["status"] != "paid":
        record_fee_payment_row(
            conn, user["id"], True, tx["pupil_id"], tx["term_id"], tx["fee_structure_id"],
            float(tx["amount"]), today_iso(), reference, "Online payment via Paystack"
        )
        conn.execute("UPDATE online_payment_transactions SET status='paid', paid_at=datetime('now'), metadata=? WHERE id=?",
                     (json_dumps(provider_payload), tx["id"]))
        if pupil:
            msg = f"Payment received: ₦{float(tx['amount']):,.2f} for {pupil['first_name']} {pupil['last_name']}. Ref: {reference}. Thank you."
            notify_parent_channels(dict(pupil), msg, event_type="fee_receipt", prefer_whatsapp=True, send_email=True)
    conn.commit()
    conn.close()
    write_audit(user, "verify_online_payment", target_type="payment", target_id=tx["id"], details=reference, ip=get_client_ip(handler))
    send_json(handler, {"message": "Payment verified successfully", "reference": reference, "amount": tx["amount"]})

def handle_get_attendance(handler, user, params):
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    attendance_date = params.get("date", [today_iso()])[0]
    class_id = params.get("class_id", [None])[0]
    conn = get_db()
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if not cls:
            conn.close()
            return send_json(handler, {"date": attendance_date, "records": []})
        class_id = cls["id"]
    if not class_id:
        conn.close()
        return send_error(handler, "class_id is required")
    term = get_current_term(conn)
    pupils = conn.execute(
        """SELECT p.id, p.first_name, p.last_name, p.parent_name, p.parent_phone, p.parent_email,
                  a.status as attendance_status, a.notes as attendance_notes
           FROM pupils p
           LEFT JOIN attendance_records a ON a.pupil_id=p.id AND a.attendance_date=?
           WHERE p.class_id=? AND p.status='active'
           ORDER BY p.last_name, p.first_name""",
        (attendance_date, class_id)
    ).fetchall()
    summary = {
        "present": sum(1 for r in pupils if r["attendance_status"] == "present"),
        "late": sum(1 for r in pupils if r["attendance_status"] == "late"),
        "absent": sum(1 for r in pupils if r["attendance_status"] == "absent"),
        "unmarked": sum(1 for r in pupils if not r["attendance_status"]),
    }
    conn.close()
    send_json(handler, {
        "date": attendance_date,
        "class_id": class_id,
        "term_id": term["id"] if term else None,
        "records": [dict(r) for r in pupils],
        "summary": summary
    })

def handle_mark_attendance(handler, user, body):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    class_id = body.get("class_id")
    attendance_date = body.get("date") or today_iso()
    records = body.get("records") or []
    if not class_id or not records:
        return send_error(handler, "class_id and records are required")
    conn = get_db()
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if not cls or cls["id"] != class_id:
            conn.close()
            return send_error(handler, "You can only mark attendance for your assigned class", 403)
    term = get_current_term(conn)
    saved = 0
    absent_alerts = 0
    for rec in records:
        pupil_id = rec.get("pupil_id")
        status = (rec.get("status") or "").strip().lower()
        if status not in ("present", "absent", "late"):
            continue
        aid = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO attendance_records
               (id, pupil_id, class_id, term_id, attendance_date, status, notes, marked_by)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(pupil_id, attendance_date) DO UPDATE SET
                   class_id=excluded.class_id,
                   term_id=excluded.term_id,
                   status=excluded.status,
                   notes=excluded.notes,
                   marked_by=excluded.marked_by,
                   updated_at=datetime('now')""",
            (aid, pupil_id, class_id, term["id"] if term else None, attendance_date, status, rec.get("notes", ""), user["id"])
        )
        saved += 1
        if status == "absent":
            pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
            if pupil:
                msg = f"Absence alert: {pupil['first_name']} {pupil['last_name']} was marked absent on {attendance_date}. Please contact the school if this is unexpected."
                notify_parent_channels(dict(pupil), msg, event_type="absence_alert", prefer_whatsapp=True, send_email=False)
                absent_alerts += 1
    conn.commit()
    conn.close()
    write_audit(user, "mark_attendance", target_type="class", target_id=class_id, details=f"{attendance_date} ({saved} records)", ip=get_client_ip(handler))
    send_json(handler, {"message": f"Attendance saved for {saved} pupil(s)", "alerts_sent": absent_alerts})

def handle_get_pupil_attendance(handler, user, pupil_id, params):
    conn = get_db()
    pupil = conn.execute("SELECT * FROM pupils WHERE id=?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    term_id = params.get("term_id", [None])[0]
    records = conn.execute(
        "SELECT attendance_date, status, notes FROM attendance_records WHERE pupil_id=? " + ("AND term_id=? " if term_id else "") + "ORDER BY attendance_date DESC LIMIT 30",
        (pupil_id, term_id) if term_id else (pupil_id,)
    ).fetchall()
    summary = calculate_attendance_summary(conn, pupil_id, term_id)
    conn.close()
    send_json(handler, {"pupil": dict(pupil), "summary": summary, "records": [dict(r) for r in records]})

def handle_get_analytics(handler, user, params):
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    term = get_current_term(conn)
    if not term:
        conn.close()
        return send_json(handler, {"subject_averages": [], "fee_collection": [], "performance": []})
    class_id = params.get("class_id", [None])[0]
    if user["role"] == "teacher":
        class_id = get_teacher_class_id(conn, user["id"])
        if not class_id:
            conn.close()
            return send_json(handler, {"subject_averages": [], "fee_collection": [], "top_performers": [], "bottom_performers": []})
    subject_args = [term["id"]]
    class_filter = ""
    if class_id:
        class_filter = " AND p.class_id=?"
        subject_args.append(class_id)
    subject_averages = conn.execute(
        f"""SELECT c.name as class_name, s.name as subject_name, ROUND(AVG(r.ca_score + r.exam_score), 2) as average_score
             FROM results r
             JOIN pupils p ON p.id=r.pupil_id
             JOIN classes c ON c.id=p.class_id
             JOIN subjects s ON s.id=r.subject_id
             WHERE r.term_id=? {class_filter}
             GROUP BY c.id, s.id
             ORDER BY c.level, s.sort_order""",
        subject_args
    ).fetchall()
    fee_query = """SELECT c.name as class_name,
                  ROUND(COALESCE(SUM(CASE WHEN prior.payment_count=0 THEN fs.new_pupil_amount ELSE fs.returning_pupil_amount END),0),2) as expected_total,
                  ROUND(COALESCE(SUM(fp.amount_paid),0),2) as collected_total
           FROM classes c
           LEFT JOIN pupils p ON p.class_id=c.id AND p.status='active'
           LEFT JOIN terms t ON t.id=?
           LEFT JOIN fee_structures fs ON (fs.class_id=c.id OR fs.class_id IS NULL) AND fs.academic_year=t.academic_year AND fs.term_number=t.term_number
           LEFT JOIN (
               SELECT pupil_id, COUNT(*) as payment_count FROM fee_payments GROUP BY pupil_id
           ) prior ON prior.pupil_id=p.id
           LEFT JOIN fee_payments fp ON fp.pupil_id=p.id AND fp.term_id=t.id AND fp.fee_structure_id=fs.id
    """
    fee_args = [term["id"]]
    if class_id:
        fee_query += " WHERE c.id=?"
        fee_args.append(class_id)
    fee_query += " GROUP BY c.id ORDER BY c.level"
    fee_collection = conn.execute(fee_query, fee_args).fetchall()

    perf_query = """SELECT p.id as pupil_id, p.first_name, p.last_name, c.name as class_name,
                  ROUND(SUM(r.ca_score + r.exam_score),2) as total_score,
                  ROUND(AVG(r.ca_score + r.exam_score),2) as average_score
           FROM pupils p
           JOIN classes c ON c.id=p.class_id
           LEFT JOIN results r ON r.pupil_id=p.id AND r.term_id=?
           WHERE p.status='active'
    """
    perf_args = [term["id"]]
    if class_id:
        perf_query += " AND p.class_id=?"
        perf_args.append(class_id)
    perf_query += " GROUP BY p.id HAVING COUNT(r.id) > 0 ORDER BY average_score DESC"
    performance = conn.execute(perf_query, perf_args).fetchall()
    top = [dict(r) for r in performance[:5]]
    bottom = [dict(r) for r in performance[-5:]] if performance else []
    conn.close()
    send_json(handler, {
        "term": dict(term),
        "subject_averages": [dict(r) for r in subject_averages],
        "fee_collection": [dict(r) for r in fee_collection],
        "top_performers": top,
        "bottom_performers": bottom
    })

def handle_get_homework(handler, user, params):
    conn = get_db()
    class_id = params.get("class_id", [None])[0]
    pupil_id = params.get("pupil_id", [None])[0]
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        class_id = cls["id"] if cls else class_id
    if user["role"] == "parent":
        if pupil_id:
            pupil = conn.execute("SELECT * FROM pupils WHERE id=? AND parent_email=?", (pupil_id, user["email"])).fetchone()
        else:
            pupil = conn.execute("SELECT * FROM pupils WHERE parent_email=? AND status='active' ORDER BY created_at LIMIT 1", (user["email"],)).fetchone()
        if not pupil:
            conn.close()
            return send_json(handler, [])
        pupil_id = pupil["id"]
        class_id = pupil["class_id"]
    if not class_id:
        if user["role"] == "admin":
            rows = conn.execute(
                """SELECT h.*, s.name as subject_name, c.name as class_name,
                          NULL as is_done, NULL as parent_note, NULL as done_at
                   FROM homework_assignments h
                   LEFT JOIN subjects s ON s.id=h.subject_id
                   LEFT JOIN classes c ON c.id=h.class_id
                   WHERE h.is_active=1
                   ORDER BY COALESCE(h.due_date, h.created_at) DESC, h.created_at DESC"""
            ).fetchall()
            conn.close()
            return send_json(handler, [dict(r) for r in rows])
        conn.close()
        return send_json(handler, [])
    rows = conn.execute(
        """SELECT h.*, s.name as subject_name, c.name as class_name,
                  hc.is_done, hc.parent_note, hc.done_at
           FROM homework_assignments h
           LEFT JOIN subjects s ON s.id=h.subject_id
           LEFT JOIN classes c ON c.id=h.class_id
           LEFT JOIN homework_completions hc ON hc.assignment_id=h.id AND hc.pupil_id=?
           WHERE h.class_id=? AND h.is_active=1
           ORDER BY COALESCE(h.due_date, h.created_at) DESC, h.created_at DESC""",
        (pupil_id or "", class_id)
    ).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_save_homework(handler, user, body, homework_id=None):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    class_id = body.get("class_id")
    title = (body.get("title") or "").strip()
    if not class_id or not title:
        return send_error(handler, "class_id and title are required")
    conn = get_db()
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if not cls or cls["id"] != class_id:
            conn.close()
            return send_error(handler, "You can only manage homework for your class", 403)
    hid = homework_id or str(uuid.uuid4())
    if homework_id:
        conn.execute(
            """UPDATE homework_assignments SET class_id=?, subject_id=?, term_id=?, title=?, description=?, due_date=?, is_active=?, updated_at=datetime('now')
               WHERE id=?""",
            (class_id, body.get("subject_id"), body.get("term_id"), title, body.get("description", ""), body.get("due_date", ""), 1 if body.get("is_active", True) else 0, homework_id)
        )
    else:
        conn.execute(
            """INSERT INTO homework_assignments (id, class_id, subject_id, term_id, title, description, due_date, created_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (hid, class_id, body.get("subject_id"), body.get("term_id"), title, body.get("description", ""), body.get("due_date", ""), user["id"])
        )
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Homework saved", "id": hid})

def handle_delete_homework(handler, user, homework_id):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    conn.execute("UPDATE homework_assignments SET is_active=0, updated_at=datetime('now') WHERE id=?", (homework_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Homework archived"})

def handle_toggle_homework_completion(handler, user, homework_id, body):
    if user["role"] != "parent":
        return send_error(handler, "Forbidden", 403)
    pupil_id = body.get("pupil_id")
    pupil = None
    conn = get_db()
    if pupil_id:
        pupil = conn.execute("SELECT * FROM pupils WHERE id=? AND parent_email=?", (pupil_id, user["email"])).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    cid = str(uuid.uuid4())
    is_done = 1 if body.get("is_done") else 0
    conn.execute(
        """INSERT INTO homework_completions (id, assignment_id, pupil_id, is_done, parent_note, done_at)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(assignment_id, pupil_id) DO UPDATE SET
               is_done=excluded.is_done,
               parent_note=excluded.parent_note,
               done_at=excluded.done_at,
               updated_at=datetime('now')""",
        (cid, homework_id, pupil_id, is_done, body.get("parent_note", ""), datetime.now().isoformat() if is_done else None)
    )
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Homework status updated"})

def handle_get_events(handler, user, params):
    conn = get_db()
    target = params.get("target", [None])[0]
    query = "SELECT * FROM school_events WHERE 1=1"
    args = []
    if user["role"] == "parent":
        query += " AND (target='all' OR target='parents')"
    elif target:
        query += " AND target=?"
        args.append(target)
    query += " ORDER BY event_date ASC"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_save_event(handler, user, body, event_id=None):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    title = (body.get("title") or "").strip()
    event_date = (body.get("event_date") or "").strip()
    if not title or not event_date:
        return send_error(handler, "title and event_date are required")
    conn = get_db()
    eid = event_id or str(uuid.uuid4())
    if event_id:
        conn.execute(
            "UPDATE school_events SET title=?, description=?, event_date=?, end_date=?, event_type=?, target=? WHERE id=?",
            (title, body.get("description", ""), event_date, body.get("end_date", ""), body.get("event_type", "general"), body.get("target", "all"), event_id)
        )
    else:
        conn.execute(
            "INSERT INTO school_events (id, title, description, event_date, end_date, event_type, target, created_by) VALUES (?,?,?,?,?,?,?,?)",
            (eid, title, body.get("description", ""), event_date, body.get("end_date", ""), body.get("event_type", "general"), body.get("target", "all"), user["id"])
        )
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Event saved", "id": eid})

def handle_delete_event(handler, user, event_id):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    conn.execute("DELETE FROM school_events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Event deleted"})

def handle_get_timetable(handler, user, params):
    conn = get_db()
    class_id = params.get("class_id", [None])[0]
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        class_id = cls["id"] if cls else class_id
    elif user["role"] == "parent":
        pupil_id = params.get("pupil_id", [None])[0]
        pupil = None
        if pupil_id:
            pupil = conn.execute("SELECT * FROM pupils WHERE id=? AND parent_email=?", (pupil_id, user["email"])).fetchone()
        if not pupil:
            pupil = conn.execute("SELECT * FROM pupils WHERE parent_email=? AND status='active' ORDER BY first_name LIMIT 1", (user["email"],)).fetchone()
        class_id = pupil["class_id"] if pupil else None
    if not class_id:
        conn.close()
        return send_json(handler, [])
    rows = conn.execute(
        """SELECT tt.*, s.name as subject_name, c.name as class_name
           FROM class_timetables tt
           LEFT JOIN subjects s ON s.id=tt.subject_id
           LEFT JOIN classes c ON c.id=tt.class_id
           WHERE tt.class_id=?
           ORDER BY CASE tt.day_of_week
                        WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 ELSE 6 END,
                    tt.start_time, tt.period_name""",
        (class_id,)
    ).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_save_timetable(handler, user, body, timetable_id=None):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    class_id = body.get("class_id")
    day_of_week = body.get("day_of_week")
    if not class_id or not day_of_week:
        return send_error(handler, "class_id and day_of_week are required")
    conn = get_db()
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if not cls or cls["id"] != class_id:
            conn.close()
            return send_error(handler, "You can only update your class timetable", 403)
    tid = timetable_id or str(uuid.uuid4())
    if timetable_id:
        conn.execute(
            "UPDATE class_timetables SET class_id=?, day_of_week=?, period_name=?, subject_id=?, start_time=?, end_time=?, teacher_name=?, location=? WHERE id=?",
            (class_id, day_of_week, body.get("period_name", ""), body.get("subject_id"), body.get("start_time", ""), body.get("end_time", ""), body.get("teacher_name", ""), body.get("location", ""), timetable_id)
        )
    else:
        conn.execute(
            "INSERT INTO class_timetables (id, class_id, day_of_week, period_name, subject_id, start_time, end_time, teacher_name, location) VALUES (?,?,?,?,?,?,?,?,?)",
            (tid, class_id, day_of_week, body.get("period_name", ""), body.get("subject_id"), body.get("start_time", ""), body.get("end_time", ""), body.get("teacher_name", ""), body.get("location", ""))
        )
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Timetable saved", "id": tid})

def handle_delete_timetable(handler, user, timetable_id):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    conn.execute("DELETE FROM class_timetables WHERE id=?", (timetable_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Timetable entry deleted"})

def handle_rollover(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
    current_term = get_current_term(conn)
    current_year = current_term["academic_year"] if current_term else f"{datetime.now().year}/{datetime.now().year + 1}"
    try:
        start_year = int(current_year.split("/")[0])
        next_year = body.get("next_academic_year") or f"{start_year + 1}/{start_year + 2}"
    except Exception:
        next_year = body.get("next_academic_year") or current_year

    classes = conn.execute("SELECT * FROM classes ORDER BY class_type DESC, level DESC").fetchall()
    promoted = 0
    graduated = 0
    primary1 = conn.execute("SELECT id FROM classes WHERE class_type='primary' AND level=1 LIMIT 1").fetchone()
    class_map = {(c["class_type"], c["level"]): c["id"] for c in classes}
    for cls in classes:
        if (cls["class_type"] or "primary") == "primary" and cls["level"] >= 6:
            conn.execute("UPDATE pupils SET status='graduated', class_id=NULL, updated_at=datetime('now') WHERE class_id=? AND status='active'", (cls["id"],))
            graduated += conn.execute("SELECT changes()").fetchone()[0]
        elif (cls["class_type"] or "primary") == "lower" and cls["level"] >= 3 and primary1:
            conn.execute("UPDATE pupils SET class_id=?, updated_at=datetime('now') WHERE class_id=? AND status='active'", (primary1["id"], cls["id"]))
            promoted += conn.execute("SELECT changes()").fetchone()[0]
        else:
            next_id = class_map.get((cls["class_type"] or "primary", cls["level"] + 1))
            if next_id:
                conn.execute("UPDATE pupils SET class_id=?, updated_at=datetime('now') WHERE class_id=? AND status='active'", (next_id, cls["id"]))
                promoted += conn.execute("SELECT changes()").fetchone()[0]
    conn.execute("UPDATE terms SET is_current=0")
    for term_number in (1, 2, 3):
        existing = conn.execute("SELECT id FROM terms WHERE academic_year=? AND term_number=?", (next_year, term_number)).fetchone()
        if existing:
            if term_number == 1:
                conn.execute("UPDATE terms SET is_current=1 WHERE id=?", (existing["id"],))
            continue
        conn.execute(
            "INSERT INTO terms (id, academic_year, term_number, is_current) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), next_year, term_number, 1 if term_number == 1 else 0)
        )
    conn.commit()
    conn.close()
    write_audit(user, "rollover_year", details=f"Next year {next_year}", ip=get_client_ip(handler))
    send_json(handler, {"message": f"Rollover completed for {next_year}", "promoted": promoted, "graduated": graduated})

def handle_get_payroll(handler, user, params):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    month = params.get("month", [None])[0]
    year = params.get("year", [None])[0]
    conn = get_db()
    query = """SELECT pe.*, u.name as staff_name, u.email as staff_email
               FROM payroll_entries pe JOIN users u ON u.id=pe.staff_id WHERE 1=1"""
    args = []
    if month:
        query += " AND pe.month=?"
        args.append(int(month))
    if year:
        query += " AND pe.year=?"
        args.append(int(year))
    query += " ORDER BY pe.year DESC, pe.month DESC, u.name"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_save_payroll(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    staff_id = body.get("staff_id")
    month = body.get("month")
    year = body.get("year")
    if not staff_id or not month or not year:
        return send_error(handler, "staff_id, month and year are required")
    basic = float(body.get("basic_salary", 0) or 0)
    allowances = float(body.get("allowances", 0) or 0)
    deductions = float(body.get("deductions", 0) or 0)
    net_pay = basic + allowances - deductions
    conn = get_db()
    pid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO payroll_entries (id, staff_id, month, year, basic_salary, allowances, deductions, net_pay, notes, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(staff_id, month, year) DO UPDATE SET
              basic_salary=excluded.basic_salary,
              allowances=excluded.allowances,
              deductions=excluded.deductions,
              net_pay=excluded.net_pay,
              notes=excluded.notes,
              created_by=excluded.created_by""",
        (pid, staff_id, int(month), int(year), basic, allowances, deductions, net_pay, body.get("notes", ""), user["id"])
    )
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Payroll saved", "net_pay": net_pay})

def handle_broadcast(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Forbidden", 403)
    message = (body.get("message") or "").strip()
    target = body.get("target") or "all_parents"
    channel = body.get("channel") or "sms_whatsapp"
    class_id = body.get("class_id")
    if not message:
        return send_error(handler, "message is required")
    conn = get_db()
    query = "SELECT DISTINCT parent_name, parent_phone, parent_email FROM pupils WHERE status='active'"
    args = []
    if target == "class" and class_id:
        query += " AND class_id=?"
        args.append(class_id)
    elif target == "debtors_only":
        current = get_current_term(conn)
        if current:
            query = """SELECT DISTINCT p.parent_name, p.parent_phone, p.parent_email
                       FROM pupils p
                       WHERE p.status='active' AND EXISTS (
                           SELECT 1 FROM fee_structures fs
                           LEFT JOIN fee_payments fp ON fp.pupil_id=p.id AND fp.term_id=? AND fp.fee_structure_id=fs.id
                           WHERE fs.academic_year=? AND fs.term_number=? AND (fs.class_id=p.class_id OR fs.class_id IS NULL)
                           GROUP BY fs.id
                           HAVING COALESCE(SUM(fp.amount_paid),0) < MAX(CASE WHEN (
                               SELECT COUNT(*) FROM fee_payments prev WHERE prev.pupil_id=p.id
                           )=0 THEN fs.new_pupil_amount ELSE fs.returning_pupil_amount END)
                       )"""
            args = [current["id"], current["academic_year"], current["term_number"]]
    recipients = [dict(r) for r in conn.execute(query, args).fetchall()]
    conn.close()
    sent = 0
    for rec in recipients:
        if channel in ("whatsapp", "sms_whatsapp"):
            send_whatsapp(rec.get("parent_phone"), message, rec.get("parent_name"), rec.get("parent_email"), event_type="broadcast")
        if channel in ("sms", "sms_whatsapp"):
            send_sms(rec.get("parent_phone"), message, rec.get("parent_name"), rec.get("parent_email"), event_type="broadcast")
        if channel == "email":
            send_email_async(rec.get("parent_email"), "GISL Schools Notice", f"<p>{message}</p>")
        sent += 1
    write_audit(user, "broadcast_message", details=f"{target} ({sent} recipients)", ip=get_client_ip(handler))
    send_json(handler, {"message": f"Broadcast queued for {sent} recipient(s)"})

def handle_publish_results(handler, user, body):
    if user["role"] not in ("admin", "teacher"):
        return send_error(handler, "Forbidden", 403)
    term_id = body.get("term_id")
    class_id = body.get("class_id")
    pupil_id = body.get("pupil_id")
    if not term_id:
        return send_error(handler, "term_id is required")
    conn = get_db()
    if user["role"] == "teacher":
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        class_id = cls["id"] if cls else class_id
    query = "SELECT DISTINCT p.* FROM pupils p JOIN results r ON r.pupil_id=p.id WHERE r.term_id=?"
    args = [term_id]
    if class_id:
        query += " AND p.class_id=?"
        args.append(class_id)
    if pupil_id:
        query += " AND p.id=?"
        args.append(pupil_id)
    pupils = conn.execute(query, args).fetchall()
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    conn.close()
    count = 0
    for pupil in pupils:
        msg = f"Results published for {pupil['first_name']} {pupil['last_name']} — {term['academic_year']} Term {term['term_number']}. Please log in to the parent portal to review them."
        notify_parent_channels(dict(pupil), msg, event_type="results_published", prefer_whatsapp=True, send_email=True)
        count += 1
    write_audit(user, "publish_results", details=f"{count} parent notification(s)", ip=get_client_ip(handler))
    send_json(handler, {"message": f"Results published to {count} parent(s)"})

def _pdf_grade(total):
    if total is None: return '—'
    if total >= 85: return 'A+'
    if total >= 75: return 'B+'
    if total >= 60: return 'B'
    if total >= 50: return 'C'
    if total >= 40: return 'D'
    return 'E'

def _pdf_rating_text(val):
    mapping = {'E': 'Excellent', 'VG': 'Very Good', 'G': 'Good', 'F': 'Fair', 'P': 'Poor'}
    return mapping.get((val or '').upper(), val or '—')

def build_report_pdf_html(pupil, term, report_data):
    TD = "padding:4px 6px;border:1px solid #ccc;font-size:9pt"
    TH = "padding:4px 6px;border:1px solid #999;font-size:9pt;background:#f9f5f5;font-weight:bold"
    SUBJ_TD = "padding:4px 6px;border:1px solid #ccc;font-size:9pt;white-space:nowrap"

    is_cumulative = report_data.get("is_cumulative", False)
    prev = report_data.get("prev_term_results", {})
    results = report_data.get("results", [])
    conduct = report_data.get("conduct", {})
    att = report_data.get("attendance_summary", {})
    num_subjects = report_data.get("num_subjects", len(results))
    grand_total = report_data.get("grand_total", 0)
    avg_per_subject = report_data.get("avg_per_subject", 0)
    position = report_data.get("position")
    total_in_class = report_data.get("total_in_class")
    least_avg = report_data.get("least_class_avg")
    max_avg = report_data.get("max_class_avg")
    max_total = report_data.get("max_total", num_subjects * 100)
    age = report_data.get("age", "")

    term_num = term.get("term_number", 1)
    ordinals = {1: "1ST", 2: "2ND", 3: "3RD"}
    cur_ord = ordinals.get(term_num, f"{term_num}TH")

    pupil_name = f"{pupil.get('last_name','').upper()}, {pupil.get('first_name','')} {pupil.get('other_name','') or ''}".strip()

    # Build results rows
    result_rows_html = ""
    for i, r in enumerate(results):
        sid = r.get("subject_id", "")
        ca = r.get("ca_score")
        exam = r.get("exam_score")
        cur_total = (ca or 0) + (exam or 0)
        row_bg = "#fafafa" if i % 2 == 0 else "white"

        if is_cumulative:
            t1 = prev.get("1", {}).get(sid)
            t2 = prev.get("2", {}).get(sid)
            vals_for_avg = [v for v in [t1, t2, cur_total] if v is not None]
            avg_total = round(sum(vals_for_avg) / len(vals_for_avg), 2) if vals_for_avg else None
            grade = _pdf_grade(avg_total)
            pos = r.get("position_in_subject", "—")
            cls_avg = r.get("class_subject_average")
            result_rows_html += f"""<tr style="background:{row_bg}">
              <td style="{SUBJ_TD}">{r.get('subject_name','')}</td>
              <td style="{TD};text-align:center">{ca if ca is not None else '—'}</td>
              <td style="{TD};text-align:center">{exam if exam is not None else '—'}</td>
              <td style="{TD};text-align:center;font-weight:bold">{cur_total or '—'}</td>
              <td style="{TD};text-align:center">{t2 if t2 is not None else '—'}</td>
              <td style="{TD};text-align:center">{t1 if t1 is not None else '—'}</td>
              <td style="{TD};text-align:center;font-weight:bold">{avg_total if avg_total is not None else '—'}</td>
              <td style="{TD};text-align:center">{pos}</td>
              <td style="{TD};text-align:center;font-weight:bold;color:#7B1D1D">{grade}</td>
              <td style="{TD};text-align:center">{f'{cls_avg:.1f}' if cls_avg is not None else '—'}</td>
            </tr>"""
        else:
            grade = _pdf_grade(cur_total)
            pos = r.get("position_in_subject", "—")
            cls_avg = r.get("class_subject_average")
            result_rows_html += f"""<tr style="background:{row_bg}">
              <td style="{SUBJ_TD}">{r.get('subject_name','')}</td>
              <td style="{TD};text-align:center">{ca if ca is not None else '—'}</td>
              <td style="{TD};text-align:center">{exam if exam is not None else '—'}</td>
              <td style="{TD};text-align:center;font-weight:bold">{cur_total or '—'}</td>
              <td style="{TD};text-align:center">{pos}</td>
              <td style="{TD};text-align:center;font-weight:bold;color:#7B1D1D">{grade}</td>
              <td style="{TD};text-align:center">{f'{cls_avg:.1f}' if cls_avg is not None else '—'}</td>
            </tr>"""

    if is_cumulative:
        table_header = f"""<tr style="background:#7B1D1D;color:white">
          <th style="{TH};background:#7B1D1D;color:white;text-align:left">Subjects</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Test (40)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Exam (60)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">{cur_ord} Total(%)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">2ND Total(%)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">1ST Total(%)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Total Avg (%)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Position</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Grade</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Class (%) Avg</th>
        </tr>"""
    else:
        table_header = f"""<tr style="background:#7B1D1D;color:white">
          <th style="{TH};background:#7B1D1D;color:white;text-align:left">Subjects</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Test (40)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Exam (60)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">{cur_ord} Total(%)</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Position</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Grade</th>
          <th style="{TH};background:#7B1D1D;color:white;text-align:center">Class (%) Avg</th>
        </tr>"""

    conduct_rows = "".join(
        f"<tr><td style='{TD};width:52%'>{label}</td><td style='{TD}'>{_pdf_rating_text(conduct.get(key,''))}</td></tr>"
        for label, key in [
            ("Punctuality", "punctuality"), ("Honesty", "honesty"), ("Cleanliness", "cleanliness"),
            ("Leadership", "leadership"), ("Politeness", "politeness"), ("Attentiveness", "attentiveness"),
        ]
    )
    skill_rows = "".join(
        f"<tr><td style='{TD};width:52%'>{label}</td><td style='{TD}'>{_pdf_rating_text(conduct.get(key,''))}</td></tr>"
        for label, key in [
            ("H/Writing", "writing"), ("Handwork", "handwork"), ("Verbal Fluency", "verbal_fluency"),
            ("Drama", "drama"), ("Sports", "sports"),
        ]
    )

    pos_str = f"{position}/{total_in_class}" if position and total_in_class else "—"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 9pt; color: #222; margin: 0; padding: 8px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  .header-box {{ border: 2px solid #7B1D1D; border-radius: 4px; padding: 6px 10px; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }}
  .school-name {{ font-size: 13pt; font-weight: 800; color: #7B1D1D; text-transform: uppercase; }}
  .section-title {{ background: #7B1D1D; color: white; padding: 3px 8px; font-weight: bold; font-size: 9pt; }}
  .stat-label {{ font-size: 8pt; color: #666; }}
  .stat-val {{ font-weight: bold; color: #7B1D1D; }}
  .grading {{ font-size: 8pt; }}
</style>
</head><body>

<!-- HEADER -->
<div class="header-box">
  <div style="flex:1;text-align:center">
    <div class="school-name">GISL Daycare Nursery &amp; Primary School</div>
    <div style="font-size:8pt;color:#666">3 Oludemi Adeniba Street, Atarere Layout, Off Tern id ire Shopping Complex, Ibadan</div>
    <div style="font-size:8pt;color:#666">Tel: 08033299074, 09151404619, 08033295403</div>
    <div style="font-size:8pt;font-style:italic;color:#7B1D1D">The Light of Knowledge</div>
  </div>
  <div style="text-align:center;border:2px solid #7B1D1D;padding:4px 8px;border-radius:3px;flex-shrink:0">
    <div style="font-weight:bold;color:#7B1D1D;font-size:10pt">PUPIL'S RESULT</div>
    <div style="font-size:8pt">{term.get('academic_year','')} — Term {term_num}</div>
  </div>
</div>

<!-- PUPIL INFO -->
<table style="margin-bottom:6px;font-size:9pt">
  <tr>
    <td style="padding:2px 8px;width:30%"><span class="stat-label">Name:</span> <strong>{pupil_name}</strong></td>
    <td style="padding:2px 8px;width:20%"><span class="stat-label">Student No:</span> <strong>{pupil.get('admission_number','—')}</strong></td>
    <td style="padding:2px 8px;width:15%"><span class="stat-label">Sex:</span> {pupil.get('gender','—')}</td>
    <td style="padding:2px 8px;width:15%"><span class="stat-label">Term:</span> {cur_ord}</td>
    <td style="padding:2px 8px;width:20%"><span class="stat-label">Session:</span> {term.get('academic_year','')}</td>
  </tr>
  <tr>
    <td style="padding:2px 8px"><span class="stat-label">Class:</span> {pupil.get('class_name','—')}</td>
    <td style="padding:2px 8px" colspan="2"><span class="stat-label">Age:</span> {age or '—'}</td>
    <td style="padding:2px 8px" colspan="2"><span class="stat-label">Attendance:</span> {att.get('present',0)} present / {att.get('absent',0)} absent</td>
  </tr>
</table>

<!-- RESULTS TABLE + RIGHT PANEL -->
<div style="display:flex;gap:8px;margin-bottom:6px">
  <div style="flex:1;overflow:hidden">
    <div class="section-title">Academic Performance</div>
    <table>
      {table_header}
      {result_rows_html}
    </table>
  </div>
  <div style="width:200px;flex-shrink:0">
    <div class="section-title" style="margin-bottom:4px">Summary</div>
    <table style="font-size:9pt;margin-bottom:6px">
      <tr><td style="{TD};width:60%" class="stat-label">No of Subjects</td><td style="{TD};font-weight:bold">{num_subjects}</td></tr>
      <tr><td style="{TD}" class="stat-label">Total Obtainable</td><td style="{TD};font-weight:bold">{max_total}</td></tr>
      <tr><td style="{TD}" class="stat-label">Total Obtained</td><td style="{TD};font-weight:bold">{grand_total}</td></tr>
      <tr><td style="{TD}" class="stat-label">No. in Class</td><td style="{TD};font-weight:bold">{total_in_class or '—'}</td></tr>
      <tr><td style="{TD}" class="stat-label">Position</td><td style="{TD};font-weight:bold;color:#7B1D1D">{pos_str}</td></tr>
      <tr><td style="{TD}" class="stat-label">Student Avg (%)</td><td style="{TD};font-weight:bold">{avg_per_subject}</td></tr>
      <tr><td style="{TD}" class="stat-label">Least Class Avg</td><td style="{TD}">{f'{least_avg:.2f}' if least_avg is not None else '—'}</td></tr>
      <tr><td style="{TD}" class="stat-label">Max Class Avg</td><td style="{TD}">{f'{max_avg:.2f}' if max_avg is not None else '—'}</td></tr>
    </table>
    <div class="section-title" style="margin-bottom:2px">Observations on Conduct</div>
    <table style="margin-bottom:6px">{conduct_rows}</table>
    <div class="section-title" style="margin-bottom:2px">Performance in Physical Skills</div>
    <table>{skill_rows}</table>
  </div>
</div>

<!-- COMMENTS -->
<div style="display:flex;gap:8px;margin-bottom:6px">
  <div style="flex:1;border:1px solid #ccc;padding:4px 8px">
    <div style="font-weight:bold;font-size:9pt;color:#7B1D1D;margin-bottom:2px">Teacher's Comment:</div>
    <div style="min-height:18px;font-size:9pt">{conduct.get('teacher_comment','') or '—'}</div>
    <div style="border-top:1px solid #333;margin-top:6px;font-size:8pt;color:#888">Signature &amp; Date</div>
  </div>
  <div style="flex:1;border:1px solid #ccc;padding:4px 8px">
    <div style="font-weight:bold;font-size:9pt;color:#7B1D1D;margin-bottom:2px">Administrator's Comment:</div>
    <div style="min-height:18px;font-size:9pt">{conduct.get('admin_comment','') or '—'}</div>
    <div style="border-top:1px solid #333;margin-top:6px;font-size:8pt;color:#888">Signature &amp; Date</div>
  </div>
</div>

<!-- GRADING + FOOTER -->
<div style="border:1px solid #ccc;padding:4px 10px;background:#fafafa;display:flex;justify-content:space-between;align-items:center">
  <div class="grading">
    <strong>Grading:</strong>
    A+ →85–100% &nbsp;:: B+ →75–84.9% &nbsp;:: B →60–74.9% &nbsp;:: C →50–59.9% &nbsp;:: D →40–49.9% &nbsp;:: E →0–39.9%
  </div>
  <div style="text-align:center;border:2px solid #7B1D1D;border-radius:50%;width:44px;height:44px;display:flex;align-items:center;justify-content:center;transform:rotate(-10deg);flex-shrink:0">
    <span style="font-size:7pt;font-weight:800;color:#7B1D1D;text-align:center;line-height:1.2">GOVT.<br/>APPROVED</span>
  </div>
</div>

</body></html>"""

def handle_download_report_pdf(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("SELECT p.*, c.name as class_name FROM pupils p LEFT JOIN classes c ON c.id=p.class_id WHERE p.id=?", (pupil_id,)).fetchone()
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    if not pupil or not term:
        conn.close()
        return send_error(handler, "Pupil or term not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    my_results = conn.execute(
        "SELECT s.name as subject_name, s.id as subject_id, r.ca_score, r.exam_score, (r.ca_score+r.exam_score) as total "
        "FROM results r JOIN subjects s ON s.id=r.subject_id WHERE r.pupil_id=? AND r.term_id=? ORDER BY s.sort_order",
        (pupil_id, term_id)
    ).fetchall()
    progress = conn.execute(
        """SELECT t.academic_year, t.term_number, ROUND(SUM(r.ca_score+r.exam_score),2) as total_score, ROUND(AVG(r.ca_score+r.exam_score),2) as average_score
           FROM results r JOIN terms t ON t.id=r.term_id WHERE r.pupil_id=? GROUP BY t.id ORDER BY t.academic_year DESC, t.term_number DESC LIMIT 3""",
        (pupil_id,)
    ).fetchall()
    progress = list(reversed(progress))
    attendance = calculate_attendance_summary(conn, pupil_id, term_id)

    # Conduct for PDF
    conduct_row = conn.execute("SELECT * FROM conduct_ratings WHERE pupil_id=? AND term_id=?", (pupil_id, term_id)).fetchone()

    # Class stats
    class_id = pupil["class_id"]
    all_grand_totals = {}
    if class_id and my_results:
        all_class = conn.execute(
            "SELECT r.pupil_id, SUM(r.ca_score+r.exam_score) as grand FROM results r "
            "JOIN pupils p ON p.id=r.pupil_id WHERE r.term_id=? AND p.class_id=? AND p.status='active' GROUP BY r.pupil_id",
            (term_id, class_id)
        ).fetchall()
        for row in all_class:
            all_grand_totals[row["pupil_id"]] = row["grand"] or 0
    my_grand = sum((r["total"] or 0) for r in my_results)
    num_subjects = len(my_results)
    class_position = sum(1 for v in all_grand_totals.values() if v > my_grand) + 1 if all_grand_totals else None
    total_in_class = len(all_grand_totals)
    least_class_avg = round(min(all_grand_totals.values()) / num_subjects, 2) if all_grand_totals and num_subjects else None
    max_class_avg = round(max(all_grand_totals.values()) / num_subjects, 2) if all_grand_totals and num_subjects else None
    avg_per_subject = round(my_grand / num_subjects, 2) if num_subjects else 0

    # For Term 3 cumulative
    prev_term_results = {}
    if term["term_number"] == 3:
        prev_terms = conn.execute(
            "SELECT * FROM terms WHERE academic_year=? AND term_number IN (1,2) ORDER BY term_number",
            (term["academic_year"],)
        ).fetchall()
        for pt in prev_terms:
            pt_rows = conn.execute(
                "SELECT (r.ca_score + r.exam_score) as total, s.id as subject_id "
                "FROM results r JOIN subjects s ON s.id=r.subject_id WHERE r.pupil_id=? AND r.term_id=?",
                (pupil_id, pt["id"])
            ).fetchall()
            prev_term_results[str(pt["term_number"])] = {r["subject_id"]: r["total"] for r in pt_rows}

    dob = pupil["date_of_birth"]
    age_str = ""
    if dob:
        try:
            from datetime import date as _date
            b = _date.fromisoformat(dob)
            today = _date.today()
            years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
            months = (today.month - b.month) % 12
            age_str = f"{years} Years {months} Months" if months else f"{years} Years"
        except Exception:
            pass

    report_data = {
        "results": [dict(r) for r in my_results],
        "grand_total": round(my_grand, 2),
        "avg_per_subject": avg_per_subject,
        "percentage": round(my_grand / (num_subjects * 100) * 100, 2) if num_subjects else 0,
        "attendance_summary": attendance,
        "progress_history": [{**dict(r), "label": f"{r['academic_year']} T{r['term_number']}"} for r in progress],
        "conduct": dict(conduct_row) if conduct_row else {},
        "position": class_position,
        "total_in_class": total_in_class,
        "num_subjects": num_subjects,
        "max_total": num_subjects * 100,
        "least_class_avg": least_class_avg,
        "max_class_avg": max_class_avg,
        "prev_term_results": prev_term_results,
        "is_cumulative": bool(prev_term_results),
        "age": age_str,
    }
    conn.close()
    pdf_bytes, err = render_pdf_bytes(build_report_pdf_html(dict(pupil), dict(term), report_data), base_url=STATIC_DIR)
    if err:
        return send_error(handler, err, 500)
    send_pdf(handler, pdf_bytes, f"report_{pupil['last_name']}_{term['academic_year'].replace('/','-')}_term{term['term_number']}.pdf")

def build_receipt_pdf_html(pupil, term, payments):
    total = sum(float(p["amount_paid"] or 0) for p in payments)
    rows = "".join(
        f"<tr><td style='padding:6px;border:1px solid #ddd'>{p['fee_name']}</td><td style='padding:6px;border:1px solid #ddd'>{p.get('payment_reference','')}</td><td style='padding:6px;border:1px solid #ddd'>{p.get('payment_date','')}</td><td style='padding:6px;border:1px solid #ddd;text-align:right'>₦{float(p['amount_paid']):,.2f}</td></tr>"
        for p in payments
    ) or "<tr><td colspan='4' style='padding:6px;border:1px solid #ddd'>No payments recorded</td></tr>"
    return f"""<html><body style='font-family:Arial,sans-serif;color:#222'>
    <h1 style='color:#7B1D1D'>GISL Schools Fee Receipt</h1>
    <p><strong>Pupil:</strong> {pupil['first_name']} {pupil['last_name']}<br>
    <strong>Class:</strong> {pupil.get('class_name','')}<br>
    <strong>Term:</strong> {term['academic_year']} Term {term['term_number']}</p>
    <table style='width:100%;border-collapse:collapse'>
      <tr><th style='padding:6px;border:1px solid #ddd'>Fee Item</th><th style='padding:6px;border:1px solid #ddd'>Reference</th><th style='padding:6px;border:1px solid #ddd'>Date</th><th style='padding:6px;border:1px solid #ddd'>Amount</th></tr>
      {rows}
    </table>
    <p style='margin-top:12px'><strong>Total Paid:</strong> ₦{total:,.2f}</p>
    </body></html>"""

def handle_download_fee_receipt_pdf(handler, user, pupil_id, term_id):
    conn = get_db()
    pupil = conn.execute("SELECT p.*, c.name as class_name FROM pupils p LEFT JOIN classes c ON c.id=p.class_id WHERE p.id=?", (pupil_id,)).fetchone()
    term = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
    if not pupil or not term:
        conn.close()
        return send_error(handler, "Pupil or term not found", 404)
    if not can_access_pupil(conn, user, pupil):
        conn.close()
        return send_error(handler, "Forbidden", 403)
    payments = conn.execute(
        "SELECT fp.*, fs.fee_name FROM fee_payments fp JOIN fee_structures fs ON fs.id=fp.fee_structure_id WHERE fp.pupil_id=? AND fp.term_id=? ORDER BY fp.created_at DESC",
        (pupil_id, term_id)
    ).fetchall()
    conn.close()
    pdf_bytes, err = render_pdf_bytes(build_receipt_pdf_html(dict(pupil), dict(term), [dict(p) for p in payments]), base_url=STATIC_DIR)
    if err:
        return send_error(handler, err, 500)
    send_pdf(handler, pdf_bytes, f"fee_receipt_{pupil['last_name']}_{term['academic_year'].replace('/','-')}_term{term['term_number']}.pdf")

# ─── HTTP REQUEST HANDLER ─────────────────────────────────────────────────────

class SchoolHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def handle_error(self, request, client_address):
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        add_security_headers(self)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        try:
            self._route(method)
        except Exception as e:
            import traceback
            traceback.print_exc()
            LOGGER.exception("Unhandled error while processing %s %s", method, self.path)
            try:
                send_error(self, f"Internal server error: {str(e)}", 500)
            except Exception:
                pass

    def _route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # Serve static files
        if not path.startswith("/api"):
            return self.serve_static(path)

        # Public health check (before auth)
        if path == "/health" and method == "GET":
            return handle_health(self)

        # API routes
        body = read_body(self) if method in ("POST", "PUT") else {}
        token = get_token_from_request(self)
        user = get_current_user(self)

        # Public routes
        if path == "/api/auth/login" and method == "POST":
            return handle_login(self, body)

        # Protected routes
        if not user:
            return send_error(self, "Unauthorized", 401)

        # Auth
        if path == "/api/auth/logout" and method == "POST":
            return handle_logout(self, user)
        if path == "/api/auth/me" and method == "GET":
            return handle_get_me(self, user)

        if path == "/api/admin/readiness" and method == "GET":
            return handle_get_readiness_report(self, user)
        if path == "/api/admin/backups" and method == "GET":
            return handle_list_backups(self, user)
        if path == "/api/admin/backups" and method == "POST":
            return handle_create_backup(self, user, body)
        m = re.match(r"^/api/admin/backups/([^/]+)/restore$", path)
        if m and method == "POST":
            return handle_restore_backup(self, user, m.group(1))
        m = re.match(r"^/api/admin/backups/([^/]+)$", path)
        if m and method == "GET":
            return handle_download_backup(self, user, m.group(1))
        if path == "/api/admin/restore-upload" and method == "POST":
            return handle_restore_upload(self, user, body)

        # Stats
        if path == "/api/stats" and method == "GET":
            return handle_get_stats(self, user)
        if path == "/api/analytics" and method == "GET":
            return handle_get_analytics(self, user, params)

        # Pupils
        if path == "/api/pupils" and method == "GET":
            return handle_get_pupils(self, user, params)
        if path == "/api/pupils" and method == "POST":
            return handle_create_pupil(self, user, body)

        m = re.match(r"^/api/pupils/([^/]+)$", path)
        if m:
            pid = m.group(1)
            if method == "GET": return handle_get_pupil(self, user, pid)
            if method == "PUT": return handle_update_pupil(self, user, pid, body)
            if method == "DELETE": return handle_archive_pupil(self, user, pid)

        m = re.match(r"^/api/pupils/([^/]+)/attendance$", path)
        if m and method == "GET":
            return handle_get_pupil_attendance(self, user, m.group(1), params)

        m = re.match(r"^/api/pupils/([^/]+)/report-pdf/term/([^/]+)$", path)
        if m and method == "GET":
            return handle_download_report_pdf(self, user, m.group(1), m.group(2))

        m = re.match(r"^/api/pupils/([^/]+)/receipt-pdf/term/([^/]+)$", path)
        if m and method == "GET":
            return handle_download_fee_receipt_pdf(self, user, m.group(1), m.group(2))

        m = re.match(r"^/api/pupils/([^/]+)/restore$", path)
        if m and method == "POST":
            return handle_restore_pupil(self, user, m.group(1))

        m = re.match(r"^/api/pupils/([^/]+)/promote$", path)
        if m and method == "POST":
            return handle_promote_class(self, user, m.group(1), body)

        # Teachers
        if path == "/api/teachers" and method == "GET":
            return handle_get_teachers(self, user)
        if path == "/api/teachers" and method == "POST":
            return handle_create_teacher(self, user, body)

        m = re.match(r"^/api/teachers/([^/]+)$", path)
        if m:
            tid = m.group(1)
            if method == "PUT": return handle_update_teacher(self, user, tid, body)
            if method == "DELETE": return handle_delete_teacher(self, user, tid)

        # Classes
        if path == "/api/classes" and method == "GET":
            return handle_get_classes(self, user)

        m = re.match(r"^/api/classes/([^/]+)/assign$", path)
        if m and method == "POST":
            return handle_assign_teacher(self, user, m.group(1), body)

        # Subjects
        if path == "/api/subjects" and method == "GET":
            return handle_get_subjects(self)
        if path == "/api/subjects" and method == "POST":
            return handle_create_subject(self, user, body)

        m = re.match(r"^/api/subjects/([^/]+)$", path)
        if m and method == "PUT":
            return handle_toggle_subject(self, user, m.group(1), body)

        # Terms
        if path == "/api/terms" and method == "GET":
            return handle_get_terms(self)
        if path == "/api/terms" and method == "POST":
            return handle_create_term(self, user, body)

        m = re.match(r"^/api/terms/([^/]+)/set-current$", path)
        if m and method == "POST":
            return handle_set_current_term(self, user, m.group(1))

        # Results
        if path == "/api/results" and method == "GET":
            return handle_get_results(self, user, params)
        if path == "/api/results/batch" and method == "POST":
            return handle_save_results_batch(self, user, body)
        if path == "/api/results/publish" and method == "POST":
            return handle_publish_results(self, user, body)

        # Report
        m = re.match(r"^/api/report/pupil/([^/]+)/term/([^/]+)$", path)
        if m and method == "GET":
            return handle_get_report(self, user, m.group(1), m.group(2))

        # Conduct ratings
        m = re.match(r"^/api/conduct/([^/]+)/term/([^/]+)$", path)
        if m:
            if method == "GET":
                return handle_get_conduct(self, user, m.group(1), m.group(2))
            if method in ("POST", "PUT"):
                return handle_save_conduct(self, user, m.group(1), m.group(2), body)

        # Fee structures
        if path == "/api/fees/structures" and method == "GET":
            return handle_get_fee_structures(self, user, params)
        if path == "/api/fees/structures" and method == "POST":
            return handle_save_fee_structure(self, user, body)
        m = re.match(r"^/api/fees/structures/([^/]+)$", path)
        if m and method == "DELETE":
            return handle_delete_fee_structure(self, user, m.group(1))
        if m and method == "PUT":
            body['id'] = m.group(1)
            return handle_save_fee_structure(self, user, body)
        m = re.match(r"^/api/fees/bill/([^/]+)/term/([^/]+)$", path)
        if m and method == "GET":
            return handle_get_fee_bill(self, user, m.group(1), m.group(2))
        if path == "/api/fees/payments" and method == "POST":
            return handle_save_fee_payment(self, user, body)
        if path == "/api/fees/payments/initialize" and method == "POST":
            return handle_initialize_online_payment(self, user, body)
        if path == "/api/fees/payments/verify" and method == "POST":
            return handle_verify_online_payment(self, user, body)
        
        # Fee payments by pupil
        m = re.match(r"^/api/fees/payments/pupil/([^/]+)$", path)
        if m and method == "GET":
            return handle_get_fee_payments_by_pupil(self, user, m.group(1))

        # Skill assessments
        m = re.match(r"^/api/skills/([^/]+)/term/([^/]+)$", path)
        if m:
            if method == "GET":
                return handle_get_skill_assessments(self, user, m.group(1), m.group(2))
            if method in ("POST", "PUT"):
                return handle_save_skill_assessments(self, user, m.group(1), m.group(2), body)

        # Attendance
        if path == "/api/attendance" and method == "GET":
            return handle_get_attendance(self, user, params)
        if path == "/api/attendance" and method == "POST":
            return handle_mark_attendance(self, user, body)

        # Homework
        if path == "/api/homework" and method == "GET":
            return handle_get_homework(self, user, params)
        if path == "/api/homework" and method == "POST":
            return handle_save_homework(self, user, body)
        m = re.match(r"^/api/homework/([^/]+)$", path)
        if m:
            if method == "PUT":
                return handle_save_homework(self, user, body, m.group(1))
            if method == "DELETE":
                return handle_delete_homework(self, user, m.group(1))
        m = re.match(r"^/api/homework/([^/]+)/complete$", path)
        if m and method == "POST":
            return handle_toggle_homework_completion(self, user, m.group(1), body)

        # Events / calendar
        if path == "/api/events" and method == "GET":
            return handle_get_events(self, user, params)
        if path == "/api/events" and method == "POST":
            return handle_save_event(self, user, body)
        m = re.match(r"^/api/events/([^/]+)$", path)
        if m:
            if method == "PUT":
                return handle_save_event(self, user, body, m.group(1))
            if method == "DELETE":
                return handle_delete_event(self, user, m.group(1))

        # Timetable
        if path == "/api/timetable" and method == "GET":
            return handle_get_timetable(self, user, params)
        if path == "/api/timetable" and method == "POST":
            return handle_save_timetable(self, user, body)
        m = re.match(r"^/api/timetable/([^/]+)$", path)
        if m:
            if method == "PUT":
                return handle_save_timetable(self, user, body, m.group(1))
            if method == "DELETE":
                return handle_delete_timetable(self, user, m.group(1))

        # Rollover
        if path == "/api/rollover" and method == "POST":
            return handle_rollover(self, user, body)

        # Payroll
        if path == "/api/payroll" and method == "GET":
            return handle_get_payroll(self, user, params)
        if path == "/api/payroll" and method == "POST":
            return handle_save_payroll(self, user, body)

        # Broadcast messaging
        if path == "/api/broadcast" and method == "POST":
            return handle_broadcast(self, user, body)

        # Lower school report
        m = re.match(r"^/api/report/lower/([^/]+)/term/([^/]+)$", path)
        if m and method == "GET":
            return handle_get_lower_school_report(self, user, m.group(1), m.group(2))

        # Notices
        if path == "/api/notices" and method == "GET":
            return handle_get_notices(self, user, params)
        
        # Parent accounts
        if path == "/api/parent-accounts" and method == "GET":
            return handle_get_parent_accounts(self, user)
        
        # Parent portal
        if path == "/api/parent/children" and method == "GET":
            return handle_get_parent_children(self, user)
        m = re.match(r"^/api/parent/child/([^/]+)/results$", path)
        if m and method == "GET":
            return handle_get_parent_child_results(self, user, m.group(1), params)
        m = re.match(r"^/api/parent/child/([^/]+)/fees/term/([^/]+)$", path)
        if m and method == "GET":
            return handle_get_parent_child_fees(self, user, m.group(1), m.group(2))
        
        # Acknowledgments for admin
        if path == "/api/acknowledgments" and method == "GET":
            return handle_get_parent_acknowledgments_for_admin(self, user, params)

        if path == "/api/parent/acknowledge" and method == "POST":
            return handle_parent_acknowledge(self, user, body)
        if path == "/api/parent-accounts" and method == "POST":
            return handle_save_parent_account(self, user, body)
        if path == "/api/notices" and method == "POST":
            return handle_save_notice(self, user, body)

        # Parent account updates
        m = re.match(r"^/api/parent-accounts/([^/]+)$", path)
        if m:
            if method == "PUT":
                return handle_save_parent_account(self, user, body, m.group(1))
            if method == "DELETE":
                return handle_delete_parent_account(self, user, m.group(1))

        # Notice updates
        m = re.match(r"^/api/notices/([^/]+)$", path)
        if m:
            if method == "PUT":
                return handle_save_notice(self, user, body, m.group(1))
            if method == "DELETE":
                return handle_delete_notice(self, user, m.group(1))

        # Change password
        if path == "/api/auth/change-password" and method == "POST":
            return handle_change_password(self, user, body)

        # CSV Exports
        if path == "/api/export/pupils" and method == "GET":
            return handle_export_pupils(self, user)
        if path == "/api/export/results" and method == "GET":
            return handle_export_results(self, user, params)
        if path == "/api/export/fees" and method == "GET":
            return handle_export_fees(self, user, params)

        # Audit log
        if path == "/api/audit-log" and method == "GET":
            return handle_get_audit_log(self, user, params)

        send_error(self, "Not found", 404)

    def serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        filepath = STATIC_DIR + path
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            filepath = os.path.join(STATIC_DIR, "index.html")
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            content_type, _ = mimetypes.guess_type(filepath)
            content_type = content_type or "text/html"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            add_security_headers(self)
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            send_error(self, str(e), 500)


class ReusableHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True


def create_http_server(handler_class):
    requested_port = PORT
    port_from_env = os.environ.get("PORT")

    # In local development, fall back to the next free port if the default
    # port is already occupied. In hosted environments, honor the provided
    # PORT and fail with a clear error message instead.
    candidate_ports = [requested_port]
    if not port_from_env:
        candidate_ports.extend([8081, 8082, 8083, 8000, 5000])

    last_error = None
    for candidate_port in candidate_ports:
        try:
            server = ReusableHTTPServer(("0.0.0.0", candidate_port), handler_class)
            return server, candidate_port
        except OSError as exc:
            last_error = exc
            if exc.errno == 48 and candidate_port != candidate_ports[-1]:
                continue
            if exc.errno == 48:
                if port_from_env:
                    raise OSError(
                        exc.errno,
                        f"Port {candidate_port} is already in use. Stop the process using that port or set a different PORT environment variable."
                    ) from exc
                raise OSError(
                    exc.errno,
                    f"Tried ports {', '.join(str(p) for p in candidate_ports)}, but all are already in use. Stop the existing server process and try again."
                ) from exc
            raise

    raise last_error or RuntimeError("Unable to create HTTP server")

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    configure_logging()
    ensure_runtime_directories()
    init_db()
    readiness_report = enforce_production_readiness()
    server, active_port = create_http_server(SchoolHandler)
    LOGGER.info("Starting GISL Schools on port %s in %s mode", active_port, ENVIRONMENT)
    LOGGER.info("Readiness summary: %s", readiness_report["summary"])

    bootstrap_message = ""
    if _BOOTSTRAP_STATUS["mode"] == "default_admin":
        bootstrap_message = f"""
║     Development Login:                   ║
║     Email:    admin@school.com           ║
║     Password: {LEGACY_DEFAULT_ADMIN_PASSWORD:<26}║
"""
    elif _BOOTSTRAP_STATUS["mode"] == "configured_admin":
        bootstrap_message = f"""
║     Initial admin created for:           ║
║     {INITIAL_ADMIN_EMAIL[:36]:<36}║
"""
    elif _BOOTSTRAP_STATUS["mode"] == "missing_admin":
        bootstrap_message = """
║  No admin account exists yet.            ║
║  Set INITIAL_ADMIN_EMAIL and             ║
║  INITIAL_ADMIN_PASSWORD to bootstrap.    ║
"""

    _fallback = "║     Existing admin login available.       ║\n"
    print(f"""
╔══════════════════════════════════════════╗
║     GISL Schools Management System       ║
║     Running at: http://localhost:{active_port}   ║
║                                          ║
{bootstrap_message if bootstrap_message else _fallback}╚══════════════════════════════════════════╝
    """)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Server stopped.")