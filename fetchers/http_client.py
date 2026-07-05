"""
统一 HTTP 客户端:超时、重试、User-Agent、错误吞掉但记录。
设计原则:任何单个数据源失败,都不应该让整个扫描崩溃——
上层调用者应该拿到 None / 空结构,并在报告里标注"数据缺失",而不是抛异常中断。
"""
from __future__ import annotations
import time
import logging
import requests
from config import REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger("scanner.http")

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": USER_AGENT})


def get_json(url: str, params: dict | None = None, retries: int = 2, backoff: float = 1.5):
    """GET 请求并解析 JSON。失败返回 None(不抛异常),调用方需自行处理缺失数据。"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = _SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001 - 数据源多样,故意宽泛捕获
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    logger.warning("get_json 失败: %s params=%s err=%s", url, params, last_err)
    return None


def get_text(url: str, params: dict | None = None, retries: int = 2, backoff: float = 1.5):
    """GET 请求并返回原始文本(用于 CSV / RSS / HTML)。失败返回 None。"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = _SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    logger.warning("get_text 失败: %s params=%s err=%s", url, params, last_err)
    return None
