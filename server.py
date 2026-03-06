#!/usr/bin/env python3
"""
School Management System - Backend Server
Requires: Python 3.6+ (no external dependencies)
"""

import http.server
import json
import sqlite3
import hashlib
import uuid
import os
import base64
import re
import mimetypes
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

PORT = 8080
DB_PATH = os.path.join(os.path.dirname(__file__), "school.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")

# ─── DATABASE ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
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
    """)

    # Migrations
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

    # Seed default admin if none exists
    admin = c.execute("SELECT id FROM users WHERE role='admin'").fetchone()
    if not admin:
        admin_id = str(uuid.uuid4())
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("""INSERT INTO users (id, name, email, password_hash, role)
                     VALUES (?, ?, ?, ?, ?)""",
                  (admin_id, "School Admin", "admin@school.com", pw_hash, "admin"))

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
    conn.close()
    print("✓ Database initialized")

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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

# ─── RESPONSE HELPERS ─────────────────────────────────────────────────────────

def send_json(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)

def send_error(handler, message, status=400):
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

# ─── API HANDLERS ─────────────────────────────────────────────────────────────

def handle_login(handler, body):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    if not email or not password:
        return send_error(handler, "Email and password required")
    conn = get_db()
    # Try staff first
    user = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
    if user and user["password_hash"] == hash_password(password):
        conn.close()
        token = create_session(user["id"], "staff")
        return send_json(handler, {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}})
    # Try parent
    parent = conn.execute("SELECT * FROM parent_accounts WHERE email = ? AND is_active = 1", (email,)).fetchone()
    conn.close()
    if parent and parent["password_hash"] == hash_password(password):
        token = create_session(parent["id"], "parent")
        return send_json(handler, {"token": token, "user": {"id": parent["id"], "name": parent["name"], "email": parent["email"], "role": "parent"}})
    return send_error(handler, "Invalid email or password", 401)

def handle_logout(handler, user):
    token = get_token_from_request(handler)
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Logged out"})

def handle_get_me(handler, user):
    result = {k: user[k] for k in ["id","name","email","role","phone"]}
    if user["role"] == "teacher":
        conn = get_db()
        cls = conn.execute("SELECT * FROM classes WHERE teacher_id = ?", (user["id"],)).fetchone()
        conn.close()
        result["class"] = dict(cls) if cls else None
    send_json(handler, result)

# ── PUPILS ────────────────────────────────────────────────────────────────────

def handle_get_pupils(handler, user, params):
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

    pid = str(uuid.uuid4())
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM pupils").fetchone()[0]
    year = datetime.now().year
    admission = body.get("admission_number") or f"SCH/{year}/{str(count+1).zfill(4)}"

    conn.execute("""
        INSERT INTO pupils (id, first_name, last_name, other_name, admission_number,
            date_of_birth, gender, class_id, blood_group, religion, photo,
            parent_name, parent_phone, parent_email, parent_address, parent_relationship,
            emergency_name, emergency_phone)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
    ))
    conn.commit()
    pupil = conn.execute("SELECT * FROM pupils WHERE id = ?", (pid,)).fetchone()
    conn.close()
    send_json(handler, dict(pupil), 201)

def handle_get_pupil(handler, user, pupil_id):
    conn = get_db()
    pupil = conn.execute("""
        SELECT p.*, c.name as class_name, c.level as class_level, c.class_type
        FROM pupils p LEFT JOIN classes c ON c.id = p.class_id
        WHERE p.id = ?
    """, (pupil_id,)).fetchone()
    conn.close()
    if not pupil:
        return send_error(handler, "Pupil not found", 404)
    send_json(handler, dict(pupil))

def handle_update_pupil(handler, user, pupil_id, body):
    conn = get_db()
    pupil = conn.execute("SELECT id FROM pupils WHERE id = ?", (pupil_id,)).fetchone()
    if not pupil:
        conn.close()
        return send_error(handler, "Pupil not found", 404)
    fields = ["first_name","last_name","other_name","date_of_birth","gender",
              "class_id","blood_group","religion","photo","parent_name","parent_phone",
              "parent_email","parent_address","parent_relationship",
              "emergency_name","emergency_phone","admission_number"]
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
    send_json(handler, dict(updated))

