"""extension_api.py: reviews sent from the browser extension are checked, then analysed like a scan's.

Run with the original app's Python, from this project's folder:

    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"

Nothing is written to the real database: saving is replaced while the route is tested. One test runs the real
checker on a made-up listing, to show it reads an extension report as it reads a scanned one.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402  (already imported by server_under_test, with its setup)
from server_under_test import accounts, app, clear_counts, extension_api, protections, sign_up, webapp  # noqa: E402

LINK = "https://www.lazada.com.ph/products/pdp-i9000002-s7.html"
# Ratings per star as the feed lists them: 5 stars first.
SCORES = [100, 20, 10, 5, 3]
# Written reviews collected per star level, and why each level stopped.
COLLECTED = {3: 8, 2: 4, 4: 15, 1: 3, 5: 60}
STOPS = {"1": "feed_ended", "2": "feed_ended", "3": "feed_ended", "4": "feed_ended", "5": "target_reached"}
TEXT = {
    1: "Uminit at umusok habang naka-charge, delikado.",
    2: "Sira agad after one week, hindi na gumagana.",
    3: "Okay lang, medyo mahina ang tunog.",
    4: "Maganda naman, mabilis dumating.",
    5: "Very good quality, fast delivery, sulit!",
}


def sent_product() -> dict:
    reviews = []
    number = 0
    for star in (3, 2, 4, 1, 5):
        for n in range(COLLECTED[star]):
            number += 1
            reviews.append({
                "comment_id": str(5_000_000 + number), "rating": star, "source_rating_filter": star,
                "time": "31 May 2026" if n % 2 else "2 weeks ago", "content": f"{TEXT[star]} ({n})",
                "variation": "Color:Black", "like_count": n % 3,
            })
    return {
        "link": LINK, "name": "Test Wireless Earbuds", "price": "₱499.00", "brand": "No Brand", "seller": "Test Store",
        "img": "https://img.lazcdn.com/g/p/test.jpg_720x720q80.jpg",
        "ratings": {"scores": list(SCORES), "average": 4.5},
        "levels": {star: {"stop_reason": stop} for star, stop in STOPS.items()},
        "reviews": reviews,
    }


def find(value, key: str) -> dict:
    """The first dict, anywhere inside `value`, that holds `key`."""
    if isinstance(value, dict):
        if key in value:
            return value
        value = list(value.values())
    if isinstance(value, list):
        for item in value:
            found = find(item, key)
            if found:
                return found
    return {}


class ProductFromExtensionTest(unittest.TestCase):
    def test_builds_the_record_a_scan_builds(self) -> None:
        product = extension_api.product_from_extension(sent_product())
        self.assertEqual(product["link"], LINK)
        self.assertEqual(product["review_star_distribution"], {"1": 3, "2": 5, "3": 10, "4": 20, "5": 100})
        self.assertEqual(product["total_rating"], 138)
        self.assertEqual(product["rating"], 4.5)
        self.assertEqual(product["sampling_method"], "stratified_by_star")
        self.assertEqual(product["review_source"], "lazada_review_feed")
        self.assertEqual(product["applied_rating_filters"], [3, 2, 4, 1, 5])
        self.assertEqual(product["star_collection"]["5"], {"listed": 100, "collected": 60, "stop_reason": "target_reached", "complete": True})
        self.assertEqual(product["star_collection"]["3"], {"listed": 10, "collected": 8, "stop_reason": "feed_ended", "complete": True})
        self.assertEqual(product["written_reviews_collected"], 90)
        self.assertEqual(product["collected_via"], "defaketive-extension")
        ratings = [review["rating"] for review in product["comments"]]
        self.assertEqual(ratings, sorted(ratings))
        first = product["comments"][0]
        self.assertEqual(first["author"], "Reviewer 1")
        self.assertIn(first["time"], {"2026-05-31", "2 weeks ago"})
        self.assertIn("2026-05-31", {review["time"] for review in product["comments"]})
        self.assertEqual({review["author"] for review in product["comments"]}, {f"Reviewer {n}" for n in range(1, 91)})

    def test_text_is_tidied(self) -> None:
        sent = sent_product()
        sent["name"] = "  Test Wireless   Earbuds \n"
        self.assertEqual(extension_api.product_from_extension(sent)["name"], "Test Wireless Earbuds")

    def test_levels_cut_at_the_list_depth(self) -> None:
        sent = sent_product()
        sent["ratings"] = {"scores": [100, 20, 10, 40, 400], "average": 1.9}
        sent["levels"]["1"] = {"stop_reason": "target_reached"}
        sent["levels"]["2"] = {"stop_reason": "feed_limit"}
        sent["reviews"] = [r for r in sent["reviews"] if r["rating"] not in (1, 2)]
        sent["reviews"] += [{**sent["reviews"][0], "comment_id": str(7_000_000 + n), "rating": 1, "source_rating_filter": 1} for n in range(60)]
        sent["reviews"] += [{**sent["reviews"][0], "comment_id": str(8_000_000 + n), "rating": 2, "source_rating_filter": 2} for n in range(12)]
        product = extension_api.product_from_extension(sent)
        self.assertEqual(product["star_collection"]["2"], {"listed": 40, "collected": 12, "stop_reason": "feed_limit", "complete": True})

    def broken(self, change) -> None:
        sent = sent_product()
        change(sent)
        with self.assertRaises(extension_api.Invalid):
            extension_api.product_from_extension(sent)

    def test_refuses_data_that_does_not_add_up(self) -> None:
        cases = {
            "another site": lambda s: s.update(link="https://www.lazada.com.my/products/pdp-i9000002-s7.html"),
            "a link with extras": lambda s: s.update(link=LINK + "?spm=1"),
            "not a product page": lambda s: s.update(link="https://www.lazada.com.ph/catalog/?q=earbuds"),
            "four star counts": lambda s: s["ratings"].update(scores=SCORES[:4]),
            "a negative count": lambda s: s["ratings"].update(scores=[100, 20, 10, 5, -3]),
            "an average the counts do not give": lambda s: s["ratings"].update(average=3.2),
            "no ratings at all": lambda s: s["ratings"].update(scores=[0, 0, 0, 0, 0], average=0),
            "a missing level": lambda s: s["levels"].pop("4"),
            "an unfinished level": lambda s: s["levels"].update({"3": {"stop_reason": "feed_verification"}}),
            "stars that do not match the level": lambda s: s["reviews"][0].update(rating=5),
            "a repeated review": lambda s: s["reviews"][1].update(comment_id=s["reviews"][0]["comment_id"]),
            "a review with no id": lambda s: s["reviews"][0].pop("comment_id"),
            "an empty review": lambda s: s["reviews"][0].update(content="   "),
            "a very long review": lambda s: s["reviews"][0].update(content="x" * 5001),
            "more reviews than the level lists": lambda s: s["reviews"].extend(
                {**s["reviews"][0], "comment_id": str(9_000_000 + n)} for n in range(3)),
            "a target reached short of 60": lambda s: s["reviews"].pop(),
            "none listed but some there": lambda s: s["levels"].update({"1": {"stop_reason": "none_listed"}}),
            "a depth cut on a short list": lambda s: s["levels"].update({"3": {"stop_reason": "feed_limit"}}),
            "an image from elsewhere": lambda s: s.update(img="https://evil.example/x.jpg"),
            "a number given as text": lambda s: s["reviews"][0].update(rating="3"),
            "no name": lambda s: s.update(name=""),
            "not an object": lambda s: s.clear(),
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.broken(change)

    def test_the_real_checker_reads_it_as_a_complete_sample(self) -> None:
        analyzed = webapp.analyze_products([extension_api.product_from_extension(sent_product())])[0]
        self.assertNotEqual(webapp.badge_view(analyzed)["state"], "not_analyzed")
        coverage = find(analyzed, "scrape_completeness")
        self.assertEqual(coverage["scrape_completeness"], "stratified", coverage.get("completeness_reason"))
        self.assertEqual(coverage["reviews_scraped"], 90)


SHOPEE_LINK = "https://shopee.ph/Crocs-Kids'-Baya-Clog-in-Navy-i.159408769.58117695286"


def sent_shopee_product() -> dict:
    """The Lazada product's numbers, as the Shopee collector sends them: the day as 2026-05-31, a Shopee link and photo."""
    sent = sent_product()
    sent["link"] = SHOPEE_LINK
    sent["img"] = "https://down-ph.img.susercontent.com/file/test"
    for n, review in enumerate(sent["reviews"]):
        review["time"] = "2026-05-31" if n % 2 else ""
    return sent


