from app.db.base import Base
from app.db.session import ensure_db_initialized, engine
from app.models.audit import AuditLog
from app.models.code import ClinicalCode
from app.models.entity import ClinicalEntity
from app.models.record import ClinicalRecord
from app.models.term import ClinicalTerm
from app.models.workflow import AgentOutput, WorkflowRecord, WorkflowState


def init_db() -> None:
    ensure_db_initialized()
    if engine is None:
        return
    Base.metadata.create_all(bind=engine)
