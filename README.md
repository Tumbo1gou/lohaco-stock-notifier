# LOHACO 在庫入荷通知ツール

LOHACOの商品が在庫切れから入荷に変わった瞬間に、メールで通知するツールです。  
**GitHub Actions** で30分ごとに自動実行されます。サーバー不要・完全無料。

---

## セットアップ手順

### 1. GitHubリポジトリを作成する

1. [GitHub](https://github.com) にログインし、**New repository** をクリック
2. リポジトリ名を入力（例: `lohaco-stock-notifier`）
3. **Public を選択**（GitHub Actions を無料・無制限で使うために必要）
4. **Create repository** をクリック

> **Public リポジトリにしても安全な理由:**  
> メールアドレス等の個人情報はすべて GitHub Secret で管理しており、`products.json` には LOHACO の商品URL（公開情報）しか含まれていません。

### 2. このフォルダをGitHubにアップロードする

```bash
cd このフォルダのパス
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/あなたのユーザー名/lohaco-stock-notifier.git
git push -u origin main
```

### 3. Gmailのアプリパスワードを取得する

通常のGmailパスワードは使えません。**アプリパスワード**が必要です。

1. Googleアカウントの [セキュリティ設定](https://myaccount.google.com/security) を開く
2. **2段階認証** を有効にする（未設定の場合）
3. 検索バーで「アプリパスワード」と検索 → 「アプリパスワード」を開く
4. アプリ名に「LOHACO通知」と入力 → **作成**
5. 表示された **16桁のパスワード** をメモする（スペースなし）

### 4. GitHubにシークレットを登録する

GitHubリポジトリの **Settings → Secrets and variables → Actions → New repository secret** で以下を登録：

| シークレット名 | 値 |
|---|---|
| `SMTP_USER` | 送信元のGmailアドレス（例: `yourname@gmail.com`） |
| `SMTP_PASSWORD` | 手順3で取得した16桁のアプリパスワード |
| `NOTIFY_EMAIL` | 通知を受け取るメールアドレス |

### 5. 監視する商品を設定する

`products.json` を編集します：

```json
{
  "products": [
    {
      "url": "https://lohaco.yahoo.co.jp/store/h-lohaco/item/ew96848/",
      "name": "商品名（省略可）"
    },
    {
      "url": "https://lohaco.yahoo.co.jp/store/h-lohaco/item/XXXXX/",
      "name": "追加したい商品名"
    }
  ]
}
```

> **注意:** メールアドレスは `products.json` に書かないでください。  
> リポジトリにコミットされるファイルに個人情報を書くのはセキュリティリスクです。  
> 通知先メールアドレスは手順4の `NOTIFY_EMAIL` シークレットだけで設定してください。

- `name` は省略可能です（省略するとページから自動取得）
- 商品は何件でも追加できます

編集後、GitHubにpushすれば自動的に反映されます：

```bash
git add products.json
git commit -m "add product"
git push
```

---

## 動作の仕組み

```
GitHub Actions (30分ごと)
        ↓
checker.py 実行
        ↓
products.json の各URLにアクセス
        ↓
「在庫切れ」テキストの有無を確認
        ↓
前回が「在庫なし」→ 今回「在庫あり」 に変化したとき
        ↓
Gmail でメール通知送信
        ↓
stock_status.json を更新・コミット
```

---

## よくある質問

**Q: 通知が来ない**  
→ GitHub Actions の **Actions タブ** でログを確認してください。  
→ Gmailの迷惑メールフォルダを確認してください。  
→ アプリパスワードが正しいか確認してください（スペースを除いて16文字）。

**Q: 手動で今すぐチェックしたい**  
→ GitHub の Actions タブ → 「LOHACO 在庫チェック」→ **Run workflow** ボタン。

**Q: チェック間隔を変えたい**  
→ `.github/workflows/stock_check.yml` の `cron` を変更してください。  
→ 例: `*/15 * * * *` = 15分ごと / `0 * * * *` = 1時間ごと

**Q: GitHub Actionsの費用は？**  
→ パブリックリポジトリ（本ツールの推奨設定）：**完全無料・無制限**  
→ プライベートリポジトリで5分間隔にした場合：月約18,000円かかるため非推奨
