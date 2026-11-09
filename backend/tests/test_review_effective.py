"""统一有效结论、费用、灰度护栏与独立通知的隔离验收；不访问真实外部系统。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.review_recovery_notifications import (
    claim_delivery,
    delivery_current,
    finish_delivery,
    retry_delivery,
)
from ocr_manager.review_recovery_store import claim, eligibility, enqueue, finish
from ocr_manager.storage import SCHEMA_VERSION, Store
from schema_fixtures import remove_effective_schema
from test_auth import create_user, enable_users, login
from test_review_conclusions import recovered as recovered
from test_review_recovery import ADMIN, child_result, command, make_source


def test_effective_consumers_and_report_preserve_initial(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """状态筛选、首页、运维、详情及导出采用同一有效版本，初审和历史不改写。"""

    _, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        get = lambda path: api.get(path, headers=ADMIN).json()  # noqa: E731
        detail = get('/api/jobs/1')
        assert detail['status'] == 'partial' and detail['effective_status'] == 'complete'
        assert detail['finding_count'] == 3
        assert detail['effective_document']['role'] == 'effective'
        assert get('/api/task-search?status=partial')['total'] == 0
        listing = get('/api/task-search?status=complete')
        assert listing['total'] == 1 and listing['items'][0]['finding_count'] == 3
        assert get('/api/task-search?view=attention')['total'] == 0
        overview = get('/api/overview')
        assert overview['summary']['complete'] == 1
        assert overview['recent'][0]['effective_status'] == 'complete'
        operations = get('/api/operations')
        assert operations['jobs'] == {'complete': 1}
        report = get('/api/jobs/1/report')
        assert report['job']['status'] == 'complete' and len(report['comments']) == 3
        assert report['initial_review']['status'] == 'partial'
        assert len(report['initial_review']['comments']) == 1
        assert report['coverage']['failed'] == 0
        assert report['reason']['code'] == 'complete'
        assert report['initial_review']['reason']['code'] == 'partial'
        assert report['failure_analysis'] is None
        assert report['version_execution_usage']['known_tokens']['total_tokens'] == 12
        history = get('/api/jobs/1/report?attempt=1')
        assert history['job']['status'] == 'partial' and len(history['comments']) == 1
        assert history['effective_conclusion'] is None
        assert history['cumulative_usage']['known_tokens']['total_tokens'] == 6
        assert detail['cumulative_usage']['known_tokens']['total_tokens'] == 12
        assert detail['initial_cumulative_usage']['known_tokens']['total_tokens'] == 6


def test_failed_later_batch_does_not_hide_previous_effective_or_unknown_cost(
    client: TestClient, settings: Settings,
) -> None:
    """后续失败/取消不抹可信部分结果，执行但无 JSON 的费用算未知，未执行排队不算。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    first = claim(store)
    assert first and finish(store, first, child_result(raw, partial=True))
    second_id = enqueue(store, enabled, 1, command(1))
    with TestClient(create_app(enabled)) as api:
        queued = api.get('/api/jobs/1', headers=ADMIN).json()
        assert queued['active_recovery_id'] == second_id
        assert queued['cumulative_usage']['total_attempts'] == 2
        assert api.post('/api/jobs/1/retry', headers=ADMIN).status_code == 409
        second = claim(store)
        assert second and finish(store, second, None, error_code='timeout')
        current = api.get('/api/jobs/1', headers=ADMIN).json()
        assert current['active_recovery_id'] is None
        assert current['effective_conclusion']['revision'] == 1
        assert current['effective_status'] == 'partial'
        assert current['cumulative_usage']['known_tokens']['total_tokens'] == 9
        assert current['cumulative_usage']['total_attempts'] == 3
        assert current['cumulative_usage']['usage_complete'] is False


