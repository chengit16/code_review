/** @description 组合已发布的能力并保存不可变方案草稿。 */

import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Tag } from "antd";

import { agentNodeLabels, saveScheme } from "../../api/agentCapabilities";
import type { AgentCatalog, AgentNode, AgentScheme, SchemeDocument } from "../../api/agentCapabilities";
import { useCapabilityAction } from "./capabilityActions";

const required = { required: true, message: "请填写此项" };
type SchemeDraft = Omit<SchemeDocument, "mcp"> & { name: string; mcp?: SchemeDocument["mcp"] };

/** 已发布方案通过复制形成新草稿，可单独调整工具和步骤。 */
export function AgentSchemeEditor({ token, catalog, basis, onSaved, onCancel }: {
  token: string; catalog: AgentCatalog; basis: AgentScheme | null;
  onSaved: (id: number) => void; onCancel: () => void;
}) {
  const [form] = Form.useForm<SchemeDraft>();
  const action = useCapabilityAction();
  const steps = Form.useWatch("steps", form) ?? [];
  const selectedService = Form.useWatch(["mcp", "service_id"], form);
  const selectedTool = Form.useWatch(["mcp", "tool"], form);
  const service = catalog.services.find((item) => item.id === selectedService);
  const initial = basis ? { ...basis.document, name: basis.name }
    : { name: "", steps: [], skill_ids: [], files: [], mcp: null };

  function save(draft: SchemeDraft) {
    action.mutate(async () => {
      const body = {
        name: draft.name, basis_id: basis?.id ?? null, steps: draft.steps ?? [],
        skill_ids: draft.steps.includes("skills") ? draft.skill_ids : [],
        files: draft.steps.includes("read_file") ? draft.files : [],
        mcp: draft.steps.includes("mcp") ? draft.mcp ?? null : null,
      };
      const created = await saveScheme(token, body);
      onSaved(created.id);
    });
  }

  function move(index: number, delta: number) {
    const order = [...steps];
    [order[index], order[index + delta]] = [order[index + delta], order[index]];
    form.setFieldValue("steps", order);
  }

  return <Card title={basis ? `复制方案 #${basis.id}` : "新建评审方案"}>
    <Form form={form} layout="vertical" initialValues={initial} onFinish={save} disabled={action.isPending}>
      <Form.Item name="name" label="方案名称" rules={[required]}>
        <Input maxLength={100} />
      </Form.Item>
      <Form.Item name="steps" label="可选流程步骤">
        <Select mode="multiple" placeholder="选择要执行的步骤"
          options={(Object.keys(agentNodeLabels) as AgentNode[]).map((value) => ({ value, label: agentNodeLabels[value] }))} />
      </Form.Item>
      <div className="agent-workflow-order" aria-label="执行顺序">
        <Tag>读取差异</Tag>
        {steps.map((step, index) => <Space key={step} size={4}>
          <Tag>{agentNodeLabels[step]}</Tag>
          <Button size="small" disabled={index === 0} onClick={() => move(index, -1)}
            aria-label={`上移${agentNodeLabels[step]}`}>上移</Button>
          <Button size="small" disabled={index === steps.length - 1} onClick={() => move(index, 1)}
            aria-label={`下移${agentNodeLabels[step]}`}>下移</Button>
        </Space>)}
        <Tag>模型评审与证据校验</Tag><Tag>保存结果</Tag>
      </div>
      {steps.includes("skills") && <Form.Item name="skill_ids" label="Skill 版本"
        rules={[{ required: true, type: "array", min: 1, message: "至少选择一个 Skill" }]}>
        <Select mode="multiple" maxCount={4}
          options={catalog.skills.map((skill) => ({ value: skill.id, label: `#${skill.id} · ${skill.name} · ${skill.pattern}` }))} />
      </Form.Item>}
      {steps.includes("read_file") && <Form.List name="files"
        rules={[{ validator: async (_, value: unknown[]) => {
          if (!value?.length) throw new Error("至少添加一个补查规则");
        } }]}>
        {(fields, { add, remove }, { errors }) => <Space orientation="vertical" style={{ width: "100%" }}>
          {fields.map(({ key, name }, index) => <Card key={key} size="small" title={`补查规则 ${index + 1}`}
            extra={<Button size="small" onClick={() => remove(name)}>移除</Button>}>
            <Form.Item name={[name, "pattern"]} label="触发文件匹配式" rules={[required]}>
              <Input placeholder="例如 *.tsx" maxLength={240} />
            </Form.Item>
            <Form.Item name={[name, "path"]} label="读取仓库相对路径" rules={[required]}>
              <Input placeholder="例如 src/components/context.ts" maxLength={240} />
            </Form.Item>
            <Space wrap>
              <Form.Item name={[name, "start_line"]} label="起始行" rules={[required]}><InputNumber min={1} max={100000} precision={0} /></Form.Item>
              <Form.Item name={[name, "lines"]} label="最多读取行数" rules={[required]}><InputNumber min={1} max={80} precision={0} /></Form.Item>
            </Space>
          </Card>)}
          <Button onClick={() => add({ pattern: "*", start_line: 1, lines: 30 })} disabled={fields.length >= 3}>添加补查规则</Button>
          <Form.ErrorList errors={errors} />
        </Space>}
      </Form.List>}
      {steps.includes("mcp") && <Card size="small" title="MCP 规范检索">
        <Form.Item name={["mcp", "service_id"]} label="MCP 服务" rules={[required]}>
          <Select onChange={() => { form.setFieldValue(["mcp", "tool"], undefined); form.setFieldValue(["mcp", "argument"], undefined); }}
            options={catalog.services.filter((item) => item.enabled).map((item) => ({ value: item.id, label: `#${item.id} · ${item.name}` }))} />
        </Form.Item>
        <Form.Item name={["mcp", "tool"]} label="只读工具" rules={[required]}>
          <Select onChange={() => form.setFieldValue(["mcp", "argument"], undefined)}
            options={Object.keys(service?.tools ?? {}).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name={["mcp", "argument"]} label="查询参数" rules={[required]}>
          <Select options={(service?.tools[selectedTool]?.arguments ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name={["mcp", "pattern"]} label="触发文件匹配式" rules={[required]}><Input placeholder="例如 *.py" maxLength={240} /></Form.Item>
        <Form.Item name={["mcp", "query"]} label="发送给 MCP 的规范关键词" rules={[required]}><Input maxLength={500} /></Form.Item>
        <Form.Item name={["mcp", "failure"]} label="查询失败时" initialValue="continue" rules={[required]}>
          <Select options={[{ value: "continue", label: "继续评审并记录失败" }, { value: "stop", label: "停止本次 Agent 评审" }]} />
        </Form.Item>
      </Card>}
      {action.error && <Alert type="error" showIcon title={action.error.message} />}
      <Space wrap className="agent-editor-actions">
        <Button type="primary" htmlType="submit" loading={action.isPending}>保存新草稿</Button>
        <Button onClick={onCancel}>取消</Button>
      </Space>
    </Form>
  </Card>;
}
