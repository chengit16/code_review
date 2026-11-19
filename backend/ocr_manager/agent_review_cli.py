"""本机试点命令，显式提交、取消和查询冻结版本；耗时工作由独立 Worker 执行。"""

from __future__ import annotations

import argparse
import json

from ocr_manager.agent_pilot import repository_agent_config
from ocr_manager.agent_review_profile import resolve_model
from ocr_manager.agent_review_store import cancel, enqueue, report
from ocr_manager.config import load_settings
from ocr_manager.storage import SCHEMA_VERSION, Store


def main() -> None:
    """仅操作已完成迁移的受控本地数据库，报告可能含敏感代码证据。"""

    parser = argparse.ArgumentParser(description="独立 Agent 影子评审")
    subcommands = parser.add_subparsers(dest="command", required=True)
    submit = subcommands.add_parser("enqueue", help="排队并选择当前固定 OCR 初审")
    submit.add_argument("--job-id", type=int, required=True)
    submit.add_argument("--request-key", required=True)
    submit.add_argument("--previous-id", type=int)
    for name in ("report", "cancel"):
        subcommands.add_parser(name).add_argument("--id", type=int, required=True)
    args = parser.parse_args()
    settings = load_settings()
    database = settings.data_dir / "app.db"
    if not database.is_file():
        parser.error("找不到已配置的业务数据库")
    store = Store(database)
    with store.connection() as db:
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            parser.error("业务数据库版本不匹配，请先在受控实例完成迁移")
    try:
        if args.command == "enqueue":
            with store.connection() as db:
                job = db.execute("SELECT repository_id FROM review_jobs WHERE id=?",
                                 (args.job_id,)).fetchone()
                if job is None:
                    parser.error("任务不存在")
                repository_id = int(job["repository_id"])
                config = repository_agent_config(db, settings, repository_id)
            if config is None:
                parser.error(settings.agent_review_error or "未启用 Agent 试点")
            if config.model_source == "project":
                config = resolve_model(store, config, repository_id)
            value: object = {"id": enqueue(
                store, config, args.job_id, args.request_key, args.previous_id,
            )}
        elif args.command == "report":
            value = report(store, args.id)
        else:
            value = {"cancel_requested": cancel(store, args.id)}
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
