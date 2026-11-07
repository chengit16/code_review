/** @description 前端质量检查；浏览器敏感能力必须经兼容层，避免普通 HTTP 下直接崩溃。 */
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs["recommended-latest"],
  { ignores: ["dist/**"] },
  {
    files: ["src/**/*.{ts,tsx}"], ignores: ["src/test/**", "src/api/commandId.ts", "src/ui/clipboard.ts"],
    rules: { "no-restricted-syntax": ["error",
      { selector: "MemberExpression[property.name='randomUUID']", message: "请使用 createCommandId，兼容普通 HTTP 并保留安全随机数。" },
      { selector: "MemberExpression[property.name='clipboard']", message: "请使用 copyText，并为复制失败提供手动选择提示。" },
      { selector: "MemberExpression[object.name='AbortSignal'][property.name=/^(timeout|any)$/]", message: "请使用 createRequestSignal，保留旧浏览器的超时与取消能力。" },
      { selector: "CallExpression[callee.name='structuredClone']", message: "固定 JSON 草稿请按类型复制，避免依赖全局克隆 API。" },
    ] },
  },
);
