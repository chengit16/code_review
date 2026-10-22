"""提供浏览器验收的临时服务和合成任务；不启动 Worker 或访问外部系统。"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from cryptography.fernet import Fernet
from ocr_manager.api import create_app
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def main() -> None:
    """退出时销毁测试数据；外部调用只能留在队列中。"""

    with TemporaryDirectory(prefix="ocr-browser-") as directory:
        settings = Settings(
            data_dir=Path(directory), admin_token="", master_key=Fernet.generate_key().decode(),
            gitlab_api_token="", ocr_command="ocr", ocr_provider="dashscope", ocr_model="test",
            ocr_api_key="synthetic-key", ocr_timeout_seconds=30,
            public_url="http://127.0.0.1:8791",
            dev_mode=True,
        )
        app = create_app(settings)
        store = Store(settings.data_dir / "app.db")
        repository_id = store.add_repository({
            "name": "验收任务项目", "gitlab_url": "https://gitlab.example.test",
            "project_id": 999, "remote_url": "https://gitlab.example.test/team/fixture.git",
            "target_branch": "main", "auth_kind": "secret", "webhook_secret": "",
            "feishu_webhook": "",
        })
        store.add_event(repository_id, 7, "fixture", "a" * 40, None)
        event = store.next_event()
        assert event is not None
        store.finish_event(event["id"], ["a" * 40], {"a" * 40: ("fixture", "")}, None)
        job = store.next_job()
        assert job is not None
        save_snapshot(store, job["id"], {"command": {"name": "ocr"}, "pricing": {
            "price_currency": "CNY", "input_price_per_million": "2",
            "output_price_per_million": "8",
        }})
        store.finish_job(job["id"], "partial", None, {
            "comments": [{"path": "app.py", "content": "示例发现", "severity": "high"}],
            "summary": {"input_tokens": 500000, "output_tokens": 250000,
                        "total_tokens": 750000},
            "manifest": {"coverage": {"selected": [1, 2], "completed": [1],
                                      "reused": [], "failed": [2], "waived": []}},
        }, None)
        # 导航夹具保留任务 1 的部分结果，新增带分支间隔的任务供跨页筛选验收。
        commits = [f"{number:040x}" for number in range(2, 7)]
        store.add_event(repository_id, 8, "navigation", commits[-1], None)
        event = store.next_event()
        assert event is not None
        store.finish_event(event["id"], commits, {sha: ("navigation", "") for sha in commits}, None)
        with store.connection() as db:
            db.execute("UPDATE review_jobs SET target_branch='develop' WHERE id IN (3, 5)")
        for index in range(25):
            store.record_audit("PATCH /api/test/{item_id}", "synthetic", index, "success")
        uvicorn.run(app, host="127.0.0.1", port=8791)


if __name__ == "__main__":
    main()
