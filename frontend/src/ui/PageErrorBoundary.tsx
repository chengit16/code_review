/** @description 页面渲染异常降级；不显示原始堆栈或敏感数据，侧栏仍可用于离开故障页面。 */
import { Component } from "react";
import type { ReactNode } from "react";

/** 捕获单页渲染错误，重试重新挂载内容，不影响后台任务。 */
export class PageErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  /** 只记录故障标记，不把异常内容展示或持久化。 */
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div className="page"><h1>页面暂时无法显示</h1><p role="alert">后台任务不受影响。可以重试，或从侧栏进入其他页面。</p><button className="button button-primary" onClick={() => this.setState({ failed: false })}>重试页面</button></div>;
    return this.props.children;
  }
}
