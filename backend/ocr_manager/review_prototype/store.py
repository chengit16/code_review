"""原型 SQLite 的输入、尝试和比较版本；每次调用在短事务内写状态。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from ocr_manager.review_prototype.input import ReviewInput
from ocr_manager.review_prototype.result import Engine, HunkCoverage, ReviewResult

OCR_FIXTURE_CONFIGURATION = "synthetic-ocr-v1"

_SCHEMA = """
CREATE TABLE inputs (
    key TEXT PRIMARY KEY, snapshot TEXT NOT NULL
);
CREATE TABLE attempts (
    id INTEGER PRIMARY KEY,
    input_key TEXT NOT NULL REFERENCES inputs(key),
    engine TEXT NOT NULL CHECK (engine IN ('ocr_fixture', 'agent_fixture')),
    configuration TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'complete', 'partial', 'failed', 'skipped')),
    result TEXT,
    UNIQUE (id, input_key),
    CHECK ((result IS NULL) = (status IN ('queued', 'running')))
);
CREATE TABLE comparisons (
    id INTEGER PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    input_key TEXT NOT NULL REFERENCES inputs(key),
    previous_id INTEGER REFERENCES comparisons(id),
    ocr_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    FOREIGN KEY (ocr_id, input_key) REFERENCES attempts(id, input_key),
    FOREIGN KEY (agent_id, input_key) REFERENCES attempts(id, input_key)
);
"""


@dataclass(frozen=True)
class Comparison:
    """两个确定的尝试编号及上一版比较；后续重跑不改写这组引用。"""

    id: int
    input_key: str
    previous_id: int | None
    ocr_id: int
    agent_id: int


@dataclass(frozen=True)
class PrototypeStore:
    """仅由隔离演示创建的 SQLite 数据库，不调用平台迁移。"""

    path: Path

    @classmethod
    def create(cls, path: Path) -> PrototypeStore:
        """以独占创建保证不会在已有文件上初始化原型库。"""
        with path.open("xb"):
            pass
        store = cls(path)
        with store._connect() as db:
            db.executescript(_SCHEMA)
        return store

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _attempt(
        self, db: sqlite3.Connection, input_key: str, engine: Engine, configuration: str,
    ) -> int:
        record = db.execute(
            """INSERT INTO attempts (input_key, engine, configuration)
               VALUES (?, ?, ?) RETURNING id""",
            (input_key, engine, configuration),
        ).fetchone()
        return int(record["id"])

    def enqueue(
        self, snapshot: ReviewInput, *, request_key: str, configuration: str,
        previous: Comparison | None = None,
    ) -> Comparison:
        """原子分配两路尝试及比较；重跑复用已存的 OCR 结果，不重写旧比较。"""
        if not request_key or not configuration:
            raise ValueError("请求键和 Agent 配置不能为空")
        input_key = snapshot.key
        previous_id = previous.id if previous else None
        with self._connect() as db:
            # 1. 在同一写事务检查重复请求，避免相同请求建立孤立尝试。
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                """SELECT c.id, c.input_key, c.previous_id, c.ocr_id, c.agent_id,
                          a.configuration FROM comparisons c JOIN attempts a ON c.agent_id = a.id
                   WHERE c.request_key = ?""",
                (request_key,),
            ).fetchone()
            if existing:
                if (input_key, previous_id, configuration) != (
                    existing["input_key"], existing["previous_id"], existing["configuration"],
                ):
                    raise ValueError("请求键已绑定另一组输入、比较版本或配置")
                return Comparison(
                    existing["id"], input_key, previous_id,
                    existing["ocr_id"], existing["agent_id"],
                )

            # 2. 初次运行保存固定输入；重跑只接受数据库里的原始比较及终态尝试。
            db.execute(
                "INSERT INTO inputs VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (input_key, snapshot.encode()),
            )
            ocr_id = (
                self._attempt(db, input_key, "ocr_fixture", OCR_FIXTURE_CONFIGURATION)
                if previous_id is None else self._previous_ocr(db, previous_id, input_key)
            )
            agent_id = self._attempt(db, input_key, "agent_fixture", configuration)
            # 3. 尝试与版本引用一并提交；失败时也不会留下半组记录。
            row = db.execute(
                """INSERT INTO comparisons (request_key, input_key, previous_id, ocr_id, agent_id)
                   VALUES (?, ?, ?, ?, ?) RETURNING id""",
                (request_key, input_key, previous_id, ocr_id, agent_id),
            ).fetchone()
            return Comparison(row["id"], input_key, previous_id, ocr_id, agent_id)

    def _previous_ocr(self, db: sqlite3.Connection, previous_id: int, input_key: str) -> int:
        row = db.execute(
            """SELECT c.ocr_id FROM comparisons c
               JOIN attempts o ON c.ocr_id = o.id JOIN attempts a ON c.agent_id = a.id
               WHERE c.id = ? AND c.input_key = ? AND o.result IS NOT NULL
                 AND a.result IS NOT NULL""",
            (previous_id, input_key),
        ).fetchone()
        if row is None:
            raise ValueError("单侧重跑要求相同输入且上一版两路已结束")
        return int(row["ocr_id"])

    def execute(
        self, attempt_id: int, snapshot: ReviewInput, engine: Engine,
        run: Callable[[], ReviewResult], *, configuration: str,
    ) -> ReviewResult | None:
        """只领取一次；无法领取返回空值，程序异常落失败并向调用者报告。"""
        # 1. 短事务领取，校验已冻结的输入、引擎身份和配置。
        with self._connect() as db:
            changed = db.execute(
                """UPDATE attempts SET status = 'running'
                   WHERE id = ? AND input_key = ? AND engine = ? AND configuration = ?
                     AND status = 'queued'""",
                (attempt_id, snapshot.key, engine, configuration),
            ).rowcount
        if not changed:
            return None

        # 2. 脱离数据库事务执行，程序错误仍保留明确的失败尝试。
        try:
            result = run()
        except Exception:
            failure = ReviewResult(
                "failed", "execution_error",
                tuple(HunkCoverage(h.hunk_id, len(h.lines)) for h in snapshot.hunks),
            )
            self._finish(attempt_id, failure)
            raise

        # 3. 只允许正在运行的尝试写入一次终态与结果。
        self._finish(attempt_id, result)
        return result

    def _finish(self, attempt_id: int, result: ReviewResult) -> None:
        with self._connect() as db:
            changed = db.execute(
                "UPDATE attempts SET status = ?, result = ? WHERE id = ? AND status = 'running'",
                (result.status, json.dumps(asdict(result), ensure_ascii=False), attempt_id),
            ).rowcount
            if changed != 1:
                raise RuntimeError("尝试已不在运行中")

    def report(self, comparison_id: int) -> dict[str, object]:
        """读取指定版本，报告身份、配置、独立状态与结果，支持重新打开数据库。"""
        with self._connect() as db:
            version = db.execute(
                "SELECT * FROM comparisons WHERE id = ?", (comparison_id,),
            ).fetchone()
            if version is None:
                raise LookupError("比较版本不存在")
            raw = db.execute(
                "SELECT snapshot FROM inputs WHERE key = ?", (version["input_key"],),
            ).fetchone()
            snapshot = json.loads(raw["snapshot"])
            snapshot["hunks"] = [
                {"hunk_id": h["hunk_id"], "path": h["path"], "lines": len(h["lines"])}
                for h in snapshot["hunks"]
            ]
            rows = db.execute(
                "SELECT * FROM attempts WHERE id IN (?, ?) ORDER BY id",
                (version["ocr_id"], version["agent_id"]),
            )
            attempts = []
            for row in rows:
                attempt = dict(row)
                if attempt["result"] is not None:
                    attempt["result"] = json.loads(attempt["result"])
                attempts.append(attempt)
            return {"comparison": dict(version), "input": snapshot, "attempts": attempts}
