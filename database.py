from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base


def init_db(url: str):
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