@pytest.mark.parametrize('fault', ['attempt', 'batch', 'aggregate', 'job', 'delete_attempt'])
def test_source_mutations_invalidate_effective_projection(
    recovered: tuple[Store, Settings, dict[str, Any]], fault: str,
) -> None:
    """来源被修改或删除立即失效，不让列表假绿，也不退回另一个旧聚合冒充最新。"""

    store, settings, _ = recovered
    with store.connection() as db:
        if fault == 'attempt':
            db.execute("UPDATE review_attempts SET result_json='{}' WHERE job_id=1")
        elif fault == 'batch':
            db.execute("UPDATE review_recoveries SET result_json='{}' WHERE id=1")
        elif fault == 'aggregate':
            db.execute("UPDATE review_recovery_aggregates SET origins_json='[]' WHERE revision=1")
        elif fault == 'job':
            db.execute("UPDATE review_jobs SET result_json='{}' WHERE id=1")
        else:
            db.execute('DELETE FROM review_attempts WHERE job_id=1')
    with TestClient(create_app(settings)) as api:
        detail = api.get('/api/jobs/1', headers=ADMIN)
        assert detail.status_code == 200
        assert detail.json()['effective_status'] == 'partial'
        assert detail.json()['effective_document'] is None
        assert api.get('/api/task-search?status=complete', headers=ADMIN).json()['total'] == 0


