#!/usr/bin/env python3
"""读取 output/summary.json，生成自包含的可视化报告 index.html（项目根目录）。

用法：python3 render_html.py
"""

# ruff: noqa: E501  # HTML/SVG 模板含长行，拆行会牺牲可读性
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SUMMARY: dict[str, Any] = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))

SELF_KEY = SUMMARY["meta"]["users"][0]["key"]
BENCH_KEY = SUMMARY["meta"]["users"][1]["key"]
SELF_NAME = SUMMARY["meta"]["users"][0]["name"]
BENCH_NAME = SUMMARY["meta"]["users"][1]["name"]
SERIES = [
    {"name": SELF_NAME, "color": "--series-1"},
    {"name": BENCH_NAME, "color": "--series-2"},
]
ORDINAL = ["--ord-1", "--ord-2", "--ord-3", "--ord-4", "--ord-5", "--ord-6"]


def esc(value: Any) -> str:
    return html.escape(str(value))


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def money(value: float) -> str:
    return f"${value:,.0f}"


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def legend(names: Sequence[str], colors: Sequence[str]) -> str:
    items = "".join(
        f'<span class="lg-item"><i style="background:var({color})"></i>{esc(name)}</span>'
        for name, color in zip(names, colors)
    )
    return f'<div class="legend">{items}</div>'


def grouped_bars(
    categories: Sequence[str],
    series: Sequence[dict[str, Any]],
    *,
    y_max: float,
    y_fmt: str,
    width: int = 760,
    height: int = 250,
    target: float | None = None,
    target_label: str = "",
) -> str:
    left, right, top, bottom = 52, 16, 24, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    band = plot_w / len(categories)
    bar_w = min(22.0, band * 0.62 / len(series))
    group_w = bar_w * len(series) + 2 * (len(series) - 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="svg-chart" role="img">']
    for index in range(5):
        y = top + plot_h * index / 4
        value = y_max * (1 - index / 4)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" class="axis" text-anchor="end">{y_fmt.format(value)}</text>'
        )
    for index, category in enumerate(categories):
        center = left + band * index + band / 2
        start = center - group_w / 2
        for slot, item in enumerate(series):
            value = float(item["values"][index])
            bar_h = plot_h * min(value / y_max, 1.0) if y_max else 0.0
            x = start + slot * (bar_w + 2)
            y = top + plot_h - bar_h
            tip = f"{item['name']} · {category}：{y_fmt.format(value)}"
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="3" fill="var({item["color"]})" data-tip="{esc(tip)}"/>'
            )
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 5:.1f}" class="val" text-anchor="middle">'
                f"{y_fmt.format(value)}</text>"
            )
        parts.append(
            f'<text x="{center:.1f}" y="{top + plot_h + 18}" class="axis" text-anchor="middle">'
            f"{esc(category)}</text>"
        )
    if target is not None:
        y = top + plot_h * (1 - target / y_max)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="target"/>'
        )
        parts.append(
            f'<text x="{left + plot_w}" y="{y - 5:.1f}" class="target-label" text-anchor="end">'
            f"{esc(target_label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def stacked_100(
    rows: Sequence[tuple[str, Sequence[float]]],
    categories: Sequence[str],
    *,
    width: int = 760,
    height: int = 170,
    value_fmt: str = "{:.0f}%",
) -> str:
    left, right, top = 96, 16, 14
    plot_w = width - left - right
    row_h = (height - top * 2) / max(len(rows), 1)
    bar_h = min(30.0, row_h * 0.62)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="svg-chart" role="img">']
    for row_index, (name, values) in enumerate(rows):
        y = top + row_h * row_index + (row_h - bar_h) / 2
        parts.append(
            f'<text x="{left - 12}" y="{y + bar_h / 2 + 4:.1f}" class="axis" text-anchor="end">{esc(name)}</text>'
        )
        x = float(left)
        for index, value in enumerate(values):
            segment = plot_w * value
            color = ORDINAL[index % len(ORDINAL)]
            tip = f"{name} · {categories[index]}：{value_fmt.format(value * 100)}"
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(segment - 2, 0):.1f}" height="{bar_h:.1f}" '
                f'rx="3" fill="var({color})" data-tip="{esc(tip)}"/>'
            )
            if segment / plot_w >= 0.08:
                parts.append(
                    f'<text x="{x + segment / 2:.1f}" y="{y + bar_h / 2 + 4:.1f}" class="val-in" '
                    f'text-anchor="middle">{value_fmt.format(value * 100)}</text>'
                )
            x += segment
    parts.append("</svg>")
    return "".join(parts)


