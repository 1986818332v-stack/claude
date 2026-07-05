"""
持久化状态存取。

GitHub Actions 每次运行都是全新的容器,没有内存态。为了让 OI 背离这类
"需要对比上一次快照"的信号生效,我们把上一轮的关键数值写入
reports/state.json,并在工作流里把这个文件连同报告一起 commit 回仓库,
下一次运行时先读取它作为"上一轮"的基准。
"""
from __future__ import annotations
import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "reports", "state.json")


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
