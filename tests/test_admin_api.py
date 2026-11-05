"""admin_api.py: the admin app has its own sign-in for admins only, keeps admins out of the shopping app, manages
accounts safely and changes the daily limits.

Run with the original app's Python, from this project's folder:

    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"

Accounts go to the temporary database server_under_test sets up. The limits are put back after every test.
"""

from __future__ import annotations

import sys
import json
import time
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_under_test import accounts, app, clear_counts, webapp  # noqa: E402

import admin_api  # noqa: E402
import password_requests  # noqa: E402
import problem_reports  # noqa: E402
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


class FiltersTest(AdminTestCase):
    """What the Products page offers: the admin picks the choices, everybody reads them."""

    def setUp(self) -> None:
        super().setUp()

        def forget() -> None:
            with admin_api._connect(DATABASE()) as connection:
                connection.execute("DELETE FROM ui_settings")

        forget()
        self.addCleanup(forget)

    def test_every_choice_is_offered_until_the_admin_changes_it(self) -> None:
        shown = app.test_client().get("/api/products-filters")
        self.assertEqual((shown.status_code, shown.get_json()), (200, admin_api.FILTER_DEFAULTS))

    def test_the_admin_saves_choices_and_everybody_sees_them(self) -> None:
        client, _me = admin_client()
        wanted = {"show": {"enabled": ["safety", "all", "clear"], "default": "clear"},
                  "sort": {"enabled": ["reviews", "fewest"], "default": "reviews"}}
        saved = client.put("/api/admin/filters", json=wanted)
        self.assertEqual(saved.status_code, 200)
        # Kept in the page's own order, whatever order they were sent in.
        expected = {"show": {"enabled": ["all", "safety", "clear"], "default": "clear"},
                    "sort": {"enabled": ["fewest", "reviews"], "default": "reviews"}, "custom": []}
        self.assertEqual(saved.get_json()["filters"], expected)
        self.assertEqual(client.get("/api/admin/filters").get_json()["filters"], expected)
        self.assertEqual(app.test_client().get("/api/products-filters").get_json(), expected)

    def test_choices_that_make_no_sense_are_refused_and_nothing_changes(self) -> None:
        client, _me = admin_client()
        good = {"show": {"enabled": ["all"], "default": "all"}, "sort": {"enabled": ["fewest"], "default": "fewest"}}
        bad = [
            {**good, "show": {"enabled": [], "default": "all"}},  # nothing to choose from
            {**good, "show": {"enabled": ["all"], "default": "safety"}},  # starts on a choice that is off
            {**good, "sort": {"enabled": ["fewest", "cheapest"], "default": "fewest"}},  # a choice that does not exist
            {**good, "sort": {"enabled": "fewest", "default": "fewest"}},
            {"show": good["show"]},  # one list missing
            ["all"],
        ]
        for body in bad:
            answer = client.put("/api/admin/filters", json=body)
            self.assertEqual((answer.status_code, answer.get_json()["error"]), (400, admin_api.FILTERS_MESSAGE), body)
        self.assertEqual(app.test_client().get("/api/products-filters").get_json(), admin_api.FILTER_DEFAULTS)

    def test_a_saved_row_that_cannot_be_read_falls_back_to_every_choice(self) -> None:
        with admin_api._connect(DATABASE()) as connection:
            connection.execute("INSERT INTO ui_settings(name, value, updated_at) VALUES (?, ?, ?)", (admin_api.FILTERS_KEY, "{not json", "now"))
        self.assertEqual(app.test_client().get("/api/products-filters").get_json(), admin_api.FILTER_DEFAULTS)

    def test_the_admin_adds_options_of_their_own(self) -> None:
        client, _me = admin_client()
        wanted = {
            "show": {"enabled": ["all", "cfour5", "cunder5"], "default": "cfour5"},
            "sort": {"enabled": ["fewest", "cnew001"], "default": "cnew001"},
            "custom": [
                {"id": "cfour5", "group": "show", "label": "  Rated 4.5 stars or more ", "kind": "min_rating", "value": 4.46},
                {"id": "cunder5", "group": "show", "label": "Under 500", "kind": "max_price", "value": 500},
                {"id": "cnew001", "group": "sort", "label": "Newest checked", "kind": "checked", "direction": "desc"},
            ],
        }
        saved = client.put("/api/admin/filters", json=wanted)
        self.assertEqual(saved.status_code, 200, saved.get_json())
        got = saved.get_json()["filters"]
        # Names are trimmed, a rating is kept to one decimal, and the page's order is kept: built-in first, then added.
        self.assertEqual([one["label"] for one in got["custom"]], ["Rated 4.5 stars or more", "Under 500", "Newest checked"])
        self.assertEqual(got["custom"][0]["value"], 4.5)
        self.assertEqual(got["show"], {"enabled": ["all", "cfour5", "cunder5"], "default": "cfour5"})
        self.assertEqual(got["sort"], {"enabled": ["fewest", "cnew001"], "default": "cnew001"})
        self.assertEqual(app.test_client().get("/api/products-filters").get_json(), got)

    def test_an_option_that_is_not_listed_cannot_be_turned_on_and_removing_one_drops_it_everywhere(self) -> None:
        client, _me = admin_client()
        base = {"show": {"enabled": ["all"], "default": "all"}, "sort": {"enabled": ["fewest"], "default": "fewest"}}
        ghost = client.put("/api/admin/filters", json={**base, "show": {"enabled": ["all", "cghost1"], "default": "all"}, "custom": []})
        self.assertEqual((ghost.status_code, ghost.get_json()["error"]), (400, admin_api.FILTERS_MESSAGE))
        # An option made for the order list is not a choice in the result list.
        wrong_list = {"id": "cthing1", "group": "sort", "label": "Cheapest", "kind": "price", "direction": "asc"}
        mixed = client.put("/api/admin/filters", json={**base, "show": {"enabled": ["all", "cthing1"], "default": "all"}, "custom": [wrong_list]})
        self.assertEqual(mixed.status_code, 400)
        # Take an option away from the list of options, and it is gone from the enabled choices too (a start on it is refused).
        added = {**base, "show": {"enabled": ["all", "cthing2"], "default": "cthing2"},
                 "custom": [{"id": "cthing2", "group": "show", "label": "Lazada", "kind": "marketplace", "value": "lazada"}]}
        self.assertEqual(client.put("/api/admin/filters", json=added).status_code, 200)
        removed = client.put("/api/admin/filters", json={**added, "custom": []})
        self.assertEqual(removed.status_code, 400)

    def test_options_that_make_no_sense_are_refused_with_the_reason_and_nothing_changes(self) -> None:
        client, _me = admin_client()
        base = {"show": {"enabled": ["all"], "default": "all"}, "sort": {"enabled": ["fewest"], "default": "fewest"}}

        def made(**one):
            group = one.get("group", "show")
            listed = group if group in base else "show"  # a made-up group is put in a real list, so only its name is wrong
            item = {"id": "cmade01", "group": group, "label": "Mine", **one}
            return {**base, listed: {"enabled": [base[listed]["enabled"][0], "cmade01"], "default": base[listed]["default"]}, "custom": [item]}

        bad = [
            ("name", made(label="")), ("name", made(label="   ")), ("name", made(label="x" * 41)), ("name", made(label="two\nlines")),
            ("name", made(label=5)),
            ("number", made(kind="min_rating", value=0)), ("number", made(kind="min_rating", value=5.5)),
            ("number", made(kind="min_rating", value=True)), ("number", made(kind="min_rating", value="4")),
            ("number", made(kind="max_price", value=-1)), ("number", made(kind="max_price", value=10_000_001)),
            ("number", made(kind="min_reviews", value=0)), ("number", made(kind="max_price", value=float("nan"))),
            ("Lazada or Shopee", made(kind="marketplace", value="temu")), ("Lazada or Shopee", made(kind="marketplace", value=1)),
            ("filter by", made(kind="made_up", value=3)), ("filter by", made(kind="price", value=3)),
            ("order by", made(group="sort", kind="rating", direction="up")), ("order by", made(group="sort", kind="min_rating", direction="asc")),
            ("order by", made(group="sort", kind="rating")),
            ("id", made(id="Capital")), ("id", made(id="c")), ("id", made(id="cwaytoolongforanid")), ("id", made(id="x12345")),
            ("belongs to no list", made(group="other")),
            ("not an object", {**base, "custom": ["cmade01"]}),
        ]
        for needle, body in bad:
            answer = client.put("/api/admin/filters", json=body)
            self.assertEqual(answer.status_code, 400, (needle, body["custom"]))
            self.assertTrue(answer.get_json()["error"].startswith(admin_api.CUSTOM_MESSAGE), answer.get_json())
        # Too many, and the same id twice.
        many = [{"id": f"cmany{n:02d}", "group": "show", "label": f"No. {n}", "kind": "min_reviews", "value": n + 1} for n in range(admin_api.MAX_CUSTOM + 1)]
        self.assertEqual(client.put("/api/admin/filters", json={**base, "custom": many}).status_code, 400)
        twice = [{"id": "cdup001", "group": "show", "label": "A", "kind": "min_reviews", "value": 1}] * 2
        self.assertEqual(client.put("/api/admin/filters", json={**base, "custom": twice}).status_code, 400)
        not_a_list = client.put("/api/admin/filters", json={**base, "custom": {"id": "x"}})
        self.assertEqual(not_a_list.status_code, 400)
        # The most is allowed, and nothing that was refused was kept.
        top = client.put("/api/admin/filters", json={**base, "custom": many[: admin_api.MAX_CUSTOM]})
        self.assertEqual(top.status_code, 200, top.get_json())
        client.put("/api/admin/filters", json={**base, "custom": []})
        self.assertEqual(app.test_client().get("/api/products-filters").get_json()["custom"], [])

    def test_a_row_saved_before_options_could_be_added_still_reads(self) -> None:
        old = {"show": {"enabled": ["all", "safety"], "default": "all"}, "sort": {"enabled": ["fewest"], "default": "fewest"}}
        with admin_api._connect(DATABASE()) as connection:
            connection.execute("INSERT INTO ui_settings(name, value, updated_at) VALUES (?, ?, ?)", (admin_api.FILTERS_KEY, json.dumps(old), "now"))
        got = app.test_client().get("/api/products-filters").get_json()
        self.assertEqual(got, {**old, "custom": []})

    def test_a_shopper_cannot_change_them(self) -> None:
        shopper, _user = shopper_client()
        self.assertEqual(shopper.put("/api/admin/filters", json=admin_api.FILTER_DEFAULTS).status_code, 401)
        self.assertEqual(app.test_client().get("/api/admin/filters").status_code, 401)


