"""维护仓库的 Agent 授权，管理台写入与手动入队竞争同一个 SQLite 写锁。"""

import sqlite3

from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.agent_review_profile import resolve_model
from ocr_manager.config import Settings
from ocr_manager.storage import Store


class PilotConflict(ValueError):
    """试点设置冲突携带可供界面恢复的稳定原因。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def managed_pilot_enabled(db: sqlite3.Connection, repository_id: int) -> bool:
    """在调用方事务核对该仓库是否仍有管理台授权。"""

    return db.execute("SELECT 1 FROM agent_review_pilots WHERE repository_id=?",
                      (repository_id,)).fetchone() is not None


def _file_config(settings: Settings, repository_id: int) -> AgentReviewConfig | None:
    config = settings.agent_review
    return config if config is not None and repository_id in config.repositories else None


def _project_config(repository_id: int) -> AgentReviewConfig:
    return AgentReviewConfig("", "", frozenset({repository_id}), "",
                             model_source="project", managed_pilot=True)


def can_manage_pilot(settings: Settings, repository_id: int) -> bool:
    """已有私有配置继续由运维维护，配置无效时保持默认拒绝。"""

    return settings.agent_review_error is None and _file_config(settings, repository_id) is None


def repository_agent_config(db: sqlite3.Connection, settings: Settings,
                            repository_id: int) -> AgentReviewConfig | None:
    """统一解析 API、CLI 与 Worker 的仓库授权，页面授权复用项目生效模型。"""

    if settings.agent_review_error is not None:
        return None
    config = _file_config(settings, repository_id)
    if config is not None:
        return config
    return _project_config(repository_id) if managed_pilot_enabled(db, repository_id) else None


def set_task_pilot(store: Store, settings: Settings, job_id: int, enabled: bool,
                   actor: str) -> None:
    """由已授权的管理员保存任务所属仓库的试点状态，不登记模型任务。"""

    from ocr_manager.agent_capabilities import audit, check_scheme, effective_scheme

    with store.connection() as db:
        # 1. 从任务关联确定授权仓库，与入队串行检查，调用方不能指定其他仓库。
        db.execute("BEGIN IMMEDIATE")
        repository = db.execute("""SELECT r.id,r.enabled FROM review_jobs j
            JOIN repositories r ON r.id=j.repository_id WHERE j.id=?""", (job_id,)).fetchone()
        if repository is None:
            raise LookupError("任务不存在")
        repository_id = int(repository["id"])
        selected = db.execute("SELECT model_profile_id FROM agent_project_settings WHERE "
                              "repository_id=?", (repository_id,)).fetchone()
        changed = set_repository_pilot(
            db, store, settings, repository, enabled, actor, selected[0] if selected else None,
        )
        if changed:
            if enabled:
                try:
                    check_scheme(db, effective_scheme(db, repository_id), trial=False,
                                 repository_id=repository_id)
                except ValueError as error:
                    raise PilotConflict("pilot_scheme_unavailable", str(error)) from error
            db.execute("UPDATE agent_project_settings SET version=version+1 WHERE repository_id=?",
                       (repository_id,))
            db.execute("""INSERT OR IGNORE INTO agent_project_settings(repository_id,version)
                VALUES (?,1)""", (repository_id,))
            audit(db, actor, "project_pilot", repository_id, before=not enabled, after=enabled)


def set_repository_pilot(
    db: sqlite3.Connection, store: Store, settings: Settings, repository: sqlite3.Row,
    enabled: bool, actor: str, profile_id: int | None,
) -> bool:
    """在调用方写事务内复用仓库试点授权与正在运行的保护。"""

    repository_id = int(repository["id"])
    if not can_manage_pilot(settings, repository_id):
        raise PilotConflict("pilot_config_managed", "此仓库的 Agent 试点由服务配置管理")
    if managed_pilot_enabled(db, repository_id) == enabled:
        return False
    if enabled:
        if not repository["enabled"]:
            raise PilotConflict("pilot_repository_disabled", "请先启用该仓库")
        try:
            resolve_model(store, _project_config(repository_id), repository_id,
                          profile_id=profile_id, db=db)
        except ValueError as error:
            raise PilotConflict("pilot_model_unavailable", str(error)) from error
        db.execute("INSERT INTO agent_review_pilots(repository_id,enabled_by) VALUES (?,?)",
                   (repository_id, actor))
    else:
        if db.execute("""SELECT 1 FROM agent_reviews a JOIN review_jobs j ON j.id=a.job_id
            WHERE j.repository_id=? AND a.status IN ('queued','running') LIMIT 1""",
                      (repository_id,)).fetchone():
            raise PilotConflict("pilot_active_runs", "请等此仓库的 Agent 任务结束后再关闭试点")
        db.execute("DELETE FROM agent_review_pilots WHERE repository_id=?", (repository_id,))
    return True
