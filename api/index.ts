/**
 * Exporter管理API
 * Prometheusの監視対象にnode-exporterやsmart-exporterを動的に追加するAPIサーバー
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { readFile, writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { dirname } from 'path';

const app = new Hono();

// ミドルウェア
app.use('*', logger());
app.use('*', cors());

// 設定
const NODE_TARGETS_FILE = process.env.NODE_TARGETS_FILE || process.env.TARGETS_FILE || '/etc/prometheus/targets/node-exporters.json';
const SMART_TARGETS_FILE = process.env.SMART_TARGETS_FILE || '/etc/prometheus/targets/smart-exporters.json';
const PROMETHEUS_URL = process.env.PROMETHEUS_URL || 'http://prometheus:9090';

// 型定義
interface TargetGroup {
  targets: string[];
  labels: Record<string, string>;
}

interface NodeExporterRequest {
  ip: string;
  port?: number;
  host_type?: 'physical' | 'virtual';
  labels?: Record<string, string>;
}

interface NodeExporterDeleteRequest {
  ip: string;
  port?: number;
}

interface SmartExporterRequest {
  ip: string;
  port?: number;
  labels?: Record<string, string>;
}

interface SmartExporterDeleteRequest {
  ip: string;
  port?: number;
}

// ユーティリティ関数
async function loadTargets(targetsFile: string): Promise<TargetGroup[]> {
  try {
    if (!existsSync(targetsFile)) {
      return [];
    }

    const data = await readFile(targetsFile, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('Failed to load targets file:', error);
    return [];
  }
}

async function saveTargets(targetsFile: string, targets: TargetGroup[]): Promise<boolean> {
  try {
    const dir = dirname(targetsFile);
    if (!existsSync(dir)) {
      await mkdir(dir, { recursive: true });
    }

    await writeFile(targetsFile, JSON.stringify(targets, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error('Failed to save targets file:', error);
    return false;
  }
}

async function reloadPrometheus(): Promise<boolean> {
  try {
    const response = await fetch(`${PROMETHEUS_URL}/-/reload`, {
      method: 'POST',
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      console.warn(`Prometheus reload failed: ${response.status}`);
      return false;
    }

    return true;
  } catch (error) {
    console.warn('Failed to reload Prometheus:', error);
    return false;
  }
}

function validateIP(ip: string): boolean {
  // IPv4の簡易バリデーション
  const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/;
  if (!ipv4Regex.test(ip)) {
    return false;
  }

  const parts = ip.split('.');
  return parts.every(part => {
    const num = parseInt(part, 10);
    return num >= 0 && num <= 255;
  });
}

function validatePort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

// ルート定義
app.get('/health', (c) => {
  return c.json({
    status: 'healthy',
    service: 'node-exporter-api',
  });
});

app.get('/node-exporters', async (c) => {
  const targets = await loadTargets(NODE_TARGETS_FILE);

  const exporters = [];
  for (const targetGroup of targets) {
    const labels = targetGroup.labels || {};
    const host_type = labels.host_type || 'physical';

    for (const target of targetGroup.targets) {
      // labelsからhost_typeを除外したコピーを作成
      const { host_type: _, ...labelsWithoutHostType } = labels;

      exporters.push({
        target,
        host_type,
        labels: labelsWithoutHostType,
      });
    }
  }

  return c.json({
    count: exporters.length,
    exporters,
  });
});

app.post('/node-exporter', async (c) => {
  const body = await c.req.json<NodeExporterRequest>();

  // 必須パラメータのチェック
  const { ip } = body;
  const port = body.port || 9100;
  const host_type = body.host_type || 'physical';

  if (!ip) {
    return c.json({ error: 'IP address is required' }, 400);
  }

  // バリデーション
  if (!validateIP(ip)) {
    return c.json({ error: 'Invalid IP address' }, 400);
  }

  if (!validatePort(port)) {
    return c.json({ error: 'Invalid port number (1-65535)' }, 400);
  }

  if (host_type !== 'physical' && host_type !== 'virtual') {
    return c.json({ error: 'host_type must be "physical" or "virtual"' }, 400);
  }

  // ラベルの取得（オプション）
  const labels: Record<string, string> = body.labels || {};
  if (!labels.instance) {
    labels.instance = ip;
  }

  // host_typeをラベルに追加
  labels.host_type = host_type;

  // ターゲット文字列を作成
  const target = `${ip}:${port}`;

  // 既存のターゲットを読み込み
  const targets = await loadTargets(NODE_TARGETS_FILE);

  // 既に存在するかチェック
  for (const targetGroup of targets) {
    if (targetGroup.targets.includes(target)) {
      return c.json(
        {
          error: 'Target already exists',
          target,
        },
        409
      );
    }
  }

  // 新しいターゲットグループを追加
  targets.push({
    targets: [target],
    labels,
  });

  // 保存
  if (!(await saveTargets(NODE_TARGETS_FILE, targets))) {
    return c.json({ error: 'Failed to save targets' }, 500);
  }

  // Prometheusに設定リロードを指示
  await reloadPrometheus();

  return c.json(
    {
      message: 'Node exporter added successfully',
      target,
      host_type,
      labels,
    },
    201
  );
});

app.delete('/node-exporter', async (c) => {
  const body = await c.req.json<NodeExporterDeleteRequest>();

  const { ip } = body;
  const port = body.port || 9100;

  if (!ip) {
    return c.json({ error: 'IP address is required' }, 400);
  }

  const target = `${ip}:${port}`;

  // 既存のターゲットを読み込み
  const targets = await loadTargets(NODE_TARGETS_FILE);

  // ターゲットを検索して削除
  let found = false;
  const newTargets: TargetGroup[] = [];

  for (const targetGroup of targets) {
    if (targetGroup.targets.includes(target)) {
      found = true;
      // ターゲットを削除
      const filteredTargets = targetGroup.targets.filter(t => t !== target);
      // ターゲットが空になったグループは除外
      if (filteredTargets.length > 0) {
        newTargets.push({
          ...targetGroup,
          targets: filteredTargets,
        });
      }
    } else {
      newTargets.push(targetGroup);
    }
  }

  if (!found) {
    return c.json(
      {
        error: 'Target not found',
        target,
      },
      404
    );
  }

  // 保存
  if (!(await saveTargets(NODE_TARGETS_FILE, newTargets))) {
    return c.json({ error: 'Failed to save targets' }, 500);
  }

  // Prometheusに設定リロードを指示
  await reloadPrometheus();

  return c.json({
    message: 'Node exporter deleted successfully',
    target,
  });
});

// SMARTExporter エンドポイント
app.get('/smart-exporters', async (c) => {
  const targets = await loadTargets(SMART_TARGETS_FILE);

  const exporters = [];
  for (const targetGroup of targets) {
    const labels = targetGroup.labels || {};

    for (const target of targetGroup.targets) {
      exporters.push({
        target,
        labels,
      });
    }
  }

  return c.json({
    count: exporters.length,
    exporters,
  });
});

app.post('/smart-exporter', async (c) => {
  const body = await c.req.json<SmartExporterRequest>();

  // 必須パラメータのチェック
  const { ip } = body;
  const port = body.port || 9633; // SMARTExporterのデフォルトポート

  if (!ip) {
    return c.json({ error: 'IP address is required' }, 400);
  }

  // バリデーション
  if (!validateIP(ip)) {
    return c.json({ error: 'Invalid IP address' }, 400);
  }

  if (!validatePort(port)) {
    return c.json({ error: 'Invalid port number (1-65535)' }, 400);
  }

  // ラベルの取得（オプション）
  const labels: Record<string, string> = body.labels || {};
  if (!labels.instance) {
    labels.instance = ip;
  }

  // ターゲット文字列を作成
  const target = `${ip}:${port}`;

  // 既存のターゲットを読み込み
  const targets = await loadTargets(SMART_TARGETS_FILE);

  // 既に存在するかチェック
  for (const targetGroup of targets) {
    if (targetGroup.targets.includes(target)) {
      return c.json(
        {
          error: 'Target already exists',
          target,
        },
        409
      );
    }
  }

  // 新しいターゲットグループを追加
  targets.push({
    targets: [target],
    labels,
  });

  // 保存
  if (!(await saveTargets(SMART_TARGETS_FILE, targets))) {
    return c.json({ error: 'Failed to save targets' }, 500);
  }

  // Prometheusに設定リロードを指示
  await reloadPrometheus();

  return c.json(
    {
      message: 'SMART exporter added successfully',
      target,
      labels,
    },
    201
  );
});

app.delete('/smart-exporter', async (c) => {
  const body = await c.req.json<SmartExporterDeleteRequest>();

  const { ip } = body;
  const port = body.port || 9633;

  if (!ip) {
    return c.json({ error: 'IP address is required' }, 400);
  }

  const target = `${ip}:${port}`;

  // 既存のターゲットを読み込み
  const targets = await loadTargets(SMART_TARGETS_FILE);

  // ターゲットを検索して削除
  let found = false;
  const newTargets: TargetGroup[] = [];

  for (const targetGroup of targets) {
    if (targetGroup.targets.includes(target)) {
      found = true;
      // ターゲットを削除
      const filteredTargets = targetGroup.targets.filter(t => t !== target);
      // ターゲットが空になったグループは除外
      if (filteredTargets.length > 0) {
        newTargets.push({
          ...targetGroup,
          targets: filteredTargets,
        });
      }
    } else {
      newTargets.push(targetGroup);
    }
  }

  if (!found) {
    return c.json(
      {
        error: 'Target not found',
        target,
      },
      404
    );
  }

  // 保存
  if (!(await saveTargets(SMART_TARGETS_FILE, newTargets))) {
    return c.json({ error: 'Failed to save targets' }, 500);
  }

  // Prometheusに設定リロードを指示
  await reloadPrometheus();

  return c.json({
    message: 'SMART exporter deleted successfully',
    target,
  });
});

// 初期化: ターゲットファイルが存在しない場合は空配列で作成
if (!existsSync(NODE_TARGETS_FILE)) {
  await saveTargets(NODE_TARGETS_FILE, []);
}
if (!existsSync(SMART_TARGETS_FILE)) {
  await saveTargets(SMART_TARGETS_FILE, []);
}

export default {
  port: 5000,
  fetch: app.fetch,
};
