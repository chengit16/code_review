/** @description 项目级合并前配置；读取成功后才允许编辑，草稿不被后台刷新覆盖，服务端复核权限。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, Collapse, Input, Switch, Tag } from "antd";
import { useId } from "react";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";
import { useConfigurationDraft, useDraftStatus } from "../ui/useConfigurationDraft";
import type { DraftStatus } from "../ui/useConfigurationDraft";

interface Configuration { enabled: boolean; include_description: boolean; context_paths: string[] }

/** 配置独立保存，写入失败保留草稿；外层窗口负责离开确认。 */
export function PremergeSetting({ token, repositoryId, targetBranch, onOpenDiagnosis, onStatusChange }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
  /** 已保存的目标分支；省略时提示核对基础接入配置。 */ targetBranch?: string;
  /** 切换到同一项目的接入诊断，保留当前草稿；省略时隐藏入口。 */ onOpenDiagnosis?: () => void;
  /** 汇总未保存与写入状态，不负责授权。 */ onStatusChange?: (status: DraftStatus) => void;
}) {
  const client = useQueryClient();
  const fieldId = useId();
  const key = ["premerge-setting", repositoryId];
  const query = useQuery({ queryKey: key, queryFn: () => apiRequest<Configuration>(token, `/api/repositories/${repositoryId}/premerge`) });
  const draft = useConfigurationDraft(query.data);
  const save = useMutation({
    mutationFn: (input: Configuration) => apiRequest<Configuration>(token, `/api/repositories/${repositoryId}/premerge`, { method: "PUT", body: JSON.stringify(input) }),
    onSuccess: (result) => {
      // 先更新读取基线再释放草稿，避免失效重取期间短暂回显旧配置。
      client.setQueryData(key, result);
      draft.saved();
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ["premerge-reviews"] });
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
    <div className="publication-section-heading"><h3>合并前审查</h3><Tag>手动保存</Tag></div>
    <p className="publication-section-description">在 MR 合并前，审查相对目标分支基准的完整差异。</p>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {value && <>
      <fieldset className="configuration-fields publication-fields" disabled={save.isPending}>
        <div className="publication-toggle-row">
          <div><label htmlFor={`${fieldId}-enabled`}>审查未合并 MR 的完整差异</label><p id={`${fieldId}-enabled-help`}>新建、重新打开或更新 MR 时触发；相同提交与背景的重复事件不会重复审查。</p></div>
          <Switch id={`${fieldId}-enabled`} aria-label="审查未合并 MR 的完整差异" aria-describedby={`${fieldId}-enabled-help`} checked={value.enabled} disabled={save.isPending} onChange={(enabled) => changeValue({ ...value, enabled })} />
        </div>
        <div className="publication-context">
          <div className="publication-field-label">审查背景 <span>可选</span></div>
          <Checkbox checked={value.include_description} disabled={save.isPending} onChange={(event) => changeValue({ ...value, include_description: event.target.checked })}>包含 GitLab MR 描述</Checkbox>
          <p className="publication-field-help">将 MR 中的需求和验收说明作为业务背景，辅助理解代码。</p>
          <div className="publication-document-field">
            <label htmlFor={`${fieldId}-paths`}>仓库业务文档路径</label>
            <Input.TextArea id={`${fieldId}-paths`} aria-label="仓库业务文档路径" aria-describedby={`${fieldId}-paths-help${pathsError ? ` ${fieldId}-paths-error` : ""}`} aria-invalid={Boolean(pathsError)} status={pathsError ? "error" : undefined} rows={3} value={value.context_paths.join("\n")} disabled={save.isPending} onChange={(event) => changeValue({ ...value, context_paths: event.target.value.split("\n") })} placeholder="例如：docs/review-context.md" />
            <p id={`${fieldId}-paths-help`} className="publication-field-help">每行一份，最多 3 份 .md 或 .txt 文件；从 MR 的头提交读取，可留空。</p>
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
      <Alert role="note" type="info" showIcon title="开启并保存后，新建 MR 可自动进入审查队列" description="需接通 GitLab Webhook，并由运行中的 Worker 执行。结果在平台「合并前审查」查看，不自动发送飞书、发布 GitLab 评论或阻止合并。" />
      <Collapse ghost size="small" items={[{ key: "setup", label: "自动触发需要哪些配置？", children: <div className="publication-setup-help">
        <ol>
          <li>在 GitLab 的 Settings → Webhooks 填写本项目回调地址和对应 Token，勾选 <strong>Merge request events</strong>；只勾选 Push events 不够。</li>
          <li>保持项目的 Webhook 接收开关开启，MR 目标分支须与{targetBranch ? <>已保存的 <code>{targetBranch}</code></> : "基础接入中的目标分支"}一致。</li>
          <li>在接入诊断中验证 Git 与 GitLab API 权限，配置可用的评审模型，并确认 Worker 正常运行。</li>
        </ol>
        <p>无需配置 GitLab CI。未收到过事件的已有 MR 不会自动补扫，需后续更新触发。「合并后评审」开关与此独立。</p>
        {onOpenDiagnosis && <Button type="link" size="small" onClick={onOpenDiagnosis}>查看接入诊断</Button>}
      </div> }]} />
    </div>
  </section>;
}
