# Discord旅行ランダム通知

2026年8月28日〜31日の旅行中、事前に1度だけ生成したランダム時刻にDiscordへ写真撮影通知を送ります。PCの常時起動は不要で、GitHub Actionsが約5分ごとに期限到来済みの通知を確認します。

## 重要：通知総数について

依頼の日別指定は `3 + 8 + 8 + 2 = 21回` で、別途記載された「合計20回」と算術上一致しません。2026年8月25日に日別指定を優先する **合計21回** で運用することを確定しました。生成済み本番スケジュールも21件です。

| 日付（JST） | 通知可能時間 | 回数 |
|---|---:|---:|
| 2026-08-28 | 17:00〜24:00 | 3 |
| 2026-08-29 | 07:00〜24:00 | 8 |
| 2026-08-30 | 07:00〜24:00 | 8 |
| 2026-08-31 | 07:00〜10:00 | 2 |

今後回数を変更する場合は、本番開始前に [`config/production.json`](config/production.json) の `count` を変更して「[スケジュールの作り直し](#スケジュールの作り直し)」を実行してください。

## 仕組み

1. [`config/production.json`](config/production.json) に対象日、時間帯、回数、5分単位、最小45分間隔を定義します。
2. 生成コマンドを1回だけ実行し、[`data/notification_schedule.json`](data/notification_schedule.json) へ固定します。定期実行中は再生成しません。
3. GitHub Actionsが約5分ごとに起動し、現在時刻以前で未送信の先頭1件を送信します。遅延してもスキップしません。
4. Discordが2xxを返した場合だけ [`data/notification_state.json`](data/notification_state.json) を更新し、1件ごとにcommit/pushします。失敗時は未送信のままで、次回以降に再試行します。
5. 期限到来済みが複数あれば、同じActions実行内で1件ごとに送信・pushを繰り返します。
6. 全件の送信成功後は、不要なActions消費を避けるためworkflow自身を自動で無効化します。

GitHub Actionsのcronは予定時刻どおりの起動を保証しません。そのため「予定時刻と完全一致したとき」ではなく「予定時刻を過ぎているか」で判定します。

## ファイル構成

```text
.
├─ .github/workflows/discord-notification.yml  # 5分定期・手動実行
├─ config/
│  ├─ production.json                     # 本番の日付・時間帯・回数
│  └─ discord_message.txt                 # 編集可能な通知文
├─ data/
│  ├─ notification_schedule.json          # 1回だけ生成した本番予定
│  └─ notification_state.json             # 成功済みIDの永続状態
├─ scripts/create_test_schedule.py            # 現在+5分などのテスト作成
├─ src/trip_notify/                           # Python実装
├─ tests/                                     # pytest
└─ README.md
```

## 送信状態をJSONとGit commitで保存する理由

GitHub Actionsの各実行は独立しており、ローカルディスクは次回に引き継がれません。Actions Cacheは永続データベースではなく削除される可能性があり、Artifactにも保持期限があります。そのため、小さなJSONをリポジトリのGit履歴に保存する方法を採用しています。

この方法は次の利点があります。

- GitHub以外のDBやサービスが不要
- Git履歴から送信成功の記録を確認・復元できる
- JSON破損、未知の通知ID、予定ファイルとのハッシュ不一致を即時にエラーにできる

### 二重送信について

workflowの `concurrency` により、定期実行と手動実行を同時に動かさず直列化します。さらに送信前に状態を読み、Discord成功後に1件ごとに即時pushします。

ただし、Discord WebhookとGitは別々のシステムで、両方をまとめて原子的に確定する機能もWebhookの冪等性キーもありません。「Discordは受信したが、直後にGitHub側が強制終了して状態をpushできなかった」というごく短い障害窓では、再送による重複が起こり得ます。本実装は通知の欠落を避ける `at-least-once`（少なくとも1回）送信を優先しています。

## 1. Discordの準備

### 写真撮影ロールを作る

1. Discordで対象サーバーを開き、サーバ名をクリックします。
2. 「サーバー設定」→「ロール」→「ロールを作成」を選びます。
3. 例えば「写真撮影メンバー」と命名し、参加者にそのロールを付与します。
4. 対象チャンネルの権限で、そのロールがチャンネルを閲覧できることを確認します。
5. メンションテスト中は必要に応じてロールの「このロールに対してメンションすることを許可する」を有効にします。

### DiscordロールIDを取得する

1. Discord左下の歯車「ユーザー設定」を開きます。
2. 「詳細設定」→「開発者モード」を有効にします。
3. 「サーバー設定」→「ロール」で対象ロールを右クリックし、「ロールIDをコピー」を選びます。
4. コピーした数字を後述の `DISCORD_ROLE_ID` として登録します。

### Discord Webhookを作る

1. 「サーバー設定」→「連携サービス」→「ウェブフック」を開きます。
2. 「新しいウェブフック」を押し、通知先のチャンネルを選びます。
3. 「ウェブフックURLをコピー」を押します。
4. URLはパスワード相当です。チャット、README、コード、issue、Actionsログに貼らないでください。漏れた場合はWebhookを削除して作り直します。

Webhookには対象チャンネルの「チャンネルを見る」と「メッセージを送信」が必要です。

## 2. GitHubリポジトリの準備

GitHub上でこのリポジトリを使う場合は、予定時刻を一般公開しないため **Privateリポジトリ** を推奨します。JSONの時刻を暗号化はしていないため、リポジトリの読み取り権限がある人は予定を見られます。

新規作成する場合は次の手順です。

1. GitHubにログインし、右上の `+` → `New repository` を開きます。
2. Repository nameを入力し、Visibilityは `Private` を選びます。
3. このローカルリポジトリが既にあるため、READMEや `.gitignore` の自動追加は選ばず作成します。
4. 表示される既存リポジトリ用の手順に従って、このコードをdefault branchへpushします。

## 3. GitHub Actions Secretsを登録する

必要なSecretは次の2つだけです。

| Secret名 | 値 | 注意 |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | DiscordでコピーしたWebhook URL | 絶対にGit管理しない |
| `DISCORD_ROLE_ID` | メンションするロールの数字ID | `@`や `<@&...>` ではなく数字だけ |

登録手順は次のとおりです。

1. GitHubでリポジトリを開きます。
2. `Settings` → `Secrets and variables` → `Actions` を開きます。
3. `New repository secret` を押します。
4. Nameに上記のSecret名、Secretに実際の値を入れ、`Add secret` で保存します。
5. 2つとも同じように登録します。

## 4. GitHub Actionsへ書き込み権限を付ける

送信状態のcommit/pushと、全件完了後のworkflow自動停止に権限が必要です。

1. `Settings` → `Actions` → `General` を開きます。
2. `Actions permissions` でActionsの実行を許可します。
3. 画面下部の `Workflow permissions` で `Read and write permissions` を選び、保存します。
4. default branchにブランチ保護ルールがある場合は、`github-actions[bot]` の状態ファイルpushが拒否されないようルールを調整します。シンプルに運用する場合は、旅行期間中だけdefault branchへのActionsによる直接pushを許可します。

## 5. 通知スケジュール

本リポジトリでは本番スケジュールをすでに1回生成済みです。普段は次の生成コマンドを実行しないでください。生成スクリプトは既存ファイルの上書きをデフォルトで拒否します。

新規に1度だけ生成するコマンドは次のとおりです。

```powershell
$env:PYTHONPATH = "src"
python -m trip_notify.generate_schedule
```

通常出力には件数と保存先だけを表示し、予定時刻は表示しません。生成時に予定も見る必要があるときだけ `--show` を付けます。

```powershell
python -m trip_notify.generate_schedule --show
```

この生成コマンドは既存ファイルがあるとエラーになり、予定を表示することもありません。生成済み予定を明示的にデバッグ表示する場合は、次を使います。

```powershell
python -m trip_notify.validate --show
```

### スケジュールの作り直し

**Discordへ本番通知を1件でも送った後には実行しないでください。** 本番開始前に日付や回数を変える場合だけ、`config/production.json` を編集して次を実行します。`--force` は送信状態も空に戻します。

```powershell
$env:PYTHONPATH = "src"
python -m trip_notify.generate_schedule --force
python -m trip_notify.validate
git add config/production.json data/notification_schedule.json data/notification_state.json
git commit -m "[manual] 本番通知スケジュールを再生成"
git push
```

## 6. GitHub Actionsを有効化する

1. GitHubのリポジトリで `Actions` タブを開きます。
2. 初回に有効化ボタンが表示された場合は、ボタンを押します。
3. 左側の `Discord旅行通知` を開きます。
4. 右側のメニューから `Enable workflow` が表示されている場合は押します。

workflowは最後の通知に成功するまで、日付をまたいでも約5分間隔で再試行します。全件成功すると自動で無効化します。

## 7. GitHub上で手動テストする

1. `Actions` → `Discord旅行通知` を開きます。
2. `Run workflow` を押し、default branchを選びます。
3. 次のいずれかのモードを選びます。

| モード | 動作 | Discord送信 | 本番状態更新 |
|---|---|---:|---:|
| `validate` | 設定、予定、状態、通知文を検証 | なし | なし |
| `webhook_test` | ロールメンション付きのテスト文を即時送信 | あり | なし |
| `process_due` | 本番の期限到来済み通知を実送信 | 対象があればあり | 成功時のみあり |

最初に `validate`、次に `webhook_test` を行ってください。`process_due` は本番予定を実際に処理するため、意味が分かる場合だけ選びます。

### 2026-08-25 23:00の1回限り定期実行テスト

5分定期起動からの自動送信を確認するため、23:00 JSTの1回限りテスト予定を `data/one_time_test_schedule.json` に保存しています。専用の `data/one_time_test_state.json` で送信済みを管理するため、本番21回の予定と状態には影響しません。23:00にActionsが起動しなかった場合でも、次回以降の起動時に未送信であれば送信します。

## 8. ローカルでのテスト

Python 3.11以上を使います。本番送信に外部ライブラリは不要です。単体テストにだけpytestを使います。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"
pytest
python -m trip_notify.validate
```

`trip_notify.validate` は通知時刻一覧を出力しません。

### 現在から5分後、10分後のテスト

本番ファイルと混ざらないよう、テスト予定はGit管理外の `tmp/` へ作ります。

```powershell
$env:PYTHONPATH = "src"
python scripts/create_test_schedule.py --minutes 5 10
```

時刻も見てデバッグする場合だけ `--show` を追加します。すぐに判定を確認したい場合は `--minutes 0 5` も使えます。

送信対象件数だけ確認するdry-runは次のとおりです。

```powershell
python -m trip_notify.send_due `
  --schedule tmp/test_notification_schedule.json `
  --state tmp/test_notification_state.json `
  --dry-run
```

実際にDiscordへ送る場合は、テスト用予定時刻を過ぎた後に、ローカルターミナルだけで環境変数を設定します。値をコードやファイルへ書かないでください。

```powershell
$env:DISCORD_WEBHOOK_URL = "Discordの実際のWebhook URL"
$env:DISCORD_ROLE_ID = "実際のロールID"
python -m trip_notify.send_due `
  --schedule tmp/test_notification_schedule.json `
  --state tmp/test_notification_state.json `
  --max-notifications 1
Remove-Item Env:DISCORD_WEBHOOK_URL
Remove-Item Env:DISCORD_ROLE_ID
```

同じテストを作り直す場合は `python scripts/create_test_schedule.py --minutes 5 10 --force` を使います。`tmp/` は `.gitignore` の対象です。

## 通知文を変える

[`config/discord_message.txt`](config/discord_message.txt) を編集します。使える変数は次のとおりです。

- `{role_mention}`：許可した1ロールのメンション（必須）
- `{overall_index}` / `{overall_total}`：全体の何回目 / 総数
- `{daily_index}` / `{daily_total}`：その日の何回目 / 日内総数
- `{notification_id}`：デバッグ用の通知ID

未対応の変数、壊れた波括弧、2000文字超過は送信前にエラーになります。

Discordへは次の `allowed_mentions` 相当を必ず付けます。そのため、通知文に誤って `@everyone`、別ロール、ユーザーメンションを書いても通知は発生しません。

```json
{
  "parse": [],
  "roles": ["DISCORD_ROLE_IDの値だけ"],
  "users": [],
  "replied_user": false
}
```

## 本番開始前チェックリスト

- [x] 日別指定を優先し、合計21回で運用すると決めた
- [ ] GitHubリポジトリがPrivateになっている
- [ ] `DISCORD_WEBHOOK_URL` と `DISCORD_ROLE_ID` をActions Secretsへ登録した
- [ ] Actionsの `Workflow permissions` をRead and writeにした
- [ ] `validate` の手動実行が緑色のチェックで終わった
- [ ] `webhook_test` で正しいチャンネルに届いた
- [ ] テスト通知で対象ロールだけに通知が届いた
- [ ] 通知文、回数表示、ロール名が期待どおりだった
- [ ] Actionsの定期実行が有効である
- [ ] default branchの保護がActionsによる状態pushを妨げない
- [ ] Webhook URLがGit管理ファイルやログに入っていない

## 実行履歴と失敗の確認

### 実行履歴

1. GitHubの `Actions` タブを開きます。
2. 左側の `Discord旅行通知` を選びます。
3. 各実行を開くと、設定検証、通知判定、状態pushの成否を確認できます。

予定時刻とWebhook URLは通常ログに出しません。送信時は「全体の何回目」と「今日の何回目」だけが表示されます。

### Discord通知が失敗した場合

Actionsが赤いバツで終わったら、実行を開き、失敗したstepのエラー種別を確認します。Secretの値自体は出力しません。

- `DISCORD_WEBHOOK_URLが設定されていません`：Secret名と登録先がActions用かを確認
- `DISCORD_ROLE_ID...`：数字だけを登録したか確認
- `HTTP 401` / `HTTP 404`：Webhook URLが間違い、削除済み、または再生成済みでないか確認
- `HTTP 403`：Webhookとチャンネルの権限を確認
- `HTTP 429`：Discordのレート制限。状態は未送信のままで次回に再試行
- `pushできません`：ActionsのRead and write権限とdefault branchの保護ルールを確認
- JSON破損・ハッシュ不一致：手作業で `data/` を編集していないか確認し、Git履歴の直前の正常な状態と比較

Discord送信に失敗した通知は送信済みにならず、workflowが有効な限り次回以降も何日遅れでも再試行されます。修正後すぐ試す場合は `process_due` を手動実行します。

## セキュリティと運用上の注意

- Webhook URLは常にGitHub Actions Secretか一時的なローカル環境変数から読みます。
- Discordのエラー応答本文やリクエストURLをログに出しません。
- `allowed_mentions.parse` は空で、Secretで指定した1ロールだけを許可します。
- `data/notification_state.json` を手で書き換えないでください。送信済み記録を消すと再送されます。
- 本番期間中に `notification_schedule.json` を編集すると、ハッシュ不一致で安全に停止します。
- 旅行後はActionsのworkflowが無効になっていることと、状態が全件送信済みであることを確認してください。

## 公式仕様の参照先

- [GitHub Actionsのworkflow構文](https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub Actionsの並列実行制御](https://docs.github.com/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- [GitHub Actions workflowの無効化と有効化](https://docs.github.com/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)
- [Discord Webhook API](https://docs.discord.com/developers/resources/webhook)
- [Discord Allowed Mentions](https://docs.discord.com/developers/resources/message#allowed-mentions-object)
