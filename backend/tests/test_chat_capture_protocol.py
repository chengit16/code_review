"""以隔离协议进程验证分页、范围校验、消息边界与超时；不连接真实会话或执行模型。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from ocr_manager.chat_capture_adapter import ChatCaptureUnavailable, read_user_messages


def _server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> Path:
    """生成只响应四种只读请求的合成协议进程，未知方法直接失败。"""

    script = tmp_path / "synthetic-server"
    log = tmp_path / "methods.jsonl"
    script.write_text(
        f"#!{sys.executable}\n"
        + "import json,sys,time\n"
        + f"root={str(tmp_path)!r}; mode={mode!r}; log={str(log)!r}\n"
        + """for line in sys.stdin:
 r=json.loads(line); method=r['method']
 if mode=='partial':
  sys.stdout.write('{');sys.stdout.flush();time.sleep(30);continue
 with open(log,'a') as f: f.write(json.dumps(r)+'\\n')
 if method=='initialized': continue
 if method=='initialize': result={'userAgent':'synthetic'}
 elif method=='thread/read':
  result={'thread':{'id':'thread','cwd':root if mode!='wrong' else '/other'}}
 elif method=='thread/turns/list':
  page=r['params'].get('cursor')
  item={'type':'userMessage','id':'new' if not page else 'old',
    'startedAtMs':2000 if not page else 1000,
    'content':[{'type':'text','text':'报错'},{'type':'image','url':'synthetic-private'}]}
  if mode=='timestamp': item.pop('startedAtMs')
  result={'data':[{'id':'turn','items':[
    {'type':'agentMessage','text':'synthetic-private'},item]}],
    'nextCursor':'cursor' if not page or mode=='repeat' else None}
 else: raise RuntimeError('禁止写入或读取其他资源')
 output=json.dumps({'id':r['id'],'result':result})+'\\n'
 # 分片及通知模拟真实流边界，不能依赖一次 readline 恰好取得完整响应。
 sys.stdout.write(json.dumps({'method':'synthetic/notification'})+'\\n');sys.stdout.flush()
 sys.stdout.write(output[:10]);sys.stdout.flush();time.sleep(.005)
 sys.stdout.write(output[10:]);sys.stdout.flush()
"""
    )
    script.chmod(0o700)
    monkeypatch.setenv("CODEX_APP_SERVER_COMMAND", str(script))
    return log


def test_protocol_reads_summary_pages_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """按摘要分页读授权用户文本；忽略助手和图片载荷，协议不访问全量线程或运行模型。"""

    log = _server(tmp_path, monkeypatch, "valid")
    result = read_user_messages("thread", str(tmp_path), 1000)
    assert [message.message_id for message in result] == ["old", "new"]
    assert all(message.text == "报错" for message in result)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert {call["method"] for call in calls} == {
        "initialize",
        "initialized",
        "thread/read",
        "thread/turns/list",
    }
    assert calls[2]["params"] == {"threadId": "thread", "includeTurns": False}
    pages = [call for call in calls if call["method"] == "thread/turns/list"]
    assert len(pages) == 2 and all(call["params"]["itemsView"] == "summary" for call in pages)


@pytest.mark.parametrize("mode", ["wrong", "timestamp", "repeat"])
def test_protocol_invalid_source_fails_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """项目不符、无来源时间或重复游标均整轮拒绝，不误记为正常空列表。"""

    _server(tmp_path, monkeypatch, mode)
    with pytest.raises(ChatCaptureUnavailable):
        read_user_messages("thread", str(tmp_path), 1000)


def test_protocol_stops_at_authorized_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """跨越授权时间的分页只返回范围内消息，不把过往内容保存为候选。"""

    _server(tmp_path, monkeypatch, "valid")
    result = read_user_messages("thread", str(tmp_path), 1500)
    assert len(result) == 1 and result[0].message_id == "new"


def test_partial_line_obeys_whole_scan_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """来源写一半就挂起时仍受总截止时间约束，不阻塞 monitor 无限等待。"""

    import time

    import ocr_manager.chat_capture_adapter as adapter

    _server(tmp_path, monkeypatch, "partial")
    monkeypatch.setattr(adapter, "SCAN_TIMEOUT_SECONDS", 0.15)
    started = time.monotonic()
    with pytest.raises(ChatCaptureUnavailable, match="超时"):
        read_user_messages("thread", str(tmp_path), 1000)
    assert time.monotonic() - started < 3
