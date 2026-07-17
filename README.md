# IrucaOrca Updates

IrucaOrcaアプリ向けの静的なお知らせフィードです。GitHub Pagesで公開し、8keyは次の固定URLを参照します。

`https://updates.irucaorca.com/8key/v1/announcements.json`

## お知らせの追加・更新

1. `public/8key/v1/announcements.json`を編集します。
2. `python3 scripts/validate_announcements.py`を実行します。
3. Pull Requestを作成します。検証に成功した変更だけを`main`へマージします。
4. `main`へのマージ後、GitHub ActionsがGitHub Pagesへ自動配信します。

本文はプレーンテキスト専用です。リンク、Markdown、HTML、画像は配信しません。日時はUTCのRFC 3339形式（例: `2026-07-17T10:00:00Z`）で記述します。

同じ`id`の本文を更新しても、8keyでは既読状態を維持します。更新を新着として再通知する場合は、新しい`id`で別のお知らせを追加してください。`revision`は同じ`id`を更新するたびに増やします。一度使った`id`は再利用しません。

掲載開始前の項目も公開JSONから閲覧できます。公開前の機密情報や秘密情報は、このリポジトリへコミットしないでください。

## 初回セットアップ

- Repository Settings > Pages > Build and deploymentで`GitHub Actions`を選択します。
- PagesのCustom domainに`updates.irucaorca.com`を設定し、HTTPSを強制します。
- DNSで`updates.irucaorca.com`を`bigroomfujita.github.io`へCNAME設定します。
- GitHubのドメイン検証用TXTレコードを設定します。
- `main`を保護し、Pull Requestと`Validate announcement feed`の成功を必須にします。

GitHub Pagesへのアクセス時、GitHubはセキュリティ目的でアクセス元IPアドレスを記録・保存します。8keyのプライバシーポリシーとApp Store申告は、この通信を含む内容に保ちます。
