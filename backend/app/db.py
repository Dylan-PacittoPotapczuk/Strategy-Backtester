"""SQLite persistence for backtest runs, Monte Carlo, and config presets."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    BenchmarkResult,
    ConfigPreset,
    EquityPoint,
    Metrics,
    MonteCarloRequest,
    MonteCarloResponse,
    MonteCarloResult,
    RunSummary,
    Trade,
    WalkForwardResult,
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
                    error TEXT,
                    name TEXT
                )
                """
            )
            # Migrate older DBs that lack name
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(backtest_runs)").fetchall()
            }
            if "name" not in cols:
                conn.execute("ALTER TABLE backtest_runs ADD COLUMN name TEXT")

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS config_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    config_json TEXT NOT NULL
                )
                """
            )

    def create(self, request: BacktestRequest) -> BacktestResponse:
        run_id = uuid4()
        created = datetime.now(timezone.utc)
        name = (request.name or "").strip() or None
        resp = BacktestResponse(
            id=run_id,
            created_at=created,
            status=BacktestStatus.PENDING,
            request=request,
            name=name,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_runs
                    (id, created_at, status, request_json, result_json, error, name)
                VALUES (?, ?, ?, ?, NULL, NULL, ?)
                """,
                (
                    str(run_id),
                    created.isoformat(),
                    BacktestStatus.PENDING.value,
                    request.model_dump_json(),
                    name,
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
            "walk_forward": (
                response.walk_forward.model_dump(mode="json")
                if response.walk_forward
                else None
            ),
            "benchmark": (
                response.benchmark.model_dump(mode="json") if response.benchmark else None
            ),
            "no_oos_warning": response.no_oos_warning,
        }
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE backtest_runs
                SET status = ?, result_json = ?, error = ?, name = ?
                WHERE id = ?
                """,
                (
                    response.status.value,
                    json.dumps(result),
                    response.error,
                    response.name,
                    str(response.id),
                ),
            )

    def rename(self, run_id: UUID, name: str) -> Optional[BacktestResponse]:
        cleaned = name.strip()
        if not cleaned:
            return None
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE backtest_runs SET name = ? WHERE id = ?",
                (cleaned, str(run_id)),
            )
            if cur.rowcount == 0:
                return None
        run = self.get(run_id)
        if run:
            run.name = cleaned
        return run

    def get(self, run_id: UUID) -> Optional[BacktestResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE id = ?", (str(run_id),)
            ).fetchone()
        if not row:
            return None
        return self._row_to_response(row)

    def _row_to_response(self, row: sqlite3.Row) -> BacktestResponse:
        request = BacktestRequest.model_validate_json(row["request_json"])
        created = datetime.fromisoformat(row["created_at"])
        status = BacktestStatus(row["status"])
        equity_curve: list[EquityPoint] = []
        trades: list[Trade] = []
        metrics: Optional[Metrics] = None
        daily_returns: list[float] = []
        dd_halted = False
        dd_halt_date = None
        walk_forward: Optional[WalkForwardResult] = None
        benchmark: Optional[BenchmarkResult] = None
        no_oos_warning: Optional[str] = None
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
            if result.get("walk_forward"):
                walk_forward = WalkForwardResult.model_validate(result["walk_forward"])
            if result.get("benchmark"):
                benchmark = BenchmarkResult.model_validate(result["benchmark"])
            no_oos_warning = result.get("no_oos_warning")
        name = row["name"] if "name" in row.keys() else None
        return BacktestResponse(
            id=UUID(row["id"]),
            created_at=created,
            status=status,
            request=request,
            name=name,
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
            daily_returns=daily_returns,
            error=row["error"],
            dd_halted=dd_halted,
            dd_halt_date=dd_halt_date,
            walk_forward=walk_forward,
            benchmark=benchmark,
            no_oos_warning=no_oos_warning,
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

    def list_summaries(self, limit: int = 30) -> list[RunSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, status, request_json, result_json, name
                FROM backtest_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: list[RunSummary] = []
        for row in rows:
            req = BacktestRequest.model_validate_json(row["request_json"])
            total_return = None
            if row["result_json"]:
                result = json.loads(row["result_json"])
                m = result.get("metrics") or {}
                total_return = m.get("total_return")
            out.append(
                RunSummary(
                    id=UUID(row["id"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    name=row["name"],
                    status=BacktestStatus(row["status"]),
                    strategy_type=req.strategy.type,
                    symbols=req.symbols,
                    start_date=req.start_date,
                    end_date=req.end_date,
                    total_return=total_return,
                    walk_forward_enabled=req.walk_forward.enabled,
                    benchmark_symbol=req.benchmark.symbol if req.benchmark.enabled else None,
                )
            )
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

    # --- Config presets -----------------------------------------------------

    def create_preset(self, name: str, config: dict[str, Any]) -> ConfigPreset:
        preset_id = uuid4()
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO config_presets
                    (id, name, created_at, updated_at, config_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(preset_id),
                    name.strip(),
                    now.isoformat(),
                    now.isoformat(),
                    json.dumps(config),
                ),
            )
        return ConfigPreset(
            id=preset_id,
            name=name.strip(),
            created_at=now,
            updated_at=now,
            config=config,
        )

    def list_presets(self, limit: int = 50) -> list[ConfigPreset]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM config_presets
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_preset(r) for r in rows]

    def get_preset(self, preset_id: UUID) -> Optional[ConfigPreset]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM config_presets WHERE id = ?", (str(preset_id),)
            ).fetchone()
        if not row:
            return None
        return self._row_to_preset(row)

    def update_preset(
        self,
        preset_id: UUID,
        *,
        name: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> Optional[ConfigPreset]:
        existing = self.get_preset(preset_id)
        if not existing:
            return None
        new_name = name.strip() if name else existing.name
        new_config = config if config is not None else existing.config
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE config_presets
                SET name = ?, config_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_name, json.dumps(new_config), now.isoformat(), str(preset_id)),
            )
        return ConfigPreset(
            id=preset_id,
            name=new_name,
            created_at=existing.created_at,
            updated_at=now,
            config=new_config,
        )

    def delete_preset(self, preset_id: UUID) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM config_presets WHERE id = ?", (str(preset_id),)
            )
            return cur.rowcount > 0

    @staticmethod
    def _row_to_preset(row: sqlite3.Row) -> ConfigPreset:
        return ConfigPreset(
            id=UUID(row["id"]),
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            config=json.loads(row["config_json"]),
        )
