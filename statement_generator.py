from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from io import BytesIO

from PyPDF2 import PdfReader, PdfWriter
from weasyprint import HTML

from models import Account, Statement, Transaction
from zoneinfo import ZoneInfo


def format_datetime_msk(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y | %H:%M")


def format_amount(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def mask_account(number: str) -> str:
    return number[:-4].replace(number[:-4], "*" * (len(number) - 4)) + number[-4:]


def format_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def render_pdf(html: str, template_pdf: Optional[Path] = None) -> bytes:
    pdf_bytes = HTML(string=html, base_url=str(Path(".").resolve())).write_pdf()
    if not template_pdf:
        return pdf_bytes
    # overlay generated pdf onto template background
    reader_bg = PdfReader(str(template_pdf))
    reader_fg = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i, page in enumerate(reader_fg.pages):
        bg_page = reader_bg.pages[min(i, len(reader_bg.pages) - 1)]
        bg_page.merge_page(page)
        writer.add_page(bg_page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@dataclass
class StatementData:
    statement: Statement
    account: Account
    transactions: Iterable[Transaction]


def generate_statement_pdf(data: StatementData, template_pdf: Optional[Path] = None) -> bytes:
    env = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape(["html"])  # type: ignore
    )
    env.filters["amount"] = format_amount
    env.filters["mask"] = mask_account
    env.filters["date"] = format_date
    env.filters["datetime_msk"] = format_datetime_msk

    txs = list(data.transactions)
    opening_balance = txs[0].balance - txs[0].amount if txs else 0
    closing_balance = txs[-1].balance if txs else opening_balance
    total_incoming = sum(t.amount for t in txs if t.amount > 0)
    total_outgoing = sum(t.amount for t in txs if t.amount < 0)

    template = env.get_template("statement.html")
    html = template.render(
        data=data,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_incoming=total_incoming,
        total_outgoing=total_outgoing,
    )
    return render_pdf(html, template_pdf)
