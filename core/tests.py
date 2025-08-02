import json
from datetime import date

from django.test import TestCase, Client
from django.contrib.auth.models import User

from .models import Account, Transaction, Statement


class StatementAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create two users
        self.u1 = User.objects.create_user(username="u1", password="pw")
        self.u2 = User.objects.create_user(username="u2", password="pw")
        # create accounts
        self.a1 = Account.objects.create(number="111", user=self.u1)
        self.a2 = Account.objects.create(number="222", user=self.u2)
        # create transactions for each account
        Transaction.objects.create(
            account=self.a1,
            date=date(2024, 1, 1),
            description="t1",
            counterparty="",
            amount=10,
            balance=10,
        )
        Transaction.objects.create(
            account=self.a2,
            date=date(2024, 1, 1),
            description="t2",
            counterparty="",
            amount=20,
            balance=20,
        )

    def _generate(self, user, account):
        self.client.logout()
        assert self.client.login(username=user.username, password="pw")
        resp = self.client.post(
            "/statement/generate",
            data=json.dumps(
                {
                    "account_id": account.id,
                    "from": "2024-01-01",
                    "to": "2024-01-01",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["id"]

    def test_list_shows_only_user_statements(self):
        id1 = self._generate(self.u1, self.a1)
        self._generate(self.u2, self.a2)

        # list for user1
        self.client.logout()
        self.client.login(username="u1", password="pw")
        resp = self.client.get("/statements")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], id1)
        self.assertEqual(Statement.objects.get(id=id1).generated_by, "u1")
