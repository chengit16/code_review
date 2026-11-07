"""通过合成 Git、隔离 HOME 和本机端点探测 OCR 恢复；不触碰业务库或真实模型。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ocr_manager.cancellation import ReviewCancelled, cancellation_scope
from ocr_manager.ocr import classify_result
from ocr_manager.ocr_commands import execute_ocr_command
from ocr_manager.ocr_probe_endpoint import SyntheticEndpoint

PATHS = ("alpha/a.py", "beta/comma,name[1].ts")


class ResumeProbe:
    """控制一个模式的完整实验；固定输入和配置，各冲突用例恢复原始 session 后运行。"""

    def __init__(self, binary: str, root: Path, mode: str, endpoint: SyntheticEndpoint) -> None:
        self.binary, self.root, self.mode, self.endpoint = binary, root, mode, endpoint
        self.repo, self.home = root / "repo", root / "home"
        self.repo.mkdir(parents=True)
        self.home.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if key in {"PATH", "TMPDIR", "LANG"}}
        self.env.update(HOME=str(self.home), OCR_NO_UPDATE="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_NOSYSTEM="1", NO_PROXY="127.0.0.1,localhost")
        self.base = self.head = ""
        self.index = 0

    def command(self, arguments: list[str], *, cwd: Path | None = None,
                timeout: float = 30) -> tuple[int, str, str]:
        """所有命令有界执行，超时终止进程组，不仅杀 Node 启动器。"""

        return execute_ocr_command(arguments, self.env, cwd or self.repo, timeout)

    def prepare(self) -> None:
        """两个较大合成差异让固定版 CLI 按文件分组，避免小差异被自动合为一组。"""

        def git(*args: str) -> str:
            code, stdout, _ = self.command(["git", "-c", "core.hooksPath=/dev/null", *args])
            if code:
                raise ValueError("合成 Git 准备失败")
            return stdout.strip()

        # 1. 仅操作临时仓库，不复制待审查代码，不执行仓库脚本。
        git("init", "-q")
        git("config", "user.name", "合成恢复验证")
        git("config", "user.email", "synthetic@example.invalid")
        for path in PATHS:
            file = self.repo / path
            file.parent.mkdir()
            file.write_text("x=1\n" * 200)
        git("add", ".")
        git("commit", "-qm", "base")
        self.base = git("rev-parse", "HEAD")
        for path in PATHS:
            (self.repo / path).write_text("x=2\n" * 200)
        git("add", ".")
        git("commit", "-qm", "head")
        self.head = git("rev-parse", "HEAD")
        # 2. 丢弃宿主模型和代理环境，仅配置本机端点及合成凭据。
        for key, value in (("url", self.endpoint.url), ("protocol", "openai"),
                           ("api_key", "synthetic-key")):
            code, _, _ = self.command([self.binary, "config", "set",
                                       f"custom_providers.resume-probe.{key}", value])
            if code:
                raise ValueError("合成 provider 配置失败")

    def review(self, resume: str | None = None, *, extra: list[str] | None = None,
               repo: Path | None = None,
               expected: tuple[str, ...] = PATHS) -> dict[str, Any]:
        """运行真实正式命令，只返回合成结果及请求白名单；不保存原始 stderr。"""

        self.index += 1
        output = self.root / f"result-{self.index}.json"
        args = [self.binary, "review", "--repo", str(repo or self.repo),
                *(["--commit", self.head] if self.mode == "commit" else
                  ["--from", self.base, "--to", self.head]),
                "--provider", "resume-probe", "--model", "synthetic", "--effort", "low",
                "--concurrency", "1", "--timeout", "1", "--no-filter", "--audience", "agent",
                "--format", "json", "--output", str(output),
                *(["--resume", resume] if resume else []), *(extra or [])]
        start = len(self.endpoint.calls)
        try:
            with cancellation_scope(lambda: self.endpoint.beta_reached.is_set()
                                    if self.endpoint.block_beta else False):
                code, _, stderr = self.command(args)
        except ReviewCancelled:
            code, stderr = -1, ""
        finally:
            self.endpoint.release_beta.set()
        payload = json.loads(output.read_text()) if output.is_file() else {}
        valid = False
        if payload:
            try:
                classify_result(payload, self.head, self.base if self.mode == "range" else None)
                valid = _paths(payload["manifest"]["coverage"]["selected"]) == sorted(expected)
            except (ValueError, KeyError, TypeError):
                pass
        return {"exit_code": code, "payload": payload, "calls": self.endpoint.calls[start:],
                "manifest_valid": valid,
                "diagnostic": ("session_not_found" if "not found" in stderr.lower() else
                               "configuration_conflict" if "mismatch" in stderr.lower()
                               or "incompatible" in stderr.lower() else "not_classified")}


def _coverage(run: dict[str, Any]) -> dict[str, list[Any]]:
    return dict(run["payload"].get("manifest", {}).get("coverage", {}))


def _paths(items: list[Any]) -> list[str]:
    return sorted(item["path"] for item in items)


def _public(run: dict[str, Any]) -> dict[str, Any]:
    coverage = _coverage(run)
    return {key: run[key] for key in ("exit_code", "calls", "diagnostic", "manifest_valid")} | {
        "status": run["payload"].get("status"),
        "coverage": {key: _paths(items) for key, items in coverage.items()},
        "comments": len(run["payload"].get("comments") or []),
        "tokens": run["payload"].get("summary", {}).get("total_tokens"),
        "local_success_tokens": None if run["exit_code"] == -1 else
        sum(2 for call in run["calls"] if call["status"] == 200)}


def _mode_probe(binary: str, root: Path, mode: str, endpoint: SyntheticEndpoint) -> dict[str, Any]:
    probe = ResumeProbe(binary, root, mode, endpoint)
    probe.prepare()
    # 1. 先获得可信部分结果及真实 session，后续每个冲突实验都从同一基线恢复。
    endpoint.fail = True
    initial = probe.review()
    session = initial["payload"].get("session_id")
    if not isinstance(session, str) or not session:
        return {"mode": mode, "initial": _public(initial), "verified": False,
                "reason": "no_session"}
    sessions = probe.home / ".opencodereview" / "sessions"
    baseline = {path.relative_to(sessions): path.read_bytes() for path in sessions.rglob("*")
                if path.is_file()}

    def restore() -> None:
        shutil.rmtree(sessions)
        for path, content in baseline.items():
            target = sessions / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    endpoint.fail = False
    resumed = probe.review(session)
    repeated = probe.review(session)
    # 2. 检查实际覆盖与请求边界，而非只看退出码或 session ID。
    cov = _coverage(resumed)
    original = _coverage(initial)
    verified = (initial["manifest_valid"] and resumed["manifest_valid"]
                and initial["payload"].get("status") == "partial"
                and _paths(original.get("completed", [])) == [PATHS[0]]
                and _paths(original.get("failed", [])) == [PATHS[1]]
                and resumed["payload"].get("status") == "complete"
                and _paths(cov.get("reused", [])) == [PATHS[0]]
                and _paths(cov.get("completed", [])) == [PATHS[1]]
                and bool(resumed["calls"])
                and all(call["paths"] == [PATHS[1]] for call in resumed["calls"])
                and set(json.dumps(item, sort_keys=True) for item in
                        initial["payload"].get("comments", [])) <= set(
                            json.dumps(item, sort_keys=True)
                            for item in resumed["payload"].get("comments", [])))
    variants = []
    rule = root / "changed-rule.json"
    rule.write_text(json.dumps({"rules": [{"path": "**/*", "rule": "合成规则变更",
                                         "merge_system_rule": True}]}))
    for name, extra, session_id in (
        ("changed_model", ["--model", "changed"], session),
        ("changed_rule", ["--rule", str(rule)], session),
        ("missing_session", [], "00000000-0000-0000-0000-000000000000"),
    ):
        restore()
        variant = probe.review(session_id, extra=extra)
        variants.append({"case": name, **_public(variant),
                         "rejected_without_calls": variant["exit_code"] != 0 and
                         not variant["calls"]})
    restore()
    moved = root / "moved"
    shutil.copytree(probe.repo, moved)
    cross = probe.review(session, repo=moved)
    subset_rule = root / "subset-rule.json"
    subset_rule.write_text(json.dumps({"exclude": ["alpha/a.py"]}))
    subset_args = ["--rule", str(subset_rule)]
    preview = probe.review(repo=moved, extra=[*subset_args, "--preview"])
    preview_paths = sorted(item["path"] for item in preview["payload"].get("files", [])
                           if item.get("will_review") is True)
    preview_matches = preview["exit_code"] == 0 and preview_paths == [PATHS[1]]
    subset = (probe.review(repo=moved, extra=subset_args, expected=(PATHS[1],))
              if preview_matches else preview)
    # 3. 会话损坏测试只修改临时基线，不接触业务会话或故障工件。
    restore()
    for path in baseline:
        if path.name == session + ".jsonl":
            (sessions / path).write_text("{invalid\n")
    corrupt = probe.review(session)
    # 4. 在第二组请求悬挂时走平台取消边界，随后只恢复该临时中断会话。
    restore()
    before = set(sessions.rglob("*.jsonl"))
    endpoint.beta_reached.clear()
    endpoint.release_beta.clear()
    endpoint.block_beta = True
    interrupted = probe.review()
    endpoint.block_beta = False
    created = set(sessions.rglob("*.jsonl")) - before
    interrupted_resume = probe.review(next(iter(created)).stem) if len(created) == 1 else None
    initial_public, resumed_public = _public(initial), _public(resumed)
    return {"mode": mode, "initial": _public(initial), "resumed": _public(resumed),
            "repeated": _public(repeated), "variants": variants, "cross_checkout": _public(cross),
            "corrupt_session": _public(corrupt), "verified": verified,
            "independent_subset": _public(subset),
            "subset_preview_matches": preview_matches,
            "independent_subset_verified": preview_matches and subset["manifest_valid"] and
            subset["payload"].get("status") == "complete" and bool(subset["calls"]) and
            all(call["paths"] == [PATHS[1]] for call in subset["calls"]),
            "interrupted": _public(interrupted),
            "interrupted_resume": _public(interrupted_resume) if interrupted_resume else None,
            "repeat_without_calls": not repeated["calls"],
            "usage_matches_incremental": resumed_public["tokens"] ==
            resumed_public["local_success_tokens"],
            "usage_matches_cumulative": resumed_public["tokens"] ==
            initial_public["local_success_tokens"] + resumed_public["local_success_tokens"]}


def probe_resume(command: Path) -> dict[str, Any]:
    """显式指定已安装 CLI，产生能力报告；不因某模式不支持而伪造成功。"""

    binary = str(command.resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="ocr-resume-probe-") as temporary:
        root = Path(temporary)
        endpoint = SyntheticEndpoint(PATHS)
        endpoint.start()
        try:
            code, version, _ = execute_ocr_command(
                [binary, "--version"], {"HOME": str(root), "PATH": os.environ.get("PATH", ""),
                                       "OCR_NO_UPDATE": "1"}, root, 15)
            if code:
                raise ValueError("无法核对 CLI 版本")
            reports = [_mode_probe(binary, root / mode, mode, endpoint)
                       for mode in ("commit", "range")]
        finally:
            endpoint.close()
        return {"schema_version": "platform.resume-probe/v1", "modes": reports,
                "version": version.splitlines()[0],
                "real_model_called": False, "business_data_modified": False,
                "native_coverage_reuse_verified": all(report["verified"] for report in reports),
                "production_resume_approved": False}


def main() -> None:
    """输出仅含合成路径及计数的报告；命令失败由调用方查看报告，不自动恢复业务任务。"""

    parser = argparse.ArgumentParser(description="验证 OCR 的本机合成续审能力")
    parser.add_argument("--command", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(probe_resume(args.command), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