def handle_archive_pupil(handler, user, pupil_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    conn.execute("UPDATE pupils SET status='archived', updated_at=datetime('now') WHERE id=?", (pupil_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Pupil archived"})

def handle_restore_pupil(handler, user, pupil_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    conn.execute("UPDATE pupils SET status='active', updated_at=datetime('now') WHERE id=?", (pupil_id,))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Pupil restored"})

def handle_promote_class(handler, user, class_id):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    cls = conn.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
    if not cls:
        conn.close()
        return send_error(handler, "Class not found", 404)
    level = cls["level"]
    if level >= 6:
        conn.execute("""UPDATE pupils SET status='graduated', class_id=NULL, updated_at=datetime('now')
                        WHERE class_id=? AND status='active'""", (class_id,))
        count = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        conn.close()
        return send_json(handler, {"message": f"{count} pupils graduated from Primary 6"})

    next_cls = conn.execute("SELECT * FROM classes WHERE level=?", (level+1,)).fetchone()
    if not next_cls:
        conn.close()
        return send_error(handler, "Next class not found")
    next_id = next_cls["id"]
    conn.execute("""UPDATE pupils SET class_id=?, updated_at=datetime('now')
                    WHERE class_id=? AND status='active'""", (next_id, class_id))
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    send_json(handler, {"message": f"{count} pupils promoted to {next_cls['name']}", "count": count})

# ── TEACHERS ──────────────────────────────────────────────────────────────────

def handle_get_teachers(handler, user):
    conn = get_db()
    rows = conn.execute("""
        SELECT u.*, c.name as class_name, c.id as class_id
        FROM users u
        LEFT JOIN classes c ON c.teacher_id = u.id
        WHERE u.role = 'teacher' AND u.is_active = 1
        ORDER BY u.name
    """).fetchall()
    conn.close()
    send_json(handler, [dict(r) for r in rows])

def handle_create_teacher(handler, user, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    required = ["name", "email", "password"]
    for f in required:
        if not body.get(f):
            return send_error(handler, f"{f} is required")
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
    send_json(handler, dict(teacher), 201)

def handle_update_teacher(handler, user, teacher_id, body):
    if user["role"] != "admin":
        return send_error(handler, "Not authorized", 403)
    conn = get_db()
    updates = []
    values = []
    for f in ["name","phone"]:
        if f in body:
            updates.append(f"{f} = ?")
            values.append(body[f])
    if body.get("password"):
        updates.append("password_hash = ?")
        values.append(hash_password(body["password"]))
    if updates:
        values.append(teacher_id)
        conn.execute(f"UPDATE users SET {','.join(updates)} WHERE id=?", values)
    if "class_id" in body:
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
    send_json(handler, {"message": "Teacher removed"})

# ── CLASSES ───────────────────────────────────────────────────────────────────

def handle_get_classes(handler, user):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, u.name as teacher_name,
               (SELECT COUNT(*) FROM pupils p WHERE p.class_id=c.id AND p.status='active') as pupil_count
        FROM classes c
        LEFT JOIN users u ON u.id = c.teacher_id
        ORDER BY c.level
    """).fetchall()
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
    conn = get_db()
    existing = conn.execute("SELECT id FROM terms WHERE academic_year=? AND term_number=?",
                            (body.get("academic_year"), body.get("term_number"))).fetchone()
    if existing:
        conn.close()
        return send_error(handler, "Term already exists")
    tid = str(uuid.uuid4())
    conn.execute("""INSERT INTO terms (id, academic_year, term_number, start_date, end_date)
                    VALUES (?,?,?,?,?)""",
                 (tid, body.get("academic_year"), body.get("term_number"),
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
    pupil_id = params.get("pupil_id", [None])[0]
    term_id = params.get("term_id", [None])[0]
    class_id = params.get("class_id", [None])[0]

    if user["role"] == "teacher":
        conn = get_db()
        cls = conn.execute("SELECT id FROM classes WHERE teacher_id=?", (user["id"],)).fetchone()
        if cls:
            class_id = class_id or cls["id"]
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
    results = body.get("results", [])
    if not results:
        return send_error(handler, "No results provided")
    conn = get_db()
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
    send_json(handler, {"message": f"Saved {len(results)} results"})

# ── STATS ─────────────────────────────────────────────────────────────────────

def handle_get_stats(handler, user):
    conn = get_db()
    total_pupils = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='active'").fetchone()[0]
    total_teachers = conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher' AND is_active=1").fetchone()[0]
    total_classes = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    archived = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='archived'").fetchone()[0]
    graduated = conn.execute("SELECT COUNT(*) FROM pupils WHERE status='graduated'").fetchone()[0]
    current_term = conn.execute("SELECT * FROM terms WHERE is_current=1").fetchone()

    class_counts = conn.execute("""
        SELECT c.name, c.level,
               COUNT(p.id) as count,
               u.name as teacher_name
        FROM classes c
        LEFT JOIN pupils p ON p.class_id=c.id AND p.status='active'
        LEFT JOIN users u ON u.id=c.teacher_id
        GROUP BY c.id ORDER BY c.level
    """).fetchall()
    conn.close()

    send_json(handler, {
        "total_pupils": total_pupils,
        "total_teachers": total_teachers,
        "total_classes": total_classes,
        "archived": archived,
        "graduated": graduated,
        "current_term": dict(current_term) if current_term else None,
        "class_breakdown": [dict(r) for r in class_counts]
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
    if user["role"] == "parent" and pupil["parent_email"] != user["email"]:
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
        "class_type": pupil["class_type"] if "class_type" in pupil.keys() else "primary"
    })

# ── CONDUCT RATINGS ───────────────────────────────────────────────────────────

def handle_get_conduct(handler, user, pupil_id, term_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM conduct_ratings WHERE pupil_id=? AND term_id=?",
        (pupil_id, term_id)
    ).fetchone()
    conn.close()
    send_json(handler, dict(row) if row else {})

def handle_save_conduct(handler, user, pupil_id, term_id, body):
    conn = get_db()
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
    if user["role"] == "parent" and pupil["parent_email"] != user["email"]:
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
    pid = str(uuid.uuid4())
    is_parent = 1 if user["role"] == "parent" else 0
    conn.execute("""INSERT INTO fee_payments
        (id, pupil_id, term_id, fee_structure_id, amount_paid, payment_date, payment_reference, notes, recorded_by, is_parent_payment)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(pupil_id, term_id, fee_structure_id) DO UPDATE SET
        amount_paid=amount_paid + excluded.amount_paid,
        payment_date=excluded.payment_date,
        payment_reference=excluded.payment_reference,
        notes=excluded.notes,
        is_parent_payment=excluded.is_parent_payment""",
        (pid, body['pupil_id'], body['term_id'], body['fee_structure_id'],
         amount, body.get('payment_date', ''),
         body.get('payment_reference', ''), body.get('notes', ''), user['id'], is_parent))
    conn.commit()
    conn.close()
    send_json(handler, {"message": "Payment recorded", "amount": amount})

def handle_get_fee_payments_by_pupil(handler, user, pupil_id):
    # Only staff (admin/teachers) may view full payment history by pupil.
    # Parents must use the fee bill endpoint which is scoped to their child.
    if user["role"] == "parent":
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
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
    conn = get_db()
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
    if user["role"] == "parent" and pupil["parent_email"] != user["email"]:
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
        pid = str(uuid.uuid4())
        try:
            conn.execute("INSERT INTO parent_accounts (id,name,email,password_hash,phone) VALUES (?,?,?,?,?)",
                (pid, name, email, hash_password(password), body.get("phone","")))
            conn.commit()
            conn.close()
            send_json(handler, {"id": pid, "message": "Created"})
        except Exception as e:
            conn.close()
            send_error(handler, str(e))

def handle_delete_parent_account(handler, user, parent_id):
    if user["role"] not in ("admin",):
        return send_error(handler, "Forbidden", 403)
    conn = get_db()
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
    comment = body.get("comment", "")
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
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
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

        # Stats
        if path == "/api/stats" and method == "GET":
            return handle_get_stats(self, user)

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

        m = re.match(r"^/api/pupils/([^/]+)/restore$", path)
        if m and method == "POST":
            return handle_restore_pupil(self, user, m.group(1))

        m = re.match(r"^/api/pupils/([^/]+)/promote$", path)
        if m and method == "POST":
            return handle_promote_class(self, user, m.group(1))

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
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            send_error(self, str(e), 500)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    init_db()
    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("0.0.0.0", PORT), SchoolHandler)
    print(f"""
╔══════════════════════════════════════════╗
║     GISL Schools Management System       ║
║     Running at: http://localhost:{PORT}   ║
║                                          ║
║     Default Login:                       ║
║     Email:    admin@school.com           ║
║     Password: admin123                   ║
╚══════════════════════════════════════════╝
    """)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
