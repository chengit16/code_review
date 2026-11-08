"""概览与目标列表共用只读范围；固定 SQL 不接受用户拼接。"""

OPEN_ISSUE_SCOPE = "i.status='open'"
EVENT_ACTIONABLE_SCOPE = (
    "EXISTS (SELECT 1 FROM repositories ar WHERE ar.id=e.repository_id AND ar.enabled=1)"
)
PREMERGE_ACTIONABLE_SCOPE = """EXISTS (SELECT 1 FROM repositories ar
    JOIN premerge_settings aps ON aps.repository_id=ar.id
    WHERE ar.id=p.repository_id AND ar.enabled=1 AND aps.enabled=1)"""
LATEST_PREMERGE_SCOPE = """NOT EXISTS (SELECT 1 FROM premerge_reviews n
    WHERE n.repository_id=p.repository_id AND n.mr_iid=p.mr_iid AND n.id>p.id)"""
