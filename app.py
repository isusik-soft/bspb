from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from flask import Flask, abort, jsonify, request, send_file, render_template
from sqlalchemy.orm import Session

from database import init_db
from models import Account, Statement, StatementTransaction, Transaction
from statement_generator import StatementData, generate_statement_pdf
from dataclasses import dataclass
from io import BytesIO

# --- конфиг путей ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATEMENTS_DIR = BASE_DIR / "statements"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATEMENTS_DIR.mkdir(parents=True, exist_ok=True)

# --- база ---
default_sqlite = f"sqlite:///{(DATA_DIR / 'bspb.db')}"
DB_URL = os.environ.get("DATABASE_URL", default_sqlite)
SessionLocal = init_db(DB_URL)

# --- фласк ---
app = Flask(__name__)


# --- простые структуры данных для ручной генерации ---


@dataclass
class SimpleUser:
    username: str


@dataclass
class SimpleAccount:
    number: str
    currency: str = "RUB"
    user: SimpleUser | None = None


@dataclass
class SimpleStatement:
    period_start: date
    period_end: date
    created_at: datetime = datetime.utcnow()
    generated_by: str = "manual"


@dataclass
class SimpleTransaction:
    date: date
    description: str
    counterparty: str
    amount: float
    balance: float


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        # поддерживаем как дата, так и полное время
        dt = datetime.fromisoformat(value)
        return dt.date()
    except ValueError:
        # попробуем вырезать только часть даты (на всякий случай)
        try:
            return datetime.fromisoformat(value.split("T")[0]).date()
        except Exception:
            return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/accounts", methods=["GET"])
def accounts():
    with SessionLocal() as db:  # type: Session
        accounts = db.query(Account).all()
        return jsonify([
            {"id": a.id, "number": a.number, "currency": a.currency} for a in accounts
        ])


@app.route("/transactions", methods=["GET"])
def list_transactions():
    account_id = request.args.get("account")
    start_raw = request.args.get("from")
    end_raw = request.args.get("to")

    start = parse_iso_date(start_raw)
    end = parse_iso_date(end_raw)
    if (start_raw and start is None) or (end_raw and end is None):
        return jsonify({"error": "Неправильный формат даты. Ожидается ISO (YYYY-MM-DD или с временем)."}), 400

    with SessionLocal() as db:
        query = db.query(Transaction)
        if account_id:
            try:
                query = query.filter(Transaction.account_id == int(account_id))
            except ValueError:
                return jsonify({"error": "account должен быть целым числом"}), 400
        if start:
            query = query.filter(Transaction.date >= start)
        if end:
            query = query.filter(Transaction.date <= end)
        txs = query.order_by(Transaction.date, Transaction.id).all()
        return jsonify(
            [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "description": t.description,
                    "amount": float(t.amount),
                    "balance": float(t.balance),
                }
                for t in txs
            ]
        )


@app.route("/statement/custom", methods=["POST"])
def statement_custom():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"error": "Тело должно быть JSON"}), 400

    try:
        fio = payload["fio"]
        account_number = payload["account"]
        start = datetime.fromisoformat(payload["from"]).date()
        end = datetime.fromisoformat(payload["to"]).date()
        opening_raw = payload.get("opening_balance")
        opening_balance = float(opening_raw) if opening_raw is not None else None
        ops = payload.get("operations", [])
    except KeyError as e:
        return jsonify({"error": f"Отсутствует поле: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": f"Ошибка разбора даты/суммы: {e}"}), 400

    user = SimpleUser(username=fio)
    account = SimpleAccount(number=account_number, user=user)
    statement = SimpleStatement(period_start=start, period_end=end)

    running_balance = opening_balance if opening_balance is not None else 0
    transactions: list[SimpleTransaction] = []
    for op in ops:
        try:
            dt = datetime.fromisoformat(op["date"]).date()
            amount = float(op["amount"])
            desc = op.get("description", "")
            cp = op.get("counterparty", "")
        except KeyError as e:
            return jsonify({"error": f"Отсутствует поле операции: {e.args[0]}"}), 400
        except ValueError as e:
            return jsonify({"error": f"Ошибка в операции: {e}"}), 400
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

    stmt_data = StatementData(
        statement=statement,
        account=account,
        transactions=transactions,
        opening_balance=opening_balance,
    )
    pdf_bytes = generate_statement_pdf(stmt_data)

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="statement.pdf",
    )