class ShopeeProductFromExtensionTest(unittest.TestCase):
    def test_builds_the_same_record_for_shopee(self) -> None:
        product = extension_api.product_from_extension(sent_shopee_product())
        self.assertEqual(product["link"], SHOPEE_LINK)
        self.assertEqual(product["platform"], "shopee")
        self.assertEqual(product["review_source"], "shopee_review_feed")
        self.assertEqual(product["review_star_distribution_source"], "shopee_review_feed")
        self.assertEqual(product["review_star_distribution"], {"1": 3, "2": 5, "3": 10, "4": 20, "5": 100})
        self.assertEqual(product["written_reviews_collected"], 90)
        self.assertEqual(product["collected_via"], "defaketive-extension")
        self.assertIn("2026-05-31", {review["time"] for review in product["comments"]})
        self.assertEqual(product["img"], "https://down-ph.img.susercontent.com/file/test")

    def test_the_other_product_address_is_accepted(self) -> None:
        sent = sent_shopee_product()
        sent["link"] = "https://shopee.ph/product/159408769/58117695286"
        self.assertEqual(extension_api.product_from_extension(sent)["platform"], "shopee")

    def test_lazada_still_reads_as_lazada(self) -> None:
        product = extension_api.product_from_extension(sent_product())
        self.assertEqual(product["platform"], "lazada")
        self.assertEqual(product["review_source"], "lazada_review_feed")

    def test_a_shopee_level_that_stops_at_the_depth_counts_only_its_own_list(self) -> None:
        # Lazada's 2-star list also holds the 1-star reviews; Shopee's does not, so 40 + 3 reviews cannot reach the cut.
        sent = sent_shopee_product()
        sent["levels"]["2"] = {"stop_reason": "feed_limit"}
        with self.assertRaises(extension_api.Invalid):
            extension_api.product_from_extension(sent)

    def test_refuses_what_does_not_add_up(self) -> None:
        cases = {
            "another shop site": lambda s: s.update(link="https://shopee.com.my/x-i.1.2"),
            "a search page": lambda s: s.update(link="https://shopee.ph/search?keyword=crocs"),
            "a link with extras": lambda s: s.update(link=SHOPEE_LINK + "?sp_atk=abc"),
            "a Lazada photo": lambda s: s.update(img="https://img.lazcdn.com/g/p/test.jpg"),
            "a photo from elsewhere": lambda s: s.update(img="https://evil.example/x.jpg"),
            "a day written the Lazada way": lambda s: s["reviews"][1].update(time="31 May 2026"),
            "a repeated review": lambda s: s["reviews"][1].update(comment_id=s["reviews"][0]["comment_id"]),
            "an average the counts do not give": lambda s: s["ratings"].update(average=3.2),
        }
        for name, change in cases.items():
            with self.subTest(name):
                sent = sent_shopee_product()
                change(sent)
                with self.assertRaises(extension_api.Invalid):
                    extension_api.product_from_extension(sent)

    def test_a_lazada_link_cannot_carry_a_shopee_photo(self) -> None:
        sent = sent_product()
        sent["img"] = "https://down-ph.img.susercontent.com/file/test"
        with self.assertRaises(extension_api.Invalid):
            extension_api.product_from_extension(sent)

    def test_the_real_checker_reads_it_as_a_complete_sample(self) -> None:
        analyzed = webapp.analyze_products([extension_api.product_from_extension(sent_shopee_product())])[0]
        self.assertNotEqual(webapp.badge_view(analyzed)["state"], "not_analyzed")
        coverage = find(analyzed, "scrape_completeness")
        self.assertEqual(coverage["scrape_completeness"], "stratified", coverage.get("completeness_reason"))
        self.assertEqual(coverage["reviews_scraped"], 90)


