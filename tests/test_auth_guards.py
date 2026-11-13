"""Privilege-escalation guard and login throttle. Pure logic only; no MongoDB needed."""
import unittest

from service import auth
from service.auth import PermissionDenied, check_user_change


class PrivilegeGuardTests(unittest.TestCase):
    def test_internal_call_without_actor_is_allowed(self):
        check_user_change(None, None, target_role="admin", new_role="admin", new_permissions=["manage_users"])

    def test_admin_actor_is_allowed_everything(self):
        check_user_change("admin", ["manage_users"], target_role="admin", new_role="admin",
                          new_permissions=list(auth.ROLE_PRESETS["admin"]))

    def test_non_admin_cannot_change_admin_target(self):
        with self.assertRaises(PermissionDenied):
            check_user_change("operator", ["manage_users"], target_role="admin")

    def test_non_admin_cannot_promote_to_admin(self):
        with self.assertRaises(PermissionDenied):
            check_user_change("operator", ["manage_users"], target_role="viewer", new_role="admin")

    def test_non_admin_cannot_create_admin(self):
        with self.assertRaises(PermissionDenied):
            check_user_change("operator", ["manage_users"], new_role="admin")

    def test_non_admin_cannot_grant_manage_users(self):
        with self.assertRaises(PermissionDenied):
            check_user_change("operator", ["manage_users", "pump_1_control"], target_role="viewer",
                              new_permissions=["manage_users"])

    def test_non_admin_cannot_grant_permission_it_does_not_hold(self):
        with self.assertRaises(PermissionDenied):
            check_user_change("operator", ["manage_users", "view_dashboard"], target_role="viewer",
                              new_permissions=["view_dashboard", "pump_1_control"])

    def test_non_admin_can_grant_subset_it_holds(self):
        check_user_change("operator", ["manage_users", "view_dashboard", "pump_1_control"],
                          target_role="viewer", new_role="viewer",
                          new_permissions=["view_dashboard"])


class LoginThrottleTests(unittest.TestCase):
    def setUp(self):
        auth._login_fail_log.clear()

    def test_locks_after_max_failures_within_window(self):
        for i in range(auth._LOGIN_MAX_FAILS):
            self.assertFalse(auth.login_locked("Ann", now=1000 + i))
            auth.record_login_result("Ann", False, now=1000 + i)
        self.assertTrue(auth.login_locked("ann", now=1010))

    def test_lock_expires_after_window(self):
        for i in range(auth._LOGIN_MAX_FAILS):
            auth.record_login_result("bob", False, now=1000 + i)
        self.assertTrue(auth.login_locked("bob", now=1100))
        self.assertFalse(auth.login_locked("bob", now=1000 + auth._LOGIN_WINDOW_S + 10))

    def test_success_clears_failures(self):
        for i in range(auth._LOGIN_MAX_FAILS - 1):
            auth.record_login_result("cy", False, now=1000 + i)
        auth.record_login_result("cy", True, now=1010)
        self.assertFalse(auth.login_locked("cy", now=1011))
        auth.record_login_result("cy", False, now=1012)
        self.assertFalse(auth.login_locked("cy", now=1013))


if __name__ == "__main__":
    unittest.main()
