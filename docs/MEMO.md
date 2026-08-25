# 実装メモ

## 2026-08-25

[codex] Discord旅行ランダム通知を新規実装。Python標準ライブラリだけで予定生成、期限判定、Discord Webhook送信、JSON状態の原子更新を構成した。GitHub Actionsは5分ごとに起動し、concurrencyで直列化、Webhook成功後に1通知ごとの状態をcommit/push、全件完了後にworkflowを自動無効化する。

[codex] 依頼文の日別回数 `3 + 8 + 8 + 2` は21回で、記載された合計20回と矛盾する。根拠なく特定日を1回減らさず、具体的な日別指定を優先して21件の本番スケジュールを生成した。20回を優先する場合は、本番前に対象日の `count` を1つ減らして明示的に再生成する。

[codex] Discord Webhookは冪等性キーを提供しないため、Webhook成功直後からGit push成功前の強制終了時に限って二重送信の可能性が残る。通知欠落を避けるため、送信成功後にだけ状態を更新するat-least-once設計を採用した。

[codex] 完了時にPython構文確認、本番ファイル整合性検証、Secret形式の混入検査、pytestを実行。pytestは13件すべて成功した。
