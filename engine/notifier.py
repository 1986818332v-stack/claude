"""
可选的即时推送。默认不启用——只有在 GitHub 仓库的 Settings > Secrets 里配置了
对应的环境变量,推送才会生效;否则静默跳过,只依赖 reports/ 目录里的报告文件。
"""
from __future__ import annotations
import os
import requests

from config import TELEGRAM_BOT_TOKEN_ENV, TELEGRAM_CHAT_ID_ENV, DISCORD_WEBHOOK_URL_ENV


def send_telegram(text: str) -> bool:
    token = os.environ.get(TELEGRAM_BOT_TOKEN_ENV)
    chat_id = os.environ.get(TELEGRAM_CHAT_ID_ENV)
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "Markdown"},
            timeout=15,
        )
        return resp.ok
    except requests.RequestException:
        return False


def send_discord(text: str) -> bool:
    webhook = os.environ.get(DISCORD_WEBHOOK_URL_ENV)
    if not webhook:
        return False
    try:
        resp = requests.post(webhook, json={"content": text[:2000]}, timeout=15)
        return resp.ok
    except requests.RequestException:
        return False


def notify_all(text: str) -> dict:
    return {
        "telegram_sent": send_telegram(text),
        "discord_sent": send_discord(text),
    }
