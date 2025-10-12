# bema-observer

GrafanaとPrometheusを使用した監視スタックのPodman Composeテンプレート

## 概要

このプロジェクトは、PrometheusとGrafanaを使用した監視スタックを、Podmanコンテナで簡単にデプロイできるようにしたものです。

## 使用バージョン

- **Prometheus**: v3.6.0 (2025年9月17日リリース)
- **Grafana**: 12.2.0 (2025年9月23日リリース)
- **API Server**: Hono + Bun (TypeScript)

## 必要な環境

- Podman
- podman-compose

## クイックスタート

### 1. スタックの起動

```bash
podman-compose up -d
```

### 2. アクセス

起動後、以下のURLからアクセスできます：

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
  - デフォルトユーザー: `admin`
  - デフォルトパスワード: `admin`
- **Exporter管理API**: http://localhost:5000

初回ログイン後、パスワードの変更を求められます。

### 3. Grafanaダッシュボード

Grafanaには自動的にPrometheusがデータソースとして登録されます。また、サンプルダッシュボード「Prometheus Overview」も自動的にインポートされます。

## プロジェクト構成

```
bema-observer/
├── docker-compose.yml          # Podman Compose設定
├── api/
│   ├── index.ts               # Exporter管理API (Hono + Bun)
│   ├── package.json           # npm依存関係
│   ├── tsconfig.json          # TypeScript設定
│   └── Dockerfile             # APIサーバー用Dockerfile
├── prometheus/
│   ├── prometheus.yml         # Prometheus設定
│   ├── alerts.yml             # アラートルール
│   ├── rules/                 # 追加ルール用ディレクトリ
│   └── targets/               # 動的ターゲット定義（file_sd_configs）
│       ├── node-exporters.json
│       └── smart-exporters.json
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/       # データソース設定
│   │   └── dashboards/        # ダッシュボード設定
│   └── dashboards/            # ダッシュボードJSON
└── README.md
```

## カスタマイズ

### Exporterの動的管理（API経由）

Exporter管理APIを使用して、HTTPリクエストで動的に監視対象（Node ExporterやSMART Exporter）を追加・削除できます。

#### APIエンドポイント

APIサーバーは`http://localhost:5000`で起動します。

#### Node Exporter

**Node Exporterを追加**

```bash
curl -X POST http://localhost:5000/node-exporter \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.100",
    "port": 9100,
    "host_type": "physical",
    "labels": {
      "instance": "server1"
    }
  }'
```

パラメータ：
- `ip` (必須): Node ExporterのIPアドレス
- `port` (オプション, デフォルト: 9100): Node Exporterのポート番号
- `host_type` (オプション, デフォルト: "physical"): ホストタイプ（"physical" または "virtual"）
- `labels` (オプション): 追加のPrometheusラベル

**登録されているNode Exporterの一覧を取得**

```bash
curl http://localhost:5000/node-exporters
```

**Node Exporterを削除**

```bash
curl -X DELETE http://localhost:5000/node-exporter \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.100",
    "port": 9100
  }'
```

**APIヘルスチェック**

```bash
curl http://localhost:5000/health
```

#### SMART Exporter

**SMART Exporterを追加**

```bash
curl -X POST http://localhost:5000/smart-exporter \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.200",
    "port": 9633,
    "labels": {
      "environment": "production",
      "server": "storage-01"
    }
  }'
```

パラメータ：
- `ip` (必須): SMART ExporterのIPアドレス
- `port` (オプション, デフォルト: 9633): SMART Exporterのポート番号
- `labels` (オプション): 追加のPrometheusラベル

**登録されているSMART Exporterの一覧を取得**

```bash
curl http://localhost:5000/smart-exporters
```

**SMART Exporterを削除**

```bash
curl -X DELETE http://localhost:5000/smart-exporter \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.200",
    "port": 9633
  }'
```

#### 仕組み

