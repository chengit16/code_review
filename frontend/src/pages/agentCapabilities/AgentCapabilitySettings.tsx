/** @description 系统设置中的 Agent 方案、Skill、工具和 MCP 入口。 */

import { useQuery } from "@tanstack/react-query";
import { Alert, App, Button, Card, Descriptions, Form, Input, Select, Space, Tabs, Tag } from "antd";
import { useState } from "react";

import { agentCatalogKey, agentNodeLabels, getAgentCatalog, publishScheme, saveSkill, selectDefaultScheme } from "../../api/agentCapabilities";
import type { AgentCatalog, AgentScheme, AgentSkill } from "../../api/agentCapabilities";
import { apiRequest } from "../../api/client";
import type { Repository } from "../../api/types";
import { QueryState } from "../../ui/QueryState";
import { AgentMcpSettings } from "./AgentMcpSettings";
import { AgentSchemeEditor } from "./AgentSchemeEditor";
import { AgentSchemeTrial } from "./AgentSchemeTrial";
import { useCapabilityAction } from "./capabilityActions";
import "./agentCapabilities.css";

const states = { draft: "草稿", published: "已发布", disabled: "已停用" };

function changesFromBasis(scheme: AgentScheme, basis: AgentScheme) {
  const labels = { steps: "执行顺序", skill_ids: "Skill 版本", files: "补查规则", mcp: "MCP 配置" };
  return [...(scheme.name === basis.name ? [] : ["名称"]),
    ...Object.entries(labels).filter(([key]) => {
      const field = key as keyof typeof labels;
      return JSON.stringify(scheme.document[field]) !== JSON.stringify(basis.document[field]);
    }).map(([, label]) => label)];
}

function Schemes({ token, catalog, repositories }: { token: string; catalog: AgentCatalog; repositories: Repository[] }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [basis, setBasis] = useState<AgentScheme | null | undefined>(undefined);
  const action = useCapabilityAction();
  const { modal } = App.useApp();
  const scheme = catalog.schemes.find((item) => item.id === (selected ?? catalog.default_id));
  const inheriting = repositories.filter((item) => catalog.inheriting_projects.includes(item.id));
  const document = scheme?.document;
  const reference = catalog.schemes.find((item) => item.id === scheme?.basis_id);
  const bound = repositories.filter((item) => catalog.project_bindings[item.id] === scheme?.id);

  function change(title: string, perform: () => Promise<void>, content?: React.ReactNode) {
    modal.confirm({
      title, content, okText: "确认", onOk: () => action.mutateAsync(perform),
    });
  }

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    <div className="agent-scheme-toolbar">
      <Select aria-label="方案版本" value={scheme?.id} onChange={setSelected} className="agent-scheme-select"
        options={catalog.schemes.map((item) => ({ value: item.id,
          label: `#${item.id} · ${item.name} · ${catalog.default_id === item.id ? "平台默认" : states[item.state]}` }))} />
      <Button type="primary" disabled={basis !== undefined} onClick={() => setBasis(null)}>新建方案</Button>
      <Button disabled={!scheme || basis !== undefined} onClick={() => setBasis(scheme)}>复制为草稿</Button>
    </div>
    {basis !== undefined && <AgentSchemeEditor token={token} catalog={catalog} basis={basis}
      onSaved={(id) => { setSelected(id); setBasis(undefined); }} onCancel={() => setBasis(undefined)} />}
    {scheme && document && <Card title={`#${scheme.id} · ${scheme.name}`} extra={<Tag>{states[scheme.state]}</Tag>}>
      <Descriptions size="small" column={1} items={[
        { key: "actor", label: "创建人", children: scheme.actor },
        ...(reference ? [{ key: "basis", label: "相对来源版本的更改",
          children: `#${reference.id} · ${changesFromBasis(scheme, reference).join("、") || "配置相同"}` }] : []),
        { key: "projects", label: "引用项目", children: [
          ...bound.slice(0, 12).map((item) => item.name),
          ...(bound.length > 12 ? [`另有 ${bound.length - 12} 个固定项目`] : []),
          ...(scheme.id === catalog.default_id ? [`${inheriting.length} 个继承项目`] : []),
        ].join("、") || "暂无引用" },
        { key: "flow", label: "执行顺序", children: ["读取差异", ...document.steps.map((step) => agentNodeLabels[step]), "评审与证据校验", "保存结果"].join(" → ") },
        { key: "skill", label: "Skill", children: document.skill_ids.map((id) => `#${id} ${catalog.skills.find((skill) => skill.id === id)?.name ?? ""}`).join("、") || "未配置" },
        { key: "tools", label: "补查文件", children: document.files.map((item) => `${item.pattern} → ${item.path}`).join("、") || "未配置" },
        { key: "mcp", label: "MCP", children: document.mcp ? `服务 #${document.mcp.service_id} · ${document.mcp.tool}` : "未配置" },
      ]} />
      <Space wrap className="agent-editor-actions">
        {scheme.state === "draft" && <Button type="primary" loading={action.isPending}
          onClick={() => change(`发布方案 #${scheme.id}？`, () => publishScheme(token, scheme.id, true))}>发布方案</Button>}
        {scheme.state === "published" && scheme.id !== catalog.default_id &&
          <Button onClick={() => change("设为平台默认方案？", () => selectDefaultScheme(token, scheme.id, catalog.default_id),
            <div><p>{catalog.inheriting_projects.length} 个继承项目的后续运行将采用此版本。</p>
              <p className="agent-break">{inheriting.slice(0, 20).map((item) => item.name).join("、")}{inheriting.length > 20 ? "…" : ""}</p></div>)}>设为平台默认</Button>}
        {scheme.id !== 1 && scheme.id !== catalog.default_id && scheme.state !== "disabled" && <Button danger
          onClick={() => change(`停用方案 #${scheme.id}？`, () => publishScheme(token, scheme.id, false),
            "使用这个版本的项目需要切换方案才能开始新的运行。")}>停用方案</Button>}
      </Space>
    </Card>}
    {scheme && scheme.state !== "disabled" && <AgentSchemeTrial key={scheme.id} token={token} schemeId={scheme.id} />}
  </Space>;
}

