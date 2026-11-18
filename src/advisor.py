"""予定やタスクごとにローカルAI（Ollama）に聞いて、必要な持ち物・作業を考えてもらう。"""

import json
import logging
import os
import shutil
import subprocess
import time

import requests

log = logging.getLogger(__name__)

PROMPT = """次の予定（またはタスク）のために、必要な持ち物と、事前にやっておくべき作業を考えてください。
説明があれば、そこに書かれている持ち物や作業を必ず含めてください。
それ以外は、タイトルと説明から自然に推測できるものだけを挙げてください。
それぞれ0〜4個、短い日本語で挙げ、準備が要らなければ空のリストにしてください。

予定：{title}{place}{description}

次のJSON形式だけで答えてください。
{{"持ち物": ["..."], "作業": ["..."]}}"""


def ollama_host():
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def ollama_is_running():
    try:
        requests.get(f"{ollama_host()}/api/tags", timeout=5).raise_for_status()
        return True
    except requests.RequestException:
        return False


def ensure_ollama(wait_seconds=120):
    """Ollamaが動いていなければ起動して、応答するまで待つ。

    PCの起動・ログオン直後の自動実行では、Ollamaの常駐がまだ立ち上がっておらず
    「接続が拒否されました」(WinError 10061) になることがあるため。
    """
    if ollama_is_running():
        return
    log.info("Ollamaが起動していないので起動します")
    exe = shutil.which("ollama") or os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if os.path.exists(exe):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windowsで黒い画面を出さない
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags)
    else:
        log.warning("ollama.exe が見つかりません。起動するのを待ちます")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(3)
        if ollama_is_running():
            log.info("Ollamaの起動を確認しました")
            return
    raise RuntimeError(f"Ollama（{ollama_host()}）に{wait_seconds}秒待っても接続できませんでした。"
                       "Ollamaがインストール・起動されているか確認してください。")


def ask_ollama(prompt):
    host = ollama_host()
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    response = requests.post(
        f"{host}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # JSONで答えるように強制する
            "options": {"temperature": 0, "seed": 42},  # 毎回同じ答えになるように固定
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["response"]


def advise_event(event):
    """1件の予定（またはタスク）について {"持ち物": [...], "作業": [...]} を返す。"""
    place = f"（場所：{event['location']}）" if event["location"] else ""
    description = f"\n説明：{event['description']}" if event.get("description") else ""
    raw = ask_ollama(PROMPT.format(title=event["title"], place=place, description=description))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    result = {}
    for key in ("持ち物", "作業"):
        items = data.get(key) or []
        if isinstance(items, str):
            items = [items]
        result[key] = [str(x).strip() for x in items if str(x).strip()]
    return result


def format_when(event):
    if event["all_day"]:
        return event["start"][5:10].replace("-", "/") + " 終日"
    return event["start"][5:16].replace("-", "/").replace("T", " ")


def format_due(task):
    return f"（期限：{task['due'][5:].replace('-', '/')}）" if task["due"] else ""


def build_message(soon_events, week_events, tasks):
    """今日・明日の予定と準備、やること、1週間の予定（明後日から7日目まで）の順にまとめる。"""
    ensure_ollama()
    lines = []
    if soon_events:
        lines.append("**■ 予定と準備**")
        for e in soon_events:
            advice = advise_event(e)
            lines.append(f"【{format_when(e)}】{e['title']}")
            lines.append("・持ち物：" + ("、".join(advice["持ち物"]) or "特になし"))
            lines.append("・作業：" + ("、".join(advice["作業"]) or "特になし"))
    else:
        lines.append("今日と明日の予定はありません。")

    lines.append("")
    lines.append("**■ やること**")
    for t in tasks:
        advice = advise_event(t)
        needs = advice["持ち物"] + advice["作業"]
        lines.append(f"・{t['title']}{format_due(t)}" + ("：" + "、".join(needs) if needs else ""))

    # 1週間の予定は、なければ見出しだけにする
    lines.append("")
    lines.append("**■ 1週間の予定**")
    for e in week_events:
        advice = advise_event(e)
        needs = advice["持ち物"] + advice["作業"]
        lines.append(f"・【{format_when(e)}】{e['title']}" + ("：" + "、".join(needs) if needs else ""))
    return "\n".join(lines).strip()