def test_feedback_summary_counts_each_stable_identity_once(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """根反馈兼容镜像不双计；补审反馈纳入相同项目汇总，重审不复活历史标记。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        for identity in ('j1:a1:c0', 'j1:a1:r1:c0', 'j1:a1:r2:c0'):
            assert api.put(f'/api/jobs/1/finding-feedback/{identity}', headers=ADMIN,
                           json={'source_attempt': 1, 'revision': 2,
                                 'verdict': 'false_positive'}).status_code == 200
        summary = api.get('/api/review-feedback/summary', headers=ADMIN).json()[0]
        assert summary['total'] == summary['false_positive'] == 3
        effectiveness = api.get('/api/review-effectiveness', headers=ADMIN).json()['summary']
        assert effectiveness['feedback_marked'] == effectiveness['false_positive'] == 3
        assert len(api.get('/api/jobs/1', headers=ADMIN).json()['finding_feedback']) == 3
        assert store.retry_job(1) == 1
        assert api.get('/api/review-feedback/summary', headers=ADMIN).json()[0]['total'] == 0


@pytest.mark.parametrize('initial_status', ['pending', 'sending', 'sent', 'failed', None])
def test_supplement_waits_for_initial_and_is_versioned(
    recovered: tuple[Store, Settings, dict[str, Any]], initial_status: str | None,
) -> None:
    """初审在途不越过，初审失败/成功/无记录均可独立发新发现，不重发根评论。"""

    store, _, _ = recovered
    with store.connection() as db:
        if initial_status is None:
            db.execute('DELETE FROM notification_deliveries')
        else:
            db.execute('UPDATE notification_deliveries SET status=?', (initial_status,))
    first = claim_delivery(store)
    if initial_status in {'pending', 'sending'}:
        assert first is None
        return
    assert first and first['revision'] == 1
    comments = json.loads(first['result_json'])['comments']
    assert len(comments) == 1 and comments[0]['finding_id'] == 'j1:a1:r1:c0'
    finish_delivery(store, first, None)
    second = claim_delivery(store)
    assert second and second['revision'] == 2
    assert len(json.loads(second['result_json'])['comments']) == 1
    finish_delivery(store, second, None)
    assert claim_delivery(store) is None
    assert retry_delivery(store, first['id']) is False
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM review_recovery_deliveries').fetchone()[0] == 2
        assert db.execute('SELECT count(*) FROM review_recoveries').fetchone()[0] == 2


def test_supplement_retry_token_fence_restart_and_source_change(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """有限通知重试不重跑 OCR；旧令牌不能完成，新进程将响应未知转人工核对。"""

    store, _, _ = recovered
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET status='sent'")
    delivery = claim_delivery(store)
    assert delivery
    finish_delivery(store, delivery | {'execution_token': 'old'}, None)
    with store.connection() as db:
        assert db.execute('SELECT status FROM review_recovery_deliveries WHERE id=1'
                          ).fetchone()[0] == 'sending'
    finish_delivery(store, delivery, '合成暂时错误')
    with store.connection() as db:
        db.execute("UPDATE review_recovery_deliveries SET next_run_at=CURRENT_TIMESTAMP")
    again = claim_delivery(store)
    assert again and again['execution_token'] != delivery['execution_token']
    store.recover()
    with store.connection() as db:
        row = db.execute('SELECT * FROM review_recovery_deliveries WHERE id=1').fetchone()
        assert row['status'] == 'failed' and '核对' in row['error']
    assert retry_delivery(store, 1)
    delivery = claim_delivery(store)
    assert delivery and store.retry_job(1) == 1
    assert delivery_current(store, delivery) is False
    assert claim_delivery(store) is None
    assert retry_delivery(store, 2) is False


def test_supplement_five_failures_stop_and_api_permissions(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """五次失败转人工；只读角色只能查看，响应契约不泄露执行令牌和发现。"""

    store, settings, _ = recovered
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET status='sent'")
        db.execute("UPDATE review_recovery_deliveries SET status='superseded' WHERE id=2")
    for index in range(5):
        delivery = claim_delivery(store)
        assert delivery
        finish_delivery(store, delivery, '合成网络故障')
        with store.connection() as db:
            row = db.execute('SELECT * FROM review_recovery_deliveries WHERE id=1').fetchone()
            assert row['status'] == ('failed' if index == 4 else 'pending')
            db.execute("UPDATE review_recovery_deliveries SET next_run_at=CURRENT_TIMESTAMP")
    assert claim_delivery(store) is None
    with TestClient(create_app(settings)) as api:
        assert api.get('/api/jobs/1/recovery-deliveries').status_code == 401
        response = api.get('/api/jobs/1/recovery-deliveries?limit=1', headers=ADMIN).json()
        assert len(response) == 1 and 'execution_token' not in response[0]
        assert 'document_json' not in response[0]
        create_user(api, 'administrator', 'admin')
        create_user(api, 'reader', 'reader')
        enable_users(api)
        reader = login(api, 'reader')
        headers = {'Authorization': f"Bearer {reader['token']}"}
        assert api.get('/api/jobs/1/recovery-deliveries', headers=headers).status_code == 200
        assert api.post('/api/recovery-deliveries/1/retry', headers=headers).status_code == 403


def test_pilot_limits_actor_and_fairness(client: TestClient, settings: Settings) -> None:
    """无需项目白名单；批次/总批准预算服务端裁决；幂等重放不重复扣预算，正常任务不饿死。"""

    store, enabled, raw = make_source(client, settings)
    limited = replace(enabled, review_recovery_max_batches=1,
                      review_recovery_max_total_tokens=1000)
    assert eligibility(store, limited, 1).eligible
    with TestClient(create_app(limited)) as api:
        body = command().model_dump(mode='json')
        response = api.post('/api/jobs/1/recoveries', headers=ADMIN, json=body)
        assert response.status_code == 202 and response.json()['requested_by'] == '共享管理员'
        assert api.post('/api/jobs/1/recoveries', headers=ADMIN, json=body).status_code == 202
    task = claim(store)
    assert task and finish(store, task, child_result(raw, partial=True))
    assert eligibility(store, limited, 1).reason_code == 'recovery_limit'
    with pytest.raises(RecoveryConflict, match='recovery_limit'):
        enqueue(store, limited, 1, command(1))
    enqueue(store, enabled, 1, command(1))
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET status='queued',next_run_at=CURRENT_TIMESTAMP")
    assert claim(store) is None
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET next_run_at=datetime('now','+1 day')")
    assert claim(store) is not None


def test_schema44_migration_no_automatic_promotion_or_duplicate_history(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """代表性旧库迁移保留候选/初审、不自动补发通知；重复 migrate 不重复建表。"""

    store, _, _ = recovered
    with store.connection() as db:
        remove_effective_schema(db)
        db.execute('PRAGMA user_version=44')
        before = list(db.execute('SELECT result_json FROM review_jobs'))
    store.migrate()
    store.migrate()
    with store.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION
        assert db.execute('SELECT count(*) FROM review_recovery_aggregates').fetchone()[0] == 2
        assert db.execute('SELECT count(*) FROM review_effective_conclusions').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM review_recovery_deliveries').fetchone()[0] == 0
        assert list(db.execute('SELECT result_json FROM review_jobs')) == before
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO review_recovery_fairness VALUES(1,'initial')")


def test_schema45_failure_rolls_back_and_replays(
    recovered: tuple[Store, Settings, dict[str, Any]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DDL、列和版本同事务；迁移中断后仍是完整 44 版，再次执行可恢复。"""

    from ocr_manager import storage

    store, _, _ = recovered
    with store.connection() as db:
        remove_effective_schema(db)
        db.execute('PRAGMA user_version=44')
    migration = storage.EFFECTIVE_MIGRATION
    monkeypatch.setattr(storage, 'EFFECTIVE_MIGRATION', migration + '\nINVALID SYNTHETIC SQL;')
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 44
        assert db.execute("SELECT name FROM sqlite_master WHERE name='review_recovery_deliveries'"
                          ).fetchone() is None
        assert 'requested_by' not in {
            row['name'] for row in db.execute('PRAGMA table_info(review_recoveries)')}
    monkeypatch.setattr(storage, 'EFFECTIVE_MIGRATION', migration)
    store.migrate()
    with store.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION


@pytest.mark.parametrize('value,projects,batches,tokens,valid', [
    ('0', '', '3', '1000', True), ('1', '1,2', '2', '2000', True),
    ('1', '', '3', '1000', True), ('maybe', '1', '3', '1000', True),
    ('1', '-1', '3', '1000', True), ('1', '1', '11', '1000', False),
    ('1', '1', '3', '0', False), ('1', 'bad', '3', '1000', True),
])
def test_recovery_ignores_removed_switches_but_checks_budget(
    monkeypatch: pytest.MonkeyPatch, value: str, projects: str, batches: str,
    tokens: str, valid: bool,
) -> None:
    """废弃开关和白名单不再影响启动或资格，有限预算仍严格验证。"""

    from ocr_manager.config import load_settings

    monkeypatch.delenv('OCR_APP_CONFIG_FILE', raising=False)
    for name, setting in {
        'OCR_APP_MASTER_KEY': 'synthetic-master', 'OCR_APP_DEV_MODE': '1',
        'OCR_APP_REVIEW_RECOVERY_ENABLED': value,
        'OCR_APP_REVIEW_RECOVERY_REPOSITORY_IDS': projects,
        'OCR_APP_REVIEW_RECOVERY_MAX_BATCHES': batches,
        'OCR_APP_REVIEW_RECOVERY_MAX_TOTAL_TOKENS': tokens,
    }.items():
        monkeypatch.setenv(name, setting)
    if valid:
        loaded = load_settings()
        assert not hasattr(loaded, 'review_recovery_enabled')
        assert loaded.review_recovery_max_total_tokens == int(tokens)
    else:
        with pytest.raises(RuntimeError):
            load_settings()


def test_real_scheduler_drains_recovery_and_supplement_without_extra_model_slot(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验收真实协调器接线，只有 Git/OCR 与外发动作被替换，不仅测试旧 run_once。"""

    from ocr_manager import review_recovery_worker, worker
    from ocr_manager.worker_scheduler import WorkerScheduler
    from test_worker_scheduler import pump

    store, enabled, raw = make_source(client, settings)
    recovery_id = enqueue(store, enabled, 1, command())
    seen: list[str] = []

    def recover(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        seen.append('review_recovery')
        assert task['id'] == recovery_id
        with _store.connection() as db:
            assert db.execute("SELECT count(*) FROM worker_execution_slots WHERE lane='model' "
                              "AND state='running'").fetchone()[0] == 1
        finish(_store, task, child_result(raw))

    def notify(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        seen.append(task.get('delivery_kind', 'initial'))
        if task.get('delivery_kind') == 'recovery':
            assert delivery_current(_store, task)
            finish_delivery(_store, task, None)
        else:
            _store.finish_delivery(task['id'], None)

    monkeypatch.setattr(review_recovery_worker, 'execute_recovery', recover)
    monkeypatch.setattr(worker, 'deliver_notification', notify)
    with worker.worker_lock(settings.data_dir), WorkerScheduler(store, enabled) as scheduler:
        pump(scheduler, lambda: len(seen) == 3)
        assert set(seen) == {'initial', 'review_recovery', 'recovery'}
        assert seen.index('initial') < seen.index('recovery')
        assert seen.index('review_recovery') < seen.index('recovery')
    with store.connection() as db:
        assert db.execute('SELECT status FROM review_recovery_deliveries').fetchone()[0] == 'sent'
        assert db.execute('SELECT status FROM review_jobs').fetchone()[0] == 'partial'


def test_full_history_usage_does_not_merge_currency_or_erase_unknown(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """逐次按自己的币种单价累计；历史已知费用不会随当前结论失效而消失。"""

    store, settings, _ = recovered
    for recovery_id, currency in ((1, 'CNY'), (2, 'USD')):
        with store.connection() as db:
            snapshot = json.loads(db.execute('SELECT config_snapshot FROM review_recoveries '
                                             'WHERE id=?', (recovery_id,)).fetchone()[0])
            snapshot['pricing'] = {'price_currency': currency, 'input_price_per_million': '2',
                                   'output_price_per_million': '8'}
            db.execute('UPDATE review_recoveries SET config_snapshot=? WHERE id=?',
                       (json.dumps(snapshot), recovery_id))
    with TestClient(create_app(settings)) as api:
        usage = api.get('/api/jobs/1', headers=ADMIN).json()['cumulative_usage']
        assert {item['currency'] for item in usage['known_costs']} == {'CNY', 'USD'}
        assert usage['total_attempts'] == 3 and usage['priced_attempts'] == 2
        assert usage['usage_complete'] is True and usage['cost_complete'] is False


def test_corrupt_intermediate_coverage_blocks_new_execution_and_pending_notification(
    client: TestClient, settings: Settings,
) -> None:
    """中间版本伪造覆盖即使没改最终发现也不可复用，拒绝资格且不发送冻结成功消息。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task and finish(store, task, child_result(raw, partial=True))
    with store.connection() as db:
        row = db.execute('SELECT result_json FROM review_recovery_aggregates').fetchone()
        result = json.loads(row[0])
        result['manifest']['coverage']['completed'].append(
            result['manifest']['coverage']['failed'].pop())
        result['manifest']['terminal_state'] = 'complete'
        db.execute('UPDATE review_recovery_aggregates SET result_json=?', (json.dumps(result),))
        db.execute("UPDATE notification_deliveries SET status='sent'")
    assert eligibility(store, enabled, 1).eligible is False
    with pytest.raises(RecoveryConflict):
        enqueue(store, enabled, 1, command(1))
    assert claim_delivery(store) is None
    with store.connection() as db:
        assert db.execute('SELECT status FROM review_recovery_deliveries'
                          ).fetchone()[0] == 'superseded'


def test_supplement_no_new_findings_never_hides_previous_issues(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """本批无新增不等于整个任务无问题，补充卡片明确累计并保留非绿色。"""

    from ocr_manager import feishu
    from test_feishu import card_text

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    child = child_result(raw)
    child['comments'] = []
    assert task and finish(store, task, child)
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET status='sent'")
    delivery = claim_delivery(store)
    assert delivery
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(feishu, 'post_message', lambda _url, body: captured.append(body))
    feishu.send_review('https://feishu.example.test/synthetic', delivery)
    assert captured[0]['card']['header']['template'] != 'green'
    assert '当前累计 1 条发现' in captured[0]['card']['header']['title']['content']
    assert '不代表整体没有问题' in card_text(captured[0])
    assert '不撤销或改写初审消息' in card_text(captured[0])
    assert '未发现问题' not in card_text(captured[0])


def test_parent_wide_budget_does_not_reset_after_full_rereview(
    client: TestClient, settings: Settings,
) -> None:
    """同一父任务换根尝试不能重置补审额度；已取消未执行批次也保留批准审计。"""

    from ocr_manager.attempt_history import save_snapshot
    from ocr_manager.review_recovery_store import cancel
    from ocr_manager.worker import configuration_snapshot

    store, enabled, raw = make_source(client, settings)
    limited = replace(enabled, review_recovery_max_batches=1)
    recovery_id = enqueue(store, limited, 1, command())
    assert cancel(store, recovery_id)
    assert store.retry_job(1) == 1
    task = store.next_job()
    assert task
    save_snapshot(store, 1, configuration_snapshot(store, enabled, repository_id=1))
    store.finish_job(1, 'partial', str(settings.data_dir / 'runs/1/2/result.json'), raw, None)
    assert eligibility(store, limited, 1).reason_code == 'recovery_limit'
    with pytest.raises(RecoveryConflict, match='recovery_limit'):
        enqueue(store, limited, 1, command(source_attempt=2))
