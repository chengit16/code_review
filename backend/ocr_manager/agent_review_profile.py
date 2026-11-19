"""复用项目生效的模型档案；入队只取身份，Worker 执行时才解密凭据。"""

from __future__ import annotations

from dataclasses import replace

from ocr_manager.agent_review_config import (
    AgentReviewConfig,
    validate_model_endpoint,
    validate_model_id,
)
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store

API_ROOTS = {
    "openai": "https://api.openai.com/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def resolve_model(
    store: Store, config: AgentReviewConfig, repository_id: int, *, master_key: str | None = None,
) -> AgentReviewConfig:
    """按项目覆盖优先解析；凭据只在 Worker 的主密钥可用时解密。"""

    if repository_id not in config.repositories:
        raise ValueError("仓库未获准运行 Agent")
    if config.model_source == "dedicated":
        return config
    profile = store.get_model_profile(repository_id)
    if profile is None:
        raise ValueError("此项目没有可复用的模型配置")
    provider = profile["provider"]
    if provider not in API_ROOTS:
        raise ValueError("此项目模型的协议暂不支持复用")
    root = (profile["base_url"] or API_ROOTS[provider]).strip().rstrip("/")
    endpoint = root if root.endswith("/chat/completions") else f"{root}/chat/completions"
    validate_model_endpoint(endpoint, allow_loopback=False)
    model = profile["model"]
    validate_model_id(model)
    ciphertext = profile["api_key_ciphertext"]
    if not ciphertext:
        raise ValueError("项目模型缺少已保存的凭据")
    return replace(
        config, model=model, endpoint=endpoint,
        profile_reference=(int(profile["id"]), int(profile["version"])),
        api_key=SecretBox(master_key).decrypt(ciphertext) if master_key is not None else "",
    )
