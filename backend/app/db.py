"""SQLite persistence for backtest runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    EquityPoint,
    Metrics,
    MonteCarloRequest,
    MonteCarloResponse,
    MonteCarloResult,
    Trade,
)

DB_PATH = Path(__file__).resolve().parent.parent / "cache" / "runs.sqlite"


class RunStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS monte_carlo_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    backtest_run_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    FOREIGN KEY (backtest_run_id) REFERENCES backtest_runs(id)
                )
                """
            )

    def create(self, request: BacktestRequest) -> BacktestResponse:
        run_id = uuid4()
        created = datetime.now(timezone.utc)
        resp = BacktestResponse(
            id=run_id,
            created_at=created,
            status=BacktestStatus.PENDING,
            request=request,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_runs (id, created_at, status, request_json, result_json, error)
                VALUES (?, ?, ?, ?, NULL, NULL)
                """,
                (
                    str(run_id),
                    created.isoformat(),
                    BacktestStatus.PENDING.value,
                    request.model_dump_json(),
                ),
            )
        return resp

    def update(self, response: BacktestResponse) -> None:
        result = {
            "equity_curve": [e.model_dump(mode="json") for e in response.equity_curve],
            "trades": [t.model_dump(mode="json") for t in response.trades],
            "metrics": response.metrics.model_dump(mode="json") if response.metrics else None,
            "daily_returns": response.daily_returns,
            "dd_halted": response.dd_halted,
            "dd_halt_date": response.dd_halt_date.isoformat() if response.dd_halt_date else None,
        }
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE backtest_runs
                SET status = ?, result_json = ?, error = ?
                WHERE id = ?
                """,
                (
                    response.status.value,
                    json.dumps(result),
                    response.error,
                    str(response.id),
                ),
            )

    def get(self, run_id: UUID) -> Optional[BacktestResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE id = ?", (str(run_id),)
            ).fetchone()
        if not row:
            return None
        request = BacktestRequest.model_validate_json(row["request_json"])
        created = datetime.fromisoformat(row["created_at"])
        status = BacktestStatus(row["status"])
        equity_curve: list[EquityPoint] = []
        trades: list[Trade] = []
        metrics: Optional[Metrics] = None
        daily_returns: list[float] = []
        dd_halted = False
        dd_halt_date = None
        if row["result_json"]:
            result = json.loads(row["result_json"])
            equity_curve = [EquityPoint.model_validate(e) for e in result.get("equity_curve", [])]
            trades = [Trade.model_validate(t) for t in result.get("trades", [])]
            if result.get("metrics"):
                metrics = Metrics.model_validate(result["metrics"])
            daily_returns = result.get("daily_returns", [])
            dd_halted = bool(result.get("dd_halted", False))
            if result.get("dd_halt_date"):
                from datetime import date as date_cls

                dd_halt_date = date_cls.fromisoformat(result["dd_halt_date"])
        return BacktestResponse(
            id=UUID(row["id"]),
            created_at=created,
            status=status,
            request=request,
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
            daily_returns=daily_returns,
            error=row["error"],
            dd_halted=dd_halted,
            dd_halt_date=dd_halt_date,
        )

    def list_recent(self, limit: int = 20) -> list[BacktestResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM backtest_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[BacktestResponse] = []
        for r in rows:
            item = self.get(UUID(r["id"]))
            if item:
                out.append(item)
        return out

    def create_monte_carlo(
        self,
        backtest_run_id: UUID,
        request: MonteCarloRequest,
        result: MonteCarloResult,
    ) -> MonteCarloResponse:
        run_id = uuid4()
        created = datetime.now(timezone.utc)
        resp = MonteCarloResponse(
            id=run_id,
            created_at=created,
            backtest_run_id=backtest_run_id,
            request=request,
            result=result,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO monte_carlo_runs
                    (id, created_at, backtest_run_id, request_json, result_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(run_id),
                    created.isoformat(),
                    str(backtest_run_id),
                    request.model_dump_json(),
                    result.model_dump_json(),
                ),
            )
        return resp

    def get_monte_carlo(self, mc_id: UUID) -> Optional[MonteCarloResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM monte_carlo_runs WHERE id = ?", (str(mc_id),)
            ).fetchone()
        if not row:
            return None
        return MonteCarloResponse(
            id=UUID(row["id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            backtest_run_id=UUID(row["backtest_run_id"]),
            request=MonteCarloRequest.model_validate_json(row["request_json"]),
            result=MonteCarloResult.model_validate_json(row["result_json"]),
        )

    def list_monte_carlo_for_backtest(
        self, backtest_run_id: UUID, limit: int = 10
    ) -> list[MonteCarloResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM monte_carlo_runs
                WHERE backtest_run_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (str(backtest_run_id), limit),
            ).fetchall()
        out: list[MonteCarloResponse] = []
        for r in rows:
            item = self.get_monte_carlo(UUID(r["id"]))
            if item:
                out.append(item)
        return out
