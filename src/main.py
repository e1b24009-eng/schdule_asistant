"""今日・明日の予定から必要な準備を考えて、Discordに通知する。

使い方:
    python src/main.py            # Discordに送る
    python src/main.py --dry-run  # 送らずに画面に表示するだけ
    python src/main.py --scheduled  # タスクスケジューラ用（失敗したらDiscordに知らせる）
"""

import argparse
import datetime as dt
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from advisor import build_message
from google_data import LoginRequired, fetch_events, fetch_tasks, get_credentials, one_week_later, today_and_tomorrow
from notify import send_to_discord

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# run.log でいつの出来事か分かるように、各行の先頭に日時を付ける
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("main")


def main():
    parser = argparse.ArgumentParser(description="今日・明日と1週間分の準備リストをDiscordに送る")
    parser.add_argument("--dry-run", action="store_true", help="送らずに画面に表示するだけ")
    parser.add_argument("--scheduled", action="store_true",
                        help="自動実行用。ブラウザを開かず、失敗したらその内容をDiscordに送る")
    args = parser.parse_args()  # 打ち間違えたオプションはここでエラーになる

    if not args.dry_run and not os.environ.get("DISCORD_WEBHOOK_URL"):
        raise SystemExit(".env に DISCORD_WEBHOOK_URL がありません。README の「Discord Webhook」を参照してください。")

    log.info("--- 実行開始 ---")

    if not args.scheduled:
        run(args)
        return

    # 自動実行では画面を誰も見ていないので、失敗したらDiscordで知らせる
    try:
        run(args)
    except LoginRequired:
        log.error("Googleのログインが切れています。python src/main.py を実行して再ログインしてください")
        send_to_discord("⚠️ Googleのログインが切れたため、準備リストを作れませんでした。\n"
                        "PCで `python src/main.py` を実行して、ブラウザから再ログインしてください。")
        sys.exit(1)
    except Exception as error:
        log.exception("エラーで終了しました")  # 日時の行のあとに詳しいエラー内容が続く
        send_to_discord(f"⚠️ 準備リストの作成中にエラーが起きました：{type(error).__name__}: {error}\n"
                        "詳しくは run.log を確認してください。")
        sys.exit(1)
    log.info("--- 正常終了 ---")


def run(args):
    creds = get_credentials(allow_browser=not args.scheduled)
    start, soon_end = today_and_tomorrow()
    week_end = one_week_later(start)
    events = fetch_events(creds, start, week_end)
    tasks = fetch_tasks(creds, week_end)

    # 今日・明日の分と、その先（明後日から7日目まで）の分に分ける
    soon = soon_end.date().isoformat()
    soon_events = [e for e in events if e["start"][:10] < soon]
    week_events = [e for e in events if e["start"][:10] >= soon]

    today = dt.date.today()
    header = f"📅 {today.month}/{today.day} の準備リスト\n\n"
    message = header + build_message(soon_events, week_events, tasks)

    if args.dry_run:
        print(message)
    else:
        send_to_discord(message)
        log.info("Discordに送信しました")


if __name__ == "__main__":
    main()
