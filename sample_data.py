import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bspb_site.settings')
import django
django.setup()

from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from core.models import Account, Transaction


def main():
    User.objects.all().delete()
    Account.objects.all().delete()
    Transaction.objects.all().delete()

    user = User.objects.create_user(username='demo', password='demo')
    account = Account.objects.create(number='40817810000000000001', user=user)
    balance = Decimal('10000.00')
    for i in range(10):
        amount = Decimal('1000.00')
        balance -= amount
        Transaction.objects.create(
            account=account,
            date=date(2024, 1, 1) + timedelta(days=i * 3),
            counterparty=f'Контрагент {i}',
            description=f'Покупка №{i}',
            amount=-amount,
            balance=balance,
        )


if __name__ == '__main__':
    main()
