from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from io import BytesIO

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Account, Statement
from statement_generator import StatementData, generate_statement_pdf

BASE_DIR = Path(__file__).resolve().parent.parent
STATEMENTS_DIR = BASE_DIR / 'statements'
STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SimpleUser:
    username: str


@dataclass
class SimpleAccount:
    number: str
    currency: str = 'RUB'
    user: SimpleUser | None = None


@dataclass
class SimpleStatement:
    period_start: date
    period_end: date
    created_at: datetime = datetime.utcnow()
    generated_by: str = 'manual'


@dataclass
class SimpleTransaction:
    date: date
    description: str
    counterparty: str
    amount: float
    balance: float


def parse_amount(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace('\xa0', '').replace(' ', '').replace(',', '.')
    return float(value)


@login_required
def index(request):
    return render(request, 'index.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('index')
        return render(request, 'login.html', {'error': 'Неверные данные'})
    return render(request, 'login.html')


def logout_view(request):
    auth_logout(request)
    return redirect('login')


@csrf_exempt
@require_POST
@login_required
def statement_custom(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Тело должно быть JSON'}, status=400)

    try:
        stmt_id = payload.get('id')
        fio = payload['fio']
        account_number = payload['account']
        start = datetime.fromisoformat(payload['from']).date()
        end = datetime.fromisoformat(payload['to']).date()
        opening_raw = payload.get('opening_balance')
        opening_balance = parse_amount(opening_raw) if opening_raw is not None else 0
        ops = payload.get('operations', [])
    except KeyError as e:
        return JsonResponse({'error': f'Отсутствует поле: {e.args[0]}'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Ошибка разбора даты/суммы: {e}'}, status=400)

    account, _ = Account.objects.get_or_create(number=account_number, defaults={'user': request.user})

    if stmt_id:
        statement = get_object_or_404(Statement, pk=stmt_id, generated_by=request.user.username)
        statement.account = account
        statement.period_start = start
        statement.period_end = end
        statement.data = payload
        statement.save()
    else:
        statement = Statement.objects.create(
            account=account,
            period_start=start,
            period_end=end,
            generated_by=request.user.username,
            data=payload,
        )

    running_balance = opening_balance
    transactions: list[SimpleTransaction] = []
    for op in ops:
        try:
            dt = datetime.fromisoformat(op['date']).date()
            amount = parse_amount(op['amount'])
            desc = op.get('description', '')
            cp = op.get('counterparty', '')
        except KeyError as e:
            return JsonResponse({'error': f'Отсутствует поле операции: {e.args[0]}'}, status=400)
        except ValueError as e:
            return JsonResponse({'error': f'Ошибка в операции: {e}'}, status=400)
        running_balance += amount
        transactions.append(
            SimpleTransaction(
                date=dt,
                description=desc,
                counterparty=cp,
                amount=amount,
                balance=running_balance,
            )
        )

    stmt_obj = SimpleStatement(period_start=start, period_end=end)
    user_obj = SimpleUser(username=fio)
    account_obj = SimpleAccount(number=account_number, user=user_obj)

    stmt_data = StatementData(
        statement=stmt_obj,
        account=account_obj,
        transactions=transactions,
        opening_balance=opening_balance,
    )
    pdf_bytes = generate_statement_pdf(stmt_data)
    pdf_file = STATEMENTS_DIR / f'statement_{statement.id}.pdf'
    pdf_file.write_bytes(pdf_bytes)

    return JsonResponse({'id': statement.id})


@login_required
def statement_meta(request, statement_id: int):
    stmt = get_object_or_404(Statement, pk=statement_id, generated_by=request.user.username)
    payload = stmt.data or {}
    return JsonResponse({
        'id': stmt.id,
        'bank': payload.get('bank', 'BSPB'),
        'account': payload.get('account', stmt.account.number if stmt.account else ''),
        'fio': payload.get('fio', ''),
        'from': stmt.period_start.isoformat(),
        'to': stmt.period_end.isoformat(),
        'opening_balance': payload.get('opening_balance', 0),
        'operations': payload.get('operations', []),
    })


@login_required
def statement_pdf(request, statement_id: int):
    file_path = STATEMENTS_DIR / f'statement_{statement_id}.pdf'
    if not file_path.exists():
        return HttpResponseNotFound()
    return FileResponse(open(file_path, 'rb'), content_type='application/pdf')


@login_required
def list_statements_meta(request):
    stmts = (
        Statement.objects.filter(generated_by=request.user.username)
        .order_by('-created_at')
    )
    data = []
    for s in stmts:
        payload = s.data or {}
        data.append({
            'id': s.id,
            'account_number': payload.get('account', s.account.number if s.account else ''),
            'owner': payload.get('fio', s.account.user.username if s.account and s.account.user else ''),
            'period_start': s.period_start.isoformat(),
            'period_end': s.period_end.isoformat(),
            'status': payload.get('status'),
            'generated_at': s.created_at.isoformat(),
        })
    return JsonResponse(data, safe=False)
