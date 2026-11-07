"""由执行器启动的轻量进程组栅栏；持有继承锁，不读取业务数据或执行模型调用。"""

from __future__ import annotations

import os
import signal
import sys


def main() -> None:
    """父协调器断开控制管道即终止整组；即使 OCR 启动器关闭继承描述符也不提前放锁。"""

    # 本进程是独立进程组的组长，与命令共组但不共享命令的输出管道。
    # 忽略宽限信号以保持栅栏，最终 SIGKILL 同时终止本进程与所有同组后代。
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    sys.stdout.write("ready\n")
    sys.stdout.flush()
    sys.stdout.close()
    try:
        sys.stdin.buffer.read(1)
    finally:
        os.killpg(os.getpgrp(), signal.SIGKILL)


if __name__ == "__main__":
    main()
