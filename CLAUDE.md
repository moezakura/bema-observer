# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

bema-observerは、GrafanaとPrometheusを再現性高くデプロイするためのPodman Composeテンプレートプロジェクトです。
インフラストラクチャの監視スタックを簡単にセットアップ・デプロイできることを目的としています。

## Technology Stack

- **Container Runtime**: Podman
- **Orchestration**: podman-compose
- **Monitoring**: Prometheus
- **Visualization**: Grafana
- **API Server**: Hono + Bun (TypeScript)
- **CI/CD**: GitHub Actions (Self-hosted runner)

## Project Structure

```
bema-observer/
├── docker-compose.yml          # Podman compose設定ファイル
├── api/
│   ├── index.ts               # Node Exporter管理API (Hono + Bun)
│   ├── package.json           # npm dependencies
│   ├── tsconfig.json          # TypeScript設定
│   └── Dockerfile             # APIサーバー用Dockerfile
├── prometheus/
│   ├── prometheus.yml         # Prometheus本体の設定
│   ├── alerts.yml             # アラートルール定義
│   ├── rules/                 # 追加のルールファイル
│   └── targets/               # 動的ターゲット定義（file_sd_configs）
│       └── node-exporters.json
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/       # データソース自動プロビジョニング
│   │   └── dashboards/        # ダッシュボードプロビジョニング設定
│   └── dashboards/            # ダッシュボードJSON定義
├── .github/
│   └── workflows/
│       └── deploy.yml         # Self-hosted runnerによるデプロイワークフロー
└── volumes/                   # 永続化データ（gitignore推奨）
```

## Common Commands

### ローカル開発

```bash
# スタック全体を起動
podman-compose up -d

# ログを確認
podman-compose logs -f

# 特定のサービスのログを確認
podman-compose logs -f prometheus
podman-compose logs -f grafana

# コンテナの状態を確認
podman-compose ps

# 設定変更後に再起動
podman-compose restart

# スタックを停止
podman-compose down

# ボリュームも含めて完全に削除
podman-compose down -v
```

### 設定の検証

```bash
# Prometheusの設定ファイルを検証
podman run --rm -v ./prometheus:/etc/prometheus:ro \
  prom/prometheus:latest \
  promtool check config /etc/prometheus/prometheus.yml

# アラートルールを検証
podman run --rm -v ./prometheus:/etc/prometheus:ro \
  prom/prometheus:latest \
  promtool check rules /etc/prometheus/alerts.yml
```

### アクセス

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (デフォルト: admin/admin)
- Node Exporter API: http://localhost:5000

## Architecture Notes

### Podman Compose設定のポイント

1. **rootlessモード**: 可能な限りrootless Podmanで動作するよう設計
2. **ネットワーク**: 同一Composeファイル内のサービスは自動的に同じネットワークに配置され、サービス名で通信可能
3. **永続化**: ボリュームを使用してPrometheusのデータとGrafanaの設定を永続化

### Prometheus設定

- `scrape_configs`: 監視対象の定義
- `alerting`: Alertmanager連携設定（オプション）
- `rule_files`: アラートルールやレコーディングルールの読み込み

### Grafana Provisioning

Grafanaのプロビジョニング機能を活用して、データソースとダッシュボードを自動設定：
- `provisioning/datasources/`: Prometheusデータソースを自動登録
- `provisioning/dashboards/`: ダッシュボードの自動インポート設定
- `dashboards/`: 実際のダッシュボードJSON定義

## Deployment

GitHub Actions Self-hosted runnerを使用してデプロイを自動化。

### デプロイフロー

1. mainブランチへのpush/マージをトリガー
2. Self-hosted runnerが最新のコードをpull
3. `podman-compose up -d`で更新を適用
4. 必要に応じてヘルスチェック実行

### Self-hosted Runner設定時の注意

- Podmanとpodman-composeがインストールされていること
- 必要なポートが開放されていること
- 永続化データのバックアップ戦略を考慮すること

## Development Workflow

1. **設定変更**: `prometheus.yml`やダッシュボード定義を編集
2. **ローカルテスト**: `podman-compose up -d`でローカル環境で動作確認
3. **設定検証**: promtoolで設定ファイルの構文チェック
4. **コミット**: 変更をコミットしてpush
5. **デプロイ**: GitHub Actionsが自動的にSelf-hosted runnerでデプロイ

## Tips

- Grafanaダッシュボードをエクスポートする際は「Export for sharing externally」オプションを使用してJSON化
- Prometheusのデータ保持期間は`--storage.tsdb.retention.time`で調整可能
- podman-composeの代わりに`podman kube play`も検討できる（Kubernetes互換性向上）
