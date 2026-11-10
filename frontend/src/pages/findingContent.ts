/** @description 按明确标签和有序分项整理发现展示；保护代码与引用，不推断缺陷或写回原文。 */
import { maskFindingLiterals, splitFindingBlocks } from "./findingLists";

export { splitFindingList } from "./findingLists";

/** 原文中可识别的段落；未标注文字保留为普通段落。 */
export interface FindingContentSection {
  /** 原始标签，未标注时为空。 */ label: string | null;
  /** 标签后的完整文字，保留内部换行。 */ content: string;
}

const labels = "问题描述|发现问题|触发条件|代码依据|实际后果|修复建议|修复方案|补充|后果|建议";
const aliases: Record<string, string> = { 发现问题: "问题描述", 后果: "实际后果", 建议: "修复建议", 修复方案: "修复建议" };
const labelToken = `(?:【(${labels})】|\\[(${labels})\\]|(?:\\*\\*)?(${labels})(?:\\*\\*)?\\s*[:：](?:\\*\\*(?=\\s|$))?)\\s*[:：]?\\s*`;
const heading = new RegExp(`^\\s*(?:[-*]\\s+|\\d+[.)、]\\s*)?${labelToken}([\\s\\S]*)$`);

function normalizeFindingNewlines(content: string): string {
  const masked = maskFindingLiterals(content);
  const boundary = new RegExp(`(?:\\\\r\\\\n|\\\\n|\\\\r)+(?=[ \\t]*${labelToken})`, "g");
  // 仅兼容标签前的转义分隔符；代码、引文及普通转义字符串均保持原文，混合真实换行同样适用。
  let normalized = content;
  for (const match of [...masked.matchAll(boundary)].reverse()) {
    if (content[match.index - 1] !== "\\") normalized = `${normalized.slice(0, match.index)}\n${normalized.slice(match.index + match[0].length)}`;
  }
  return normalized;
}

function labelledLines(line: string) {
  const pattern = new RegExp(labelToken, "g");
  const matches = [...maskFindingLiterals(line).matchAll(pattern)].filter((match) => match[1] || match[2] || match.index === 0 || /[\s。；;！？]/.test(line[match.index - 1]));
  if (!matches.length) return [line];
  const label = (match: RegExpMatchArray) => aliases[match[1] ?? match[2] ?? match[3]] ?? match[1] ?? match[2] ?? match[3];
  // 单个行内冒号标签只接受明确建议；括号标签自带结构，正文引用仍由遮蔽保护。
  if (matches.length === 1 && matches[0].index > 0 && !matches[0][1] && !matches[0][2] && label(matches[0]) !== "修复建议") return [line];
  // 已有行首结构仅在后续标签顺序明确时拆分，建议正文提及“实际后果”仍是正文。
  if (heading.test(line)) {
    const order = ["问题描述", "触发条件", "代码依据", "实际后果", "修复建议", "补充"];
    const ranks = matches.map((match) => order.indexOf(label(match)));
    if (ranks.some((rank, index) => index > 0 && rank <= ranks[index - 1])) return [line];
  }
  const starts = matches.map((match) => match.index);
  return [line.slice(0, starts[0]), ...starts.map((start, index) => line.slice(start, starts[index + 1]))].filter(Boolean);
}

/** 识别行首及明确连续的旧行内标签；代码围栏和不明确的引用保持原文。 */
export function splitFindingContent(content: string): FindingContentSection[] {
  const sections: FindingContentSection[] = [];
  let current: FindingContentSection = { label: null, content: "" };
  let fence: string | null = null;
  for (const line of content.split("\n")) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/);
    for (const part of !fence && !marker ? labelledLines(line) : [line]) {
      const match = !fence && !marker && part.match(heading);
      if (match) {
        if (current.label || current.content.trim()) sections.push(current);
        const label = match[1] ?? match[2] ?? match[3];
        current = { label: aliases[label] ?? label, content: match[4] };
      } else {
        current.content += `${current.content ? "\n" : ""}${part}`;
      }
    }
    if (marker) {
      if (!fence) fence = marker[1];
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = null;
    }
  }
  if (current.label || current.content.trim()) sections.push(current);
  return sections.length ? sections : [{ label: null, content }];
}

function extractSuggestions(content: string): { description: string; suggestions: string[] } {
  const masked = maskFindingLiterals(content);
  const pattern = /建议(?=用|使用|将|把|删除|移除|增加|添加|改|统一|抽|提取|拆|合并|保留|补|检查|先|在|对|仅|通过|等待|确保|避免|恢复|关闭|修复|返回|调用|限制|启用|禁用|不)/g;
  const suggestions: string[] = [];
  let description = "";
  let cursor = 0;
  for (const match of masked.matchAll(pattern)) {
    const index = match.index;
    if (index < cursor || (index > 0 && !/[\s。；;，,（(]/.test(masked[index - 1]))) continue;
    let start = index;
    let end = index;
    // 括号内的建议仅移出完整括号，不能吞掉其后属于问题的描述。
    if (/[（(]/.test(masked[index - 1] ?? "")) {
      const opening = masked[index - 1];
      const closing = opening === "（" ? "）" : ")";
      let depth = 1;
      for (end = index; end < masked.length; end++) {
        if (masked[end] === opening) depth++;
        if (masked[end] === closing && --depth === 0) break;
      }
      if (end === masked.length) continue;
      start--;
      suggestions.push(content.slice(index, end).trim());
      end++;
    } else {
      const rest = masked.slice(index).search(/[。；;\n]/);
      end = rest < 0 ? content.length : index + rest + (masked[index + rest] === "\n" ? 0 : 1);
      suggestions.push(content.slice(index, end).trim());
    }
    description += content.slice(cursor, start);
    cursor = end;
  }
  return { description: description + content.slice(cursor), suggestions };
}

/** 历史与新描述共用的只读整理；明确建议移入修复建议，无标签正文统一问题描述，不写回原文。 */
export function presentFindingContent(content: string): FindingContentSection[] {
  const sections = splitFindingContent(normalizeFindingNewlines(content));
  const suggestions: string[] = [];
  const result = sections.map((section) => {
    if (section.label === "修复建议") { suggestions.push(section.content); return null; }
    const blocks = splitFindingBlocks(section.content);
    const description = blocks.map((block) => {
      if (block.kind === "paragraph") {
        const extracted = extractSuggestions(block.content);
        suggestions.push(...extracted.suggestions);
        return extracted.description;
      }
      return block.items.map((item) => {
        const extracted = extractSuggestions(item.content);
        suggestions.push(...extracted.suggestions.map((text) => `${item.marker} ${text}`));
        return extracted.description.trim() ? `${item.marker} ${extracted.description}` : "";
      }).join("\n");
    }).filter((text) => text.trim()).join("\n\n");
    return description.trim() ? { label: section.label ?? "问题描述", content: description.trim() } : null;
  }).filter((section) => section !== null);
  if (suggestions.length) {
    const position = result.findIndex((section) => section.label === "补充");
    result.splice(position < 0 ? result.length : position, 0, { label: "修复建议", content: suggestions.join("\n\n") });
  }
  return result;
}
