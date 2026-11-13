/** @description 单任务危险操作确认；冻结目标并显示服务端冲突，删除成功后刷新统计及返回列表。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Modal } from "antd";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { deleteTask } from "../api/tasks";
import type { TaskDeletionTarget } from "../api/tasks";

/** 仅为可编辑账号呈现；服务端再次验证管理员权限、版本与在途状态。 */
export function TaskDelete({ token, target, back, disabled = false, compact = false }: {
  /** 内存管理凭据，不进入 URL。 */ token: string;
  /** 页面最近一次获取的任务版本，打开确认框时复制。 */ target: TaskDeletionTarget;
  /** 删除成功后的任务列表地址。 */ back: string;
  /** 存在活动补审或同页写操作时不能发起删除。 */ disabled?: boolean;
  /** 列表使用紧凑文字按钮，仍提供包含任务编号的可访问名称。 */ compact?: boolean;
}) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [frozen, setFrozen] = useState<TaskDeletionTarget | null>(null);
  const submitting = useRef(false);
  const mutation = useMutation({
    retry: false,
    mutationFn: (selected: TaskDeletionTarget) => deleteTask(token, selected),
    onSuccess: () => {
      // 删除使任务、发现、跟进与成本统计同时失效；取消旧详情读取避免回填缓存。
      void client.cancelQueries({ queryKey: ["job", String(target.id)] });
      client.removeQueries({ queryKey: ["job", String(target.id)] });
      for (const key of ["jobs", "job-neighbors", "overview", "review-issues", "review-issue", "review-findings", "review-finding", "review-feedback-summary", "review-effectiveness", "event-search", "operations"]) {
        void client.invalidateQueries({ queryKey: [key] });
      }
      navigate(back, { replace: true });
    },
    onSettled: () => { submitting.current = false; },
  });
  function submit() {
    if (!frozen || submitting.current || mutation.isError) return;
    submitting.current = true;
    mutation.mutate(frozen);
  }
  const terminal = ["complete", "partial", "failed", "skipped", "cancelled"].includes(target.status);
  // 弹窗 Portal 的事件也会冒泡到表格行；隔离删除交互，避免点击说明时打开详情。
  return <span onClick={(event) => event.stopPropagation()}><Button danger
    type={compact ? "text" : "default"} size={compact ? "small" : "middle"}
    aria-label={compact ? `删除任务 ${target.id}` : "删除任务"}
    title={!terminal ? "请先取消任务或等待执行结束" : disabled ? "请等待当前操作或补审结束" : undefined}
    disabled={disabled || !terminal || frozen !== null} onClick={() => { mutation.reset(); setFrozen({ ...target }); }}>{compact ? "删除" : "删除任务"}</Button>
    <Modal title={`删除任务 #${frozen?.id ?? target.id}`} open={frozen !== null} onOk={submit}
      onCancel={() => { if (!submitting.current) setFrozen(null); }}
      okText="确认删除" cancelText="取消" confirmLoading={mutation.isPending}
      okButtonProps={{ danger: true, disabled: mutation.isPending || mutation.isError }}
      cancelButtonProps={{ disabled: mutation.isPending }} closable={!mutation.isPending}
      keyboard={!mutation.isPending} mask={{ closable: !mutation.isPending }}>
      <p>将永久删除任务 #{frozen?.id}（第 {frozen?.attempts} 次）的评审记录、发现及反馈，并移除仅由该任务产生的跟进问题，相关统计会重新计算。</p>
      <Alert type="warning" showIcon title="此操作不可撤销" description="共享问题保留其他任务的来源。已发送的飞书消息和 GitLab 评论不会撤回，已发生的模型费用不会退还。原始工件保留至运维清理。" />
      {mutation.error && <Alert type="error" showIcon title="删除未确认成功" description={`${mutation.error.message}。请关闭弹窗并刷新核对后再操作。`} />}
    </Modal></span>;
}
