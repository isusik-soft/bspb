import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from .models import Statement


class StatementAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create two users
        self.u1 = User.objects.create_user(username="u1", password="pw")
        self.u2 = User.objects.create_user(username="u2", password="pw")

    def _create(self, user, account_number):
        self.client.logout()
        assert self.client.login(username=user.username, password="pw")
        payload = {
            "fio": user.username,
            "account": account_number,
            "from": "2024-01-01",
            "to": "2024-01-31",
            "opening_balance": 0,
            "operations": [
                {
                    "date": "2024-01-01",
                    "counterparty": "",
                    "description": "t",
                    "amount": 10,
                }
            ],
        }
        resp = self.client.post(
            "/statement/custom",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["id"]

    def test_list_shows_only_user_statements(self):
        id1 = self._create(self.u1, "111")
        self._create(self.u2, "222")

        # list for user1
        self.client.logout()
        self.client.login(username="u1", password="pw")
        resp = self.client.get("/statements")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], id1)
        self.assertEqual(Statement.objects.get(id=id1).generated_by, "u1")


class TemplateAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pw")
        self.u2 = User.objects.create_user(username="u2", password="pw")

    def test_templates_stored_per_user(self):
        assert self.client.login(username="u1", password="pw")
        resp = self.client.post(
            "/templates/counterparty",
            data=json.dumps(["A", "B"]),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/templates/counterparty")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), ["A", "B"])

        self.client.logout()
        assert self.client.login(username="u2", password="pw")
        resp = self.client.get("/templates/counterparty")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])
