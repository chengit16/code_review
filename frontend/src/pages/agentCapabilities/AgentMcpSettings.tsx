/** @description 管理 MCP 服务、后台发现及仓库授权。 */

import { Alert, App, Button, Card, Empty, Form, Input, InputNumber, Select, Space, Tag } from "antd";
import { useState } from "react";

import { checkMcp, registerMcp, revokeGrant, saveGrant, updateMcp } from "../../api/agentCapabilities";
import type { AgentMcpService } from "../../api/agentCapabilities";
import type { Repository } from "../../api/types";
import { useCapabilityAction, useCapabilityCheck } from "./capabilityActions";

function ServiceCard({ token, service, repositories, onDiscovered }: {
  token: string; service: AgentMcpService; repositories: Repository[]; onDiscovered: () => void;
}) {
  const action = useCapabilityAction();
  const { modal } = App.useApp();
  const [checkId, setCheckId] = useState<number | null>(null);
  const check = useCapabilityCheck(token, checkId);
  const [grantForm] = Form.useForm<{ repository_id: number; tool: string }>();
  const tools = check.data?.result?.tools ?? service.tools;
  const pending = check.data?.status === "queued" || check.data?.status === "running" ||
    (checkId !== null && check.isPending);

  function toggle() {
    modal.confirm({
      title: `${service.enabled ? "停用" : "启用"} ${service.name}？`,
      content: service.enabled ? "停用后，该服务无法再用于 Agent 取证。" : undefined,
      onOk: () => action.mutateAsync(async () => {
        await updateMcp(token, service.id, !service.enabled);
      }),
    });
  }

  return <Card size="small" className="agent-mcp-service" title={`#${service.id} · ${service.name}`}
    extra={<Tag color={service.enabled ? "green" : undefined}>{service.enabled ? "已启用" : "已停用"}</Tag>}>
    <p className="agent-break">{service.endpoint} · {service.timeout_seconds} 秒 · {service.has_token ? "已保存令牌" : "无令牌"}</p>
    <Space wrap>
      <Button disabled={!service.enabled || pending} loading={pending} onClick={() => action.mutate(async () => {
        setCheckId((await checkMcp(token, service.id)).id);
      })}>测试连接并发现工具</Button>
      <Button onClick={toggle}>{service.enabled ? "停用服务" : "启用服务"}</Button>
    </Space>
    {check.error && <Alert type="error" showIcon title={check.error.message} />}
    {check.data?.status === "failed" && <Alert type="error" showIcon title={check.data.result?.message} />}
    {check.data?.status === "complete" && <Alert type="success" showIcon
      title={`连接成功，发现 ${Object.keys(tools).length} 个可用只读工具`}
      action={<Button size="small" onClick={onDiscovered}>刷新目录</Button>} />}
    {Object.entries(tools).map(([name, tool]) => <p key={name} className="agent-break">
      <Tag>{name}</Tag>{tool.description}
    </p>)}
    {Object.keys(tools).length > 0 && service.enabled &&
      <Form form={grantForm} layout="vertical" disabled={action.isPending} onFinish={(input) =>
        action.mutate(async () => {
          await saveGrant(token, service.id, input);
          grantForm.resetFields();
        })}>
        <Form.Item name="repository_id" label="授权仓库" rules={[{ required: true, message: "请选择仓库" }]}>
          <Select options={repositories.map((item) => ({ value: item.id, label: `${item.name} · #${item.id}` }))} />
        </Form.Item>
        <Form.Item name="tool" label="允许的工具" rules={[{ required: true, message: "请选择只读工具" }]}>
          <Select options={Object.keys(tools).map((name) => ({ value: name, label: name }))} />
        </Form.Item>
        <Button htmlType="submit" loading={action.isPending}>添加授权</Button>
      </Form>}
    {service.grants.length > 0 && <ul className="agent-capability-grants">
      {service.grants.map((grant) => <li key={`${grant.repository_id}:${grant.tool}`}>
        <span>{repositories.find((item) => item.id === grant.repository_id)?.name ?? `#${grant.repository_id}`} · {grant.tool}</span>
        <Button size="small" danger onClick={() => modal.confirm({
          title: `撤销 ${grant.tool} 的仓库授权？`,
          onOk: () => action.mutateAsync(async () => {
            await revokeGrant(token, service.id, grant.repository_id, grant.tool);
          }),
        })}>撤销</Button>
      </li>)}
    </ul>}
  </Card>;
}

/** 令牌输入只保存在表单中，服务变更登记新版本。 */
export function AgentMcpSettings({ token, services, repositories, onDiscovered }: {
  token: string; services: AgentMcpService[]; repositories: Repository[]; onDiscovered: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const action = useCapabilityAction();
  return <div className="agent-settings-stack">
    <div className="agent-settings-list-heading">
      <span>{services.length} 个已登记服务</span>
      <Button type="primary" disabled={open} onClick={() => setOpen(true)}>登记 MCP 服务</Button>
    </div>
    {open && <Card size="small" title="登记规范检索服务">
      <Form form={form} layout="vertical" initialValues={{ token: "", timeout_seconds: 8 }}
        disabled={action.isPending} onFinish={(input) => action.mutate(async () => {
          await registerMcp(token, input);
          form.resetFields();
          setOpen(false);
        })}>
        <Form.Item label="服务名称" name="name" rules={[{ required: true, message: "请填写名称" }]}><Input maxLength={100} /></Form.Item>
        <Form.Item label="MCP 地址" name="endpoint" rules={[{ required: true, message: "请填写 HTTPS 地址" }]}
          extra="使用公开 HTTPS Streamable HTTP 端点，查询只发送方案指定的关键词。">
          <Input placeholder="https://docs.example.com/mcp" maxLength={500} />
        </Form.Item>
        <Form.Item label="访问令牌（可选）" name="token"><Input.Password autoComplete="new-password" maxLength={2048} /></Form.Item>
        <Form.Item label="超时秒数" name="timeout_seconds" rules={[{ required: true, message: "请填写超时" }]}>
          <InputNumber min={1} max={15} precision={0} />
        </Form.Item>
        <Space wrap><Button type="primary" htmlType="submit" loading={action.isPending}>保存服务</Button>
          <Button onClick={() => { form.resetFields(); setOpen(false); }}>取消</Button></Space>
      </Form>
    </Card>}
    {services.map((service) => <ServiceCard key={service.id} token={token} service={service}
      repositories={repositories} onDiscovered={onDiscovered} />)}
    {services.length === 0 && !open && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={<><strong>尚未登记 MCP 服务</strong><p>登记后可测试连接、发现只读工具，再为仓库授权。</p></>} />}
  </div>;
}
