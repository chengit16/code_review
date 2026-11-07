"""显式读取单份受控工件，校验固定输入后输出安全诊断；不回填、不调用模型或写库。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ocr_manager.ocr import classify_result
from ocr_manager.review_diagnostics import failure_analysis
from ocr_manager.review_failures import ReviewFailure


def diagnostic_report(path: Path, head: str, base: str | None = None) -> dict[str, Any]:
    """管理员提供预期 SHA；损坏、超限或输入不符时拒绝解析，不输出原始错误正文。"""

    try:
        with path.open("rb") as source:
            content = source.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024:
            raise ValueError
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError
        state = classify_result(result, head, base)
    except (OSError, ValueError, TypeError, ReviewFailure) as error:
        raise ValueError("工件不可用、超限、格式无效或固定输入不匹配") from error
    return {"schema_version": "platform.diagnostic-report/v1", "state": state,
            "failure_analysis": failure_analysis(result), "business_data_modified": False}


def main() -> None:
    """只向 stdout 返回白名单投影；输入错误返回非零退出码，不打印受控工件。"""

    parser = argparse.ArgumentParser(description="只读分析单份历史 OCR 结果")
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base")
    args = parser.parse_args()
    try:
        report = diagnostic_report(args.result, args.head, args.base)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
