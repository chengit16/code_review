/** @description 将发现原文分区展示；只识别显式标签与行内代码，不注入模型生成的 HTML。 */
import { presentFindingContent } from "./findingContent";
import { splitFindingBlocks } from "./findingLists";

function FindingText({ content }: { content: string }) {
  return <>{content.split(/(`[^`\n]+`)/g).map((part, index) =>
    part.startsWith("`") && part.endsWith("`") && part.length > 2
      ? <code key={index}>{part.slice(1, -1)}</code> : part)}</>;
}

function FindingParagraph({ content }: { content: string }) {
  return <div className="finding-text-blocks">{splitFindingBlocks(content).map((block, index) => block.kind === "list"
    ? <ol key={index} className="finding-ordered-list">{block.items.map((item, itemIndex) => <li key={itemIndex}>
    <span className="finding-list-marker" aria-hidden="true">{item.marker}</span><span><FindingText content={item.content} /></span>
  </li>)}</ol> : <p key={index}><FindingText content={block.content} /></p>)}</div>;
}

/** 旧正文归问题描述，明确建议归修复建议；所有区统一分项展示，不修改持久化内容。 */
export function FindingDescription({ content }: {
  /** 未经改写的 OCR 描述，按不可信纯文本展示。 */ content: string;
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
