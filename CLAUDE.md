# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

bema-observerは、GrafanaとPrometheusを再現性高くデプロイするためのPodman Composeテンプレートプロジェクトです。
インフラストラクチャの監視スタックを簡単にセットアップ・デプロイできることを目的としています。

## Technology Stack

Primary stack: TypeScript, HTML, CSS, Markdown. When writing new code, default to TypeScript unless explicitly asked otherwise.

- **Container Runtime**: Podman
- **Orchestration**: `podman compose` (Podman built-in subcommand)
- **Monitoring**: Prometheus
- **Visualization**: Grafana
- **API Server**: Hono + Bun (TypeScript)
- **CI/CD**: GitHub Actions (Self-hosted runner)

## Project Structure

```
bema-observer/
├── docker-compose.yml          # Podman compose設定ファイル
├── api/
│   ├── index.ts               # Exporter管理API (Hono + Bun)
│   ├── package.json           # npm dependencies
│   ├── tsconfig.json          # TypeScript設定
│   └── Dockerfile             # APIサーバー用Dockerfile
├── prometheus/
│   ├── prometheus.yml         # Prometheus本体の設定
│   ├── alerts.yml             # アラートルール定義
│   ├── rules/                 # 追加のルールファイル
│   └── targets/               # 動的ターゲット定義（file_sd_configs）
│       ├── node-exporters.json
│       └── smart-exporters.json
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
podman compose up -d

# ログを確認
podman compose logs -f

# 特定のサービスのログを確認
podman compose logs -f prometheus
podman compose logs -f grafana

# コンテナの状態を確認
podman compose ps

# 設定変更後に再起動
podman compose restart

# スタックを停止
podman compose down

# ボリュームも含めて完全に削除
podman compose down -v
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
- Exporter管理API: http://localhost:5000

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
3. `podman compose up -d`で更新を適用
4. 必要に応じてヘルスチェック実行

### Self-hosted Runner設定時の注意

- Podmanと`podman compose`が利用できること
- 必要なポートが開放されていること
- 永続化データのバックアップ戦略を考慮すること

## Development Workflow

1. **設定変更**: `prometheus.yml`やダッシュボード定義を編集
2. **ローカルテスト**: `podman compose up -d`でローカル環境で動作確認
3. **設定検証**: promtoolで設定ファイルの構文チェック
4. **コミット**: 変更をコミットしてpush
5. **デプロイ**: GitHub Actionsが自動的にSelf-hosted runnerでデプロイ

## Exporter管理API

APIを使用して動的にNode ExporterやSMART Exporterを追加・削除できます。

### Node Exporter

```bash
# Node Exporterの一覧を取得
curl http://localhost:5000/node-exporters

# Node Exporterを追加
curl -X POST http://localhost:5000/node-exporter \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.10",
    "port": 9100,
    "host_type": "physical",
    "labels": {
      "environment": "production",
      "datacenter": "dc1"
    }
  }'

# Node Exporterを削除
curl -X DELETE http://localhost:5000/node-exporter \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.10", "port": 9100}'
```

### SMART Exporter

```bash
# SMART Exporterの一覧を取得
curl http://localhost:5000/smart-exporters

# SMART Exporterを追加
curl -X POST http://localhost:5000/smart-exporter \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.20",
    "port": 9633,
    "labels": {
      "environment": "production",
      "server": "storage-01"
    }
  }'

# SMART Exporterを削除
curl -X DELETE http://localhost:5000/smart-exporter \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.20", "port": 9633}'
```

**注意事項**:
- Node Exporterのデフォルトポートは9100
- SMART Exporterのデフォルトポートは9633
- ターゲットを追加・削除すると、自動的にPrometheusに設定リロードが指示される

## Tips

- Grafanaダッシュボードをエクスポートする際は「Export for sharing externally」オプションを使用してJSON化
- Prometheusのデータ保持期間は`--storage.tsdb.retention.time`で調整可能
- `podman compose`の代わりに`podman kube play`も検討できる（Kubernetes互換性向上）