class ReportsTest(AdminTestCase):
    """The problem reports people send from the site, and what the admin does with them."""

    def setUp(self) -> None:
        super().setUp()

        def forget() -> None:
            with admin_api._connect(DATABASE()) as connection:
                problem_reports.ensure_schema(connection)
                connection.execute("DELETE FROM problem_reports")
            problem_reports._recent.clear()

        forget()
        self.addCleanup(forget)

    def send(self, client, message: str, **extra):
        return client.post("/api/problem-report", json={"category": "scan-problem", "message": message, **extra})

    def test_a_report_a_guest_or_a_shopper_sends_reaches_the_admin_with_who_sent_it(self) -> None:
        admin, _me = admin_client()
        self.assertEqual(admin.get("/api/admin/reports").get_json(), {"reports": [], "counts": {"new": 0, "done": 0, "total": 0}})
        guest = app.test_client()
        self.assertEqual(self.send(guest, "The scan stopped halfway and nothing happened", page="/scan").status_code, 201)
        shopper, user = shopper_client()
        self.assertEqual(self.send(shopper, "My wishlist did not save this product", category="display-bug", email="me@example.com", page="/app/report?link=x").status_code, 201)
        got = admin.get("/api/admin/reports").get_json()
        self.assertEqual(got["counts"], {"new": 2, "done": 0, "total": 2})
        newest, oldest = got["reports"]
        # Newest first, with the label the person picked, and who the shopper was; a guest has no account.
        self.assertEqual((newest["category"], newest["label"], newest["status"]), ("display-bug", "Something looks or works broken", "new"))
        self.assertEqual(newest["user"], {"name": user["name"], "email": user["email"]})
        self.assertEqual((newest["email"], newest["page"]), ("me@example.com", "/app/report?link=x"))
        self.assertIsNone(oldest["user"])
        self.assertEqual(oldest["message"], "The scan stopped halfway and nothing happened")
        self.assertNotIn("password", str(got).lower())

    def test_the_admin_marks_reports_handled_and_open_again_and_narrows_the_list(self) -> None:
        admin, _me = admin_client()
        guest = app.test_client()
        self.send(guest, "First: the scan failed on a Lazada link")
        self.send(guest, "Second: I cannot sign in at all", category="account")
        self.send(guest, "Third: the result looks wrong to me", category="wrong-result", email="reply@example.com")
        by_text = {one["message"].split(":")[0]: one["id"] for one in admin.get("/api/admin/reports").get_json()["reports"]}
        done = admin.put(f"/api/admin/reports/{by_text['First']}", json={"status": "done"})
        self.assertEqual((done.status_code, done.get_json()["status"]), (200, "done"))
        self.assertEqual(admin.get("/api/admin/reports").get_json()["counts"], {"new": 2, "done": 1, "total": 3})
        names = lambda **query: [one["message"].split(":")[0] for one in admin.get("/api/admin/reports", query_string=query).get_json()["reports"]]
        self.assertEqual(names(status="new"), ["Third", "Second"])
        self.assertEqual(names(status="done"), ["First"])
        self.assertEqual(names(category="account"), ["Second"])
        self.assertEqual(names(q="reply@example"), ["Third"])
        self.assertEqual(names(q="LAZADA"), ["First"])
        # The counts are for every report, whatever the list is narrowed to.
        self.assertEqual(admin.get("/api/admin/reports", query_string={"status": "done"}).get_json()["counts"]["total"], 3)
        self.assertEqual(admin.put(f"/api/admin/reports/{by_text['First']}", json={"status": "new"}).status_code, 200)
        self.assertEqual(admin.get("/api/admin/reports").get_json()["counts"]["new"], 3)

    def test_percent_and_underscore_in_a_search_are_just_characters(self) -> None:
        admin, _me = admin_client()
        guest = app.test_client()
        self.send(guest, "It said 100% done but nothing showed")
        self.send(guest, "Plain words and nothing odd at all")
        self.send(guest, "snake_case in the page title looks odd")
        texts = lambda q: [one["message"] for one in admin.get("/api/admin/reports", query_string={"q": q}).get_json()["reports"]]
        self.assertEqual(texts("100%"), ["It said 100% done but nothing showed"])
        self.assertEqual(texts("%"), ["It said 100% done but nothing showed"])
        self.assertEqual(texts("_"), ["snake_case in the page title looks odd"])
        self.assertEqual(texts("a_e"), [])  # not "any letter between a and e"

    def test_bad_requests_are_refused(self) -> None:
        admin, _me = admin_client()
        self.send(app.test_client(), "A report so it has an id to point at")
        rid = admin.get("/api/admin/reports").get_json()["reports"][0]["id"]
        for body in ({"status": "deleted"}, {"status": 1}, {}, [], None):
            self.assertEqual(admin.put(f"/api/admin/reports/{rid}", json=body).status_code, 400, body)
        missing = admin.put("/api/admin/reports/999999", json={"status": "done"})
        self.assertEqual((missing.status_code, missing.get_json()["error"]), (404, admin_api.NO_REPORT_MESSAGE))
        # Odd filters are ignored, not an error.
        self.assertEqual(admin.get("/api/admin/reports", query_string={"status": "x", "category": "y"}).status_code, 200)
        # Nobody else may read or change them.
        for client in (app.test_client(), shopper_client()[0]):
            self.assertEqual(client.get("/api/admin/reports").status_code, 401)
            self.assertEqual(client.put(f"/api/admin/reports/{rid}", json={"status": "done"}).status_code, 401)
        self.assertEqual(admin.get("/api/admin/reports").get_json()["reports"][0]["status"], "new")

    def test_the_form_still_refuses_a_short_message_and_too_many_reports(self) -> None:
        guest = app.test_client()
        self.assertEqual(self.send(guest, "short").status_code, 400)
        for n in range(problem_reports.PER_HOUR):
            self.assertEqual(self.send(guest, f"Report number {n} so the hourly limit is reached").status_code, 201)
        self.assertEqual(self.send(guest, "One more than the hour allows").status_code, 429)

    def test_a_database_that_had_the_table_before_reports_had_a_status_is_upgraded(self) -> None:
        with admin_api._connect(DATABASE()) as connection:
            connection.executescript("DROP TABLE problem_reports; CREATE TABLE problem_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                                     "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, category TEXT NOT NULL, message TEXT NOT NULL, "
                                     "email TEXT NOT NULL DEFAULT '', page TEXT NOT NULL DEFAULT '', user_id INTEGER);")
            connection.execute("INSERT INTO problem_reports (category, message) VALUES ('other', 'Sent long before reports had a status')")
        admin, _me = admin_client()
        got = admin.get("/api/admin/reports").get_json()
        self.assertEqual([(one["status"], one["message"]) for one in got["reports"]], [("new", "Sent long before reports had a status")])
        self.assertEqual(admin.put(f"/api/admin/reports/{got['reports'][0]['id']}", json={"status": "done"}).status_code, 200)


