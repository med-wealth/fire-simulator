# FIRE Simulator — Medwealth Lab Tokyo

Human Capital Safety Valve 論文準拠 + GAS版機能完全移植

---

## ファイル構成

```
fire_simulator_streamlit/
├── app.py              ← メインアプリ（これを起動する）
├── simulation.py       ← シミュレーションエンジン（論文準拠）
├── requirements.txt    ← 必要パッケージ
├── .streamlit/
│   ├── config.toml     ← テーマ設定
│   └── secrets.toml    ← パスワード管理（GitHubに上げないこと！）
└── README.md
```

---

## GitHubへのアップロード手順

### Step 1：リポジトリを作成
1. https://github.com にログイン
2. 右上の「+」→「New repository」
3. Repository name: `fire-simulator`
4. **Private**を選択（コードを非公開にする場合）
5. 「Create repository」をクリック

### Step 2：ファイルをアップロード
1. 作成したリポジトリのページで「uploading an existing file」をクリック
2. 以下のファイルをドラッグ&ドロップ：
   - `app.py`
   - `simulation.py`
   - `requirements.txt`
3. **⚠️ `.streamlit/secrets.toml` はアップロードしないこと**
4. 「Commit changes」をクリック

### Step 3：.streamlit/config.toml のアップロード
1. 「Add file」→「Upload files」
2. `.streamlit/config.toml` のみアップロード
3. Commit

---

## Streamlit Community Cloud デプロイ手順

### Step 1：アカウント作成
1. https://share.streamlit.io にアクセス
2. 「Sign up」→ GitHubアカウントでログイン

### Step 2：アプリをデプロイ
1. 「New app」をクリック
2. Repository: `あなたのGitHubユーザー名/fire-simulator`
3. Branch: `main`
4. Main file path: `app.py`
5. 「Advanced settings」をクリック

### Step 3：Secretsを設定（重要）
「Advanced settings」の「Secrets」欄に以下を貼り付け：

```toml
PAID_PASSWORD = "0216"
```

※ここでパスワードを変更することもできます

6. 「Deploy!」をクリック

### Step 4：公開URL確認
数分後に `https://あなたのアプリ名.streamlit.app` という形でURLが発行されます。

---

## ローカルで動かす場合

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## パスワードの変更方法

Streamlit Cloud の管理画面 → アプリの「Settings」→「Secrets」で
`PAID_PASSWORD = "新しいパスワード"` に変更するだけです。

---

## 機能一覧

| 機能 | 無料版 | 有料版 |
|---|---|---|
| 基本FIREシミュレーション | ✅ | ✅ |
| FIRE到達年齢 | ✅ | ✅ |
| 人的資本セーフティバルブ | ✅ | ✅ |
| パーセンタイル帯グラフ | ✅ | ✅ |
| 推奨シナリオ閲覧 | ✅ | ✅ |
| 軌跡分析 | ✅ | ✅ |
| 教育費PV表示 | — | ✅ |
| 年齢別資産テーブル | — | ✅ |
| 取り崩し率別成功率グラフ | — | ✅ |
| MC試行回数変更（最大1,000） | — | ✅ |
| 月間投資額・生活防衛資金表示 | — | ✅ |
