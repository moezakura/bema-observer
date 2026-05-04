#!/usr/bin/env python3
"""Build SMART fleet health dashboard JSON for Grafana 12.x."""
import json

DS = {"type": "prometheus", "uid": "prometheus"}

PID = [0]
def nid():
    PID[0] += 1
    return PID[0]

def target(expr, legend=None, fmt="time_series", instant=False, ref="A"):
    t = {"datasource": DS, "expr": expr, "refId": ref}
    if legend is not None:
        t["legendFormat"] = legend
    if fmt != "time_series":
        t["format"] = fmt
    if instant:
        t["instant"] = True
        t["range"] = False
    return t

def grid(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}

def stat(title, expr, gp, thresholds, unit="none", text_mode="value_and_name", color_mode="background"):
    return {
        "id": nid(),
        "type": "stat",
        "title": title,
        "datasource": DS,
        "gridPos": gp,
        "targets": [target(expr, legend="", instant=True)],
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": text_mode,
            "colorMode": color_mode,
            "graphMode": "none",
            "justifyMode": "center",
            "orientation": "auto",
        },
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": thresholds},
                "unit": unit,
                "mappings": [],
            },
            "overrides": [],
        },
    }

def timeseries(title, queries, gp, unit="none", legend_placement="bottom", min_=None):
    p = {
        "id": nid(),
        "type": "timeseries",
        "title": title,
        "datasource": DS,
        "gridPos": gp,
        "targets": queries,
        "options": {
            "legend": {"displayMode": "table", "placement": legend_placement, "showLegend": True, "calcs": ["lastNotNull", "max"]},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "unit": unit,
                "custom": {
                    "drawStyle": "line",
                    "lineWidth": 1,
                    "fillOpacity": 10,
                    "pointSize": 4,
                    "showPoints": "auto",
                    "spanNulls": True,
                    "axisPlacement": "auto",
                },
            },
            "overrides": [],
        },
    }
    if min_ is not None:
        p["fieldConfig"]["defaults"]["min"] = min_
    return p

def heatmap(title, queries, gp):
    return {
        "id": nid(),
        "type": "heatmap",
        "title": title,
        "datasource": DS,
        "gridPos": gp,
        "targets": queries,
        "options": {
            "calculate": False,
            "color": {"scheme": "RdYlGn", "reverse": True, "mode": "scheme"},
            "yAxis": {"axisPlacement": "left"},
            "tooltip": {"show": True},
            "legend": {"show": True},
        },
        "fieldConfig": {"defaults": {"unit": "celsius"}, "overrides": []},
    }

def bargauge(title, queries, gp, unit="none", thresholds=None, max_=None):
    p = {
        "id": nid(),
        "type": "bargauge",
        "title": title,
        "datasource": DS,
        "gridPos": gp,
        "targets": queries,
        "options": {
            "displayMode": "gradient",
            "orientation": "horizontal",
            "showUnfilled": True,
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "unit": unit,
                "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]},
            },
            "overrides": [],
        },
    }
    if max_ is not None:
        p["fieldConfig"]["defaults"]["max"] = max_
    return p

def table(title, queries, gp, transformations=None, overrides=None):
    return {
        "id": nid(),
        "type": "table",
        "title": title,
        "datasource": DS,
        "gridPos": gp,
        "targets": queries,
        "transformations": transformations or [],
        "options": {"showHeader": True, "cellHeight": "sm"},
        "fieldConfig": {
            "defaults": {
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "filterable": True},
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": overrides or [],
        },
    }

def row(title, gp, collapsed=False, panels=None):
    return {
        "id": nid(),
        "type": "row",
        "title": title,
        "collapsed": collapsed,
        "gridPos": gp,
        "panels": panels or [],
    }

# ===== Build panels =====
panels = []

# Section 1: Fleet health summary
panels.append(row("Section 1: Fleet health summary (全0=正常)", grid(0, 0, 24, 1)))
y = 1
kpi_thr_bin = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
kpi_thr_temp = [{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 3}]
TEMP_CURRENT_AVG_1H = 'avg_over_time((max by(instance, device, server) (smartctl_device_temperature{temperature_type="current"}))[1h:])'

