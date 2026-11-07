/** @description 台账显示标签与草稿基线；未知、未验证和未部署不映射为成功。 */
import type { ImprovementContent } from "../api/improvements";

export const kindLabels = { problem: "问题记录", improvement: "阶段改进" };
export const categoryLabels = { stability: "稳定性", performance: "性能", integration: "外部集成", deployment: "部署运维", experience: "使用体验", security: "安全", other: "其他" };
export const progressLabels = { open: "待处理", investigating: "排查中", planned: "已完成方案", verifying: "待验证", resolved: "已解决", deferred: "暂缓" };
export const codeLabels = { unchanged: "未修改", modified: "代码已修改", not_applicable: "不适用（仅文档等）" };
export const verificationLabels = { not_run: "未运行", passed: "本地验证通过", failed: "本地验证失败", blocked: "验证受阻", not_applicable: "不适用" };
export const deploymentLabels = { not_deployed: "未部署", confirmed: "部署已生效", unknown: "无法确认", not_applicable: "不适用" };

export const improvementTextFields = [
  { key: "description", label: "现象或目标", max: 10000 },
  { key: "analysis", label: "原因与排查", max: 10000 },
  { key: "solution", label: "解决办法与改进", max: 10000 },
  { key: "validation_evidence", label: "验证命令、结果与范围", max: 10000 },
  { key: "deployment_evidence", label: "部署环境与生效证据", max: 10000 },
  { key: "next_steps", label: "遗留与下一步", max: 10000 },
  { key: "references", label: "关联记录、文件与提交", max: 5000 },
] as const;

/** 新建默认不假设已经修改、验证或部署。 */
export function emptyImprovement(): ImprovementContent {
  return { title: "", kind: "problem", category: "other", status: "open", scope: "平台",
    description: "", analysis: "", solution: "", code_state: "unchanged", verification_state: "not_run",
    validation_evidence: "", deployment_state: "not_deployed", deployment_evidence: "", next_steps: "", references: "" };
}
