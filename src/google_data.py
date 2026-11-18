"""Googleカレンダーの予定とGoogle Tasksのタスクを取得する。"""

import datetime as dt
import html
import re
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token.json"


class LoginRequired(Exception):
    """Googleへの再ログインが必要（ブラウザを開けない自動実行のときに使う）。"""


def get_credentials(allow_browser=True):
    """初回はブラウザでログインし、以降は token.json を使い回す。

    ログインの期限が切れていたら、allow_browser=True ならブラウザで再ログインし、
    False（タスクスケジューラからの自動実行）なら LoginRequired を投げる。
    """
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except RefreshError:
            pass  # 期限切れ・取り消し。下で再ログインする
    if not allow_browser:
        raise LoginRequired()
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def clean_description(text):
    """説明欄はHTMLになっていることがあるので、タグを外して普通の文章にする。"""
    text = re.sub(r"<br\s*/?>|</p>|</li>", "\n", text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:500]  # 長すぎるとAIが遅くなるので先頭だけ


def fetch_events(creds, start, end):
    """start〜end の間にある、全カレンダーの予定を時刻順に返す。"""
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    events = []
    for cal in service.calendarList().list().execute().get("items", []):
        result = service.events().list(
            calendarId=cal["id"],
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        for item in result.get("items", []):
            start_info = item["start"]
            events.append({
                "title": item.get("summary", "(タイトルなし)"),
                "start": start_info.get("dateTime", start_info.get("date")),
                "all_day": "date" in start_info,
                "location": item.get("location", ""),
                "description": clean_description(item.get("description", "")),
                "calendar": cal.get("summary", ""),
            })
    events.sort(key=lambda e: e["start"])
    return events


def fetch_tasks(creds, end):
    """未完了タスクのうち、期限が end までのもの（期限なしも含む）を返す。"""
    service = build("tasks", "v1", credentials=creds, cache_discovery=False)
    tasks = []
    for tasklist in service.tasklists().list().execute().get("items", []):
        result = service.tasks().list(tasklist=tasklist["id"], showCompleted=False).execute()
        for item in result.get("items", []):
            due = item.get("due")  # 例: 2026-10-27T00:00:00.000Z（日付のみ意味がある）
            if due and due[:10] >= end.date().isoformat():
                continue
            tasks.append({
                "title": item.get("title", ""),
                "due": due[:10] if due else None,
                "location": "",
                "description": clean_description(item.get("notes", "")),  # タスクの「詳細」欄
            })
    return tasks


def today_and_tomorrow():
    """ローカル時刻で、今日の0時〜明後日の0時を返す。"""
    now = dt.datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + dt.timedelta(days=2)


def one_week_later(start):
    """今日を含めて7日間の終わり（7日後の0時）を返す。"""
    return start + dt.timedelta(days=7)


if __name__ == "__main__":
    creds = get_credentials()
    start, _ = today_and_tomorrow()
    end = one_week_later(start)

    print("■ 予定（今日から7日間）")
    for e in fetch_events(creds, start, end):
        when = e["start"][:10] + " 終日" if e["all_day"] else e["start"][:16].replace("T", " ")
        place = f" @ {e['location']}" if e["location"] else ""
        print(f"  {when}  {e['title']}{place}")

    print("■ タスク（7日以内が期限・期限なし）")
    for t in fetch_tasks(creds, end):
        print(f"  [{t['due'] or '期限なし'}] {t['title']}")
