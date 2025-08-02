from django.contrib import admin
from .models import Account, Transaction, Statement, StatementTransaction

admin.site.register(Account)
admin.site.register(Transaction)
admin.site.register(Statement)
admin.site.register(StatementTransaction)
