from app.db.base import Base
from app.db.session import ensure_db_initialized, engine
from app.models.audit import AuditLog
from app.models.code import ClinicalCode
from app.models.entity import ClinicalEntity
from app.models.record import ClinicalRecord
from app.models.term import ClinicalTerm
from app.models.workflow import AgentOutput, WorkflowRecord, WorkflowState
from app.models.svm import SvmAuditLog
from app.models.governance import GovernanceAuditLog
from app.models.denial import Claim, CorrectionApplied, DenialEvent, LearningLog, Resubmission


def init_db() -> None:
    ensure_db_initialized()
    if engine is None:
        return
    Base.metadata.create_all(bind=engine)

    try:
        from sqlalchemy import inspect, text

        insp = inspect(engine)
        if "records" in set(insp.get_table_names()):
            cols = {c.get("name") for c in insp.get_columns("records")}
            if "timestamp" not in cols:
                with engine.begin() as conn:
                    dialect = engine.dialect.name
                    if dialect == "postgresql":
                        conn.execute(text("ALTER TABLE records ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ DEFAULT NOW()"))
                    else:
                        conn.execute(text("ALTER TABLE records ADD COLUMN timestamp DATETIME"))
                    if "created_at" in cols:
                        try:
                            conn.execute(text("UPDATE records SET timestamp = created_at WHERE timestamp IS NULL"))
                        except Exception:
                            pass
    except Exception:
        return
