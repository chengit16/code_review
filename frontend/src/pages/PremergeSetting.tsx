/** @description 项目级合并前配置；读取成功后才允许编辑，草稿不被后台刷新覆盖，服务端复核权限。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, Collapse, Input, Switch } from "antd";
import { useId } from "react";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";
import { useConfigurationDraft, useDraftStatus } from "../ui/useConfigurationDraft";
import type { DraftStatus } from "../ui/useConfigurationDraft";

interface Configuration { enabled: boolean; include_description: boolean; context_paths: string[] }

/** 配置独立保存，写入失败保留草稿；外层窗口负责离开确认。 */
export function PremergeSetting({ token, repositoryId, targetBranch, onOpenDiagnosis, onStatusChange, onEnabledSaved, contextOnly = false }: {
  /** 嵌入评审参数时仅保存背景，开关统一在基础接入。 */ contextOnly?: boolean;
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
  /** 已保存的目标分支；省略时提示核对基础接入配置。 */ targetBranch?: string;
  /** 切换到同一项目的接入诊断，保留当前草稿；省略时隐藏入口。 */ onOpenDiagnosis?: () => void;
  /** 保存后同步基础接入开关，避免随后保存覆盖新值。 */ onEnabledSaved?: (enabled: boolean) => void;
  /** 汇总未保存与写入状态，不负责授权。 */ onStatusChange?: (status: DraftStatus) => void;
}) {
  const client = useQueryClient();
  const fieldId = useId();
  const key = ["premerge-setting", repositoryId];
  const query = useQuery({ queryKey: key, queryFn: () => apiRequest<Configuration>(token, `/api/repositories/${repositoryId}/premerge`) });
  const draft = useConfigurationDraft(query.data);
  const save = useMutation({
    mutationFn: (input: Configuration) => apiRequest<Configuration>(token, `/api/repositories/${repositoryId}/premerge`, { method: "PUT", body: JSON.stringify(contextOnly ? { include_description: input.include_description, context_paths: input.context_paths } : input) }),
    onSuccess: (result) => {
      // 先更新读取基线再释放草稿，避免失效重取期间短暂回显旧配置。
      client.setQueryData(key, result);
      draft.saved();
      onEnabledSaved?.(result.enabled);
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ["premerge-reviews"] });
      void client.invalidateQueries({ queryKey: ["jobs"] });
      void client.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
  useDraftStatus(draft.dirty, save.isPending, onStatusChange);
  const value = draft.value;
  const paths = value?.context_paths.map((path) => path.trim()).filter(Boolean) ?? [];
  const pathsError = paths.length > 3 ? "最多填写 3 份业务文档，请删除多余路径。"
    : new Set(paths).size !== paths.length ? "业务文档路径不能重复，请检查后再保存。" : "";

  function changeValue(next: Configuration) {
    save.reset();
    draft.setValue(next);
  }

  return <section className="section repository-publication-setting">
    <div className="publication-section-heading"><h3>{contextOnly ? "合并前审查背景" : "合并前审查"}</h3></div>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {value && <>
      <fieldset className="configuration-fields publication-fields" disabled={save.isPending}>
        {!contextOnly && <div className="publication-toggle-row">
          <div><label htmlFor={`${fieldId}-enabled`}>审查未合并 MR 的完整差异</label><p id={`${fieldId}-enabled-help`}>新建、重新打开或更新 MR 时触发；相同提交与背景的重复事件不会重复审查。</p></div>
          <Switch id={`${fieldId}-enabled`} aria-label="审查未合并 MR 的完整差异" aria-describedby={`${fieldId}-enabled-help`} checked={value.enabled} disabled={save.isPending} onChange={(enabled) => changeValue({ ...value, enabled })} />
        </div>}
        <div className="publication-context">
          <div className="publication-field-label">审查背景 <span>可选</span></div>
          <Checkbox checked={value.include_description} disabled={save.isPending} onChange={(event) => changeValue({ ...value, include_description: event.target.checked })}>包含 GitLab MR 描述</Checkbox>
          <div className="publication-document-field">
            <label htmlFor={`${fieldId}-paths`}>仓库业务文档路径</label>
            <Input.TextArea id={`${fieldId}-paths`} aria-label="仓库业务文档路径" aria-describedby={`${fieldId}-paths-help${pathsError ? ` ${fieldId}-paths-error` : ""}`} aria-invalid={Boolean(pathsError)} status={pathsError ? "error" : undefined} rows={3} value={value.context_paths.join("\n")} disabled={save.isPending} onChange={(event) => changeValue({ ...value, context_paths: event.target.value.split("\n") })} placeholder="例如：docs/review-context.md" />
            <p id={`${fieldId}-paths-help`} className="publication-field-help">每行一份，最多 3 份 .md 或 .txt 文件，取自 MR 头提交。</p>
            {pathsError && <p id={`${fieldId}-paths-error`} className="publication-validation" role="alert">{pathsError}</p>}
          </div>
        </div>
        <div className="publication-save-row">
          <span className={`publication-save-status${draft.dirty ? " is-dirty" : ""}`} role="status">{save.isPending ? "正在保存合并前配置…" : draft.dirty ? "有未保存的更改，保存后生效" : save.isSuccess ? "合并前配置已保存" : "当前配置已保存"}</span>
          <Button type="primary" loading={save.isPending} disabled={!draft.dirty || Boolean(pathsError) || save.isPending} onClick={() => save.mutate({ ...value, context_paths: paths })}>保存合并前配置</Button>
        </div>
      </fieldset>
      {save.error && <Alert type="error" showIcon title={`保存失败：${save.error.message}`} description="草稿已保留，请重试保存。" />}
    </>}
    <div className="publication-trigger-help">
      <Collapse ghost size="small" items={[{ key: "setup", label: "自动触发需要哪些配置？", children: <div className="publication-setup-help">
        <p>开启并保存后，新建 MR 可自动进入审查队列。结果在「评审任务」查看，按项目配置通知飞书；合入相同版本时复用原任务。GitLab 行内发布独立控制，不强制阻止合并。</p>
        <ol>
          <li>在 GitLab 的 Settings → Webhooks 填写本项目回调地址和对应 Token，勾选 <strong>Merge request events</strong>；只勾选 Push events 不够。</li>
          <li>保持项目的 Webhook 接收开关开启，MR 目标分支须属于{targetBranch ? <>已保存的目标分支：<code>{targetBranch}</code></> : "基础接入中选择的目标分支"}。</li>
          <li>在接入诊断中验证 Git 与 GitLab API 权限，配置可用的评审模型，并确认 Worker 正常运行。</li>
        </ol>
        <p>无需配置 GitLab CI。未收到过事件的已有 MR 不会自动补扫，需后续更新触发。目标分支 Push 评审用于接收合并或直接推送后的变更。</p>
        {onOpenDiagnosis && <Button type="link" size="small" onClick={onOpenDiagnosis}>查看接入诊断</Button>}
      </div> }]} />
    </div>
  </section>;
}
