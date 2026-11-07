/** @description 合并调用方取消与请求超时；不依赖较新的 AbortSignal 静态方法，不重试请求。 */

/** 单次请求持有的取消资源；响应读取结束后必须释放定时器和监听。 */
export interface RequestSignal {
  /** 交给 fetch 的统一取消信号。 */ signal: AbortSignal;
  /** 区分截止时间与主动取消，不根据错误正文猜测。 */ hasTimedOut: () => boolean;
  /** 请求结束或初始化失败时释放监听和定时器；可重复调用。 */ dispose: () => void;
}

/** 创建有限生命周期的请求信号；已取消的调用方不会重新启动超时计时。 */
export function createRequestSignal(parent?: AbortSignal | null, milliseconds = 30000): RequestSignal {
  const controller = new AbortController();
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const abort = () => controller.abort(parent?.reason);
  if (parent?.aborted) abort();
  else {
    parent?.addEventListener("abort", abort, { once: true });
    timer = setTimeout(() => {
      if (!controller.signal.aborted) { timedOut = true; controller.abort(); }
    }, milliseconds);
  }
  return { signal: controller.signal, hasTimedOut: () => timedOut, dispose: () => {
    clearTimeout(timer);
    parent?.removeEventListener("abort", abort);
  } };
}
