/** @description 安全展示合并前版本的文件范围与上下文来源摘要，不展示代码或原始提示词。 */

function parse(text: string | null | undefined): unknown {
  try { return text ? JSON.parse(text) : null; } catch { return null; }
}
function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** 旧版本工件格式不完整时标记未知，不让单个坏字段中断整页。 */
export function PremergeEvidence({ filesJson, contextJson }: {
  /** 已保存的变更文件元数据。 */ filesJson?: string | null;
  /** 已保存的上下文摘要，不含原始业务文档。 */ contextJson?: string | null;
}) {
  const files = parse(filesJson);
  const context = parse(contextJson);
  const paths = Array.isArray(files) ? files.filter(record).filter((file) => typeof file.path === "string").map((file) => String(file.path)) : [];
  const sources = record(context) && Array.isArray(context.sources) ? context.sources.filter(record) : [];
  return <details className="advanced-panel"><summary>变更文件与业务上下文来源</summary>
    <h3>变更文件</h3>{paths.length ? <ul>{paths.map((path) => <li className="mono file-path" key={path}>{path}</li>)}</ul> : <p>没有可用的变更文件记录</p>}
    <h3>业务上下文</h3>{record(context) && typeof context.digest === "string" ? <><p className="file-path">本次上下文摘要：{context.digest}</p><ul>{sources.map((source, index) => <li className="file-path" key={index}>{typeof source.label === "string" ? source.label : "未知来源"} · {typeof source.characters === "number" ? source.characters : "未知"} 字 · 摘要 {typeof source.digest === "string" ? source.digest : "未知"}</li>)}</ul></> : <p>{contextJson ? "上下文来源记录格式不可用" : "未保存业务上下文来源"}</p>}
  </details>;
}