class PastedShopeeLinkTest(unittest.TestCase):
    """A Shopee link pasted into the site is not scanned: it is answered with how to use the extension."""

    def test_a_live_scan_of_a_shopee_link_points_to_the_extension(self) -> None:
        answer = app.test_client().post("/api/search", json={"query": SHOPEE_LINK, "live": True})
        self.assertEqual(answer.status_code, 400)
        body = answer.get_json()
        self.assertTrue(body.get("use_extension"))
        self.assertIn("DeFaketive extension", body["error"])
        self.assertNotIn("lazada_only", body)

    def test_temu_still_says_lazada_only(self) -> None:
        answer = app.test_client().post("/api/search", json={"query": "https://www.temu.com/goods.html?goods_id=123456789", "live": True})
        self.assertEqual(answer.status_code, 400)
        self.assertTrue(answer.get_json().get("lazada_only"))


NODE = shutil.which("node") or next(
    (str(path) for path in (Path("C:/Program Files/nodejs/node.exe"),) if path.is_file()), None
)
COLLECT_ONCE = Path(__file__).resolve().parent / "extension" / "collect-once.mjs"


@unittest.skipUnless(NODE, "Node.js is not installed")
class FromTheRealCollectorTest(unittest.TestCase):
    """What extension/collect.js really gathers passes the server's checks (and a broken collector would not)."""

    def collect(self, options: dict) -> dict:
        done = subprocess.run([NODE, str(COLLECT_ONCE), json.dumps(options)], capture_output=True, text=True,
                              encoding="utf-8", timeout=60, check=True)
        return json.loads(done.stdout)

    def test_listings_of_every_shape_pass(self) -> None:
        shapes = {
            "ordinary": {"scores": [400, 20, 10, 5, 3], "written": {"5": 150, "4": 15, "3": 8, "2": 4, "1": 3}},
            "many one-star": {"scores": [100, 0, 0, 40, 400], "written": {"5": 90, "2": 0, "1": 400}},
            "ratings without text": {"scores": [30, 10, 5, 2, 1], "written": {"5": 12, "4": 4, "3": 1, "2": 0, "1": 1},
                                     "blankEvery": 4},
            "one level only": {"scores": [7, 0, 0, 0, 0], "written": {"5": 7}},
        }
        for name, options in shapes.items():
            with self.subTest(name):
                sent = self.collect(options)
                self.assertEqual(sent["status"], "ok")
                product = extension_api.product_from_extension(sent["product"])
                self.assertEqual(product["written_reviews_collected"], len(sent["product"]["reviews"]))

    def test_a_product_with_a_wrong_count_is_refused(self) -> None:
        sent = self.collect({"scores": [400, 20, 10, 5, 3], "written": {"5": 150, "4": 15, "3": 8, "2": 4, "1": 3}})
        sent["product"]["ratings"]["scores"][2] = 4  # fewer 3-star ratings than 3-star reviews collected
        sent["product"]["ratings"]["average"] = round(sum((5 - i) * n for i, n in enumerate(sent["product"]["ratings"]["scores"]))
                                                      / sum(sent["product"]["ratings"]["scores"]), 1)
        with self.assertRaises(extension_api.Invalid):
            extension_api.product_from_extension(sent["product"])