- APIサーバーは受け取ったIPアドレスとポートを`prometheus/targets/node-exporters.json`または`prometheus/targets/smart-exporters.json`に保存
- host_type（Node Exporterのみ）はPrometheusの`host_type`ラベルとして保存され、PromQLでのフィルタリングやGrafanaでの可視化に利用可能
- Prometheusは30秒ごとにこれらのファイルをチェックし、自動的に監視対象を更新
- APIサーバーがPrometheusに設定のリロードも指示するため、即座に反映されます

#### host_typeの活用例（Node Exporter）

host_typeを使用することで、Prometheusでのクエリが簡単になります：

```promql
# 物理サーバーのみのCPU使用率
node_cpu_seconds_total{host_type="physical"}

# 仮想サーバーのメモリ使用量
node_memory_MemAvailable_bytes{host_type="virtual"}

# 仮想サーバーのディスクI/O
node_disk_io_time_seconds_total{host_type="virtual"}

# ホストタイプごとのノード数
count by (host_type) (up)
```

#### SMART Exporterの活用例

SMART Exporterを使用することで、ディスクの健康状態を監視できます：

```promql
# SMART属性値の取得
smartctl_device_smart_status{device="/dev/sda"}

# ディスクの温度
smartctl_device_temperature

# ディスクエラー数
smartctl_device_error_log_count

# 電源投入時間
smartctl_device_power_on_seconds
```

### 監視対象の手動追加

`prometheus/prometheus.yml`の`scrape_configs`セクションに監視対象を手動で追加することもできます：

```yaml
scrape_configs:
  - job_name: 'myapp'
    static_configs:
      - targets: ['myapp:8080']
```

### アラートルールの追加

`prometheus/alerts.yml`にアラートルールを追加するか、`prometheus/rules/`ディレクトリに新しいルールファイルを作成します。

### Grafanaダッシュボードの追加

1. Grafana UIでダッシュボードを作成
2. 「Share」→「Export」→「Save to file」でJSONをエクスポート
3. `grafana/dashboards/`にJSONファイルを配置
4. `podman-compose restart grafana`で反映

## 便利なコマンド

```bash
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

## Prometheus設定の検証

設定ファイルを変更した後は、以下のコマンドで構文チェックができます：

```bash
# Prometheus設定ファイルの検証
podman run --rm -v ./prometheus:/etc/prometheus:ro \
  prom/prometheus:v3.6.0 \
  promtool check config /etc/prometheus/prometheus.yml

# アラートルールの検証
podman run --rm -v ./prometheus:/etc/prometheus:ro \
  prom/prometheus:v3.6.0 \
  promtool check rules /etc/prometheus/alerts.yml
```

## データの永続化

PrometheusとGrafanaのデータは、Podmanのボリューム機能を使用して永続化されます：

- `prometheus_data`: Prometheusの時系列データ
- `grafana_data`: Grafanaの設定とダッシュボード

ボリュームの管理：

```bash
# ボリューム一覧
podman volume ls

# ボリュームの詳細
podman volume inspect bema-observer_prometheus_data
podman volume inspect bema-observer_grafana_data
```

## トラブルシューティング

### コンテナが起動しない

```bash
# ログを確認
podman-compose logs

# 個別のサービスのログを確認
podman-compose logs prometheus
```

### 設定が反映されない

```bash
# サービスを再起動
podman-compose restart prometheus
podman-compose restart grafana

# または完全に再作成
podman-compose down
podman-compose up -d
```

### Grafanaにログインできない

デフォルトの認証情報：
- ユーザー名: `admin`
- パスワード: `admin`

それでもログインできない場合は、Grafanaコンテナを再作成してください：

```bash
podman-compose down grafana
podman-compose up -d grafana
```

## セキュリティに関する注意

本番環境で使用する場合は、以下を必ず変更してください：

1. Grafanaの管理者パスワード（`docker-compose.yml`の`GF_SECURITY_ADMIN_PASSWORD`）
2. 必要に応じてネットワークアクセス制限の設定
3. HTTPSの有効化（リバースプロキシ経由など）

## ライセンス

MIT

## 参考リンク

- [Prometheus公式ドキュメント](https://prometheus.io/docs/)
- [Grafana公式ドキュメント](https://grafana.com/docs/)
- [Podman公式ドキュメント](https://docs.podman.io/)