panels += [
    stat("Pending sectors growing (7d)",
         'count(disk:pending_sectors:growth_7d > 0) OR on() vector(0)',
         grid(0, y, 4, 4), kpi_thr_bin),
    stat("Reallocated growing (7d)",
         'count(disk:reallocated_sectors:growth_7d > 0) OR on() vector(0)',
         grid(4, y, 4, 4), kpi_thr_bin),
    stat("Offline uncorrectable",
         'count(disk:offline_uncorrectable:raw > 0) OR on() vector(0)',
         grid(8, y, 4, 4), kpi_thr_bin),
    stat("NVMe spare below threshold",
         'count(smartctl_device_available_spare < smartctl_device_available_spare_threshold) OR on() vector(0)',
         grid(12, y, 4, 4), kpi_thr_bin),
    stat("NVMe critical warning",
         'count(smartctl_device_critical_warning != 0) OR on() vector(0)',
         grid(16, y, 4, 4), kpi_thr_bin),
    stat("High temperature (>50°C, 1h)",
         f'count({TEMP_CURRENT_AVG_1H} > 50) OR on() vector(0)',
         grid(20, y, 4, 4), kpi_thr_temp),
]
y += 4

# Section 2: Worst offenders
panels.append(row("Section 2: Worst offenders top 10", grid(0, y, 24, 1)))
y += 1
# Score クエリだけに drive identity labels を持たせ、各 metric クエリは
# label_join で作った _key だけを残す。Grafana 側は _key で outer join する。
INFO_JOIN = (
    " * on(instance, device) group_left(serial_number, model_family, model_name, firmware_version) "
    "max by(instance, device, serial_number, model_family, model_name, firmware_version) (smartctl_device)"
)
KEY_JOIN = 'label_join({expr}, "_key", "/", "instance", "device")'

# 設計書 §5.2 通り: 1ドライブ=1行、属性別カラム
# 各 metric を別々の instant table query で取得し、joinByField で水平結合。
# 各クエリは worst10 (anomaly score > 0) にフィルタし、欠損 metric は 0 で補完する。
TOP10_FILTER = " and on(instance, device) topk(10, disk:anomaly:score > 0)"
ALL_DRIVES_FALLBACK = " or on(instance, device, server) (disk:anomaly:score * 0)"
def metric_col(metric_expr):
    """Metric value query for the top10 drives, reduced to (_key, Value)."""
    inner = f"sum by(instance, device, server) ({metric_expr})"
    top10_value = f"(({inner}){ALL_DRIVES_FALLBACK}){TOP10_FILTER}"
    return f"sum by(_key) ({KEY_JOIN.format(expr=top10_value)})"

score_expr = KEY_JOIN.format(
    expr=f"topk(10, (disk:anomaly:score > 0){INFO_JOIN})"
)

worst_queries = [
    target(score_expr, legend="", fmt="table", instant=True, ref="Score"),
    target(metric_col("disk:pending_sectors:growth_7d"), legend="", fmt="table", instant=True, ref="PendingD"),
    target(metric_col("disk:reallocated_sectors:growth_7d"), legend="", fmt="table", instant=True, ref="ReallocD"),
    target(metric_col("disk:offline_uncorrectable:raw"), legend="", fmt="table", instant=True, ref="OffUnc"),
    target(metric_col("disk:reported_uncorrectable:raw"), legend="", fmt="table", instant=True, ref="ReportUnc"),
    target(metric_col("disk:crc_errors:growth_24h"), legend="", fmt="table", instant=True, ref="CrcD"),
    target(metric_col("disk:command_timeout:raw"), legend="", fmt="table", instant=True, ref="CmdTO"),
    target(metric_col("smartctl_scsi_grown_defect_list"), legend="", fmt="table", instant=True, ref="ScsiDef"),
    target(metric_col(TEMP_CURRENT_AVG_1H), legend="", fmt="table", instant=True, ref="Temp"),
]
worst_transforms = [
    {"id": "joinByField", "options": {"byField": "_key", "mode": "outerTabular"}},
    {"id": "organize", "options": {
        "excludeByName": {"Time": True, "__name__": True, "_key": True},
        "renameByName": {
            "server": "サーバー",
            "instance": "IP",
            "device": "デバイス",
            "serial_number": "シリアル",
            "model_name": "型番",
            "model_family": "モデル",
            "firmware_version": "FW",
            "Value #Score": "Score",
            "Value #PendingD": "Pending Δ 7d",
            "Value #ReallocD": "Realloc Δ 7d",
            "Value #OffUnc": "Off-Unc",
            "Value #ReportUnc": "Reported-Unc",
            "Value #CrcD": "CRC Δ 24h",
            "Value #CmdTO": "Command Timeout",
            "Value #ScsiDef": "SCSI defects",
            "Value #Temp": "Temp 1h avg",
        },
        "indexByName": {
            "サーバー": 0, "IP": 1, "デバイス": 2, "シリアル": 3,
            "型番": 4, "モデル": 5, "FW": 6, "Score": 7,
            "Pending Δ 7d": 8, "Realloc Δ 7d": 9, "Off-Unc": 10,
            "Reported-Unc": 11, "CRC Δ 24h": 12, "Command Timeout": 13,
            "SCSI defects": 14, "Temp 1h avg": 15,
        },
    }},
    {"id": "sortBy", "options": {"fields": {}, "sort": [{"field": "Score", "desc": True}]}},
]
def red_col(name):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [
                {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                    {"color": "green", "value": None},
                    {"color": "red", "value": 1}]}},
                {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
            ]}
