from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file
from sqlalchemy.orm import Session

from database import init_db
from models import Account, Statement, StatementTransaction, Transaction
from statement_generator import StatementData, generate_statement_pdf

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///bspb.db")
SessionLocal = init_db(DB_URL)

app = Flask(__name__)


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
    start = request.args.get("from")
    end = request.args.get("to")
    with SessionLocal() as db:
        query = db.query(Transaction)
        if account_id:
            query = query.filter(Transaction.account_id == int(account_id))
        if start:
            query = query.filter(Transaction.date >= datetime.fromisoformat(start).date())
        if end:
            query = query.filter(Transaction.date <= datetime.fromisoformat(end).date())
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
    account_id = int(payload["account_id"])
    start = datetime.fromisoformat(payload["from"]).date()
    end = datetime.fromisoformat(payload["to"]).date()
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
        out_dir = Path("statements")
        out_dir.mkdir(exist_ok=True)
        pdf_file = out_dir / f"statement_{statement.id}.pdf"
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
    file_path = Path("statements") / f"statement_{statement_id}.pdf"
    if not file_path.exists():
        abort(404)
    return send_file(file_path, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True)
