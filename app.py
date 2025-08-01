from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, abort, jsonify, request, send_file
from sqlalchemy.orm import Session

from database import init_db
from models import Account, Statement, StatementTransaction, Transaction
from statement_generator import StatementData, generate_statement_pdf

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


def parse_iso_date(value: Optional[str]) -> Optional[datetime.date]:
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
        statement = Statement(
            account_id=account.id,
            period_start=start,
            period_end=end,
            generated_by=user,
        )
        db.add(statement)
        running_balance = 0
        for t in txs:
            running_balance = t.balance
            db.add(
                StatementTransaction(
                    statement=statement,
                    transaction=t,
                    running_balance=running_balance,
                )
            )
        db.commit()

        stmt_data = StatementData(statement=statement, account=account, transactions=txs)
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


if __name__ == "__main__":
    debug_flag = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=3000, debug=debug_flag)