def amber_col(name):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [
                {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                    {"color": "green", "value": None},
                    {"color": "orange", "value": 1}]}},
                {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
            ]}

worst_overrides = [
    amber_col("Score"),
    red_col("Pending Δ 7d"),
    red_col("Realloc Δ 7d"),
    red_col("Off-Unc"),
    red_col("Reported-Unc"),
    amber_col("CRC Δ 24h"),
    amber_col("Command Timeout"),
    red_col("SCSI defects"),
    {"matcher": {"id": "byName", "options": "Temp 1h avg"},
     "properties": [
         {"id": "unit", "value": "celsius"},
         {"id": "thresholds", "value": {"mode": "absolute", "steps": [
             {"color": "green", "value": None},
             {"color": "orange", "value": 50},
             {"color": "red", "value": 60}]}},
         {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
     ]},
    {"matcher": {"id": "byName", "options": "サーバー"},
     "properties": [{"id": "links", "value": [
         {"title": "このサーバーをドリルダウン",
          "url": "/d/${__dashboard.uid}?var-server=${__value.raw}"}
     ]}]},
]
worst = table("Worst offenders top 10 (per-drive metrics)", worst_queries, grid(0, y, 24, 12),
              transformations=worst_transforms, overrides=worst_overrides)
panels.append(worst)
y += 12

# 旧 per-metric 補助表は不要 (メイン表に統合済み)
def _unused_metric_table(title, score_expr, gp, value_unit="short", value_thresholds=None):
    """単一 metric の topk 表 (group_left で識別 label 注入)"""
    queries = [
        target(f'topk(10, (({score_expr}) > 0){INFO_JOIN})',
               legend="", fmt="table", ref="A"),
    ]
    transforms = [
        {"id": "groupBy", "options": {
            "fields": {
                "instance": {"aggregations": [], "operation": "groupby"},
                "device": {"aggregations": [], "operation": "groupby"},
                "server": {"aggregations": [], "operation": "groupby"},
                "serial_number": {"aggregations": [], "operation": "groupby"},
                "model_family": {"aggregations": [], "operation": "groupby"},
                "model_name": {"aggregations": [], "operation": "groupby"},
                "firmware_version": {"aggregations": [], "operation": "groupby"},
                "Value": {"aggregations": ["last"], "operation": "aggregate"},
            },
        }},
        {"id": "organize", "options": {
            "excludeByName": {"Time": True, "instance": True, "model_name": True, "firmware_version": True},
            "renameByName": {
                "server": "サーバー", "device": "デバイス",
                "serial_number": "シリアル", "model_family": "モデル",
                "Value (last)": "値",
            },
            "indexByName": {
                "サーバー": 0, "デバイス": 1, "シリアル": 2, "モデル": 3, "値": 4,
            },
        }},
        {"id": "sortBy", "options": {"fields": {}, "sort": [{"field": "値", "desc": True}]}},
    ]
    overrides = [
        {"matcher": {"id": "byName", "options": "値"},
         "properties": [
             {"id": "unit", "value": value_unit},
             {"id": "thresholds", "value": {"mode": "absolute",
                                            "steps": value_thresholds or [{"color": "red", "value": None}]}},
             {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
         ]},
    ]
    return table(title, queries, gp, transformations=transforms, overrides=overrides)

# 旧 per-metric 補助表は不要 (メイン Worst offenders 表に統合済み)

# Section 3a: SATA trends
panels.append(row("Section 3a: SATA HDD/SSD trends", grid(0, y, 24, 1)))
y += 1
sata_filter = '{server=~"$server", model_family=~"$model_family"}'
panels += [
    timeseries("Pending sectors daily Δ (top10)",
               [target(f'topk(10, disk:pending_sectors:growth_7d{sata_filter} / 7)',
                       legend="{{server}}/{{device}} ({{model_family}})")],
               grid(0, y, 12, 8), unit="short", min_=0),
    timeseries("Reallocated sectors daily Δ (top10)",
               [target(f'topk(10, disk:reallocated_sectors:growth_7d{sata_filter} / 7)',
                       legend="{{server}}/{{device}} ({{model_family}})")],
               grid(12, y, 12, 8), unit="short", min_=0),
]
y += 8
panels += [
    timeseries("CRC errors daily Δ (cable health, top10)",
               [target(f'topk(10, disk:crc_errors:growth_24h{sata_filter})',
                       legend="{{server}}/{{device}} ({{model_family}})")],
               grid(0, y, 12, 8), unit="short", min_=0),
    heatmap("Temperature distribution (all SATA)",
            [target(f'disk:temperature:celsius{sata_filter}',
                    legend="{{server}}/{{device}}")],
            grid(12, y, 12, 8)),
]
y += 8

# Section 3b: NVMe
panels.append(row("Section 3b: NVMe health", grid(0, y, 24, 1)))
y += 1
nvme_filter = '{server=~"$server", model_family=~"$model_family"}'
panels += [
    bargauge("NVMe percentage_used",
             [target(f'smartctl_device_percentage_used{nvme_filter}',
                     legend="{{server}}/{{device}} ({{serial_number}})", instant=True)],
             grid(0, y, 12, 8), unit="percent", max_=100,
             thresholds=[{"color": "green", "value": None},
                         {"color": "orange", "value": 50},
                         {"color": "red", "value": 80}]),
    bargauge("NVMe available_spare (vs threshold)",
             [target(f'smartctl_device_available_spare{nvme_filter}',
                     legend="spare {{server}}/{{device}}", instant=True),
              target(f'smartctl_device_available_spare_threshold{nvme_filter}',
                     legend="threshold {{server}}/{{device}}", instant=True, ref="B")],
             grid(12, y, 12, 8), unit="percent", max_=100,
             thresholds=[{"color": "red", "value": None},
                         {"color": "orange", "value": 10},
                         {"color": "green", "value": 20}]),
]
y += 8
panels += [
    stat("media_and_data_integrity_errors",
         f'sum(smartctl_device_media_errors{nvme_filter}) OR on() vector(0)',
         grid(0, y, 12, 4),
         [{"color": "green", "value": None}, {"color": "red", "value": 1}], color_mode="background"),
    stat("unsafe_shutdowns (informational)",
         f'max(smartctl_device_num_err_log_entries{nvme_filter}) OR on() vector(0)',
         grid(12, y, 12, 4),
         [{"color": "blue", "value": None}], color_mode="value", text_mode="value"),
]
y += 4

# Section 3c: SAS (collapsed)
sas_panels = []
sas_filter = '{server=~"$server"}'
sas_panels += [
    timeseries("SAS Grown defect list",
               [target(f'smartctl_scsi_grown_defect_list{sas_filter}',
                       legend="{{server}}/{{device}}")],
               grid(0, y + 1, 8, 8), unit="short", min_=0),
    timeseries("SAS Read uncorrected total",
               [target(f'smartctl_read_total_uncorrected_errors{sas_filter}',
                       legend="{{server}}/{{device}}")],
               grid(8, y + 1, 8, 8), unit="short", min_=0),
    timeseries("SAS Write uncorrected total",
               [target(f'smartctl_write_total_uncorrected_errors{sas_filter}',
                       legend="{{server}}/{{device}}")],
               grid(16, y + 1, 8, 8), unit="short", min_=0),
]
panels.append(row("Section 3c: SAS health (折りたたみ)",
                  grid(0, y, 24, 1), collapsed=True, panels=sas_panels))
y += 1

# Section 4: Drilldown (collapsed)
drill_panels = []
inv_queries = [
    target('smartctl_device{server=~"$server"}', legend="", fmt="table", instant=True, ref="Dev"),
    target('smartctl_device_capacity_bytes{server=~"$server"}', legend="", fmt="table", instant=True, ref="Cap"),
    target('smartctl_device_power_on_seconds{server=~"$server"} / 3600', legend="", fmt="table", instant=True, ref="POH"),
    target('disk:temperature:celsius{server=~"$server"}', legend="", fmt="table", instant=True, ref="Temp"),
    target('smartctl_device_power_cycle_count{server=~"$server"}', legend="", fmt="table", instant=True, ref="PCC"),
]
inv_transforms = [
    {"id": "merge", "options": {}},
    {"id": "organize", "options": {
        "excludeByName": {
            "Time": True, "__name__": True, "job": True, "node_address": True, "node_ip": True,
            "ata_additional_product_id": True, "ata_version": True, "form_factor": True,
            "protocol": True, "sata_version": True, "Value #Dev": True,
        },
        "renameByName": {
            "server": "サーバー", "instance": "IP", "device": "デバイス",
            "serial_number": "シリアル", "model_name": "型番", "model_family": "モデル",
            "firmware_version": "FW", "interface": "I/F",
            "Value #Cap": "容量", "Value #POH": "POH(時間)",
            "Value #Temp": "Temp(°C)", "Value #PCC": "電源投入回数",
        },
    }},
]
inv_overrides = [
    {"matcher": {"id": "byName", "options": "容量"},
     "properties": [{"id": "unit", "value": "decbytes"}]},
    {"matcher": {"id": "byName", "options": "POH(時間)"},
     "properties": [{"id": "unit", "value": "h"}]},
    {"matcher": {"id": "byName", "options": "Temp(°C)"},
     "properties": [{"id": "unit", "value": "celsius"}]},
]
drill_panels.append(table("Drive inventory ($server)", inv_queries, grid(0, y + 1, 24, 10),
                          transformations=inv_transforms, overrides=inv_overrides))
drill_panels.append(timeseries("All raw attributes (selected device)",
                               [target('smartctl_device_attribute{server=~"$server", device=~"$device", attribute_value_type="raw"}',
                                       legend="{{device}} #{{attribute_id}} {{attribute_name}}")],
                               grid(0, y + 11, 24, 10), unit="short"))
panels.append(row("Section 4: Per-server drilldown ($server を絞ると展開)",
                  grid(0, y, 24, 1), collapsed=True, panels=drill_panels))
y += 1

# Section 5: Lifetime & capacity
panels.append(row("Section 5: Lifetime & capacity (informational)", grid(0, y, 24, 1)))
y += 1
panels += [
    bargauge("Power_On_Hours (per drive)",
             [target('smartctl_device_power_on_seconds{server=~"$server"} / 3600',
                     legend="{{server}}/{{device}} ({{serial_number}})", instant=True)],
             grid(0, y, 12, 10), unit="h",
             thresholds=[{"color": "green", "value": None},
                         {"color": "orange", "value": 30000},
                         {"color": "red", "value": 50000}]),
    bargauge("Power cycle count",
             [target('smartctl_device_power_cycle_count{server=~"$server"}',
                     legend="{{server}}/{{device}}", instant=True)],
             grid(12, y, 12, 10), unit="short"),
]
y += 10
panels += [
    timeseries("Bytes written (cumulative)",
               [target('smartctl_device_bytes_written{server=~"$server"}',
                       legend="{{server}}/{{device}}")],
               grid(0, y, 12, 8), unit="decbytes"),
    bargauge("Capacity by server",
             [target('sum by(server) (smartctl_device_capacity_bytes)',
                     legend="{{server}}", instant=True)],
             grid(12, y, 12, 8), unit="decbytes"),
]
y += 8

# ===== Templating =====
def variable(name, label, query, multi=True, include_all=True, hide=0):
    v = {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": DS,
        "query": {"query": query, "refId": f"PrometheusVariableQueryEditor-{name}"},
        "definition": query,
        "refresh": 2,
        "sort": 1,
        "multi": multi,
        "includeAll": include_all,
        "current": {"selected": False, "text": "All", "value": "$__all"} if include_all else {},
        "hide": hide,
    }
    if include_all:
        v["allValue"] = ".*"
    return v

templating = {
    "list": [
        variable("server", "サーバー", "label_values(smartctl_device, server)"),
        variable("model_family", "モデル", "label_values(smartctl_device, model_family)"),
        variable("device", "デバイス",
                 'label_values(smartctl_device{server=~"$server"}, device)', hide=0),
    ],
}

dashboard = {
    "title": "SMART Fleet Health",
    "uid": "smart-fleet-health",
    "tags": ["smart", "disk", "storage"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "editable": True,
    "graphTooltip": 0,
    "refresh": "5m",
    "time": {"from": "now-7d", "to": "now"},
    "timepicker": {},
    "templating": templating,
    "annotations": {"list": []},
    "panels": panels,
}

with open("grafana/dashboards/01-smart/smart-fleet-health.json", "w") as f:
    json.dump(dashboard, f, ensure_ascii=False, indent=2)

print(f"Generated {len(panels)} panels.")
