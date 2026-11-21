import os
import sqlite3
import tempfile
import unittest

import app as checkout_app


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = checkout_app.DB_PATH
        checkout_app.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        checkout_app.init_db()
        checkout_app.app.config["TESTING"] = True
        self.client = checkout_app.app.test_client()
        self.client.post(
            "/login", data={"username": "melek", "password": "motdepasse1"}
        )

    def tearDown(self):
        checkout_app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def start_checkout(self, card_number="4242424242424242"):
        return self.client.post(
            "/checkout/1/start",
            data={
                "card_number": card_number,
                "expiry": "12/30",
                "cvc": "123",
            },
        )

    def get_checkout_record(self):
        db = sqlite3.connect(checkout_app.DB_PATH)
        try:
            return db.execute(
                "SELECT id, status, attempts FROM demo_checkouts"
            ).fetchone()
        finally:
            db.close()

    def test_catalog_has_a_buy_button_for_each_product(self):
        response = self.client.get("/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'>Acheter</a>'), 9)

    def test_only_synthetic_card_is_accepted_and_not_stored(self):
        response = self.start_checkout(card_number="4111111111111111")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"carte fictive", response.data)

        response = self.start_checkout()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"123456", response.data)
        self.assertNotIn(b"4242424242424242", response.data)

        db = sqlite3.connect(checkout_app.DB_PATH)
        try:
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(demo_checkouts)")
            }
        finally:
            db.close()
        self.assertNotIn("card_number", columns)
        self.assertNotIn("cvc", columns)

    def test_wrong_otp_cannot_be_overridden_by_client_success_field(self):
        response = self.start_checkout()
        self.assertEqual(response.status_code, 200)

        db = sqlite3.connect(checkout_app.DB_PATH)
        try:
            checkout_id = db.execute(
                "SELECT id FROM demo_checkouts"
            ).fetchone()[0]
        finally:
            db.close()

        response = self.client.post(
            "/checkout/verify",
            data={"checkout_id": checkout_id, "otp": "000000", "success": "true"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Code incorrect", response.data)
        self.assertEqual(self.get_checkout_record()[1:], ("pending", 1))

        response = self.client.post(
            "/checkout/verify",
            data={"checkout_id": checkout_id, "otp": "123456", "success": "false"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Commande de démonstration confirmée".encode(), response.data)
        self.assertEqual(self.get_checkout_record()[1:], ("completed", 1))

        response = self.client.post(
            "/checkout/verify",
            data={"checkout_id": checkout_id, "otp": "123456"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