def line_chart(
    x_labels: Sequence[str],
    series: Sequence[dict[str, Any]],
    *,
    y_max: float,
    y_fmt: str,
    width: int = 760,
    height: int = 250,
) -> str:
    left, right, top, bottom = 52, 60, 24, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    step = plot_w / max(len(x_labels) - 1, 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="svg-chart" role="img">']
    for index in range(5):
        y = top + plot_h * index / 4
        value = y_max * (1 - index / 4)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" class="axis" text-anchor="end">{y_fmt.format(value)}</text>'
        )
    for index, label in enumerate(x_labels):
        x = left + step * index
        parts.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 18}" class="axis" text-anchor="middle">{esc(label)}</text>'
        )
    for item in series:
        points = []
        for index, value in enumerate(item["values"]):
            x = left + step * index
            y = (
                top + plot_h * (1 - min(float(value) / y_max, 1.0))
                if y_max
                else top + plot_h
            )
            points.append((x, y))
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
            for i, (x, y) in enumerate(points)
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="var({item["color"]})" stroke-width="2"/>'
        )
        for (x, y), label, value in zip(points, x_labels, item["values"]):
            tip = f"{item['name']} · {label}：{y_fmt.format(float(value))}"
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="var({item["color"]})" '
                f'stroke="var(--surface-1)" stroke-width="2" data-tip="{esc(tip)}"/>'
            )
        last_x, last_y = points[-1]
        parts.append(
            f'<text x="{last_x + 8:.1f}" y="{last_y + 4:.1f}" class="val" '
            f'fill="var({item["color"]})">{esc(item["name"])}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], classes: str = ""
) -> str:
    head = "".join(f"<th>{esc(item)}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f'<table class="data {classes}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def figure(title: str, subtitle: str, body: str, footer: str = "") -> str:
    sub = f'<p class="chart-sub">{esc(subtitle)}</p>' if subtitle else ""
    foot = f'<div class="chart-foot">{footer}</div>' if footer else ""
    return f'<figure class="chart"><figcaption><h3>{esc(title)}</h3>{sub}</figcaption>{body}{foot}</figure>'


def build() -> str:
    daily = SUMMARY["daily"]
    window = SUMMARY["window"]
    percentiles = SUMMARY["percentiles"]
    spend_percentiles = SUMMARY["spend_percentiles"]
    effective = SUMMARY["effective"]
    accounts = SUMMARY["accounts"]
    languages = SUMMARY["languages"]
    zero = SUMMARY["zero_order"]
    blocks = SUMMARY["hourly_blocks"]
    curves = SUMMARY["d0_curve"]
    decomp = SUMMARY["hourly_decomp"]
    ladder = SUMMARY["cpi_ladder"]
    targets = SUMMARY["targets"]

    self_daily, bench_daily = daily[SELF_KEY], daily[BENCH_KEY]
    gap = bench_daily["recharge_new_roi"] - self_daily["recharge_new_roi"]
    head_share = {
        key: sum(bucket["cost_share"] for bucket in percentiles[key][:3])
        for key in (SELF_KEY, BENCH_KEY)
    }

    blocks_labels = [block["label"] for block in blocks[SELF_KEY]]
    block_roi = {
        "name": "ROI",
        "values": [
            [block["roi"] for block in blocks[key]] for key in (SELF_KEY, BENCH_KEY)
        ],
    }
    block_share = {
        "name": "消耗占比",
        "values": [
            [block["cost_share"] for block in blocks[key]]
            for key in (SELF_KEY, BENCH_KEY)
        ],
    }

    pct_categories = [bucket["label"] for bucket in percentiles[SELF_KEY]]
    pct_roi_series = [
        {
            "name": SELF_NAME,
            "color": "--series-1",
            "values": [b["roi"] for b in percentiles[SELF_KEY]],
        },
        {
            "name": BENCH_NAME,
            "color": "--series-2",
            "values": [b["roi"] for b in percentiles[BENCH_KEY]],
        },
    ]
    pct_share_series = [
        {
            "name": SELF_NAME,
            "color": "--series-1",
            "values": [b["cost_share"] for b in percentiles[SELF_KEY]],
        },
        {
            "name": BENCH_NAME,
            "color": "--series-2",
            "values": [b["cost_share"] for b in percentiles[BENCH_KEY]],
        },
    ]
    spend_categories = [bucket["label"] for bucket in spend_percentiles[SELF_KEY]]
    spend_roi_series = [
        {
            "name": SELF_NAME,
            "color": "--series-1",
            "values": [b["roi"] for b in spend_percentiles[SELF_KEY]],
        },
        {
            "name": BENCH_NAME,
            "color": "--series-2",
            "values": [b["roi"] for b in spend_percentiles[BENCH_KEY]],
        },
    ]

    curve_hours = [0, 1, 2, 5, 11, 23]
    curve_labels = ["第1小时", "第2小时", "第3小时", "第6小时", "第12小时", "第24小时"]
    curve_series = [
        {
            "name": SELF_NAME,
            "color": "--series-1",
            "values": [curves[SELF_KEY][i] for i in curve_hours],
        },
        {
            "name": BENCH_NAME,
            "color": "--series-2",
            "values": [curves[BENCH_KEY][i] for i in curve_hours],
        },
    ]

    ladder_labels = [f"CPI {item['cpi']:.2f}" for item in ladder]
    ladder_values = [item["roi"] for item in ladder]

    kpis = [
        (
            "rechargeNewRoi",
            pct(self_daily["recharge_new_roi"]),
            pct(bench_daily["recharge_new_roi"]),
            f"{gap * 100:+.2f}pp",
        ),
        (
            "CPI",
            num(self_daily["cpi"]),
            num(bench_daily["cpi"]),
            f"{(self_daily['cpi'] / bench_daily['cpi'] - 1) * 100:+.0f}%",
        ),
        (
            "零单消耗占比",
            pct(zero[SELF_KEY]["spend_share"]),
            pct(zero[BENCH_KEY]["spend_share"]),
            f"{(zero[SELF_KEY]['spend_share'] - zero[BENCH_KEY]['spend_share']) * 100:+.1f}pp",
        ),
        (
            "前 10% 计划预算占比",
            pct(head_share[SELF_KEY]),
            pct(head_share[BENCH_KEY]),
            f"{(head_share[SELF_KEY] - head_share[BENCH_KEY]) * 100:+.1f}pp",
        ),
        (
            "首小时 ROI",
            pct(curves[SELF_KEY][0]),
            pct(curves[BENCH_KEY][0]),
            f"{(curves[SELF_KEY][0] - curves[BENCH_KEY][0]) * 100:+.1f}pp",
        ),
        (
            "可打计划数",
            str(effective[SELF_KEY]["plans"]),
            str(effective[BENCH_KEY]["plans"]),
            f"{effective[SELF_KEY]['plans'] - effective[BENCH_KEY]['plans']:+d}",
        ),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-name">{esc(name)}</div>'
        f'<div class="kpi-values"><span class="v-self">{esc(a)}</span>'
        f'<span class="v-sep">/</span><span class="v-bench">{esc(b)}</span></div>'
        f'<div class="kpi-delta">{esc(delta)}</div></div>'
        for name, a, b, delta in kpis
    )

    zero_rows = [
        (SELF_NAME, [zero[SELF_KEY]["spend_share"], 1 - zero[SELF_KEY]["spend_share"]]),
        (
            BENCH_NAME,
            [zero[BENCH_KEY]["spend_share"], 1 - zero[BENCH_KEY]["spend_share"]],
        ),
    ]

    account_rows = []
    for index in range(max(len(accounts[SELF_KEY]), len(accounts[BENCH_KEY]))):
        left = accounts[SELF_KEY][index] if index < len(accounts[SELF_KEY]) else None
        right = accounts[BENCH_KEY][index] if index < len(accounts[BENCH_KEY]) else None
        account_rows.append(
            [
                esc(left["name"]) if left else "—",
                pct(left["cost_share"]) if left else "—",
                pct(left["roi"]) if left else "—",
                pct(left["zero_order_share"]) if left else "—",
                esc(right["name"]) if right else "—",
                pct(right["cost_share"]) if right else "—",
                pct(right["roi"]) if right else "—",
                pct(right["zero_order_share"]) if right else "—",
            ]
        )

    language_rows = []
    for index in range(max(len(languages[SELF_KEY]), len(languages[BENCH_KEY]))):
        left = languages[SELF_KEY][index] if index < len(languages[SELF_KEY]) else None
        right = (
            languages[BENCH_KEY][index] if index < len(languages[BENCH_KEY]) else None
        )
        language_rows.append(
            [
                esc(left["name"]) if left else "—",
                pct(left["cost_share"]) if left else "—",
                pct(left["roi"]) if left else "—",
                esc(right["name"]) if right else "—",
                pct(right["cost_share"]) if right else "—",
                pct(right["roi"]) if right else "—",
            ]
        )

    pct_table = table(
        ["分位", SELF_NAME, BENCH_NAME, f"{SELF_NAME} CPI", f"{BENCH_NAME} CPI"],
        [
            [
                esc(bucket["label"]),
                f"{pct(bucket['cost_share'])} / {pct(bucket['roi'])}",
                f"{pct(percentiles[BENCH_KEY][i]['cost_share'])} / {pct(percentiles[BENCH_KEY][i]['roi'])}",
                num(bucket["cpi"]),
                num(percentiles[BENCH_KEY][i]["cpi"]),
            ]
            for i, bucket in enumerate(percentiles[SELF_KEY])
        ],
    )
    spend_table = table(
        ["消耗分位", SELF_NAME, BENCH_NAME],
        [
            [
                esc(bucket["label"]),
                f"{pct(bucket['roi'])} / CPI {num(bucket['cpi'])}",
                f"{pct(spend_percentiles[BENCH_KEY][i]['roi'])} / CPI {num(spend_percentiles[BENCH_KEY][i]['cpi'])}",
            ]
            for i, bucket in enumerate(spend_percentiles[SELF_KEY])
        ],
    )
    block_table = table(
        [
            "时段（北京时间）",
            f"{SELF_NAME} 消耗占比",
            f"{SELF_NAME} ROI",
            f"{BENCH_NAME} 消耗占比",
            f"{BENCH_NAME} ROI",
        ],
        [
            [
                esc(blocks[SELF_KEY][i]["label"]),
                pct(blocks[SELF_KEY][i]["cost_share"]),
                pct(blocks[SELF_KEY][i]["roi"]),
                pct(blocks[BENCH_KEY][i]["cost_share"]),
                pct(blocks[BENCH_KEY][i]["roi"]),
            ]
            for i in range(len(blocks[SELF_KEY]))
        ],
    )
    curve_table = table(
        ["首日累计", SELF_NAME, BENCH_NAME],
        [
            [esc(curve_labels[i]), pct(curves[SELF_KEY][h]), pct(curves[BENCH_KEY][h])]
            for i, h in enumerate(curve_hours)
        ],
    )

    summary_points = [
        f"单日 rechargeNewRoi {pct(self_daily['recharge_new_roi'])} vs {pct(bench_daily['recharge_new_roi'])}，差 {gap * 100:.2f}pp。",
        f"付费率与 ARPPU {SELF_NAME}更优，差距全部来自 CPI：{num(self_daily['cpi'])} vs {num(bench_daily['cpi'])}。",
        f"头部计划不输：前 10% 计划 ROI {pct(sum(b['roi'] * b['cost_share'] for b in percentiles[SELF_KEY][:3]) / head_share[SELF_KEY])} vs "
        f"{pct(sum(b['roi'] * b['cost_share'] for b in percentiles[BENCH_KEY][:3]) / head_share[BENCH_KEY])}。",
        f"真正差距是分配：前 10% 计划拿到 {pct(head_share[SELF_KEY])} vs {pct(head_share[BENCH_KEY])} 的预算。",
        "反事实：保持各分层 ROI 不变，仅换成优秀投手的分配比例，整体 ROI 可从 23.7% 到 41.3%。",
    ]
    hot_from = 2
    hot_class = ' class="hot"'
    summary_html = "".join(
        f"<li{hot_class if index >= hot_from else ''}>{esc(item)}</li>"
        for index, item in enumerate(summary_points)
    )

    actions = [
        (
            "本周 · 止损与收缩",
            [
                "零单止损：单计划消耗 ≥ $20 且当日零单，立即暂停。11-12 这一类占 24.9% 消耗、次日零回收。",
                "语种收缩：葡语、土语、德语、阿语各砍 50%，预算转给日语、韩语。",
                "账户止损：XTQ+8-04、ZM+8-01 套用同一止损线，各挪 10%~15% 预算给 RONGKOUL-东八-09。",
            ],
        ),
        (
            "本周 · 降 CPI",
            [
                "时段降速：16-24 点消耗占比从 47.8% 压到 40%，增量放到 04-16 点。",
                "CPM 专项：同语种同剧跨账户对比 CPM，检查版位、出价策略、受众重叠；CTR 目标 6.26% 到 7.5%。",
            ],
        ),
        (
            "本周 · 预算向头部集中",
            [
                "预算搬家：止损释放的预算不回补尾部，全部加给 ROI≥40% 的头部计划，前 10% 计划消耗占比本周从 30% 提到 40% 以上。",
                "账户与语种：新增预算优先给日语、韩语的已验证账户，有消耗账户从 12 个往上扩。",
            ],
        ),
    ]
    actions_html = "".join(
        f'<div class="action"><h4>{esc(title)}</h4><ul>'
        + "".join(f"<li>{esc(item)}</li>" for item in items)
        + "</ul></div>"
        for title, items in actions
    )

    return f"""<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(SELF_NAME)} vs {esc(BENCH_NAME)} · 投放效率对比</title>
<style>
:root{{
  color-scheme: light;
  --surface-0:#f7f6f2; --surface-1:#fcfcfb; --surface-2:#f1f0ea;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#7a7973;
  --grid:#e6e5e0; --border:#dedcd5;
  --series-1:#2a78d6; --series-2:#eb6834;
  --ord-1:#184f95; --ord-2:#1c5cab; --ord-3:#2a78d6; --ord-4:#3987e5; --ord-5:#5598e7; --ord-6:#86b6ef;
  --good:#0ca30c; --critical:#d03b3b; --warning:#fab219;
}}
:root[data-theme="dark"]{{
  color-scheme: dark;
  --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#232322;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8f8e86;
  --grid:#383835; --border:#3a3a37;
  --series-1:#3987e5; --series-2:#d95926;
  --ord-1:#cde2fb; --ord-2:#b7d3f6; --ord-3:#9ec5f4; --ord-4:#86b6ef; --ord-5:#6da7ec; --ord-6:#5598e7;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--surface-0);color:var(--text-primary);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}}
.page{{max-width:1180px;margin:0 auto;padding:32px 24px 64px}}
header{{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin-bottom:28px}}
h1{{font-size:24px;margin:0 0 6px;letter-spacing:-.01em}}
.subtitle{{color:var(--text-secondary);margin:0}}
.theme-btn{{border:1px solid var(--border);background:var(--surface-1);color:var(--text-secondary);
  border-radius:999px;padding:6px 14px;font-size:12px;cursor:pointer}}
.hero{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.hero-card{{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:22px 24px}}
.hero-card.bench{{border-left:3px solid var(--series-2)}}
.hero-card.self{{border-left:3px solid var(--series-1)}}
.hero-label{{color:var(--text-secondary);font-size:13px;margin-bottom:6px}}
.hero-value{{font-size:44px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}
.hero-foot{{color:var(--text-muted);font-size:12px;margin-top:6px}}
.gap-badge{{display:inline-block;margin-top:10px;background:var(--surface-2);border-radius:999px;
  padding:4px 12px;font-size:12px;color:var(--text-secondary)}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:24px}}
.kpi{{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:14px}}
.kpi-name{{color:var(--text-secondary);font-size:12px;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.kpi-values{{display:flex;align-items:baseline;gap:6px;font-variant-numeric:tabular-nums}}
.v-self{{color:var(--series-1);font-size:19px;font-weight:600}}
.v-sep{{color:var(--text-muted);font-size:12px}}
.v-bench{{color:var(--series-2);font-size:19px;font-weight:600}}
.kpi-delta{{color:var(--text-muted);font-size:11px;margin-top:4px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.chart{{margin:0 0 16px;background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:18px 20px 12px}}
.chart figcaption h3{{font-size:15px;margin:0 0 2px}}
.chart-sub{{margin:0 0 10px;color:var(--text-muted);font-size:12px}}
.svg-chart{{width:100%;height:auto;display:block}}
.grid{{stroke:var(--grid);stroke-width:1}}
.axis{{fill:var(--text-muted);font-size:11px}}
.val{{fill:var(--text-primary);font-size:10.5px;font-variant-numeric:tabular-nums}}
.val-in{{fill:#fff;font-size:10.5px;font-weight:600}}
.target{{stroke:var(--text-muted);stroke-width:1;stroke-dasharray:4 4;opacity:.7}}
.target-label{{fill:var(--text-muted);font-size:10px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0 2px}}
.lg-item{{display:inline-flex;align-items:center;gap:6px;color:var(--text-secondary);font-size:12px}}
.lg-item i{{width:10px;height:10px;border-radius:3px;display:inline-block}}
.chart-foot{{color:var(--text-muted);font-size:12px;margin-top:6px}}
details{{margin-top:6px}}
details summary{{cursor:pointer;color:var(--text-muted);font-size:12px}}
table.data{{width:100%;border-collapse:collapse;margin-top:8px;font-variant-numeric:tabular-nums}}
table.data th{{text-align:left;font-weight:500;color:var(--text-muted);font-size:11px;padding:6px 8px;border-bottom:1px solid var(--border)}}
table.data td{{padding:6px 8px;border-bottom:1px solid var(--grid);font-size:12px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}}
table.data td:first-child{{color:var(--text-primary)}}
.section-title{{font-size:16px;margin:26px 0 12px}}
.insight{{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:18px 22px;margin-bottom:16px}}
.insight ul{{margin:0;padding-left:20px}}
.insight li{{margin:6px 0}}
.insight li.hot{{color:var(--critical);font-weight:500}}
.actions{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:8px}}
.action{{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:16px 18px}}
.action h4{{margin:0 0 8px;font-size:14px}}
.action ul{{margin:0;padding-left:18px;color:var(--text-secondary);font-size:12.5px}}
.action li{{margin:5px 0}}
footer{{margin-top:28px;color:var(--text-muted);font-size:12px;border-top:1px solid var(--border);padding-top:14px}}
.tip{{position:fixed;z-index:50;pointer-events:none;background:var(--surface-1);color:var(--text-primary);
  border:1px solid var(--border);border-radius:8px;padding:6px 9px;font-size:12px;opacity:0;transition:opacity .12s;
  box-shadow:0 6px 18px rgba(0,0,0,.12)}}
.tip.on{{opacity:1}}
@media (max-width:900px){{
  .hero,.grid2,.actions{{grid-template-columns:1fr}}
  .kpis{{grid-template-columns:repeat(3,1fr)}}
}}
</style>
</head>
<body>
<div class="page">
<header>
  <div>
    <h1>{esc(SELF_NAME)} vs {esc(BENCH_NAME)} · 投放效率对比</h1>
    <p class="subtitle">{esc(SUMMARY["meta"]["day"])} 单日口径 · 六日窗口 {
        esc(SUMMARY["meta"]["window"][0])
    } ~ {esc(SUMMARY["meta"]["window"][1])} · 数据快照 {
        esc(SUMMARY["meta"].get("snapshot") or SUMMARY["meta"]["generated_at"])
    }</p>
  </div>
  <button class="theme-btn" id="theme">切换深色</button>
</header>

<section class="hero">
  <div class="hero-card self">
    <div class="hero-label">{esc(SELF_NAME)} · rechargeNewRoi</div>
    <div class="hero-value">{pct(self_daily["recharge_new_roi"], 2)}</div>
    <div class="hero-foot">消耗 {money(self_daily["cost"])} · D0充值 {
        money(self_daily["new_recharge"])
    } · 新付费 {self_daily["new_payers"]:.0f} 人</div>
  </div>
  <div class="hero-card bench">
    <div class="hero-label">{esc(BENCH_NAME)} · rechargeNewRoi</div>
    <div class="hero-value">{pct(bench_daily["recharge_new_roi"], 2)}</div>
    <div class="hero-foot">消耗 {money(bench_daily["cost"])} · D0充值 {
        money(bench_daily["new_recharge"])
    } · 新付费 {bench_daily["new_payers"]:.0f} 人</div>
    <div class="gap-badge">差距 {gap * 100:+.2f}pp · 六日口径 {
        pct(window[SELF_KEY]["recharge_new_roi"])
    } vs {pct(window[BENCH_KEY]["recharge_new_roi"])}</div>
  </div>
</section>

<section class="insight">
  <h3 class="section-title" style="margin-top:0">结论摘要</h3>
  <ul>{summary_html}</ul>
</section>

<h3 class="section-title">执行路线</h3>
<section class="actions">{actions_html}</section>
<div class="chart-foot">本周目标：rechargeNewRoi 38%。</div>

<section class="kpis">{kpi_html}</section>

{legend([SELF_NAME, BENCH_NAME], ["--series-1", "--series-2"])}

<section class="grid2">
  {
        figure(
            "预算分配：按计划数量分位",
            "横条为消耗占比，六段按计划数量分位由头部到尾部排列",
            legend(pct_categories, ORDINAL)
            + stacked_100(
                [
                    (SELF_NAME, pct_share_series[0]["values"]),
                    (BENCH_NAME, pct_share_series[1]["values"]),
                ],
                pct_categories,
            ),
            f"前 10% 计划消耗占比：{pct(head_share[SELF_KEY])} vs {pct(head_share[BENCH_KEY])}",
        )
    }
  {
        figure(
            "零单消耗占比",
            "零单 = 当日充值 0 且有消耗的计划",
            legend(["零单", "有单"], ["--critical", "--grid"])
            + stacked_100(
                [*zero_rows], ["零单", "有单"], height=140, value_fmt="{:.0f}%"
            ),
            f"零单消耗占比 {pct(zero[SELF_KEY]['spend_share'])} vs {pct(zero[BENCH_KEY]['spend_share'])}",
        )
    }
</section>

{
        figure(
            "各分位的 ROI",
            f"按有消耗计划数量分位（{esc(SELF_NAME)} {effective[SELF_KEY]["total_plans"]:,} 个 / {esc(BENCH_NAME)} {effective[BENCH_KEY]["total_plans"]:,} 个）",
            legend([SELF_NAME, BENCH_NAME], ["--series-1", "--series-2"])
            + grouped_bars(
                pct_categories,
                pct_roi_series,
                y_max=0.65,
                y_fmt="{:.0%}",
                target=targets["recharge_new_roi"],
                target_label="优秀线 38%",
            )
            + "<details><summary>查看数据</summary>"
            + pct_table
            + "</details>",
        )
    }

{
        figure(
            "各消耗分位的 ROI",
            "按累计消耗四分位，回答「钱花到第几段开始不赚钱」",
            legend([SELF_NAME, BENCH_NAME], ["--series-1", "--series-2"])
            + grouped_bars(
                spend_categories,
                spend_roi_series,
                y_max=0.65,
                y_fmt="{:.0%}",
                target=targets["recharge_new_roi"],
                target_label="优秀线 38%",
            )
            + "<details><summary>查看数据</summary>"
            + spend_table
            + "</details>",
        )
    }

<section class="grid2">
  {
        figure(
            "分时段 ROI（北京时间）",
            f"16-24 点是主要消耗区；排期只解释 {decomp["schedule_effect"] * 100:+.1f}pp，小时效率解释 {decomp["efficiency_effect"] * 100:+.1f}pp",
            legend([SELF_NAME, BENCH_NAME], ["--series-1", "--series-2"])
            + grouped_bars(
                blocks_labels,
                [
                    dict(
                        name=SELF_NAME,
                        color="--series-1",
                        values=block_roi["values"][0],
                    ),
                    dict(
                        name=BENCH_NAME,
                        color="--series-2",
                        values=block_roi["values"][1],
                    ),
                ],
                y_max=0.5,
                y_fmt="{:.0%}",
                target=targets["recharge_new_roi"],
                target_label="38%",
            ),
        )
    }
  {
        figure(
            "分时段消耗占比",
            "同一横轴，单独一张图，不做双轴",
            legend([SELF_NAME, BENCH_NAME], ["--series-1", "--series-2"])
            + grouped_bars(
                blocks_labels,
                [
                    dict(
                        name=SELF_NAME,
                        color="--series-1",
                        values=block_share["values"][0],
                    ),
                    dict(
                        name=BENCH_NAME,
                        color="--series-2",
                        values=block_share["values"][1],
                    ),
                ],
                y_max=0.3,
                y_fmt="{:.0%}",
            )
            + "<details><summary>查看数据</summary>"
            + block_table
            + "</details>",
        )
    }
</section>

<section class="grid2">
  {
        figure(
            "首日回收曲线",
            "用户生命周期第 N 小时的累计 ROI，前 3 小时贡献约 86%",
            legend([SELF_NAME, BENCH_NAME], ["--series-1", "--series-2"])
            + line_chart(curve_labels, curve_series, y_max=0.5, y_fmt="{:.0%}")
            + "<details><summary>查看数据</summary>"
            + curve_table
            + "</details>",
        )
    }
  {
        figure(
            "CPI 与 ROI 的关系",
            f"保持{SELF_NAME}付费率与 ARPPU 不变，仅改变 CPI",
            grouped_bars(
                ladder_labels,
                [{"name": SELF_NAME, "color": "--series-1", "values": ladder_values}],
                y_max=0.5,
                y_fmt="{:.0%}",
                target=bench_daily["recharge_new_roi"],
                target_label=f"优秀投手 {pct(bench_daily['recharge_new_roi'])}",
            )
            + f'<div class="chart-foot">CPI 降到 1.28，ROI 约 {pct(ladder[4]["roi"])}，追平优秀投手。</div>',
        )
    }
</section>

<section class="grid2">
  {
        figure(
            "账户对比",
            "按消耗排序，展示消耗占比 / 新客 ROI / 零单消耗占比",
            "",
            table(
                ["账户", "占比", "ROI", "零单", "账户", "占比", "ROI", "零单"],
                account_rows,
            )
            + '<div class="chart-foot">左三列 '
            + esc(SELF_NAME)
            + "，右三列 "
            + esc(BENCH_NAME)
            + "</div>",
        )
    }
  {
        figure(
            "语言对比",
            "按消耗排序",
            "",
            table(["语言", "占比", "ROI", "语言", "占比", "ROI"], language_rows),
        )
    }
</section>

<footer>
数据来源：cost_list（系列级）、cost_list/sum（校验）、hours/roi（小时级，hour 为北京时间）。效率口径为 rechargeNewAmount / cost。
<br>数据快照 {
        esc(SUMMARY["meta"].get("snapshot") or "")
    }；11-12 的平台数据仍在回补，重新取数后数值会小幅变动，以最新快照为准。
<br>口径限制：零单为当日口径，部分计划次日会回补；高消耗零单计划次日零回收。分位分桶基于当日有消耗计划。反事实 41.3% 为理论上界。
</footer>
</div>
<div class="tip" id="tip"></div>
<script>
const root=document.documentElement;
const btn=document.getElementById('theme');
btn.addEventListener('click',()=>{{
  const dark=root.getAttribute('data-theme')==='dark';
  root.setAttribute('data-theme',dark?'light':'dark');
  btn.textContent=dark?'切换深色':'切换浅色';
}});
const tip=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(el=>{{
  el.addEventListener('mouseenter',e=>{{tip.textContent=el.getAttribute('data-tip');tip.classList.add('on');}});
  el.addEventListener('mousemove',e=>{{tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';}});
  el.addEventListener('mouseleave',()=>tip.classList.remove('on'));
}});
</script>
</body>
</html>
"""


def main() -> int:
    path = ROOT / "index.html"
    path.write_text(build(), encoding="utf-8")
    print(f"report -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
