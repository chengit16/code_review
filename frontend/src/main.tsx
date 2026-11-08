/** @description 管理台入口；创建 React 根节点、查询和统一设计上下文，不执行业务请求。 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./app/App";
import { DesignProvider } from "./app/DesignProvider";
import "./styles.css";
import "./styles/operations.css";
import "./styles/task-migration.css";
import "./styles/lists.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <DesignProvider><App /></DesignProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
