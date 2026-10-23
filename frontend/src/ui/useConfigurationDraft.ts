/** @description 配置草稿仅保存在内存；后台重新读取不覆盖编辑内容，由调用方汇总离开保护。 */
import { useEffect, useState } from "react";

/** 表单的草稿与写入状态，供编辑窗口统一保护。 */
export interface DraftStatus {
  /** 与读取基线不同的未保存内容。 */ dirty: boolean;
  /** 写入期间禁止关闭窗口。 */ pending: boolean;
}

/** 编辑时建立草稿；读取失败时不提供默认配置，保存后由调用方更新查询缓存。 */
export function useConfigurationDraft<T>(value: T | undefined) {
  const [draft, setDraft] = useState<{ value: T; baseline: T }>();
  return {
    /** 未编辑时使用最新读取结果，编辑后保持本地草稿。 */
    value: draft?.value ?? value,
    /** 对比编辑开始时的基线，后台刷新不清除脏状态。 */
    dirty: draft !== undefined && JSON.stringify(draft.value) !== JSON.stringify(draft.baseline),
    /** 只有已读取配置才能开始编辑。 */
    setValue: (next: T) => {
      if (value === undefined) return;
      setDraft((current) => {
        const baseline = current?.baseline ?? value;
        return JSON.stringify(next) === JSON.stringify(baseline) ? undefined : { value: next, baseline };
      });
    },
    /** 调用方更新查询基线后释放内存草稿。 */
    saved: () => setDraft(undefined),
  };
}

/** 子表单状态汇总到外层窗口，不在子表单重复注册路由拦截。 */
export function useDraftStatus(dirty: boolean, pending: boolean, onChange?: (status: DraftStatus) => void) {
  useEffect(() => { onChange?.({ dirty, pending }); }, [dirty, pending, onChange]);
}
