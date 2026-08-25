# アーキテクチャ

## 概要

旅行中の固定済みランダム予定をGitHub Actionsが定期確認し、Discord Webhookへ送信する。実行時の外部Python依存はなく、Python 3.11以上の標準ライブラリだけを使う。

## コンポーネント

| 領域 | 主なファイル | 責務 |
|---|---|---|
| 本番設定 | `config/production.json` | タイムゾーン、対象日、時間帯、回数、スロット幅、最小間隔 |
| 通知文 | `config/discord_message.txt` | ロールメンションと回数表示のテンプレート |
| 固定予定 | `data/notification_schedule.json` | 事前に1度だけ生成した通知時刻と連番 |
| 永続状態 | `data/notification_state.json` | スケジュールハッシュと送信成功済みID |
| Python実装 | `src/trip_notify/` | 生成、検証、期限判定、Webhook送信、状態更新 |
| オーケストレーション | `.github/workflows/discord-notification.yml` | 5分定期、手動テスト、直列化、状態commit/push、完了後停止 |
| 分離テスト | `scripts/create_test_schedule.py`, `tmp/` | 現在からの相対時刻で本番と独立した確認 |

## 生成アルゴリズム

日ごとに5分単位の候補時刻を列挙し、動的計画法で「残りの候補から最小間隔を満たす選び方の数」を数える。その組合せ数に応じた重み付き抽選を行うため、単純なランダム再試行のような失敗回数依存がない。本番では `secrets.SystemRandom` を使う。

## 送信と状態遷移

1. スケジュールJSONと状態JSONを厳格に読み込む。
2. スケジュールのSHA-256と状態内のハッシュを比較する。
3. `scheduled_at <= now` かつ送信済みIDに含まれない先頭1件を選ぶ。
4. Webhookへ送信し、2xxの場合だけJSONを一時ファイル経由で原子的に置き換える。
5. Actionsがその1件分の状態をcommit/pushする。
6. 次の期限到来済みがあれば繰り返す。

Webhook送信成功とGit pushは分散トランザクションにできない。送信前に状態を更新すると通知欠落になるため、Webhook成功後に状態更新する `at-least-once` を採用する。

## 並列実行制御

GitHub Actionsの `concurrency.group` を固定し、`cancel-in-progress: false` で先行実行を中断せず後続を待機させる。リポジトリ外のWebhookとGit commit間の完全なexactly-onceは保証できないが、通常のActions並列実行による二重送信は防ぐ。

## シークレットとメンション

- `DISCORD_WEBHOOK_URL` と `DISCORD_ROLE_ID` はGitHub Actions Secretsから環境変数で渡す。
- Webhook URLの応答本文、URL、トークンはログに出力しない。
- Discordペイロードの `allowed_mentions.parse` は空配列とし、`roles` に1つのSecret値だけを設定する。
