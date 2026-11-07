"""以临时仓库和本机合成端点验证 OCR 排除及正式覆盖；不调用真实模型或修改业务库。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ocr_manager.newline_filter import filtered_rule, literal_pattern, selected_paths


def probe_filter(command: Path) -> dict[str, Any]:
    """隔离 HOME 和 Git 配置，返回特殊路径的预览与真实正式命令覆盖事实。"""

    binary = str(command.resolve(strict=True))
        # 1. 合成仓库和独立 HOME 不触碰本机业务凭据、规则与数据库。
    with tempfile.TemporaryDirectory(prefix="ocr-filter-probe-") as temporary:
        root = Path(temporary)
        home, repo = root / "home", root / "repo"
        home.mkdir()
        repo.mkdir()
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "TMPDIR", "LANG"}}
        env.update(HOME=str(home), OCR_NO_UPDATE="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_CONFIG_NOSYSTEM="1")

        def git(*args: str) -> str:
            result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null",
                                     "-c", "core.autocrlf=false", *args],
                                    cwd=repo, env=env, capture_output=True, timeout=15, check=True)
            return result.stdout.decode().strip()

        # 2. 固定两个提交，只制造换行差异，保留特殊路径供预览核对。
        git("init", "-q")
        git("config", "user.name", "合成预览验证")
        git("config", "user.email", "synthetic@example.invalid")
        paths = ("a.py", "dir/a.py", "space name.py", "comma,name.py", "x[1].py",
                 "x1.py", "bang!.py", "back\\slash.py", "star*.py", "star1.py",
                 "question?.py", "question1.py", "#hash.py", "!leading.py", "中文.py")
        for name in paths:
            file = repo / name
            file.parent.mkdir(exist_ok=True)
            file.write_bytes(b"x=1\n")
        git("add", ".")
        git("commit", "-qm", "base")
        base = git("rev-parse", "HEAD")
        for name in paths:
            (repo / name).write_bytes(b"x=1\r\n")
        git("add", ".")
        git("commit", "-qm", "head")
        head = git("rev-parse", "HEAD")
        version = subprocess.run([binary, "--version"], cwd=repo, env=env,
                                 capture_output=True, text=True, timeout=15, check=True)
        # 3. 对照 CLI 参数与 JSON 数组，记录实际选中集合而非只检查退出码。
        cases = []
        for index, pattern in enumerate((None, "/a.py", "a.py", "dir/a.py", "/space name.py")):
            output = root / f"preview-{index}.json"
            result = subprocess.run([binary, "review", "--repo", str(repo), "--from", base,
                                     "--to", head, "--preview", "--format", "json", "--output",
                                     str(output), *(["--exclude", pattern] if pattern else [])],
                                    cwd=repo, env=env, capture_output=True, timeout=30)
            payload = json.loads(output.read_text()) if output.is_file() else {}
            cases.append({"pattern": pattern, "exit_code": result.returncode,
                          "selected": [file["path"] for file in payload.get("files", [])
                                       if file.get("will_review") is True]})
        # 4. 规则 JSON 的数组不经过 --exclude 逗号分割；按 gitignore 规则转义 glob 字符。
        rule_cases = []
        for index, path in enumerate(paths):
            rule_path = root / f"rule-{index}.json"
            pattern = literal_pattern(path)
            rule_path.write_text(json.dumps({"exclude": [pattern]}, ensure_ascii=False))
            output = root / f"rule-preview-{index}.json"
            result = subprocess.run([binary, "review", "--repo", str(repo), "--from", base,
                                     "--to", head, "--preview", "--format", "json", "--rule",
                                     str(rule_path), "--output", str(output)], cwd=repo,
                                    env=env, capture_output=True, timeout=30)
            payload = json.loads(output.read_text()) if output.is_file() else {}
            selected = [file["path"] for file in payload.get("files", [])
                        if file.get("will_review") is True]
            rule_cases.append({"path": path, "exit_code": result.returncode,
                               "pattern": pattern,
                               "selected": selected,
                               "excluded_only_target": (path not in selected and
                                                        set(selected) == set(paths) - {path})})
        formal = _formal_probe(binary, repo, root, env, base, head, list(paths))
        precedence = _precedence_probe(binary, repo, root, env, base, head, list(paths))
        return {"version": version.stdout.splitlines()[0], "cases": cases,
                "rule_cases": rule_cases,
                "formal_cases": formal,
                "precedence_cases": precedence,
                "formal_manifest_verified": all(case["matches_preview"] and
                                                 case["expected_terminal"] for case in formal),
                "business_configuration_modified": False}


def _precedence_probe(binary: str, repo: Path, root: Path, env: dict[str, str],
                      base: str, head: str, paths: list[str]) -> list[dict[str, Any]]:
    """用真实预览确认默认、全局、仓库和项目规则被复制后保持原语义及优先级。"""

    global_path = Path(env["HOME"]) / ".opencodereview/rule.json"
    repository_path = repo / ".opencodereview/rule.json"
    repository_path.parent.mkdir(exist_ok=True)
    cases = []
    for index, (source, excluded) in enumerate((
        ("default", None), ("global", "a.py"),
        ("repository", "dir/a.py"), ("project", "x1.py"),
    )):
        content = json.dumps({"include": ["*.py", "**/*.py"],
                              "exclude": [excluded] if excluded else []})
        if source == "global":
            global_path.write_text(content)
        if source == "repository":
            repository_path.write_text(content)
        project = root / "precedence-project.json"
        project.write_text(content)
        project_content = content if source == "project" else None
        run = root / f"precedence-{index}"
        run.mkdir()
        arguments = [binary, "review", "--repo", str(repo), "--from", base, "--to", head,
                     "--preview", "--format", "json"]
        original = run / "original.json"
        subprocess.run([*arguments, "--output", str(original),
                        *(["--rule", str(project)] if project_content else [])],
                       cwd=repo, env=env, capture_output=True, timeout=30, check=True)
        payload = json.loads(original.read_text())
        before = repository_path.read_bytes() if repository_path.exists() else None
        generated = filtered_rule(repo, run, {"newline_only_paths": ["comma,name.py"]}, payload,
                                  global_path.read_text() if global_path.exists() else None,
                                  project_content)
        assert generated is not None
        rule, expected = generated
        output = run / "filtered.json"
        subprocess.run([*arguments, "--rule", str(rule), "--output", str(output)],
                       cwd=repo, env=env, capture_output=True, timeout=30, check=True)
        actual = selected_paths(json.loads(output.read_text()))
        original_expected = set(paths) - ({excluded} if excluded else set())
        after = repository_path.read_bytes() if repository_path.exists() else None
        cases.append({"source": source, "verified": actual == expected and
                      selected_paths(payload) == original_expected and before == after})
    return cases


def _formal_probe(binary: str, repo: Path, root: Path, env: dict[str, str],
                  base: str, head: str, paths: list[str]) -> list[dict[str, Any]]:
    """本机合成成功和 HTTP 400 响应验证真实 CLI，不使用真实模型。"""

    requests: list[str] = []
    tool_names: set[str] = set()
    successful = False

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requests.append(self.path)
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            tool_names.update(tool["function"]["name"] for tool in request.get("tools", []))
            message: dict[str, Any] = {"role": "assistant", "content": "合成审查完成"}
            if any(tool["function"]["name"] == "task_done" for tool in request.get("tools", [])):
                message["tool_calls"] = [{"id": "synthetic-done", "type": "function",
                                           "function": {"name": "task_done",
                                                        "arguments": '{"summary":"synthetic"}'}}]
            body = (json.dumps({"id": "synthetic", "object": "chat.completion",
                                "choices": [{"index": 0, "message": message,
                                    "finish_reason": "tool_calls" if "tool_calls" in message
                                                     else "stop"}],
                                "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                          "total_tokens": 2}}).encode()
                    if successful else
                    b'{"error":{"message":"synthetic failure","type":"invalid_request_error"}}')
            self.send_response(200 if successful else 400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: Any) -> None:
            pass

    # 1. 端点只监听随机本机端口，CLI 只持有合成密钥，禁止调用供应商默认地址。
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for key, value in (("custom_providers.filter-probe.url",
                                f"http://127.0.0.1:{server.server_port}/v1/chat/completions"),
                               ("custom_providers.filter-probe.protocol", "openai"),
                               ("custom_providers.filter-probe.api_key", "synthetic-key")):
                subprocess.run([binary, "config", "set", key, value], cwd=repo, env=env,
                               capture_output=True, timeout=15, check=True)
            cases = []
            # 2. 部分与全量排除均运行真实正式命令，原始结果保留原样核对 selected 路径。
            for index, (excluded, successful, mode) in enumerate((
                (["comma,name.py", "x[1].py"], False, "range"),
                (["comma,name.py", "x[1].py"], True, "range"),
                (["comma,name.py", "x[1].py"], True, "commit"),
                (paths, True, "range"),
            )):
                previous_requests = len(requests)
                rule = root / f"formal-rule-{index}.json"
                rule.write_text(json.dumps({"exclude": [
                    literal_pattern(path)
                    for path in excluded]}))
                output = root / f"formal-{index}.json"
                args = [binary, "review", "--repo", str(repo),
                        *(["--from", base, "--to", head] if mode == "range"
                          else ["--commit", head]),
                        "--format", "json", "--rule", str(rule), "--output", str(output),
                        "--provider", "filter-probe", "--model", "synthetic",
                        "--audience", "agent", "--concurrency", "1"]
                preview_output = root / f"formal-preview-{index}.json"
                preview_args = args.copy()
                preview_args[preview_args.index("--output") + 1] = str(preview_output)
                preview_result = subprocess.run([*preview_args, "--preview"], cwd=repo, env=env,
                                                capture_output=True, timeout=30)
                preview_data = json.loads(preview_output.read_text())
                preview_paths = {file["path"] for file in preview_data["files"]
                                 if file["will_review"]}
                result = subprocess.run(args, cwd=repo, env=env, capture_output=True, timeout=60)
                payload = json.loads(output.read_text()) if output.is_file() else {}
                selected = payload.get("manifest", {}).get("coverage", {}).get("selected", [])
                actual = [item.get("path") for item in selected]
                cases.append({"excluded": excluded, "exit_code": result.returncode,
                              "selected": actual, "status": payload.get("status"),
                              "matches_preview": preview_result.returncode == 0 and
                              set(actual) == preview_paths == set(paths) - set(excluded),
                              "expected_terminal": payload.get("status") == (
                                  "skipped" if excluded == paths else
                                  "complete" if successful else "failed"),
                              "local_requests": len(requests) - previous_requests, "mode": mode,
                              "synthetic_success_response": successful,
                              "tools": sorted(tool_names),
                              "stderr_tail": result.stderr.decode(errors="replace")[-1000:]})
            return cases
        finally:
            server.shutdown()
            thread.join(timeout=5)


def main() -> None:
    """显式指定本地 CLI，不下载依赖，不读取生产库，也不触发真实外部投递。"""

    parser = argparse.ArgumentParser(description="验证本地 OCR 的合成预览排除能力")
    parser.add_argument("--command", required=True, type=Path)
    args = parser.parse_args()
    report = probe_filter(args.command)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if (not report["formal_manifest_verified"] or
        not all(case["excluded_only_target"] for case in report["rule_cases"]) or
        not all(case["verified"] for case in report["precedence_cases"])):
        raise SystemExit("过滤探针未通过，请保持自动过滤关闭")


if __name__ == "__main__":
    main()
