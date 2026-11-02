"""admin_api.py: the admin app has its own sign-in for admins only, keeps admins out of the shopping app, manages
accounts safely and changes the daily limits.

Run with the original app's Python, from this project's folder:

    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"

Accounts go to the temporary database server_under_test sets up. The limits are put back after every test.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_under_test import accounts, app, clear_counts, webapp  # noqa: E402

import admin_api  # noqa: E402
import protections  # noqa: E402

DATABASE = lambda: app.config["ACCOUNTS_DB"]  # noqa: E731
LAZADA = "https://www.lazada.com.ph/products/pdp-i1234-s1.html"
PASSWORD = "long enough 1"


def new_account(prefix: str = "person") -> dict:
    email = f"{prefix}{time.time_ns()}@example.com"
    return accounts.create_user(DATABASE(), "Test Person", email, PASSWORD)


def the_admin() -> dict:
    """The one admin account, which the server makes when it starts."""
    return admin_api.user_by_email(DATABASE(), admin_api.ADMIN_EMAIL)


def reset_admin() -> None:
    """Put the admin back as the server makes it: its own password, counted tries forgotten, the only admin."""
    from werkzeug.security import generate_password_hash

    with admin_api._connect(DATABASE()) as connection:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (generate_password_hash(admin_api.ADMIN_PASSWORD), admin_api.ADMIN_EMAIL),
        )
        # Admins an admin made in a test are shoppers again.
        connection.execute("DELETE FROM agency_members WHERE user_id != (SELECT id FROM users WHERE email = ?)", (admin_api.ADMIN_EMAIL,))
    admin_api.ensure_admin(DATABASE())
    with webapp._lock:
        webapp._login_failures.clear()


def shopper_client():
    """A client signed in to the shopping app with a new shopper account, and that account."""
    user = new_account("shopper")
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD}).status_code == 200
    return client, user


def admin_client():
    """A client signed in to the admin app as the one admin, and that account."""
    user = the_admin()
    client = app.test_client()
    answer = client.post("/api/admin/login", json={"email": "Admin@defake.com", "password": "Admin@defake.com"})
    assert answer.status_code == 200, answer.get_json()
    return client, user


class AdminTestCase(unittest.TestCase):
    def setUp(self) -> None:
        before = {name: getattr(protections.limits, name) for name in admin_api.LIMIT_NAMES}

        def put_back() -> None:
            for name, value in before.items():
                setattr(protections.limits, name, value)
            with admin_api._connect(DATABASE()) as connection:
                connection.execute("DELETE FROM site_settings")

        self.addCleanup(put_back)
        self.addCleanup(reset_admin)

    def row_of(self, client, user_id: int) -> dict:
        rows = client.get("/api/admin/accounts").get_json()["accounts"]
        return next(row for row in rows if row["id"] == user_id)


class SignInTest(AdminTestCase):
    ROUTES = (
        ("get", "/api/admin/accounts", None), ("post", "/api/admin/accounts", {"name": "A", "email": "a@b.co", "password": "long enough 1"}),
        ("delete", "/api/admin/accounts/1", None), ("get", "/api/admin/limits", None),
        ("put", "/api/admin/limits", {"site": 1, "account": 1, "network": 1}),
        ("put", "/api/admin/password", {"current_password": PASSWORD, "new_password": "another long one"}),
    )

    def test_nobody_signed_in_is_asked_to_sign_in(self) -> None:
        client = app.test_client()
        self.assertEqual(client.get("/api/admin/me").get_json(), {"admin": None})
        for method, path, body in self.ROUTES:
            with self.subTest(path=path, method=method):
                answer = getattr(client, method)(path, json=body)
                self.assertEqual(answer.status_code, 401)
                self.assertTrue(answer.get_json()["sign_in"])

    def test_a_shopping_app_session_does_not_open_the_admin_app(self) -> None:
        client, _user = shopper_client()
        self.assertEqual(client.get("/api/admin/me").get_json(), {"admin": None})
        for method, path, body in self.ROUTES:
            with self.subTest(path=path, method=method):
                self.assertEqual(getattr(client, method)(path, json=body).status_code, 401)
        self.assertEqual(protections.limits.site, protections.Limits().site)

    def test_a_shopper_cannot_sign_in_to_the_admin_app(self) -> None:
        user = new_account("shopper")
        answer = app.test_client().post("/api/admin/login", json={"email": user["email"], "password": PASSWORD})
        self.assertEqual(answer.status_code, 403)
        self.assertEqual(answer.get_json()["error"], admin_api.NOT_ADMIN_MESSAGE)

    def test_a_wrong_password_is_refused_and_counted(self) -> None:
        user = the_admin()
        client = app.test_client()
        for _ in range(webapp.LOGIN_FAILURE_LIMIT):
            answer = client.post("/api/admin/login", json={"email": user["email"], "password": "not it at all"})
            self.assertEqual(answer.status_code, 401)
        answer = client.post("/api/admin/login", json={"email": user["email"], "password": admin_api.ADMIN_PASSWORD})
        self.assertEqual(answer.status_code, 429)

    def test_an_admin_signs_in_and_out_apart_from_the_shopping_app(self) -> None:
        client, user = admin_client()
        me = client.get("/api/admin/me").get_json()["admin"]
        self.assertEqual((me["id"], me["email"]), (user["id"], user["email"]))
        self.assertIsNone(client.get("/api/auth/me").get_json().get("user"), "the shopping app stays signed out")
        client.post("/api/admin/logout", json={})
        self.assertEqual(client.get("/api/admin/me").get_json(), {"admin": None})
        self.assertEqual(client.get("/api/admin/accounts").status_code, 401)

    def test_the_original_admin_routes_stay_closed(self) -> None:
        client, _user = admin_client()
        for path in ("/api/admin/overview", "/api/admin/database", "/api/admin/lexicons", "/api/admin/logs"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 404)


class AdminOnlyTest(AdminTestCase):
    def test_the_shopping_app_refuses_an_admin_account(self) -> None:
        user = the_admin()
        client = app.test_client()
        answer = client.post("/api/auth/login", json={"email": user["email"], "password": admin_api.ADMIN_PASSWORD})
        self.assertEqual(answer.status_code, 403)
        self.assertEqual(answer.get_json()["error"], admin_api.ADMIN_ONLY_MESSAGE)
        self.assertIsNone(client.get("/api/auth/me").get_json().get("user"))
        # A wrong password says what it always says, so the refusal tells nothing without the password.
        wrong = client.post("/api/auth/login", json={"email": user["email"], "password": "not it at all"})
        self.assertEqual(wrong.status_code, 401)

    def test_only_an_admin_can_make_another_admin(self) -> None:
        client, me = admin_client()
        self.assertEqual((me["email"], admin_api.is_admin(DATABASE(), me["id"])), ("admin@defake.com", True))
        # Nobody else can: not signed in, a shopper, or by promoting an account that exists.
        body = {"name": "Sneaky", "email": f"sneaky{time.time_ns()}@example.com", "password": PASSWORD, "admin": True}
        self.assertEqual(app.test_client().post("/api/admin/accounts", json=body).status_code, 401)
        shopper, _user = shopper_client()
        self.assertEqual(shopper.post("/api/admin/accounts", json=body).status_code, 401)
        other = new_account("shopper")
        self.assertIn(client.put(f"/api/admin/accounts/{other['id']}/role", json={"admin": True}).status_code, (404, 405))
        self.assertFalse(admin_api.is_admin(DATABASE(), other["id"]))
        # The admin can: the new admin signs in to the admin side, and the shopping app refuses them.
        email = f"second{time.time_ns()}@example.com"
        made = client.post("/api/admin/accounts", json={"name": "Second Admin", "email": email, "password": PASSWORD, "admin": True})
        self.assertEqual((made.status_code, made.get_json()["admin"]), (201, True))
        self.assertTrue(admin_api.is_admin(DATABASE(), made.get_json()["id"]))
        self.assertTrue(self.row_of(client, made.get_json()["id"])["admin"])
        second = app.test_client()
        self.assertEqual(second.post("/api/admin/login", json={"email": email, "password": PASSWORD}).status_code, 200)
        self.assertEqual(second.get("/api/admin/accounts").status_code, 200)
        self.assertEqual(app.test_client().post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code, 403)
        # A server start keeps them.
        admin_api.ensure_admin(DATABASE())
        self.assertTrue(admin_api.is_admin(DATABASE(), made.get_json()["id"]))

    def test_the_admin_keeps_a_password_they_changed_after_a_restart(self) -> None:
        client, _me = admin_client()
        client.put("/api/admin/password", json={"current_password": "Admin@defake.com", "new_password": "something else 9"})
        admin_api.ensure_admin(DATABASE())
        self.assertIsNotNone(accounts.authenticate(DATABASE(), "admin@defake.com", "something else 9"))
        self.assertIsNone(accounts.authenticate(DATABASE(), "admin@defake.com", "Admin@defake.com"))

    def test_signing_in_to_the_shopping_app_keeps_an_admin_signed_in_on_the_same_computer(self) -> None:
        client, _admin = admin_client()
        shopper = new_account("shopper")
        self.assertEqual(client.post("/api/auth/login", json={"email": shopper["email"], "password": PASSWORD}).status_code, 200)
        self.assertEqual(client.get("/api/auth/me").get_json()["user"]["email"], shopper["email"])
        self.assertIsNotNone(client.get("/api/admin/me").get_json()["admin"])

    def test_an_admin_session_without_the_role_is_signed_out(self) -> None:
        client, _user = admin_client()
        with admin_api._connect(DATABASE()) as connection:
            connection.execute("DELETE FROM agency_members")
        answer = client.get("/api/admin/accounts")
        self.assertEqual(answer.status_code, 401)
        self.assertEqual(answer.get_json()["error"], admin_api.ROLE_REMOVED_MESSAGE)
        self.assertEqual(client.get("/api/admin/me").get_json(), {"admin": None})


class PasswordTest(AdminTestCase):
    def test_change_own_password(self) -> None:
        client, user = admin_client()
        PASSWORD = admin_api.ADMIN_PASSWORD
        wrong = client.put("/api/admin/password", json={"current_password": "nope nope", "new_password": "a new one 22"})
        self.assertEqual(wrong.status_code, 403)
        self.assertIn("current_password", wrong.get_json()["fields"])
        short = client.put("/api/admin/password", json={"current_password": PASSWORD, "new_password": "short"})
        self.assertEqual(short.status_code, 400)
        empty = client.put("/api/admin/password", json={"current_password": PASSWORD, "new_password": ""})
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(client.put("/api/admin/password", json={"current_password": PASSWORD, "new_password": "a new one 22"}).status_code, 200)
        self.assertIsNotNone(accounts.authenticate(DATABASE(), user["email"], "a new one 22"))


class AccountsTest(AdminTestCase):
    def test_lists_names_and_emails_but_never_passwords(self) -> None:
        client, me = admin_client()
        other = new_account("shopper")
        accounts.set_wishlist(DATABASE(), other["id"], LAZADA, True)
        answer = client.get("/api/admin/accounts").get_json()
        self.assertGreaterEqual(answer["total"], 2)
        self.assertGreaterEqual(answer["admins"], 1)
        text = str(answer)
        for secret in ("password", "pbkdf2", "scrypt"):
            self.assertNotIn(secret, text)
        mine, theirs = self.row_of(client, me["id"]), self.row_of(client, other["id"])
        self.assertEqual((mine["admin"], mine["you"]), (True, True))
        self.assertEqual((theirs["admin"], theirs["you"]), (False, False))
        self.assertEqual((theirs["name"], theirs["email"]), ("Test Person", other["email"]))
        self.assertEqual((theirs["history"], theirs["wishlist"], theirs["checks_today"]), (0, 1, 0))
        self.assertTrue(theirs["joined"])
        ids = [row["id"] for row in answer["accounts"]]
        self.assertLess(ids.index(other["id"]), ids.index(me["id"]), "newest first")

    def test_search_finds_by_email_and_treats_wildcards_as_text(self) -> None:
        client, _me = admin_client()
        other = new_account("shopper")
        found = client.get("/api/admin/accounts", query_string={"q": other["email"].upper()}).get_json()["accounts"]
        self.assertEqual([row["id"] for row in found], [other["id"]])
        self.assertEqual(client.get("/api/admin/accounts", query_string={"q": "%"}).get_json()["accounts"], [])

    def test_the_admin_adds_a_shopper_account_who_can_then_sign_in_to_the_shopping_app(self) -> None:
        client, _me = admin_client()
        email = f"added{time.time_ns()}@example.com"
        answer = client.post("/api/admin/accounts", json={"name": "  Added  Person ", "email": email.upper(), "password": PASSWORD})
        self.assertEqual(answer.status_code, 201)
        made = answer.get_json()
        self.assertEqual((made["name"], made["email"]), ("Added Person", email))
        row = self.row_of(client, made["id"])
        self.assertEqual((row["admin"], row["email"]), (False, email))
        shop = app.test_client()
        self.assertEqual(shop.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code, 200)

    def test_adding_an_account_checks_every_field_and_refuses_a_taken_email(self) -> None:
        client, _me = admin_client()
        answer = client.post("/api/admin/accounts", json={"name": "", "email": "nope", "password": "short"})
        self.assertEqual(answer.status_code, 400)
        self.assertEqual(set(answer.get_json()["fields"]), {"name", "email", "password"})
        self.assertEqual(client.post("/api/admin/accounts", json=["x"]).status_code, 400)
        taken = new_account("taken")
        again = client.post("/api/admin/accounts", json={"name": "Same", "email": taken["email"], "password": PASSWORD})
        self.assertEqual(again.status_code, 409)
        self.assertIn("email", again.get_json()["fields"])
        admin_again = client.post("/api/admin/accounts", json={"name": "Same", "email": "Admin@defake.com", "password": PASSWORD})
        self.assertIn(admin_again.status_code, (400, 409))
        self.assertEqual([row["email"] for row in admin_api.admins(DATABASE())], ["admin@defake.com"])

    def test_delete_removes_the_account_and_everything_it_kept(self) -> None:
        client, _me = admin_client()
        shopper, other = shopper_client()
        accounts.set_wishlist(DATABASE(), other["id"], LAZADA, True)
        self.assertEqual(client.delete(f"/api/admin/accounts/{other['id']}").get_json(), {"deleted": other["id"]})
        self.assertIsNone(accounts.get_user(DATABASE(), other["id"]))
        with admin_api._connect(DATABASE()) as connection:
            left = connection.execute("SELECT COUNT(*) FROM user_wishlist WHERE user_id = ?", (other["id"],)).fetchone()[0]
        self.assertEqual(left, 0)
        self.assertIsNone(shopper.get("/api/auth/me").get_json().get("user"))
        self.assertEqual(client.delete(f"/api/admin/accounts/{other['id']}").status_code, 404)

    def test_delete_refuses_your_own_and_the_main_admin_but_not_another_admin(self) -> None:
        client, me = admin_client()
        own = client.delete(f"/api/admin/accounts/{me['id']}")
        self.assertEqual((own.status_code, own.get_json()["error"]), (409, admin_api.OWN_ACCOUNT_MESSAGE))
        self.assertIsNotNone(accounts.get_user(DATABASE(), me["id"]))
        email = f"second{time.time_ns()}@example.com"
        second_id = client.post("/api/admin/accounts", json={"name": "Second", "email": email, "password": PASSWORD, "admin": True}).get_json()["id"]
        second = app.test_client()
        second.post("/api/admin/login", json={"email": email, "password": PASSWORD})
        main = second.delete(f"/api/admin/accounts/{me['id']}")
        self.assertEqual((main.status_code, main.get_json()["error"]), (409, admin_api.ADMIN_ACCOUNT_MESSAGE))
        self.assertEqual(client.delete(f"/api/admin/accounts/{second_id}").status_code, 200)
        self.assertIsNone(accounts.get_user(DATABASE(), second_id))
        # The deleted admin's session is over.
        self.assertEqual(second.get("/api/admin/accounts").status_code, 401)


class LimitsTest(AdminTestCase):
    def test_shows_the_limits_and_todays_use(self) -> None:
        clear_counts()
        accounts.reserve_guest_scan(DATABASE(), protections.SITE_KEY, accounts.manila_day(), 1000)
        client, _me = admin_client()
        answer = client.get("/api/admin/limits").get_json()
        self.assertEqual(set(answer["limits"]), {"site", "account", "network"})
        self.assertEqual(answer["limits"]["site"], protections.limits.site)
        self.assertEqual(answer["defaults"]["site"], protections.Limits().site)
        self.assertEqual(answer["site_used_today"], 1)
        self.assertEqual(answer["max"], admin_api.MAX_LIMIT)
        clear_counts()

    def test_a_change_counts_at_once_and_is_kept(self) -> None:
        client, _me = admin_client()
        answer = client.put("/api/admin/limits", json={"site": 250, "account": 5, "network": 0})
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer.get_json()["limits"], {"site": 250, "account": 5, "network": 0})
        self.assertEqual((protections.limits.site, protections.limits.account, protections.limits.network), (250, 5, 0))
        self.assertEqual(admin_api.saved_limits(DATABASE()), {"site": 250, "account": 5, "network": 0})
        # After a restart: the environment's numbers first, then the saved ones over them.
        protections.limits.site = 100
        admin_api.apply_saved_limits(DATABASE())
        self.assertEqual(protections.limits.site, 250)

    def test_refuses_anything_but_whole_numbers_in_range(self) -> None:
        client, _me = admin_client()
        for bad in ({"site": -1, "account": 5, "network": 5}, {"site": 10_001, "account": 5, "network": 5},
                    {"site": 2.5, "account": 5, "network": 5}, {"site": "9", "account": 5, "network": 5},
                    {"site": True, "account": 5, "network": 5}, {"site": 9, "account": 5}, []):
            with self.subTest(body=bad):
                answer = client.put("/api/admin/limits", json=bad)
                self.assertEqual(answer.status_code, 400)
                self.assertEqual(answer.get_json()["error"], admin_api.LIMITS_MESSAGE)
        self.assertEqual(admin_api.saved_limits(DATABASE()), {})

    def test_a_check_over_the_new_limit_is_refused(self) -> None:
        clear_counts()
        client, _me = admin_client()
        client.put("/api/admin/limits", json={"site": 0, "account": 10, "network": 10})
        answer = app.test_client().post("/api/search", json={"query": LAZADA, "live": True})
        self.assertEqual(answer.status_code, 429)
        self.assertTrue(answer.get_json()["site_limit"])
        clear_counts()


if __name__ == "__main__":
    unittest.main()
