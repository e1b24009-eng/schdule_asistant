"""Discordのウェブフックにメッセージを送る。"""

import os

import requests

DISCORD_LIMIT = 2000  # Discordの1メッセージあたりの最大文字数


def send_to_discord(text):
    url = os.environ["DISCORD_WEBHOOK_URL"]
    # 長いときは改行の位置で分けて、複数のメッセージとして送る
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > DISCORD_LIMIT:
            chunks.append(current)
            current = ""
        current += line[:DISCORD_LIMIT]
    if current:
        chunks.append(current)
    for chunk in chunks:
        requests.post(url, json={"content": chunk}, timeout=30).raise_for_status()