function Skills({ token, skills }: { token: string; skills: AgentSkill[] }) {
  const [form] = Form.useForm();
  const action = useCapabilityAction();
  const [editing, setEditing] = useState(false);
  function edit(skill?: AgentSkill) {
    form.resetFields();
    if (skill) form.setFieldsValue({ name: skill.name, pattern: skill.pattern, body: skill.body });
    setEditing(true);
  }
  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    <Button type="primary" onClick={() => edit()}>创建 Skill</Button>
    <Card size="small" title="编辑检查方法" hidden={!editing}>
      <Form form={form} layout="vertical" disabled={action.isPending} onFinish={(values) => action.mutate(async () => {
        await saveSkill(token, values);
        form.resetFields();
        setEditing(false);
      })}>
        <Form.Item name="name" label="Skill 名称" rules={[{ required: true, message: "请填写名称" }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="pattern" label="适用文件匹配式" rules={[{ required: true, message: "请填写匹配式" }]}
          extra="使用 * 和 ? 匹配仓库相对路径，例如 *.tsx。">
          <Input placeholder="*.tsx" maxLength={240} />
        </Form.Item>
        <Form.Item name="body" label="检查步骤" rules={[{ required: true, message: "请填写检查步骤" }]}>
          <Input.TextArea autoSize={{ minRows: 4, maxRows: 12 }} maxLength={4000} showCount />
        </Form.Item>
        <Space wrap><Button type="primary" htmlType="submit" loading={action.isPending}>发布 Skill 版本</Button>
          <Button onClick={() => { form.resetFields(); setEditing(false); }}>取消</Button></Space>
      </Form>
    </Card>
    {skills.map((skill) => <Card key={skill.id} size="small" title={`#${skill.id} · ${skill.name}`}
      extra={<Button size="small" onClick={() => edit(skill)}>复制并编辑</Button>}>
      <Tag>{skill.pattern}</Tag><p className="agent-skill-body">{skill.body}</p>
    </Card>)}
    {skills.length === 0 && !editing && <Alert type="info" title="尚未发布 Skill" />}
  </Space>;
}

/** 目录按管理员权限读取，子页操作均使用真实服务端配置。 */
export function AgentCapabilitySettings({ token }: { token: string }) {
  const catalog = useQuery({ queryKey: agentCatalogKey, queryFn: ({ signal }) => getAgentCatalog(token, signal) });
  const repositories = useQuery({ queryKey: ["repositories"],
    queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  return <Card className="agent-capability-settings" title="自建 Agent">
    <QueryState loading={catalog.isPending || repositories.isPending} error={catalog.error ?? repositories.error}
      onRetry={() => { void catalog.refetch(); void repositories.refetch(); }} />
    {catalog.data && repositories.data && <Tabs items={[
      { key: "schemes", label: "评审方案", children: <Schemes token={token} catalog={catalog.data} repositories={repositories.data} /> },
      { key: "skills", label: "Skill", children: <Skills token={token} skills={catalog.data.skills} /> },
      { key: "tools", label: "内置工具", children: <Descriptions column={1} items={[
        { key: "diff", label: "读取差异", children: "基础步骤。读取已确认的 Git 变更范围，按页交给模型。" },
        { key: "file", label: "补查相关文件", children: "在方案中选择此步骤，填入触发匹配式和仓库相对路径。只读取固定头提交的普通文本文件。" },
      ]} /> },
      { key: "mcp", label: "MCP 服务", children: <AgentMcpSettings token={token} services={catalog.data.services}
        repositories={repositories.data} onDiscovered={() => void catalog.refetch()} /> },
    ]} />}
  </Card>;
}
