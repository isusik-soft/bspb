from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

import inspect
import pydyf
from jinja2 import Environment, FileSystemLoader, select_autoescape
from io import BytesIO

from PyPDF2 import PdfReader, PdfWriter

# NOTE: Some deployments may have a combination of WeasyPrint and pydyf
# where WeasyPrint expects ``pydyf.PDF`` to accept additional ``version`` and
# ``identifier`` arguments.  Newer versions of ``pydyf`` removed these
# parameters, leading to ``TypeError`` when WeasyPrint attempts to call the
# constructor.  To remain compatible with both variants we monkeypatch
# ``pydyf.PDF.__init__`` to accept the optional arguments and ignore them when
# they are not supported.
if "version" not in inspect.signature(pydyf.PDF.__init__).parameters:
    _orig_pdf_init = pydyf.PDF.__init__

    def _patched_pdf_init(self, version=None, identifier=None):
        _orig_pdf_init(self)

    pydyf.PDF.__init__ = _patched_pdf_init

from weasyprint import HTML

from models import Account, Statement, Transaction
from zoneinfo import ZoneInfo


def format_ts(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y | %H:%M")


def rub_format(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def account_format(acc: str) -> str:
    digits = "".join(filter(str.isdigit, str(acc)))
    if len(digits) == 20:
        return f"{digits[0:5]} {digits[5:8]} {digits[8:9]} {digits[9:13]} {digits[13:]}"
    return acc


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

    # copy metadata from template and override creation date
    metadata = {}
    if reader_bg.metadata:
        metadata = {
            k: v
            for k, v in reader_bg.metadata.items()
            if isinstance(k, str) and isinstance(v, str)
        }
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    if offset:
        offset = f"{offset[:3]}'{offset[3:]}'"
    metadata["/CreationDate"] = now.strftime(f"D:%Y%m%d%H%M%S{offset}")
    writer.add_metadata(metadata)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@dataclass
class StatementData:
    statement: Statement
    account: Account
    transactions: Iterable[Transaction]
    opening_balance: Optional[float] = None


def generate_statement_pdf(data: StatementData, template_pdf: Optional[Path] = None) -> bytes:
    env = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape(["html"])  # type: ignore
    )
    env.filters["rub_format"] = rub_format
    env.filters["account_format"] = account_format
    env.filters["date"] = format_date
    env.filters["format_ts"] = format_ts

    txs = list(data.transactions)
    if data.opening_balance is not None:
        opening_balance = data.opening_balance
    else:
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