class SavedReportLookupTest(unittest.TestCase):
    """server._saved_report: when the saved report of a listing was written, found the way the app matches listings."""

    def lookup(self, saved_at: dict[str, str], link: str):
        with mock.patch.object(server.pool, "snapshot", lambda: ([], saved_at)):
            return server._saved_report(link)

    def test_finds_the_listing_however_the_address_is_written(self) -> None:
        stored = {"https://www.lazada.com.ph/products/pdp-i9000002-s7.html": "2026-10-15T11:13:25+00:00"}
        for link in (LINK, LINK.upper().replace("HTTPS", "https"), "https://lazada.com.ph/products/pdp-i9000002-s7.html/"):
            with self.subTest(link=link):
                found = self.lookup(stored, link)
                self.assertEqual(found and found["checked_at"], "2026-10-15T11:13:25+00:00")

    def test_another_listing_or_a_missing_date_finds_nothing(self) -> None:
        self.assertIsNone(self.lookup({"https://www.lazada.com.ph/products/pdp-i9000003-s7.html": "2026-10-15T11:13:25+00:00"}, LINK))
        self.assertIsNone(self.lookup({LINK: ""}, LINK))
        self.assertIsNone(self.lookup({}, LINK))


class CheckRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.saved: list = []
        save = mock.patch.object(webapp, "save_products", lambda products, source="": self.saved.append((products, source)))
        analyse = mock.patch.object(webapp, "analyze_products", lambda products: [{**p, "analyzed": True} for p in copy.deepcopy(products)])
        for patch in (save, analyse):
            patch.start()
            self.addCleanup(patch.stop)
        clear_counts()

    def wait_for(self, client, job_id: str) -> dict:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").get_json()
            if job["state"] != "running":
                return job
            time.sleep(0.05)
        self.fail("the job did not finish")

    def test_a_guest_is_asked_to_sign_in(self) -> None:
        answer = app.test_client().post("/api/extension/check", json={"product": sent_product()})
        self.assertEqual(answer.status_code, 401)
        self.assertTrue(answer.get_json()["sign_in"])
        self.assertEqual(accounts.guest_scans_used(app.config["ACCOUNTS_DB"], protections.SITE_KEY, accounts.manila_day()), 0)

    def test_only_json_is_accepted(self) -> None:
        client = app.test_client()
        sign_up(client, "form")
        self.assertEqual(client.post("/api/extension/check", data={"product": "x"}).status_code, 415)

    def saved_days_ago(self, days: float | None):
        """Pretend this listing's report was saved `days` ago (None: it has no saved report)."""
        when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days or 0)
        found = None if days is None else {"link": LINK, "checked_at": when.isoformat()}
        patch = mock.patch.object(extension_api, "saved_report", lambda link: found)
        patch.start()
        self.addCleanup(patch.stop)

    def used_today(self) -> int:
        return accounts.guest_scans_used(app.config["ACCOUNTS_DB"], protections.SITE_KEY, accounts.manila_day())

    def test_a_recent_report_is_kept_and_nothing_is_counted(self) -> None:
        self.saved_days_ago(3)
        client = app.test_client()
        sign_up(client, "recent")
        answer = client.post("/api/extension/check", json={"product": sent_product()})
        self.assertEqual(answer.status_code, 200)
        existing = answer.get_json()["existing"]
        self.assertEqual((existing["link"], existing["days_ago"], existing["keeps_for"]), (LINK, 3, 30))
        self.assertEqual(self.saved, [])  # nothing was analysed or saved
        self.assertEqual(self.used_today(), 0)  # and the check was not counted
        self.assertEqual(client.get("/api/products").get_json()["count"], 0)

    def test_an_old_report_can_be_replaced(self) -> None:
        self.saved_days_ago(31)
        client = app.test_client()
        sign_up(client, "old")
        answer = client.post("/api/extension/check", json={"product": sent_product()})
        self.assertEqual(answer.status_code, 202)
        self.assertEqual(self.wait_for(client, answer.get_json()["job"]["id"])["state"], "complete")
        self.assertEqual(len(self.saved), 1)

    def test_a_listing_nobody_checked_is_taken_on_trust(self) -> None:
        self.saved_days_ago(None)
        client = app.test_client()
        sign_up(client, "first")
        self.assertEqual(client.post("/api/extension/check", json={"product": sent_product()}).status_code, 202)

    def test_the_rule_can_be_turned_off_or_changed(self) -> None:
        self.saved_days_ago(3)
        with mock.patch.dict(os.environ, {"DEFAKETIVE_EXTENSION_RECHECK_DAYS": "0"}):
            self.assertIsNone(extension_api.recent_report(LINK))
        with mock.patch.dict(os.environ, {"DEFAKETIVE_EXTENSION_RECHECK_DAYS": "2"}):
            self.assertIsNone(extension_api.recent_report(LINK))
        with mock.patch.dict(os.environ, {"DEFAKETIVE_EXTENSION_RECHECK_DAYS": "nonsense"}):
            self.assertEqual(extension_api.recent_report(LINK)["keeps_for"], 30)

    def test_a_report_with_an_unreadable_date_does_not_block_a_check(self) -> None:
        with mock.patch.object(extension_api, "saved_report", lambda link: {"link": LINK, "checked_at": "last week"}):
            self.assertIsNone(extension_api.recent_report(LINK))

    def test_invalid_data_is_refused_even_when_the_report_is_recent(self) -> None:
        self.saved_days_ago(3)
        client = app.test_client()
        sign_up(client, "badrecent")
        sent = sent_product()
        sent["ratings"]["average"] = 1.0
        self.assertEqual(client.post("/api/extension/check", json={"product": sent}).status_code, 400)

    def test_a_signed_in_check_is_analysed_saved_and_counted(self) -> None:
        client = app.test_client()
        sign_up(client, "extension")
        answer = client.post("/api/extension/check", json={"product": sent_product()})
        self.assertEqual(answer.status_code, 202)
        job = self.wait_for(client, answer.get_json()["job"]["id"])
        self.assertEqual(job["state"], "complete", job.get("message"))
        self.assertEqual(len(self.saved), 1)
        products, source = self.saved[0]
        self.assertEqual(source, "defaketive-extension")
        self.assertTrue(products[0]["analyzed"])
        # The person's session now holds the report, as after a scan, so the screens open it the same way.
        listed = client.get("/api/products").get_json()
        self.assertEqual([card["link"] for card in listed["products"]], [LINK])
        self.assertEqual(accounts.guest_scans_used(app.config["ACCOUNTS_DB"], protections.SITE_KEY, accounts.manila_day()), 1)

    def test_data_that_does_not_add_up_is_refused_and_not_counted(self) -> None:
        client = app.test_client()
        sign_up(client, "invalid")
        sent = sent_product()
        sent["ratings"]["average"] = 1.0
        answer = client.post("/api/extension/check", json={"product": sent})
        self.assertEqual(answer.status_code, 400)
        self.assertTrue(answer.get_json()["invalid"])
        self.assertEqual(self.saved, [])
        self.assertEqual(accounts.guest_scans_used(app.config["ACCOUNTS_DB"], protections.SITE_KEY, accounts.manila_day()), 0)

    def test_the_account_limit_counts_extension_checks(self) -> None:
        saved_limit = protections.limits.account
        protections.limits.account = 1
        self.addCleanup(setattr, protections.limits, "account", saved_limit)
        client = app.test_client()
        sign_up(client, "extlimit")
        first = client.post("/api/extension/check", json={"product": sent_product()})
        self.wait_for(client, first.get_json()["job"]["id"])
        second = client.post("/api/extension/check", json={"product": sent_product()})
        self.assertEqual(second.status_code, 429)
        self.assertTrue(second.get_json()["account_limit"])


if __name__ == "__main__":
    unittest.main()
