from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.layers.rule_intelligence_layer.config import get_rule_scheduler_config
from app.layers.rule_intelligence_layer.service import RuleIntelligenceService


logger = logging.getLogger(__name__)


class RuleSyncScheduler:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._svc = RuleIntelligenceService()

    def start(self) -> None:
        cfg = get_rule_scheduler_config()
        enabled = bool(cfg.get("enabled")) if isinstance(cfg, dict) else False
        if not enabled:
            return
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        while True:
            cfg = get_rule_scheduler_config()
            interval_s = int((cfg.get("interval_seconds") or 0) if isinstance(cfg, dict) else 0) or 900
            try:
                self._run_once(cfg if isinstance(cfg, dict) else {})
            except Exception as e:
                logger.exception("rule_sync_failed error=%s", str(e))
            await asyncio.sleep(float(interval_s))

    def _run_once(self, cfg: Dict[str, Any]) -> None:
        if SessionLocal is None:
            return
        db: Session = SessionLocal()
        try:
            gmail_cfg = cfg.get("gmail") if isinstance(cfg.get("gmail"), dict) else {}
            if bool(gmail_cfg.get("enabled")):
                self._svc.ingest_gmail(
                    db,
                    query=str(gmail_cfg.get("query") or ""),
                    label_ids=gmail_cfg.get("label_ids") if isinstance(gmail_cfg.get("label_ids"), list) else [],
                    max_results=int(gmail_cfg.get("max_results") or 10),
                )
        finally:
            db.close()

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
