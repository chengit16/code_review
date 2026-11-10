/** @description 只读代码块及主动复制；保留缩进与转义字符，不执行代码、不缓存或上报正文。 */
import { Button } from "antd";
import { Check, Copy } from "lucide-react";
import { useRef, useState } from "react";

import { copyText } from "../ui/clipboard";

/** 安全展示的代码与可选语言标识。 */
export interface FindingCodeBlockProps {
  /** 去除 Markdown 围栏后的原始代码。 */ content: string;
  /** 围栏声明的语言，仅作为文字显示，不执行动态加载。 */ language: string;
}

/** 点击或键盘激活后复制当前代码；失败保留代码供手动选择，不虚报成功。 */
export function FindingCodeBlock({ content, language }: FindingCodeBlockProps) {
  const [copyState, setCopyState] = useState<"idle" | "pending" | "copied" | "error">("idle");
  const copying = useRef(false);
  async function handleCopy() {
    if (copying.current) return;
    copying.current = true;
    setCopyState("pending");
    try {
      await copyText(content);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    } finally {
      copying.current = false;
    }
  }
  return <figure className="finding-code-block">
    <figcaption><span>{language || "代码"}</span><Button type="text" size="small"
      icon={copyState === "copied" ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      aria-label="复制代码" title="复制代码" loading={copyState === "pending"} onClick={() => void handleCopy()}>
      {copyState === "copied" ? "已复制" : "复制"}
    </Button></figcaption>
    <pre tabIndex={0} aria-label={`${language || "文本"}代码，可横向滚动`}><code>{content}</code></pre>
    <span className="finding-code-copy-status" role="status">{copyState === "copied" ? "代码已复制" : copyState === "error" ? "复制失败，请手动选择代码复制。" : ""}</span>
  </figure>;
}
