/** @description GitLab 行内发布单独授权，默认关闭且不会改动飞书投递。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Switch, Tag } from "antd";
import { useId } from "react";

import { apiRequest } from "../api/client";
import { useDraftStatus } from "../ui/useConfigurationDraft";
import type { DraftStatus } from "../ui/useConfigurationDraft";
import { QueryState } from "../ui/QueryState";

/** 项目编辑时显示当前授权；关闭后待发布项暂停。 */
export function GitLabPublicationSetting({ token, repositoryId, onStatusChange }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
  /** 自动保存期间阻止外层关闭。 */ onStatusChange?: (status: DraftStatus) => void;
}) {
  const client = useQueryClient();
  const fieldId = useId();
  const query = useQuery({ queryKey: ["gitlab-publication", repositoryId], queryFn: () => apiRequest<{ enabled: boolean }>(token, `/api/repositories/${repositoryId}/gitlab-publication`) });
  const save = useMutation({
    mutationFn: (enabled: boolean) => apiRequest<{ enabled: boolean }>(token, `/api/repositories/${repositoryId}/gitlab-publication`, { method: "PUT", body: JSON.stringify({ enabled }) }),
    onSuccess: (result) => {
      // 服务端确认后立即更新显示，避免异步重取期间开关短暂回弹。
      client.setQueryData(["gitlab-publication", repositoryId], result);
      void client.invalidateQueries({ queryKey: ["gitlab-publication", repositoryId] });
    },
  });
  useDraftStatus(false, save.isPending, onStatusChange);
  return <section className="section repository-publication-setting">
    <div className="publication-section-heading"><h3>GitLab 行内评论</h3><Tag>自动保存</Tag></div>
    <p className="publication-section-description">将合并后评审中可定位的发现发布到 MR，需项目令牌具备创建 discussion 的权限。</p>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    <div className="publication-toggle-row">
      <div><label htmlFor={fieldId}>向 MR 发布可定位的评审发现</label><p id={`${fieldId}-help`}>修改后自动保存；此开关不发布合并前审查结果。</p></div>
      <Switch id={fieldId} aria-label="向 MR 发布可定位的评审发现" aria-describedby={`${fieldId}-help`} checked={query.data?.enabled ?? false} disabled={save.isPending || !query.data} loading={save.isPending} onChange={(enabled) => save.mutate(enabled)} />
    </div>
    {save.isPending && <p className="publication-save-status" role="status">正在保存行内评论配置…</p>}
    {save.error && <Alert type="error" showIcon title={`保存失败：${save.error.message}`} description="配置未确认更新，请重新操作开关。" />}
    {save.isSuccess && <p className="publication-save-status" role="status">行内评论配置已保存</p>}
  </section>;
}
