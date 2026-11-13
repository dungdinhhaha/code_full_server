"""Session cookie hardening, storage-secret fallback removal, password hash upgrade logic."""
import hashlib
import logging
import pathlib
import unittest
from unittest import mock

from service import auth
from service.session_security import resolve_storage_secret, session_middleware_kwargs

ROOT = pathlib.Path(__file__).resolve().parent.parent


class StorageSecretTests(unittest.TestCase):
    def test_main_has_no_fixed_fallback_key(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("DEV_STORAGE_SECRET", text)
        self.assertNotIn("smiot-dev-only-storage-secret", text)
        self.assertIn("session_middleware_kwargs", text)

    def test_configured_secret_is_used(self):
        self.assertEqual(resolve_storage_secret({"NICEGUI_STORAGE_SECRET": " abc "}), "abc")

    def test_missing_secret_is_random_and_not_logged(self):
        logger = logging.getLogger("test.secret")
        with self.assertLogs(logger, level="WARNING") as cm:
            first = resolve_storage_secret({}, logger)
            second = resolve_storage_secret({"APP_ENV": "production"}, logger)
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 32)
        for line in cm.output:
            self.assertNotIn(first, line)
            self.assertNotIn(second, line)


class SecureCookieTests(unittest.TestCase):
    def test_production_sets_https_only(self):
        self.assertEqual(session_middleware_kwargs({"APP_ENV": "production"}), {"https_only": True})
        self.assertEqual(session_middleware_kwargs({"APP_ENV": " Production "}), {"https_only": True})

    def test_non_production_keeps_secure_off(self):
        self.assertEqual(session_middleware_kwargs({}), {})
        self.assertEqual(session_middleware_kwargs({"APP_ENV": "development"}), {})

    def test_starlette_accepts_kwargs(self):
        from starlette.middleware.sessions import SessionMiddleware
        mw = SessionMiddleware(lambda *a: None, secret_key="x", **session_middleware_kwargs({"APP_ENV": "production"}))
        self.assertIn("secure", mw.security_flags)


class HashUpgradeTests(unittest.TestCase):
    def test_legacy_hash_verifies_and_requests_upgrade(self):
        legacy = hashlib.sha256(b"pw").hexdigest()
        self.assertEqual(auth._verify_password(legacy, "pw"), (True, True))
        self.assertEqual(auth._verify_password(legacy, "bad"), (False, True))

    def test_new_hash_is_pbkdf2_and_no_upgrade(self):
        h = auth._hash_password("pw")
        self.assertTrue(h.startswith("pbkdf2_sha256$"))
        self.assertEqual(auth._verify_password(h, "pw"), (True, False))
        self.assertEqual(auth._verify_password(h, "bad"), (False, False))

    def test_verify_user_upgrades_legacy_hash(self):
        legacy = hashlib.sha256(b"pw").hexdigest()
        user = {"_id": 1, "id": 1, "username": "u", "password": legacy, "fullname": "U", "role": "viewer", "avatar": "a"}
        coll = mock.MagicMock()
        coll.find_one.return_value = user
        with mock.patch.object(auth, "login_locked", return_value=False), \
             mock.patch.object(auth, "record_login_result"), \
             mock.patch.object(auth, "collection", return_value=coll):
            self.assertIsNotNone(auth.verify_user("u", "pw"))
        args = coll.update_one.call_args[0]
        self.assertEqual(args[0], {"_id": 1, "password": legacy})
        self.assertTrue(args[1]["$set"]["password"].startswith("pbkdf2_sha256$"))

    def test_legacy_count_query_excludes_pbkdf2_and_warns(self):
        coll = mock.MagicMock()
        coll.count_documents.return_value = 3
        with mock.patch.object(auth, "collection", return_value=coll):
            with self.assertLogs("smiot.auth", level="WARNING") as cm:
                self.assertEqual(auth.warn_legacy_password_hashes(), 3)
        self.assertIn("3", cm.output[0])


if __name__ == "__main__":
    unittest.main()
