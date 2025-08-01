from datetime import date, timedelta
from decimal import Decimal

from database import init_db
from models import Account, Transaction, User

SessionLocal = init_db("sqlite:///bspb.db")


def main():
    with SessionLocal() as db:
        user = User(username="demo", password_hash="demo")
        db.add(user)
        db.flush()
        account = Account(number="40817810000000000001", user_id=user.id)
        db.add(account)
        db.flush()
        balance = Decimal("10000.00")
        for i in range(10):
            amount = Decimal("1000.00")
            balance -= amount
            tx = Transaction(
                account_id=account.id,
                date=date(2024, 1, 1) + timedelta(days=i * 3),
                counterparty=f"Контрагент {i}",
                description=f"Покупка №{i}",
                amount=-amount,
                balance=balance,
            )
            db.add(tx)
        db.commit()


if __name__ == "__main__":
    main()
