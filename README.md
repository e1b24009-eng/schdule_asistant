# schdule-asistant

Googleカレンダーの予定とGoogle ToDoリストのタスクを読み込み、ローカルAI（Ollama）で
「必要な作業・持ち物」を推測して、Discordに毎朝通知するプログラムです。

## 構成

```
Googleカレンダー / Google Tasks ─▶ Python ─▶ Ollama（ローカルAI） ─▶ Discord Webhook
```

## 準備

### 1. Python
Python 3.10以上を入れて、このフォルダで次を実行します。

```
python -m venv .venv
.venv\Scripts\activate          # コマンドプロンプト / PowerShell の場合
source .venv/Scripts/activate   # Git Bash の場合
pip install -r requirements.txt
```

以降の `python ...` は、毎回この仮想環境を有効にした状態（行頭に `(.venv)` と出る）で実行してください。
有効にし忘れると、パッケージが入っていない普通のPythonで動いて `No module named 'dotenv'` などのエラーになります。
有効にせずに動かしたいときは `.venv/Scripts/python src/main.py` のように仮想環境のPythonを直接指定します。

### 2. Google Cloud（カレンダーとタスクを読む許可）
1. https://console.cloud.google.com/ で新しいプロジェクトを作る
2. 「APIとサービス」→「ライブラリ」で **Google Calendar API** と **Google Tasks API** を有効にする
3. 「OAuth同意画面」を設定する（ユーザーの種類は「外部」、テストユーザーに自分のGmailを追加）
4. 「認証情報」→「認証情報を作成」→「OAuthクライアントID」→種類は **デスクトップアプリ**
5. JSONをダウンロードし、このフォルダに `credentials.json` という名前で置く

※ `credentials.json` と、初回ログイン後にできる `token.json` は `.gitignore` 済みです。

### 3. Discord Webhook
1. 通知したいチャンネルの「チャンネルの編集」→「連携サービス」→「ウェブフック」→「新しいウェブフック」
2. 「ウェブフックURLをコピー」
3. `.env.example` を `.env` にコピーし、`DISCORD_WEBHOOK_URL` に貼り付ける

### 4. Ollama（ローカルAI）
1. https://ollama.com/ からインストール
2. モデルをダウンロード

```
ollama pull qwen2.5:3b
```

日本語の予定タイトルを扱うので、日本語に強い Qwen2.5 を初期値にしています。
PCが重い場合は `qwen2.5:1.5b` に変えて、`.env` の `OLLAMA_MODEL` も合わせてください。

## 使い方

### 予定とタスクの取得を確認する
```
python src/google_data.py
```
初回はブラウザが開くので、Googleアカウントでログインして許可してください。
「このアプリはGoogleで確認されていません」と出たら「詳細」→「（安全ではないページ）に移動」で進めます（自分で作ったアプリなので問題ありません）。

### 準備リストを作ってDiscordに送る
Ollamaが起動している状態で（インストール後は自動で常駐します）実行します。

```
python src/main.py --dry-run   # 送らずに画面で内容を確認
python src/main.py             # Discordに送信
```

AIには予定を1件ずつ渡して、持ち物と作業だけをJSONで答えてもらっています。指示文は `src/advisor.py` の `PROMPT` です。

## 毎朝自動で送る（Windowsのタスクスケジューラ）

`run.bat` をダブルクリックしてDiscordに届けば準備OKです（結果やエラーは `run.log` に残ります）。

1. スタートメニューで「タスクスケジューラ」を開く
2. 右側の「基本タスクの作成」→ 名前は「準備リスト」など
3. トリガー：「毎日」で送りたい時刻（例：7:00）を指定する
   - PCを起動したときに送りたいなら「コンピューターの起動時」ではなく「ログオン時」を選ぶ
4. 操作：「プログラムの開始」→「参照」で `run.bat` を選ぶ
5. 作成後、タスクをダブルクリック →「条件」タブで「AC電源の場合のみ開始する」のチェックを外す
6. 「設定」タブで「スケジュールされた時刻にタスクを開始できなかった場合、すぐにタスクを実行する」にチェックを入れる
   （朝PCが閉じていても、開いたときに送られます）

Ollamaはインストールすると自動で常駐するので、別に起動する必要はありません。

## 持ち物の精度を上げるには

Googleカレンダーの予定の「説明」欄や、Google ToDoリストのタスクの「詳細」欄に、持ち物や作業を書いておくとAIがそれを読んで反映します。

例：予定「応用演習課題」の説明に `ノートPC、充電器、第3回のレポート提出` と書く

## 通知が届かないとき

- `ModuleNotFoundError: No module named 'dotenv'`（や `google`、`requests`）と出たら：仮想環境が有効になっていません。`source .venv/Scripts/activate`（Git Bash）を実行してからもう一度。`.venv` がまだ無ければ「1. Python」の手順で作って `pip install -r requirements.txt` してください
- まず `run.log` の最後を見る（`tail -20 run.log`）。各行の先頭に `2026-11-06 09:14:03 [ERROR]` のような日時が付いています。自動実行で失敗したときは、Discordにもエラー内容が届きます
- `localhost:11434` に接続できない（WinError 10061）と出たら：Ollamaが起動していません。プログラムは自動で `ollama serve` を起動して最大2分待ちますが、それでもだめならOllamaを手で起動してください
- `invalid_grant` / 「Googleのログインが切れた」と出たら：PCで `python src/main.py` を実行してブラウザから再ログインする
- 再ログインを7日ごとに求められないようにするには：Google Cloud の「Google Auth Platform」→「対象」で **アプリを公開**（本番環境）にする。
  「テスト中」のままだと、ログインの有効期限が7日で切れます
