"""保存模型单价快照并按 OCR 实际用量计算预估费用；不推断缺失用量。"""

from __future__ import annotations

from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any

PRICE_FIELDS = ("price_currency", "input_price_per_million", "output_price_per_million")

PRICING_MIGRATION = """
ALTER TABLE model_profiles ADD COLUMN price_currency TEXT NOT NULL DEFAULT 'CNY'
    CHECK(price_currency IN ('CNY', 'USD'));
ALTER TABLE model_profiles ADD COLUMN input_price_per_million TEXT;
ALTER TABLE model_profiles ADD COLUMN output_price_per_million TEXT;
DROP TRIGGER IF EXISTS history_model_profiles_insert;
DROP TRIGGER IF EXISTS history_model_profiles_update;
DROP TRIGGER IF EXISTS history_model_profiles_delete;
CREATE TRIGGER history_model_profiles_insert AFTER INSERT ON model_profiles BEGIN
  INSERT INTO config_revisions(object_type,object_id,action,after_json)
  VALUES ('model_profile',NEW.id,'created',json_object(
    'name',NEW.name,'provider',NEW.provider,'model',NEW.model,'base_url',NEW.base_url,
    'api_key_ciphertext',NEW.api_key_ciphertext,'enabled',NEW.enabled,
    'price_currency',NEW.price_currency,'input_price_per_million',NEW.input_price_per_million,
    'output_price_per_million',NEW.output_price_per_million)); END;
CREATE TRIGGER history_model_profiles_update AFTER UPDATE ON model_profiles
WHEN json_object('name',OLD.name,'provider',OLD.provider,'model',OLD.model,
  'base_url',OLD.base_url,'api_key_ciphertext',OLD.api_key_ciphertext,'enabled',OLD.enabled,
  'price_currency',OLD.price_currency,'input_price_per_million',OLD.input_price_per_million,
  'output_price_per_million',OLD.output_price_per_million) !=
  json_object('name',NEW.name,'provider',NEW.provider,'model',NEW.model,
  'base_url',NEW.base_url,'api_key_ciphertext',NEW.api_key_ciphertext,'enabled',NEW.enabled,
  'price_currency',NEW.price_currency,'input_price_per_million',NEW.input_price_per_million,
  'output_price_per_million',NEW.output_price_per_million) BEGIN
  INSERT INTO config_revisions(object_type,object_id,action,before_json,after_json)
  VALUES ('model_profile',NEW.id,'updated',
    json_object('name',OLD.name,'provider',OLD.provider,'model',OLD.model,'base_url',OLD.base_url,
      'api_key_ciphertext',OLD.api_key_ciphertext,'enabled',OLD.enabled,
      'price_currency',OLD.price_currency,'input_price_per_million',OLD.input_price_per_million,
      'output_price_per_million',OLD.output_price_per_million),
    json_object('name',NEW.name,'provider',NEW.provider,'model',NEW.model,'base_url',NEW.base_url,
      'api_key_ciphertext',NEW.api_key_ciphertext,'enabled',NEW.enabled,
      'price_currency',NEW.price_currency,'input_price_per_million',NEW.input_price_per_million,
      'output_price_per_million',NEW.output_price_per_million)); END;
CREATE TRIGGER history_model_profiles_delete AFTER DELETE ON model_profiles BEGIN
  INSERT INTO config_revisions(object_type,object_id,action,before_json)
  VALUES ('model_profile',OLD.id,'deleted',json_object(
    'name',OLD.name,'provider',OLD.provider,'model',OLD.model,'base_url',OLD.base_url,
    'api_key_ciphertext',OLD.api_key_ciphertext,'enabled',OLD.enabled,
    'price_currency',OLD.price_currency,'input_price_per_million',OLD.input_price_per_million,
    'output_price_per_million',OLD.output_price_per_million)); END;
"""


def pricing_snapshot(profile: dict[str, Any] | None) -> dict[str, str | None] | None:
    """只冻结实际配置过的单价；旧模型或未填单价时不产生可计费快照。"""

    if profile is None or not all(profile.get(key) is not None for key in PRICE_FIELDS[1:]):
        return None
    return {key: str(profile[key]) for key in PRICE_FIELDS}


def estimate_cost(
    usage: dict[str, Any] | None, snapshot: dict[str, Any] | None,
) -> dict[str, str] | None:
    """仅在输入、输出 token 及两项历史单价齐备时估算，金额用十进制避免浮点误差。"""

    pricing = snapshot.get("pricing") if isinstance(snapshot, dict) else None
    if not isinstance(usage, dict) or not isinstance(pricing, dict):
        return None
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    if (not isinstance(input_tokens, int) or isinstance(input_tokens, bool)
        or input_tokens < 0 or not isinstance(output_tokens, int)
        or isinstance(output_tokens, bool) or output_tokens < 0):
        return None
    currency = pricing.get("price_currency")
    if currency not in {"CNY", "USD"}:
        return None
    try:
        input_rate = Decimal(pricing["input_price_per_million"])
        output_rate = Decimal(pricing["output_price_per_million"])
    except (InvalidOperation, KeyError, TypeError):
        return None
    if not all(rate.is_finite() and rate >= 0 for rate in (input_rate, output_rate)):
        return None
    divisor = Decimal(1_000_000)
    # 草稿允许任意单价文本，超出十进制运算范围时只省略估算，不影响任务详情读取。
    try:
        input_cost = input_rate * input_tokens / divisor
        output_cost = output_rate * output_tokens / divisor
        total_cost = (input_rate * input_tokens + output_rate * output_tokens) / divisor
    except DecimalException:
        return None
    return {
        "currency": currency,
        "input": str(input_cost),
        "output": str(output_cost),
        "total": str(total_cost),
    }
