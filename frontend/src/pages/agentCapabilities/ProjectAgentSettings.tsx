/** @description 仓库级 Agent 试点、评审方案和独立模型选择。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Select, Space, Switch, Tag } from "antd";
import { Link } from "react-router-dom";

import { agentCatalogKey, getAgentCatalog, getAgentProject, saveAgentProject } from "../../api/agentCapabilities";
import type { AgentCatalog, AgentProject, AgentProjectInput } from "../../api/agentCapabilities";
import { apiRequest } from "../../api/client";
import type { ModelConfiguration } from "../../api/types";
import { QueryState } from "../../ui/QueryState";
import { useConfigurationDraft, useDraftStatus } from "../../ui/useConfigurationDraft";
import type { DraftStatus } from "../../ui/useConfigurationDraft";
import { AgentStepSequence } from "./AgentStepSequence";

interface Props { token: string; repositoryId: number; onStatusChange: (status: DraftStatus) => void }

function Editor({ token, repositoryId, onStatusChange, value, models, catalog }: Props & {
  value: AgentProject; models: ModelConfiguration[]; catalog: AgentCatalog;
}) {
  const baseline: AgentProjectInput = {
    enabled: value.enabled, scheme_id: value.scheme_id, model_profile_id: value.model_profile_id,
    version: value.version,
  };
  const draft = useConfigurationDraft(baseline);
  const input = draft.value ?? baseline;
  const client = useQueryClient();
  const key = ["agent-project", repositoryId];
  const save = useMutation({
    mutationFn: () => saveAgentProject(token, repositoryId, input),
    onSuccess: (result) => {
      client.setQueryData(key, result);
      draft.saved();
      void client.invalidateQueries({ queryKey: ["agent-comparisons"] });
      void client.invalidateQueries({ queryKey: agentCatalogKey });
    },
  });
  useDraftStatus(draft.dirty, save.isPending, onStatusChange);
  const scheme = draft.dirty && input.scheme_id !== baseline.scheme_id
    ? catalog.schemes.find((item) => item.id === (input.scheme_id ?? catalog.default_id))
    : value.effective_scheme;
  const model = models.find((item) => item.id === input.model_profile_id);
  const available = catalog.schemes.filter((item) => item.state === "published" || item.id === input.scheme_id);
  const modelName = model?.model ?? (input.model_profile_id === baseline.model_profile_id
    ? value.effective_model ?? "未解析" : "按项目配置解析");
  const pilotLabel = input.enabled === baseline.enabled
    ? input.enabled ? "已启用试点" : "试点关闭"
    : input.enabled ? "将启用试点" : "将关闭试点";
  return <div className="agent-settings-stack">
    {!value.manageable && <Alert type="info" title="这个仓库由服务配置管理" showIcon />}
    {value.unavailable_reason && <Alert type="warning" title={value.unavailable_reason} showIcon />}
    <div className="agent-project-layout">
      <section className="agent-project-effective" aria-label="方案与模型摘要">
        <div className="agent-settings-list-heading">
          <h3>{draft.dirty ? "待保存配置" : "当前配置"}</h3>
          <Tag color={input.enabled ? "blue" : "default"}>{pilotLabel}</Tag>
        </div>
        {scheme && <p>{draft.dirty ? "保存后使用" : "当前使用"} #{scheme.id} · {scheme.name}</p>}
        <dl className="agent-scheme-facts">
          <div><dt>Agent 模型</dt><dd>{modelName}</dd></div>
          {scheme && <div><dt>已配置能力</dt><dd>Skill {scheme.document.skill_ids.length} 项 · 补查 {scheme.document.files.length} 条 · MCP {scheme.document.mcp?.tool ?? "未配置"}</dd></div>}
        </dl>
        {scheme && <AgentStepSequence steps={scheme.document.steps} />}
      </section>
      <Form layout="vertical" disabled={!value.manageable || save.isPending} onFinish={() => save.mutate()}>
        <Form.Item label="启用仓库试点" htmlFor="project-agent-enabled">
          <Switch id="project-agent-enabled" checked={input.enabled}
            onChange={(enabled) => draft.setValue({ ...input, enabled })} />
        </Form.Item>
        <Form.Item label="评审方案" htmlFor="project-agent-scheme">
          <Select id="project-agent-scheme" value={input.scheme_id ?? 0}
            options={[{ value: 0, label: `继承平台默认 · #${catalog.default_id}` },
              ...available.map((item) => ({ value: item.id, label: `#${item.id} · ${item.name}${item.state === "disabled" ? "（已停用）" : ""}` }))]}
            onChange={(id) => draft.setValue({ ...input, scheme_id: id || null })} />
        </Form.Item>
        <Form.Item label="Agent 模型" htmlFor="project-agent-model">
          <Select id="project-agent-model" value={input.model_profile_id ?? 0}
            options={[{ value: 0, label: "继承项目评审模型" },
              ...models.filter((item) => item.provider === "openai" || item.provider === "dashscope")
                .map((item) => ({ value: item.id, label: `${item.name} · ${item.model}` }))]}
            onChange={(id) => draft.setValue({ ...input, model_profile_id: id || null })} />
        </Form.Item>
        <Space wrap>
          <Button type="primary" htmlType="submit" loading={save.isPending} disabled={!draft.dirty}>保存 Agent 设置</Button>
          {draft.dirty && <Button onClick={draft.saved}>放弃更改</Button>}
        </Space>
      </Form>
    </div>
    {save.error && <Alert type="error" showIcon title={save.error.message} description="你的更改已保留。" />}
    {save.isSuccess && !draft.dirty && <Alert type="success" showIcon title="Agent 设置已保存" />}
  </div>;
}

/** 配置项只在打开 Agent 标签后读取。 */
export function ProjectAgentSettings(props: Props) {
  const { token, repositoryId } = props;
  const project = useQuery({
    queryKey: ["agent-project", repositoryId],
    queryFn: ({ signal }) => getAgentProject(token, repositoryId, signal),
  });
  const catalog = useQuery({ queryKey: agentCatalogKey, queryFn: ({ signal }) => getAgentCatalog(token, signal) });
  const models = useQuery({ queryKey: ["model-profiles"],
    queryFn: ({ signal }) => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles", { signal }) });
  return <Card title="自建 Agent" extra={<Link to="/settings?tab=agent">管理评审方案</Link>}>
    <QueryState loading={project.isPending || catalog.isPending || models.isPending}
      error={project.error ?? catalog.error ?? models.error}
      onRetry={() => { void project.refetch(); void catalog.refetch(); void models.refetch(); }} />
    {project.data && catalog.data && models.data && <Editor key={repositoryId} {...props}
      value={project.data} catalog={catalog.data} models={models.data} />}
  </Card>;
}
