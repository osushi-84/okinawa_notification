# 現在のタスク

## Discord旅行ランダム通知

- [x] 本番の日付・時間帯・回数を設定ファイル化
- [x] 5分単位・同日最小45分間隔のランダム予定生成を実装
- [x] 予定の1回限り生成とJSON保存を実装
- [x] 期限到来判定、Discord Webhook送信、成功時のみの状態保存を実装
- [x] `allowed_mentions`による1ロール限定メンションを実装
- [x] 5分定期実行、直列化、1通知ごとの状態push、完了後自動停止をGitHub Actionsへ実装
- [x] 本番と分離した相対時刻テスト用スケジュール生成を実装
- [x] セットアップ、手動テスト、障害確認、運用手順をREADMEへ記載
- [x] 単体テスを作成

## ユーザー側の次ステップ

- [ ] 日別回数の合計21回を採用するか、記載上の合計20回を優先して1日分を1回減らすか決定
- [ ] Discord Webhookと対象ロールを作成
- [ ] GitHub Actions Secrets `DISCORD_WEBHOOK_URL` / `DISCORD_ROLE_ID` を登録
- [ ] GitHub ActionsへRead and write permissionsを付与
- [ ] `validate` と `webhook_test` を手動実行
