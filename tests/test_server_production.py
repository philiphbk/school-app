import io
import json
import os
import tempfile
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER_PATH = ROOT / "server.py"


class DummyHandler:
    def __init__(self):
        self.headers = {}
        self.client_address = ("127.0.0.1", 12345)
        self.status_code = None
        self.response_headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status_code = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass


def load_server_module(temp_dir, extra_env=None):
    extra_env = extra_env or {}
    old_env = os.environ.copy()
    os.environ.update({
        "DATA_DIR": temp_dir,
        "ENVIRONMENT": "test",
        "ALLOW_DEFAULT_ADMIN": "false",
        "ALLOWED_ORIGIN": "http://localhost:8080",
        "APP_URL": "",
        "SMTP_HOST": "",
        "SMTP_PORT": "587",
        "SMTP_USER": "",
        "SMTP_PASS": "",
        "SMTP_FROM": "",
        "PAYSTACK_PUBLIC_KEY": "",
        "PAYSTACK_SECRET_KEY": "",
        "PAYSTACK_CALLBACK_URL": "",
        "TERMII_API_KEY": "",
        "TERMII_WHATSAPP_ENDPOINT": "",
        "META_WHATSAPP_ACCESS_TOKEN": "",
        "META_WHATSAPP_PHONE_NUMBER_ID": "",
    })
    os.environ.update(extra_env)
    module_name = f"server_test_{next(tempfile._get_candidate_names())}"
    spec = importlib.util.spec_from_file_location(module_name, SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, old_env


def restore_env(old_env):
    os.environ.clear()
    os.environ.update(old_env)


def decode_json(handler):
    handler.wfile.seek(0)
    payload = handler.wfile.read().decode("utf-8")
    return json.loads(payload or "{}")


def get_check(report, key):
    return next(item for item in report["checks"] if item["key"] == key)


class ProductionReadinessTests(unittest.TestCase):
    def test_blank_data_dir_falls_back_to_app_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "DATA_DIR": "   ",
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
            })
            try:
                expected_dir = str(SERVER_PATH.parent)
                self.assertEqual(module._DATA_DIR, expected_dir)

                module.LOG_PATH = os.path.join(temp_dir, "app.log")
                module.configure_logging()
            finally:
                restore_env(old_env)

    def test_configured_admin_bootstrap_and_login(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
                "INITIAL_ADMIN_NAME": "Secure Admin",
            })
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()

                conn = module.get_db()
                admin = conn.execute("SELECT name, email FROM users WHERE role='admin'").fetchone()
                conn.close()

                self.assertIsNotNone(admin)
                self.assertEqual(admin["email"], "admin@example.com")

                handler = DummyHandler()
                module.handle_login(handler, {
                    "email": "admin@example.com",
                    "password": "StrongPass123",
                })
                data = decode_json(handler)
                self.assertEqual(handler.status_code, 200)
                self.assertEqual(data["user"]["role"], "admin")
            finally:
                restore_env(old_env)

    def test_no_default_admin_without_opt_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir)
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()
                report = module.get_system_checks()
                self.assertGreaterEqual(report["summary"]["error"], 1)
                self.assertEqual(module._BOOTSTRAP_STATUS["mode"], "missing_admin")
            finally:
                restore_env(old_env)

    def test_local_readiness_allows_optional_integrations_to_be_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "ENVIRONMENT": "development",
                "ALLOWED_ORIGIN": "*",
                "APP_URL": "",
                "SMTP_HOST": "",
                "SMTP_USER": "",
                "SMTP_PASS": "",
                "SMTP_FROM": "",
                "PAYSTACK_PUBLIC_KEY": "",
                "PAYSTACK_SECRET_KEY": "",
                "PAYSTACK_CALLBACK_URL": "",
                "TERMII_API_KEY": "",
                "META_WHATSAPP_ACCESS_TOKEN": "",
                "META_WHATSAPP_PHONE_NUMBER_ID": "",
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
            })
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()
                report = module.get_system_checks()

                self.assertEqual(get_check(report, "cors_origin")["status"], "ok")
                self.assertEqual(get_check(report, "app_url")["status"], "ok")
                self.assertTrue(get_check(report, "app_url")["message"].startswith("http://localhost:"))
                self.assertEqual(get_check(report, "smtp")["status"], "ok")
                self.assertEqual(get_check(report, "paystack")["status"], "ok")
                self.assertEqual(get_check(report, "messaging")["status"], "ok")
                self.assertEqual(get_check(report, "admin_account")["status"], "ok")
            finally:
                restore_env(old_env)

    def test_production_readiness_still_requires_locked_origin_and_app_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "ENVIRONMENT": "production",
                "ALLOWED_ORIGIN": "*",
                "APP_URL": "",
                "SMTP_HOST": "",
                "SMTP_USER": "",
                "SMTP_PASS": "",
                "SMTP_FROM": "",
                "PAYSTACK_PUBLIC_KEY": "",
                "PAYSTACK_SECRET_KEY": "",
                "PAYSTACK_CALLBACK_URL": "",
                "TERMII_API_KEY": "",
                "META_WHATSAPP_ACCESS_TOKEN": "",
                "META_WHATSAPP_PHONE_NUMBER_ID": "",
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
            })
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()
                report = module.get_system_checks()

                self.assertEqual(get_check(report, "cors_origin")["status"], "error")
                self.assertTrue(get_check(report, "cors_origin")["fatal"])
                self.assertEqual(get_check(report, "app_url")["status"], "error")
                self.assertTrue(get_check(report, "app_url")["fatal"])
                with self.assertRaises(RuntimeError):
                    module.enforce_production_readiness()
            finally:
                restore_env(old_env)

    def test_teacher_cannot_save_results_for_other_class(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
            })
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()

                conn = module.get_db()
                class_one = conn.execute("SELECT id FROM classes ORDER BY level LIMIT 1").fetchone()["id"]
                class_two = conn.execute("SELECT id FROM classes ORDER BY level LIMIT 1 OFFSET 1").fetchone()["id"]
                term_id = conn.execute("SELECT id FROM terms LIMIT 1").fetchone()["id"]
                subject_id = conn.execute("SELECT id FROM subjects LIMIT 1").fetchone()["id"]

                teacher_id = "teacher-1"
                conn.execute(
                    "INSERT INTO users (id, name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                    (teacher_id, "Teacher One", "teacher@example.com", module.hash_password("TeacherPass1"), "teacher")
                )
                conn.execute("UPDATE classes SET teacher_id=? WHERE id=?", (teacher_id, class_one))

                pupil_one = "pupil-one"
                pupil_two = "pupil-two"
                conn.execute("INSERT INTO pupils (id, first_name, last_name, class_id) VALUES (?, ?, ?, ?)", (pupil_one, "Alice", "One", class_one))
                conn.execute("INSERT INTO pupils (id, first_name, last_name, class_id) VALUES (?, ?, ?, ?)", (pupil_two, "Bob", "Two", class_two))
                conn.commit()
                conn.close()

                teacher_user = {"id": teacher_id, "role": "teacher", "email": "teacher@example.com", "name": "Teacher One"}
                handler = DummyHandler()
                module.handle_save_results_batch(handler, teacher_user, {
                    "results": [{
                        "pupil_id": pupil_two,
                        "subject_id": subject_id,
                        "term_id": term_id,
                        "ca_score": 20,
                        "exam_score": 40,
                    }]
                })
                data = decode_json(handler)
                self.assertEqual(handler.status_code, 403)
                self.assertIn("own class", data["error"])
            finally:
                restore_env(old_env)

    def test_parent_fee_access_and_mock_payment_verification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
            })
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()

                conn = module.get_db()
                class_id = conn.execute("SELECT id FROM classes LIMIT 1").fetchone()["id"]
                term = conn.execute("SELECT * FROM terms LIMIT 1").fetchone()
                fee_id = "fee-1"
                pupil_id = "pupil-1"
                parent_id = "parent-1"
                other_parent_id = "parent-2"

                conn.execute(
                    "INSERT INTO pupils (id, first_name, last_name, class_id, parent_email, parent_name, parent_phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (pupil_id, "Child", "One", class_id, "parent@example.com", "Parent One", "+2348012345678")
                )
                conn.execute(
                    "INSERT INTO parent_accounts (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
                    (parent_id, "Parent One", "parent@example.com", module.hash_password("ParentPass1"))
                )
                conn.execute(
                    "INSERT INTO parent_accounts (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
                    (other_parent_id, "Parent Two", "other@example.com", module.hash_password("ParentPass2"))
                )
                conn.execute(
                    """INSERT INTO fee_structures
                       (id, class_id, academic_year, term_number, fee_name, new_pupil_amount, returning_pupil_amount)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (fee_id, class_id, term["academic_year"], term["term_number"], "School Fees", 1000, 800)
                )
                conn.commit()
                conn.close()

                parent_user = {"id": parent_id, "role": "parent", "email": "parent@example.com", "name": "Parent One"}
                handler = DummyHandler()
                module.handle_initialize_online_payment(handler, parent_user, {
                    "pupil_id": pupil_id,
                    "term_id": term["id"],
                    "fee_structure_id": fee_id,
                })
                init_data = decode_json(handler)
                self.assertEqual(handler.status_code, 200)
                self.assertTrue(init_data["mock"])

                verify_handler = DummyHandler()
                module.handle_verify_online_payment(verify_handler, parent_user, {
                    "reference": init_data["reference"]
                })
                verify_data = decode_json(verify_handler)
                self.assertEqual(verify_handler.status_code, 200)
                self.assertIn("verified", verify_data["message"].lower())

                fee_handler = DummyHandler()
                module.handle_get_parent_child_fees(fee_handler, parent_user, pupil_id, term["id"])
                fee_data = decode_json(fee_handler)
                self.assertEqual(fee_handler.status_code, 200)
                self.assertEqual(fee_data["pupil"]["id"], pupil_id)

                other_parent = {"id": other_parent_id, "role": "parent", "email": "other@example.com", "name": "Parent Two"}
                denied_handler = DummyHandler()
                module.handle_get_parent_child_fees(denied_handler, other_parent, pupil_id, term["id"])
                denied_data = decode_json(denied_handler)
                self.assertEqual(denied_handler.status_code, 404)
                self.assertIn("Not found", denied_data["error"])
            finally:
                restore_env(old_env)

    def test_selective_promotion_only_moves_chosen_pupils(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            module, old_env = load_server_module(temp_dir, {
                "INITIAL_ADMIN_EMAIL": "admin@example.com",
                "INITIAL_ADMIN_PASSWORD": "StrongPass123",
            })
            try:
                module.configure_logging()
                module.ensure_runtime_directories()
                module.init_db()

                conn = module.get_db()
                nursery_two = conn.execute(
                    "SELECT * FROM classes WHERE class_type='lower' AND level=3 LIMIT 1"
                ).fetchone()
                primary_one = conn.execute(
                    "SELECT * FROM classes WHERE class_type='primary' AND level=1 LIMIT 1"
                ).fetchone()
                conn.execute(
                    "INSERT INTO pupils (id, first_name, last_name, class_id) VALUES (?, ?, ?, ?)",
                    ("pupil-a", "Ada", "One", nursery_two["id"])
                )
                conn.execute(
                    "INSERT INTO pupils (id, first_name, last_name, class_id) VALUES (?, ?, ?, ?)",
                    ("pupil-b", "Bola", "Two", nursery_two["id"])
                )
                conn.commit()
                conn.close()

                admin_user = {"id": "admin-1", "role": "admin", "email": "admin@example.com", "name": "Admin"}
                handler = DummyHandler()
                module.handle_promote_class(handler, admin_user, nursery_two["id"], {"pupil_ids": ["pupil-a"]})
                data = decode_json(handler)

                self.assertEqual(handler.status_code, 200)
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["target_class"], primary_one["name"])

                conn = module.get_db()
                pupil_a = conn.execute("SELECT class_id FROM pupils WHERE id='pupil-a'").fetchone()
                pupil_b = conn.execute("SELECT class_id FROM pupils WHERE id='pupil-b'").fetchone()
                conn.close()

                self.assertEqual(pupil_a["class_id"], primary_one["id"])
                self.assertEqual(pupil_b["class_id"], nursery_two["id"])
            finally:
                restore_env(old_env)


if __name__ == "__main__":
    unittest.main()