class SignInTest(AdminTestCase):
    ROUTES = (
        ("get", "/api/admin/accounts", None), ("post", "/api/admin/accounts", {"name": "A", "email": "a@b.co", "password": "long enough 1"}),
        ("delete", "/api/admin/accounts/1", None), ("get", "/api/admin/limits", None),
        ("get", "/api/admin/filters", None), ("put", "/api/admin/filters", {"show": {"enabled": ["all"], "default": "all"}}),
        ("get", "/api/admin/reports", None), ("put", "/api/admin/reports/1", {"status": "done"}),
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

    def test_an_admin_deletes_only_their_own_account_and_never_the_last_admin(self) -> None:
        client, me = admin_client()
        shopper, other = shopper_client()
        accounts.set_wishlist(DATABASE(), other["id"], LAZADA, True)
        # Nobody else's account can be deleted, a shopper's or another admin's.
        email = f"second{time.time_ns()}@example.com"
        second_id = client.post("/api/admin/accounts", json={"name": "Second", "email": email, "password": PASSWORD, "admin": True}).get_json()["id"]
        for user_id in (other["id"], second_id, 999_999):
            answer = client.delete(f"/api/admin/accounts/{user_id}", json={"current_password": admin_api.ADMIN_PASSWORD})
            self.assertEqual((answer.status_code, answer.get_json()["error"]), (403, admin_api.OWN_ONLY_MESSAGE))
        for user_id in (other["id"], second_id):
            self.assertIsNotNone(accounts.get_user(DATABASE(), user_id))
        with admin_api._connect(DATABASE()) as connection:
            kept = connection.execute("SELECT COUNT(*) FROM user_wishlist WHERE user_id = ?", (other["id"],)).fetchone()[0]
        self.assertEqual(kept, 1)
        self.assertIsNotNone(shopper.get("/api/auth/me").get_json().get("user"))

        # The second admin deletes itself: its password is needed, and its session ends.
        second = app.test_client()
        self.assertEqual(second.post("/api/admin/login", json={"email": email, "password": PASSWORD}).status_code, 200)
        wrong = second.delete(f"/api/admin/accounts/{second_id}", json={"current_password": "not it at all"})
        self.assertEqual(wrong.status_code, 403)
        self.assertIsNotNone(accounts.get_user(DATABASE(), second_id))
        gone = second.delete(f"/api/admin/accounts/{second_id}", json={"current_password": PASSWORD})
        self.assertEqual((gone.status_code, gone.get_json()), (200, {"deleted": True}))
        self.assertIsNone(accounts.get_user(DATABASE(), second_id))
        self.assertIsNone(second.get("/api/admin/me").get_json()["admin"])

        # The only admin left can't delete itself.
        last = client.delete(f"/api/admin/accounts/{me['id']}", json={"current_password": admin_api.ADMIN_PASSWORD})
        self.assertEqual((last.status_code, last.get_json()["error"]), (409, admin_api.LAST_ADMIN_MESSAGE))
        self.assertIsNotNone(accounts.get_user(DATABASE(), me["id"]))

    def test_the_main_admin_is_not_made_again_when_another_admin_exists(self) -> None:
        client, me = admin_client()
        email = f"second{time.time_ns()}@example.com"
        client.post("/api/admin/accounts", json={"name": "Second", "email": email, "password": PASSWORD, "admin": True})
        accounts.delete_user(DATABASE(), me["id"], admin_api.ADMIN_PASSWORD)
        admin_api.ensure_admin(DATABASE())
        self.assertIsNone(admin_api.user_by_email(DATABASE(), admin_api.ADMIN_EMAIL))
        # With no other admin, the main one is made as before (and the next test finds it).
        with admin_api._connect(DATABASE()) as connection:
            connection.execute("DELETE FROM agency_members")
        admin_api.ensure_admin(DATABASE())
        self.assertIsNotNone(admin_api.user_by_email(DATABASE(), admin_api.ADMIN_EMAIL))


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


class PasswordRequestsTest(AdminTestCase):
    """"Forgot password": anyone asks, the admin sees whether the remembered password was right, and sets a new one."""

    def ask(self, user: dict, **change):
        body = {"name": user["name"], "email": user["email"], "last_password": PASSWORD, "send_to": "inbox@example.com"}
        body.update(change)
        return app.test_client().post("/api/password-request", json=body)

    def setUp(self) -> None:
        super().setUp()

        def forget() -> None:
            with admin_api._connect(DATABASE()) as connection:
                password_requests.ensure_schema(connection)
                connection.execute("DELETE FROM password_requests")

        forget()
        self.addCleanup(forget)
        with password_requests._lock:
            password_requests._recent.clear()

    def test_a_request_is_kept_without_the_password_that_was_typed(self) -> None:
        user = new_account("forgot")
        self.assertEqual(self.ask(user).status_code, 201)
        with admin_api._connect(DATABASE()) as connection:
            stored = " ".join(str(value) for row in connection.execute("SELECT * FROM password_requests") for value in tuple(row))
        self.assertNotIn(PASSWORD, stored)
        client, _me = admin_client()
        listed = client.get("/api/admin/password-requests").get_json()
        row = listed["requests"][0]
        self.assertEqual((listed["counts"]["new"], row["account_found"], row["name_matches"], row["password_matched"]), (1, True, True, True))
        self.assertEqual((row["email"], row["send_to"], row["status"]), (user["email"], "inbox@example.com", "new"))

    def test_a_wrong_remembered_password_or_a_stranger_is_told_apart_but_answered_the_same(self) -> None:
        user = new_account("forgot")
        right = self.ask(user)
        wrong = self.ask(user, last_password="something else")
        stranger = self.ask(user, email=f"nobody{time.time_ns()}@example.com")
        self.assertEqual([r.status_code for r in (right, wrong, stranger)], [201, 201, 201])
        self.assertEqual(right.get_json(), wrong.get_json())
        self.assertEqual(right.get_json(), stranger.get_json())
        client, _me = admin_client()
        rows = client.get("/api/admin/password-requests").get_json()["requests"]
        self.assertEqual([(r["account_found"], r["password_matched"]) for r in rows], [(False, False), (True, False), (True, True)])

    def test_the_form_checks_its_fields_and_slows_down_a_flood(self) -> None:
        user = new_account("forgot")
        bad = self.ask(user, name="", send_to="not an email")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(set(bad.get_json()["fields"]), {"name", "send_to"})
        answers = [self.ask(user).status_code for _ in range(password_requests.PER_HOUR + 1)]
        self.assertEqual(answers[-1], 429)

    def test_only_the_admin_reads_and_answers_requests(self) -> None:
        user = new_account("forgot")
        self.ask(user)
        for client in (app.test_client(), shopper_client()[0]):
            self.assertEqual(client.get("/api/admin/password-requests").status_code, 401)
            self.assertEqual(client.post("/api/admin/password-requests/1/reset").status_code, 401)

    def test_the_admin_sets_a_new_password_that_works_once_and_closes_the_request(self) -> None:
        user = new_account("forgot")
        self.ask(user)
        client, _me = admin_client()
        request_id = client.get("/api/admin/password-requests").get_json()["requests"][0]["id"]
        done = client.post(f"/api/admin/password-requests/{request_id}/reset")
        self.assertEqual(done.status_code, 200)
        answer = done.get_json()
        self.assertEqual((answer["send_to"], answer["emailed"]), ("inbox@example.com", False))
        self.assertGreaterEqual(len(answer["password"]), 8)
        self.assertIsNone(accounts.authenticate(DATABASE(), user["email"], PASSWORD))
        self.assertIsNotNone(accounts.authenticate(DATABASE(), user["email"], answer["password"]))
        listed = client.get("/api/admin/password-requests?status=done").get_json()
        self.assertEqual((listed["counts"]["done"], listed["requests"][0]["id"]), (1, request_id))
        reopened = client.put(f"/api/admin/password-requests/{request_id}", json={"status": "new"})
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(client.put(f"/api/admin/password-requests/{request_id}", json={"status": "?"}).status_code, 400)
        self.assertEqual(client.post("/api/admin/password-requests/999999/reset").status_code, 404)

    def test_no_password_is_set_for_an_unknown_email_or_an_admin_account(self) -> None:
        client, me = admin_client()
        self.ask(me)
        self.ask(me, email=f"nobody{time.time_ns()}@example.com")
        by_email = {r["email"]: r["id"] for r in client.get("/api/admin/password-requests").get_json()["requests"]}
        self.assertEqual(client.post(f"/api/admin/password-requests/{by_email[me['email']]}/reset").status_code, 403)
        other = next(i for e, i in by_email.items() if e != me["email"])
        self.assertEqual(client.post(f"/api/admin/password-requests/{other}/reset").status_code, 404)
        self.assertIsNotNone(accounts.authenticate(DATABASE(), "Admin@defake.com", admin_api.ADMIN_PASSWORD))


class SavedProductsTest(AdminTestCase):
    def test_only_the_admin_sees_the_saved_products(self) -> None:
        self.assertEqual(app.test_client().get("/api/admin/products").status_code, 401)
        self.assertEqual(shopper_client()[0].get("/api/admin/products").status_code, 401)
        client, _me = admin_client()
        answer = client.get("/api/admin/products")
        self.assertEqual(answer.status_code, 200)
        body = answer.get_json()
        self.assertEqual(set(body), {"products", "total", "platforms", "shown"})
        self.assertEqual(body["shown"], len(body["products"]))

    def test_search_and_marketplace_narrow_the_list_and_treat_wildcards_as_text(self) -> None:
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "products.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "CREATE TABLE products (link TEXT, name TEXT, platform TEXT, price TEXT, rating REAL, review_count INTEGER, "
                    "verdict_state TEXT, reviews_analyzed INTEGER, reviews_listed INTEGER, source TEXT, updated_at TEXT)"
                )
                connection.executemany(
                    "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [("https://a/1", "Fast charger 100%", "lazada", "P500", 4.5, 10, "clear", 10, 10, "scan", "2026-11-01"),
                     ("https://b/2", "Wired mouse", "shopee", "P99", 4.0, 5, "clear", 5, 5, "extension", "2026-11-02")],
                )
                connection.commit()
            both = admin_api.saved_products(path)
            self.assertEqual((both["total"], both["shown"], both["platforms"]), (2, 2, {"lazada": 1, "shopee": 1}))
            self.assertEqual(both["products"][0]["name"], "Wired mouse")
            self.assertEqual([p["name"] for p in admin_api.saved_products(path, platform="Lazada")["products"]], ["Fast charger 100%"])
            self.assertEqual([p["name"] for p in admin_api.saved_products(path, query="100%")["products"]], ["Fast charger 100%"])
            self.assertEqual(admin_api.saved_products(path, query="%")["shown"], 1)
        self.assertEqual(admin_api.saved_products(None)["products"], [])
