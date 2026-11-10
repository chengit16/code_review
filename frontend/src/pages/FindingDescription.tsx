/** @description 发现正文安全 Markdown 与旧编号兼容；不执行 HTML、不加载远程图片或改写持久化事实。 */
import { isValidElement } from "react";
import type { ReactNode } from "react";
import Markdown from "react-markdown";

import { FindingCodeBlock } from "./FindingCodeBlock";
import { presentFindingContent } from "./findingContent";
import { maskFindingLiterals, splitFindingBlocks } from "./findingLists";
import "../styles/findings.css";

function safeLink(url: string): string {
  return /^(?:https?:\/\/|\/(?!\/)|#)/i.test(url) ? url : "";
}

function MarkdownCode({ children }: { children?: ReactNode }) {
  if (!isValidElement<{ children?: string; className?: string }>(children)) return <pre>{children}</pre>;
  const value = children.props.children;
  if (typeof value !== "string") return <pre>{children}</pre>;
  // Markdown 渲染器在每个代码节点末尾附加一个换行；只移除此分隔符，保留代码本身的空行和缩进。
  const code = value.endsWith("\n") ? value.slice(0, -1) : value;
  const language = children.props.className?.replace(/^language-/, "") ?? "";
  return <FindingCodeBlock key={`${language}:${code}`} content={code} language={language} />;
}

function FindingMarkdown({ content }: { content: string }) {
  return <Markdown urlTransform={safeLink} components={{
    pre: MarkdownCode,
    a: ({ href, children }) => href ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>,
    img: ({ alt }) => <span>{alt ? `[图片：${alt}]` : "[图片]"}</span>,
    ol: ({ children, start }) => <ol className="finding-ordered-list finding-markdown-list" start={start}>{children}</ol>,
    ul: ({ children }) => <ul className="finding-markdown-list">{children}</ul>,
  }}>{content}</Markdown>;
}

function FindingParagraph({ content }: { content: string }) {
  // 明确的 Markdown 块保持整体结构；旧中文和行内编号仍走既有兼容分项，不重排代码或嵌套列表。
  const hasMarkdownBlocks = /^\s*(?:[-*+] |#{1,6} |>| {2,}\d+[.)] )/m.test(maskFindingLiterals(content));
  if (hasMarkdownBlocks) return <div className="finding-text-blocks"><FindingMarkdown content={content} /></div>;
  return <div className="finding-text-blocks">{splitFindingBlocks(content).map((block, index) => block.kind === "list"
    ? <ol key={index} className="finding-ordered-list">{block.items.map((item, itemIndex) => <li key={itemIndex}>
      <span className="finding-list-marker" aria-hidden="true">{item.marker}</span><div><FindingMarkdown content={item.content} /></div>
    </li>)}</ol> : <FindingMarkdown key={index} content={block.content} />)}</div>;
}

/** 旧正文归问题描述，明确建议归修复建议；安全呈现格式且不写回模型原文。 */
export function FindingDescription({ content }: {
  /** 原始 OCR 描述；HTML 仍作为文本，图片不发起请求，链接只允许安全协议。 */ content: string;
}) {
  const sections = presentFindingContent(content);
  let numbered = 0;
  return <div className="finding-description">{sections.map((section, index) => {
    const tone = section.label === "实际后果" ? "consequence" : section.label === "修复建议" ? "suggestion" : "plain";
    return section.label ? <div className="finding-description-section" data-tone={tone} key={index}>
      <h3><span className="finding-section-number" aria-hidden="true">{String(++numbered).padStart(2, "0")}</span>{section.label}</h3>
      <FindingParagraph content={section.content} />
    </div> : <div className="finding-description-plain" key={index}><FindingParagraph content={section.content} /></div>;
  })}</div>;
}
