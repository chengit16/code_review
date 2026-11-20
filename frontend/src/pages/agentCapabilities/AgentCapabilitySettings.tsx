/** @description 系统设置中的 Agent 方案、Skill、工具和 MCP 入口。 */

import { useQuery } from "@tanstack/react-query";
import { Alert, App, Button, Card, Collapse, Descriptions, Form, Input, Select, Space, Tabs, Tag } from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { agentCatalogKey, getAgentCatalog, publishScheme, saveSkill, selectDefaultScheme } from "../../api/agentCapabilities";
import type { AgentCatalog, AgentScheme, AgentSkill } from "../../api/agentCapabilities";
import { apiRequest } from "../../api/client";
import type { Repository } from "../../api/types";
import { QueryState } from "../../ui/QueryState";
import { AgentMcpSettings } from "./AgentMcpSettings";
import { AgentSchemeEditor } from "./AgentSchemeEditor";
import { AgentSchemeTrial } from "./AgentSchemeTrial";
import { AgentStepSequence } from "./AgentStepSequence";
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
  const referencedProjects = [
    ...bound.slice(0, 12).map((item) => item.name),
    ...(bound.length > 12 ? [`另有 ${bound.length - 12} 个固定项目`] : []),
    ...(scheme?.id === catalog.default_id ? [`${inheriting.length} 个继承项目`] : []),
  ];

  function change(title: string, perform: () => Promise<void>, content?: React.ReactNode) {
    modal.confirm({
      title, content, okText: "确认", onOk: () => action.mutateAsync(perform),
    });
  }

  return <div className="agent-settings-stack">
    <div className="agent-scheme-toolbar">
      <div className="agent-scheme-picker">
        <label htmlFor="agent-scheme-version">方案版本</label>
        <Select id="agent-scheme-version" value={scheme?.id} onChange={setSelected} className="agent-scheme-select"
          showSearch={{ optionFilterProp: "label" }}
          options={catalog.schemes.map((item) => ({ value: item.id,
            label: `#${item.id} · ${item.name} · ${catalog.default_id === item.id ? "平台默认" : states[item.state]}` }))} />
      </div>
      <Space wrap className="agent-scheme-toolbar-actions">
        <Button type="primary" disabled={basis !== undefined} onClick={() => setBasis(null)}>新建方案</Button>
        <Button disabled={!scheme || basis !== undefined} onClick={() => setBasis(scheme)}>复制为草稿</Button>
      </Space>
    </div>
    {basis !== undefined && <AgentSchemeEditor token={token} catalog={catalog} basis={basis}
      onSaved={(id) => { setSelected(id); setBasis(undefined); }} onCancel={() => setBasis(undefined)} />}
    {scheme && document && <Card size="small" className="agent-scheme-card" title={`#${scheme.id} · ${scheme.name}`}
      extra={<Tag color={scheme.state === "published" ? "blue" : scheme.state === "draft" ? "gold" : "default"}>{states[scheme.state]}</Tag>}>
      <div className="agent-scheme-flow">
        <h3>执行顺序</h3>
        <AgentStepSequence steps={document.steps} />
      </div>
      <dl className="agent-scheme-facts">
        <div><dt>引用项目</dt><dd>{referencedProjects.join("、") || "暂无引用"}</dd></div>
        <div><dt>创建人</dt><dd>{scheme.actor}</dd></div>
        {reference && <div><dt>相对来源版本的更改</dt><dd>#{reference.id} · {changesFromBasis(scheme, reference).join("、") || "配置相同"}</dd></div>}
      </dl>
      <div className="agent-scheme-capabilities">
        <div><span>Skill</span>{document.skill_ids.length
          ? <ul>{document.skill_ids.map((id) => <li key={id}>#{id} {catalog.skills.find((skill) => skill.id === id)?.name}</li>)}</ul> : <strong>未配置</strong>}</div>
        <div><span>补查文件</span>{document.files.length
          ? <ul>{document.files.map((item, index) => <li key={index}>{item.pattern} → {item.path}</li>)}</ul> : <strong>未配置</strong>}</div>
        <div><span>MCP</span><strong>{document.mcp ? `服务 #${document.mcp.service_id} · ${document.mcp.tool}` : "未配置"}</strong></div>
      </div>
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
  </div>;
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
  return <div className="agent-settings-stack">
    <div className="agent-settings-list-heading">
      <span>{skills.length} 个已发布版本</span>
      <Button type="primary" onClick={() => edit()}>创建 Skill</Button>
    </div>
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
    {skills.map((skill) => <Card className="agent-skill-card" key={skill.id} size="small" title={`#${skill.id} · ${skill.name}`}
      extra={<Button size="small" onClick={() => edit(skill)}>复制并编辑</Button>}>
      <Tag>{skill.pattern}</Tag>
      <Collapse size="small" ghost items={[{ key: "body", label: "查看检查步骤",
        children: <p className="agent-skill-body">{skill.body}</p> }]} />
    </Card>)}
    {skills.length === 0 && !editing && <Alert type="info" title="尚未发布 Skill" />}
  </div>;
}

/** 目录按管理员权限读取，子页操作均使用真实服务端配置。 */
export function AgentCapabilitySettings({ token }: { token: string }) {
  const [params, setParams] = useSearchParams();
  const catalog = useQuery({ queryKey: agentCatalogKey, queryFn: ({ signal }) => getAgentCatalog(token, signal) });
  const repositories = useQuery({ queryKey: ["repositories"],
    queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  const section = params.get("agent_section");
  return <Card className="agent-capability-settings" size="small" title="自建 Agent">
    <QueryState loading={catalog.isPending || repositories.isPending} error={catalog.error ?? repositories.error}
      onRetry={() => { void catalog.refetch(); void repositories.refetch(); }} />
    {catalog.data && repositories.data && <Tabs size="small" activeKey={section === "skills" || section === "tools" || section === "mcp" ? section : "schemes"}
      onChange={(key) => setParams((current) => {
        const next = new URLSearchParams(current);
        if (key === "schemes") next.delete("agent_section");
        else next.set("agent_section", key);
        return next;
      }, { preventScrollReset: true })} items={[
      { key: "schemes", label: "评审方案", children: <Schemes token={token} catalog={catalog.data} repositories={repositories.data} /> },
      { key: "skills", label: "Skill", children: <Skills token={token} skills={catalog.data.skills} /> },
      { key: "tools", label: "内置工具", children: <Descriptions layout="vertical" column={1} items={[
        { key: "diff", label: "读取差异", children: "基础步骤。读取已确认的 Git 变更范围，按页交给模型。" },
        { key: "file", label: "补查相关文件", children: "在方案中选择此步骤，填入触发匹配式和仓库相对路径。只读取固定头提交的普通文本文件。" },
      ]} /> },
      { key: "mcp", label: "MCP 服务", children: <AgentMcpSettings token={token} services={catalog.data.services}
        repositories={repositories.data} onDiscovered={() => void catalog.refetch()} /> },
    ]} />}
  </Card>;
}
