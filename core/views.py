from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from io import BytesIO

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse, FileResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Account, Statement, Template, UserProfile
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


@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def panel(request):
    """Панель управления пользователями и их подписками."""

    created_user: dict[str, str] | None = None
    if request.method == "POST":
        if "create_user" in request.POST:
            email = request.POST.get("email", "").strip()
            if email:
                password = get_random_string(10)
                user = User.objects.create_user(username=email, email=email, password=password)
                UserProfile.objects.create(user=user)
                created_user = {"email": email, "password": password}
        elif "update_subscription" in request.POST:
            user_id = request.POST.get("user_id")
            end_date = request.POST.get("subscription_end")
            profile = get_object_or_404(UserProfile, user_id=user_id)
            if end_date:
                profile.subscription_end = datetime.fromisoformat(end_date).date()
            else:
                profile.subscription_end = None
            profile.save()

    users = list(User.objects.order_by("id"))
    for u in users:
        UserProfile.objects.get_or_create(user=u)
    users = User.objects.order_by("id").select_related("profile")
    context = {
        "users": users,
        "created_user": created_user,
    }
    return render(request, "panel.html", context)


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
            'owner': payload.get('fio', s.account.user.username if s.account and s.account.user else ''),
            'period_start': s.period_start.isoformat(),
            'period_end': s.period_end.isoformat(),
            'bank': payload.get('bank', 'BSPB'),
            'generated_at': s.created_at.isoformat(),
        })
    return JsonResponse(data, safe=False)


@csrf_exempt
@login_required
def templates_api(request, field: str):
    valid_fields = {choice[0] for choice in Template.FIELD_CHOICES}
    if field not in valid_fields:
        return JsonResponse({'error': 'unknown field'}, status=400)

    if request.method == 'GET':
        items = list(
            Template.objects.filter(user=request.user, field=field).values_list('text', flat=True)
        )
        return JsonResponse(items, safe=False)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            if not isinstance(payload, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Body must be JSON list'}, status=400)

        Template.objects.filter(user=request.user, field=field).delete()
        for text in payload:
            Template.objects.create(user=request.user, field=field, text=text)
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)
