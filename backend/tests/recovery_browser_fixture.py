"""仅浏览器验收使用的合成补审流程；不导入真实 Git、模型或飞书适配器。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.config import Settings
from ocr_manager.review_diagnostic_import import import_diagnostics
from ocr_manager.review_recovery_notifications import claim_delivery, finish_delivery
from ocr_manager.review_recovery_store import claim, enqueue, finish
from ocr_manager.storage import Store
from ocr_manager.worker import configuration_snapshot, snapshot_hash

PATHS = ('done.py', 'comma,name[1].ts', 'space name.py')


def install(app: FastAPI, store: Store, settings: Settings) -> None:
    """只挂到临时测试服务；模型结果由明确测试命令推进，绝不启动真实 Worker。"""

    repository_id = store.add_repository({
        'name': '补审隔离验收', 'gitlab_url': 'https://gitlab.example.test',
        'project_id': 999, 'remote_url': 'https://gitlab.example.test/team/fixture.git',
        'target_branch': 'main', 'auth_kind': 'secret', 'webhook_secret': '',
        'feishu_webhook': '',
    })
    for number in range(1, 8):
        sha = f'{number:040x}'
        store.add_event(repository_id, number, f'fixture-{number}', sha, None)
        event = store.next_event()
        assert event
        store.finish_event(event['id'], [sha], {sha: ('fixture', '')}, None)
        job = store.next_job()
        assert job
        snapshot = configuration_snapshot(store, settings, repository_id=repository_id)
        with store.connection() as db:
            db.execute('UPDATE review_jobs SET config_hash=? WHERE id=?',
                       (snapshot_hash(snapshot), job['id']))
        save_snapshot(store, job['id'], snapshot)
        items = [{'path': path, 'item_id': f'root-{index}'} for index, path in enumerate(PATHS)]
        raw: dict[str, Any] = {
            'comments': [{'path': PATHS[0], 'content': '保留初审发现', 'severity': 'high'}],
            'summary': {'input_tokens': 4, 'output_tokens': 2, 'total_tokens': 6},
            'manifest': {'schema_version': 'ocr.run-manifest/v1', 'terminal_state': 'partial',
                         'input': {'mode': 'commit', 'resolved_head': sha},
                         'coverage': {'selected': items, 'completed': items[:1], 'reused': [],
                                      'waived': [], 'failed': items[1:]}},
        }
        if number == 5:
            raw['groups'] = [{'files': list(PATHS)}]
            raw['retry_report'] = {'schema_version': 'ocr.llm-retry-report/v1', 'requests': [{
                'outcome': 'failed', 'task_type': 'plan_task', 'file_path': ','.join(PATHS),
                'attempts': [{'status_code': 504, 'error_class': 'timeout',
                              'failure_phase': 'http', 'duration_to_headers_ms': 60001}]}]}
        path = settings.data_dir / 'runs' / str(job['id']) / '1' / 'result.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(raw))
        store.finish_job(job['id'], 'partial', str(path), raw, None)
        if number in {6, 7}:
            from test_recovery_budget import blocked
            from test_review_recovery import command

            # 用尽三批的合成历史；仅最后一批具备精确诊断，模拟旧版逐步补全证据。
            for batch in range(3):
                enqueue(store, settings, job['id'], command())
                task = claim(store)
                assert task and task['job_id'] == job['id']
                child = blocked(raw)
                child['manifest']['coverage']['selected'] = items[1:]
                child['manifest']['coverage']['failed'] = [
                    item | {'classification': 'budget'} for item in items[1:]]
                child['comments'] = []
                if batch < 2:
                    child.pop('warnings')
                assert finish(store, task, child)
        if number == 5:
            with store.connection() as db:
                result = json.loads(db.execute('SELECT result_json FROM review_jobs WHERE id=?',
                                              (job['id'],)).fetchone()[0])
                result.pop('failure_analysis')
                encoded = json.dumps(result)
                db.execute('UPDATE review_jobs SET result_json=? WHERE id=?', (encoded, job['id']))
                db.execute('UPDATE review_attempts SET result_json=? WHERE job_id=?',
                           (encoded, job['id']))
    assert import_diagnostics(settings.data_dir, apply=True)['counts'].get('imported') == 1
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET status='sent'")

    @app.post('/api/test/jobs/{job_id}/advance-recovery')
    def advance(job_id: int) -> dict[str, str]:
        """合成终态覆盖及一次通知故障，用真实应用事务验证页面全链路。"""

        task = claim(store)
        if task is None or task['job_id'] != job_id:
            raise HTTPException(409, '没有对应合成批次')
        source = json.loads(task['source_result_json'])
        items = [{'path': path, 'item_id': f'child-{index}'}
                 for index, path in enumerate(PATHS[1:])]
        child = {'comments': [{'path': PATHS[1], 'content': '新增补审发现', 'severity': 'high'}],
                 'summary': {'input_tokens': 2, 'output_tokens': 1, 'total_tokens': 3},
                 'manifest': {'schema_version': 'ocr.run-manifest/v1',
                              'terminal_state': 'complete',
                              'input': source['manifest'].get('input', {}),
                              'coverage': {'selected': items, 'completed': items, 'failed': [],
                                           'reused': [], 'waived': []}}}
        assert finish(store, task, child)
        delivery = claim_delivery(store)
        assert delivery
        finish_delivery(store, delivery, '合成通知失败，只需重发通知', retryable=False)
        return {'status': 'complete'}

    @app.post('/api/test/jobs/{job_id}/advance-notification')
    def notify(job_id: int) -> dict[str, str]:
        """只完成独立通知，不新增模型执行或覆盖版本。"""

        delivery = claim_delivery(store)
        if delivery is None or delivery['job_id'] != job_id:
            raise HTTPException(409, '没有对应合成通知')
        finish_delivery(store, delivery, None)
        return {'status': 'sent'}
