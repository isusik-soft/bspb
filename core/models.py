from django.db import models
from django.contrib.auth.models import User


class Account(models.Model):
    number = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(User, related_name='accounts', on_delete=models.CASCADE)
    currency = models.CharField(max_length=3, default='RUB')

    def __str__(self):
        return self.number


class Transaction(models.Model):
    account = models.ForeignKey(Account, related_name='transactions', on_delete=models.CASCADE)
    date = models.DateField()
    description = models.CharField(max_length=255)
    counterparty = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.date} {self.amount}"


class Statement(models.Model):
    account = models.ForeignKey(Account, related_name='statements', on_delete=models.CASCADE)
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Statement {self.id}"


class StatementTransaction(models.Model):
    statement = models.ForeignKey(Statement, related_name='entries', on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, related_name='statement_entries', on_delete=models.CASCADE)
    running_balance = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Entry {self.id}"
