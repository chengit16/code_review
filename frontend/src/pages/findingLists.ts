/** @description 将历史描述中的明确有序分项分块；保留前言、编号与正文，不把代码、版本或普通引用当列表。 */

/** 一项原文及其原始编号；不重新编号历史内容。 */
export interface FindingListItem {
  /** 原始编号，可包含场景前缀。 */ marker: string;
  /** 编号后的原始正文。 */ content: string;
}

/** 描述中的普通段落或有序列表，所有说明区共用。 */
export type FindingContentBlock = { kind: "paragraph"; content: string } | { kind: "list"; items: FindingListItem[] };

/** 等长遮蔽代码和引文，让分区与分项使用原始位置且不解析引用内的标签。 */
export function maskFindingLiterals(content: string): string {
  const fenced = content.replace(/^[ \t]*(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^[ \t]*\1[ \t]*(?=\n|$)|$(?![\s\S]))/gm,
    (value) => " ".repeat(value.length));
  return fenced.replace(/(`+)[\s\S]*?\1|~~~[\s\S]*?~~~|「[^」]*」|“[^”]*”|"[^"\n]*"|'[^'\n]*'/g, (value) => " ".repeat(value.length));
}

const chineseDigits = "一二三四五六七八九十";
const markerPattern = new RegExp(`(?:(?:而在|针对|对于|在)?(?:场景|情况|步骤)\\s*)?(?:[①-⑳]|[（(](?:\\d{1,3}|[${chineseDigits}]+)[)）]|\\d{1,3}[)）、.]|[${chineseDigits}]+[、)）.]|[a-zA-Z][).])`, "g");
const markerStartPattern = new RegExp(`^\\s*(?:${markerPattern.source})`);

function markerIdentity(marker: string): { family: string; number: number } {
  const token = marker.replace(/^(?:而在|针对|对于|在)?(?:场景|情况|步骤)\s*/, "").replace(/[（()）、.]/g, "").trim();
  if (/^[①-⑳]$/.test(token)) return { family: "circle", number: token.charCodeAt(0) - "①".charCodeAt(0) + 1 };
  if (/^\d+$/.test(token)) return { family: "number", number: Number(token) };
  if (/^[a-zA-Z]$/.test(token)) return { family: "letter", number: token.toLowerCase().charCodeAt(0) - 96 };
  const [tens, units] = token.split("十");
  const digit = (value: string) => chineseDigits.indexOf(value) + 1;
  return { family: "chinese", number: units === undefined ? digit(token) : (tens ? digit(tens) : 1) * 10 + (units ? digit(units) : 0) };
}

/** 有前言的编号、场景分项及各区列表均换行；单纯“参见场景②”不凭数字拆句。 */
export function splitFindingBlocks(content: string): FindingContentBlock[] {
  const masked = maskFindingLiterals(content);
  const paragraphBreaks = [...masked.matchAll(/\n[ \t]*\n+/g)].filter((match) => !markerStartPattern.test(masked.slice(match.index + match[0].length)));
  // 空行是明确的段落边界，尾注不能被算作最后一项或继承其建议编号。
  if (paragraphBreaks.length) {
    const starts = [0, ...paragraphBreaks.map((match) => match.index + match[0].length)];
    return starts.flatMap((start, index) => {
      const paragraph = content.slice(start, paragraphBreaks[index]?.index ?? content.length).trim();
      return paragraph ? splitFindingBlocks(paragraph) : [];
    });
  }
  const candidates = [...masked.matchAll(markerPattern)].filter((match) => {
    const index = match.index;
    if (index > 0 && !/[\s；;，,。！？：:]/.test(masked[index - 1])) return false;
    const following = content.slice(index + match[0].length);
    if (/^\d/.test(following) || !following.trim()) return false;
    // 场景编号后直接连接“和/与/的”等是正文引用，不是各项定义。
    return !/^(?:和|与|及|或|都|的|、|，|,|；|;|。)/.test(following.trimStart());
  });
  const blocks: FindingContentBlock[] = [];
  let cursor = 0;
  let start = 0;
  while (start < candidates.length) {
    const first = candidates[start];
    const identity = markerIdentity(first[0]);
    let end = start + 1;
    while (end < candidates.length) {
      const previous = markerIdentity(candidates[end - 1][0]);
      const next = markerIdentity(candidates[end][0]);
      if (next.family !== identity.family || next.number <= previous.number) break;
      end++;
    }
    const sceneClause = /^(?:而在|针对|对于|在)场景/.test(first[0]) || (/^场景/.test(first[0]) && first.index > 0 && /[；;。]\s*$/.test(masked.slice(0, first.index)));
    if (end - start < 2 && !sceneClause) { start = end; continue; }
    const prefix = content.slice(cursor, first.index).trim();
    if (prefix) blocks.push({ kind: "paragraph", content: prefix });
    // 新的编号组独立呈现，避免把下一组的开头拼进前一项。
    const limit = candidates[end]?.index ?? content.length;
    const items = candidates.slice(start, end).map((match, index, group) => ({
      marker: match[0].trim(),
      content: content.slice(match.index + match[0].length, group[index + 1]?.index ?? limit).trim(),
    }));
    blocks.push({ kind: "list", items });
    cursor = limit;
    start = end;
  }
  const suffix = content.slice(cursor).trim();
  if (suffix) blocks.push({ kind: "paragraph", content: suffix });
  return blocks.length ? blocks : [{ kind: "paragraph", content }];
}

/** 仅当整段是一个列表时返回列表；带前言的描述由分块入口完整保留。 */
export function splitFindingList(content: string): FindingListItem[] | null {
  const blocks = splitFindingBlocks(content);
  return blocks.length === 1 && blocks[0].kind === "list" ? blocks[0].items : null;
}
