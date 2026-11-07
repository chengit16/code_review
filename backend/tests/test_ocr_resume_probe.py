"""验证真实 CLI 恢复兼容矩阵；显式指定本机安装版本，不下载或调用真实模型。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from ocr_manager.ocr_resume_probe import PATHS, probe_resume


def test_installed_cli_resume_capability_matrix() -> None:
    """固定版本探针保护复用、特殊路径、配置风险及独立失败子集的实际边界。"""

    command = os.environ.get("OCR_RESUME_PROBE_COMMAND")
    if not command:
        pytest.skip("需显式设置 OCR_RESUME_PROBE_COMMAND，普通单测不执行外部 CLI")
    report = probe_resume(Path(command))
    assert report["real_model_called"] is False
    assert report["business_data_modified"] is False
    assert report["production_resume_approved"] is False
    assert report["native_coverage_reuse_verified"] is True
    for mode in report["modes"]:
        assert mode["verified"] is True
        assert mode["independent_subset_verified"] is True
        assert mode["resumed"]["coverage"]["reused"] == [PATHS[0]]
        assert mode["resumed"]["comments"] == 2
        assert mode["usage_matches_incremental"] is True
        assert mode["usage_matches_cumulative"] is False
        # 当前版本不具备防重复和配置拒绝，不能把覆盖复用成功解释为可直接上线。
        assert mode["repeat_without_calls"] is False
        for variant in mode["variants"]:
            assert variant["rejected_without_calls"] is (variant["case"] != "changed_model")
        assert mode["cross_checkout"]["exit_code"] != 0
        assert not mode["cross_checkout"]["calls"]
        assert mode["corrupt_session"]["exit_code"] != 0
        assert not mode["corrupt_session"]["calls"]
        assert mode["interrupted"]["exit_code"] == -1
        assert mode["interrupted"]["tokens"] is None
        assert mode["interrupted"]["local_success_tokens"] is None
        resumed = mode["interrupted_resume"]
        if resumed and resumed["exit_code"] == 0:
            assert resumed["manifest_valid"] is True
            assert all(call["paths"] == [PATHS[1]] for call in resumed["calls"])
