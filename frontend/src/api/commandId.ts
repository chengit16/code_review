/** @description 为幂等写命令生成安全 UUID；兼容非安全上下文，不降低为弱随机数。 */

/** 普通 HTTP 下可能没有 randomUUID，但 getRandomValues 仍可用于生成 UUID v4。 */
export function createCommandId(): string {
  const source = globalThis.crypto;
  if (typeof source?.randomUUID === "function") return source.randomUUID();
  if (typeof source?.getRandomValues !== "function") throw new Error("浏览器无法生成安全的请求标识，请更换浏览器或通过 HTTPS 访问。");
  const bytes = source.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
  return [hex.slice(0, 4), hex.slice(4, 6), hex.slice(6, 8), hex.slice(8, 10), hex.slice(10)].map((part) => part.join("")).join("-");
}
