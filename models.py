from datetime import datetime
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

    accounts = relationship("Account", back_populates="user")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    number = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    currency = Column(String, default="RUB")

    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")
    statements = relationship("Statement", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    date = Column(Date, default=datetime.utcnow)
    description = Column(String, nullable=False)
    counterparty = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    balance = Column(Numeric(12, 2), nullable=False)

    account = relationship("Account", back_populates="transactions")
    statement_entries = relationship(
        "StatementTransaction", back_populates="transaction"
    )


class Statement(Base):
    __tablename__ = "statements"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String, nullable=True)

    account = relationship("Account", back_populates="statements")
    entries = relationship(
        "StatementTransaction", back_populates="statement", cascade="all, delete-orphan"
    )


class StatementTransaction(Base):
    __tablename__ = "statement_transactions"

    id = Column(Integer, primary_key=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    running_balance = Column(Numeric(12, 2), nullable=False)

    statement = relationship("Statement", back_populates="entries")
    transaction = relationship("Transaction", back_populates="statement_entries")