@app.route("/statement/generate", methods=["POST"])
def generate_statement():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"error": "Тело должно быть JSON"}), 400

    try:
        account_id = int(payload["account_id"])
        start = datetime.fromisoformat(payload["from"]).date()
        end = datetime.fromisoformat(payload["to"]).date()
    except KeyError as e:
        return jsonify({"error": f"Отсутствует обязательное поле: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": f"Ошибка разбора даты/ид: {e}"}), 400

    user = payload.get("user", "system")
    opening_raw = payload.get("opening_balance")

    with SessionLocal() as db:
        account = db.get(Account, account_id)
        if not account:
            abort(404)
        txs = (
            db.query(Transaction)
            .filter(Transaction.account_id == account_id)
            .filter(Transaction.date >= start, Transaction.date <= end)
            .order_by(Transaction.date, Transaction.id)
            .all()
        )
        if opening_raw is not None:
            try:
                opening_balance = float(opening_raw)
            except (TypeError, ValueError):
                return jsonify({"error": "Ошибка разбора opening_balance"}), 400
        else:
            opening_tx = (
                db.query(Transaction)
                .filter(Transaction.account_id == account_id)
                .filter(Transaction.date < start)
                .order_by(Transaction.date.desc(), Transaction.id.desc())
                .first()
            )
            opening_balance = float(opening_tx.balance) if opening_tx else 0.0
        statement = Statement(
            account_id=account.id,
            period_start=start,
            period_end=end,
            generated_by=user,
        )
        db.add(statement)
        for t in txs:
            db.add(
                StatementTransaction(
                    statement=statement,
                    transaction=t,
                    running_balance=t.balance,
                )
            )
        db.commit()

        stmt_data = StatementData(
            statement=statement,
            account=account,
            transactions=txs,
            opening_balance=opening_balance,
        )
        pdf_bytes = generate_statement_pdf(stmt_data)

        pdf_file = STATEMENTS_DIR / f"statement_{statement.id}.pdf"
        pdf_file.write_bytes(pdf_bytes)
        return jsonify({"id": statement.id})


@app.route("/statement/<int:statement_id>", methods=["GET"])
def statement_meta(statement_id: int):
    with SessionLocal() as db:
        stmt = db.get(Statement, statement_id)
        if not stmt:
            abort(404)
        return jsonify(
            {
                "id": stmt.id,
                "account_id": stmt.account_id,
                "period_start": stmt.period_start.isoformat(),
                "period_end": stmt.period_end.isoformat(),
                "generated_at": stmt.created_at.isoformat(),
                "generated_by": stmt.generated_by,
            }
        )


@app.route("/statement/<int:statement_id>.pdf", methods=["GET"])
def statement_pdf(statement_id: int):
    file_path = STATEMENTS_DIR / f"statement_{statement_id}.pdf"
    if not file_path.exists():
        abort(404)
    return send_file(file_path, mimetype="application/pdf")


@app.route("/statements", methods=["GET"])
def list_statements_meta():
    with SessionLocal() as db:
        stmts = db.query(Statement).order_by(Statement.created_at.desc()).all()
        return jsonify(
            [
                {
                    "id": s.id,
                    "account_number": s.account.number,
                    "period_start": s.period_start.isoformat(),
                    "period_end": s.period_end.isoformat(),
                    "generated_at": s.created_at.isoformat(),
                }
                for s in stmts
            ]
        )


if __name__ == "__main__":
    debug_flag = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=3000, debug=debug_flag)
