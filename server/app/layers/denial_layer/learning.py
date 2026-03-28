from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.denial import LearningLog


@dataclass(frozen=True)
class StrategyPrior:
    success_rate: float
    samples: int
    boost: float

    def to_dict(self) -> Dict[str, Any]:
        return {"success_rate": float(self.success_rate), "samples": int(self.samples), "boost": float(self.boost)}


class LearningService:
    def compute_strategy_prior(
        self,
        db: Session,
        *,
        denial_type: str,
        root_cause_category: str,
        strategy_id: str,
        thresholds_cfg: Dict[str, Any],
    ) -> StrategyPrior:
        learning_cfg = thresholds_cfg.get("learning") or {}
        enabled = bool(learning_cfg.get("enabled", True))
        if not enabled:
            return StrategyPrior(success_rate=float(learning_cfg.get("prior_success", 0.0) or 0.0), samples=0, boost=0.0)

        prior_success = float(learning_cfg.get("prior_success", 0.5) or 0.5)
        alpha = float(learning_cfg.get("smoothing_alpha", 1.0) or 1.0)
        min_samples = int(learning_cfg.get("min_samples_for_boost", 0) or 0)
        max_boost = float(learning_cfg.get("max_boost", 0.0) or 0.0)

        stmt = (
            select(
                func.count(LearningLog.id),
                func.sum(case((LearningLog.outcome == "approved", 1), else_=0)),
            )
            .where(LearningLog.denial_type == str(denial_type or ""))
            .where(LearningLog.root_cause_category == str(root_cause_category or ""))
            .where(LearningLog.strategy_id == str(strategy_id or ""))
        )
        row = db.execute(stmt).first()
        total = int(row[0] or 0) if row else 0
        approved = int(row[1] or 0) if row else 0

        rate = (approved + alpha * prior_success) / (total + alpha) if (total + alpha) > 0 else prior_success
        boost = 0.0
        if total >= min_samples:
            boost = min(max_boost, max(0.0, float(rate - prior_success)))
        return StrategyPrior(success_rate=float(rate), samples=total, boost=float(boost))

    def log_outcome(
        self,
        db: Session,
        *,
        claim_id: str,
        denial_type: str,
        root_cause_category: str,
        strategy_id: str,
        outcome: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        db.add(
            LearningLog(
                claim_id=claim_id,
                denial_type=str(denial_type or ""),
                root_cause_category=str(root_cause_category or ""),
                strategy_id=str(strategy_id or ""),
                outcome=str(outcome or ""),
                meta=meta or {},
            )
        )
        db.commit()
