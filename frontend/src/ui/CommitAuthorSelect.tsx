/** @description 任务和发现共用的提交人选择器，在线读取项目范围内的已记录姓名。 */
import { useQuery } from "@tanstack/react-query";
import { Select } from "antd";

import { getReviewAuthors } from "../api/tasks";

/** 输入只用于缩小菜单范围，选中姓名后才更新筛选；旧片段链接保留可见回显。 */
export function CommitAuthorSelect({ token, scope, repository = "", value, legacyKeyword, disabled, onChange }: {
  /** 当前管理会话。 */ token: string;
  /** 选项使用任务或当前有效发现集合。 */ scope: "tasks" | "findings";
  /** 项目 ID，空值表示全部项目。 */ repository?: string;
  /** 当前选中的完整姓名，空值表示未选中。 */ value: string;
  /** 已保存链接上的姓名片段，仅在没有完整姓名时回显。 */ legacyKeyword?: string;
  /** 写入确认期间冻结筛选，包含 Portal 中的选择器。 */ disabled?: boolean;
  /** 选中姓名或清除筛选。 */ onChange: (name: string) => void;
}) {
  const authors = useQuery({
    queryKey: ["review-authors", scope, repository],
    queryFn: ({ signal }) => getReviewAuthors(token, scope, repository, signal),
  });
  const names = authors.data ?? [];
  const options: { value: string | number; label: string; disabled?: boolean }[] = [
    { value: "", label: "全部提交人" },
    ...names.map((name) => ({ value: name, label: name })),
  ];
  // 旧链接或项目切换后仍可见当前条件，即使新选项范围未包含它。
  if (value && !names.includes(value)) options.push({ value, label: value });
  if (!value && legacyKeyword) options.push({ value: 0, label: `姓名片段：${legacyKeyword}` });
  if (authors.isError) options.push({ value: -1, label: "提交人加载失败，请重新打开", disabled: true });
  return <Select<string | number>
    className="commit-author-select"
    aria-label="筛选提交人"
    value={value || (legacyKeyword ? 0 : "")}
    options={options}
    virtual={false}
    showSearch={{ optionFilterProp: "label" }}
    disabled={disabled}
    loading={authors.isFetching}
    status={authors.isError ? "error" : undefined}
    notFoundContent="没有匹配的提交人"
    onOpenChange={(open) => { if (open && authors.isError) void authors.refetch(); }}
    onChange={(name) => { if (typeof name === "string") onChange(name); }}
  />;
}
