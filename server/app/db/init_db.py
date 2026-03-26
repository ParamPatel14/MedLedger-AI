from app.db.base import Base
from app.db.session import engine
from app.models.term import ClinicalTerm


def init_db() -> None:
    if engine is None:
        return
    Base.metadata.create_all(bind=engine)

