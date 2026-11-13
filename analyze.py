#!/usr/bin/env python3
"""读取 data/ 下的原始 JSON，计算全部对比指标，输出 output/summary.json。

用法：python3 analyze.py
"""

from __future__ import annotations

import gzip
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "output"
CONFIG: dict[str, Any] = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

Row = dict[str, Any]
LAUNCH_PATTERN = re.compile(r"-(?:FB|TT)-(\d{2})(\d{2})-")
PCT_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 0.01, "Top 1%"),
    (0.01, 0.05, "1%~5%"),
    (0.05, 0.10, "5%~10%"),
    (0.10, 0.25, "10%~25%"),
    (0.25, 0.50, "25%~50%"),
    (0.50, 1.0, "50%~100%"),
]
HOUR_BLOCKS: list[int] = [0, 4, 8, 12, 16, 20]


def num(value: Any) -> float:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def load_rows(key: str, day: str) -> list[Row]:
    return list(load_gz(DATA / key / f"{day}.json.gz").get("rows") or [])


def load_hours(key: str) -> dict[str, Any]:
    return load_gz(DATA / key / "hours.json.gz")


def launch_date(row: Row) -> date | None:
    match = LAUNCH_PATTERN.search(str(row.get("campaignName") or ""))
    if not match:
        return None
    try:
        return date(2026, int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def totals(rows: Iterable[Row]) -> dict[str, float]:
    total: dict[str, float] = defaultdict(float)
    for row in rows:
        total["cost"] += num(row.get("cost"))
        total["new_recharge"] += num(row.get("rechargeNewAmount"))
        total["today_recharge"] += num(row.get("rechargeAmount"))
        total["impressions"] += num(row.get("showCnt"))
        total["clicks"] += num(row.get("clickCnt"))
        total["users"] += num(row.get("activeUserCnt"))
        total["new_payers"] += num(row.get("rechargeNewUserCnt"))
        total["payers"] += num(row.get("rechargeCnt"))
        total["meet_weighted"] += (
            num(row.get("meetStandardRate")) / 100 * num(row.get("cost"))
        )
    return dict(total)


def metrics(rows: list[Row]) -> dict[str, float]:
    t = totals(rows)
    cost = t["cost"]
    users = t["users"]
    new_payers = t["new_payers"]
    return {
        "cost": cost,
        "new_recharge": t["new_recharge"],
        "today_recharge": t["today_recharge"],
        "recharge_new_roi": t["new_recharge"] / cost if cost else 0.0,
        "today_roi": t["today_recharge"] / cost if cost else 0.0,
        "new_payers": new_payers,
        "arppu": t["new_recharge"] / new_payers if new_payers else 0.0,
        "cpa": cost / new_payers if new_payers else 0.0,
        "pay_rate": new_payers / users if users else 0.0,
        "cpm": cost / t["impressions"] * 1000 if t["impressions"] else 0.0,
        "ctr": t["clicks"] / t["impressions"] if t["impressions"] else 0.0,
        "cvr": users / t["clicks"] if t["clicks"] else 0.0,
        "cpi": cost / users if users else 0.0,
        "meet_rate": t["meet_weighted"] / cost if cost else 0.0,
        "old_recharge_share": (t["today_recharge"] - t["new_recharge"])
        / t["today_recharge"]
        if t["today_recharge"]
        else 0.0,
    }


def campaign_totals(rows: list[Row]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        if num(row.get("cost")) <= 0:
            continue
        key = str(row.get("campaignId"))
        item = grouped.setdefault(
            key,
            {
                "cost": 0.0,
                "new_recharge": 0.0,
                "impressions": 0.0,
                "clicks": 0.0,
                "users": 0.0,
                "new_payers": 0.0,
            },
        )
        item["cost"] += num(row.get("cost"))
        item["new_recharge"] += num(row.get("rechargeNewAmount"))
        item["impressions"] += num(row.get("showCnt"))
        item["clicks"] += num(row.get("clickCnt"))
        item["users"] += num(row.get("activeUserCnt"))
        item["new_payers"] += num(row.get("rechargeNewUserCnt"))
    return grouped


def percentile_buckets(rows: list[Row]) -> list[dict[str, Any]]:
    grouped = sorted(campaign_totals(rows).values(), key=lambda item: -item["cost"])
    count = len(grouped)
    total_cost = sum(item["cost"] for item in grouped)
    result: list[dict[str, Any]] = []
    for low, high, label in PCT_BUCKETS:
        start = int(math.floor(low * count))
        end = int(math.ceil(high * count))
        selection = grouped[start:end]
        if not selection:
            continue
        cost = sum(item["cost"] for item in selection)
        recharge = sum(item["new_recharge"] for item in selection)
        impressions = sum(item["impressions"] for item in selection)
        clicks = sum(item["clicks"] for item in selection)
        users = sum(item["users"] for item in selection)
        payers = sum(item["new_payers"] for item in selection)
        result.append(
            {
                "label": label,
                "plans": len(selection),
                "cost": cost,
                "cost_share": cost / total_cost if total_cost else 0.0,
                "roi": recharge / cost if cost else 0.0,
                "cpi": cost / users if users else 0.0,
                "pay_rate": payers / users if users else 0.0,
                "cpm": cost / impressions * 1000 if impressions else 0.0,
                "ctr": clicks / impressions if impressions else 0.0,
            }
        )
    return result


def spend_buckets(rows: list[Row]) -> list[dict[str, Any]]:
    grouped = sorted(campaign_totals(rows).values(), key=lambda item: -item["cost"])
    total_cost = sum(item["cost"] for item in grouped)
    result: list[dict[str, Any]] = []
    groups: list[list[dict[str, float]]] = [[], [], [], []]
    running = 0.0
    for item in grouped:
        index = min(3, int(running / total_cost * 4)) if total_cost else 0
        groups[index].append(item)
        running += item["cost"]
    for index, selection in enumerate(groups):
        if not selection:
            continue
        cost = sum(item["cost"] for item in selection)
        recharge = sum(item["new_recharge"] for item in selection)
        users = sum(item["users"] for item in selection)
        payers = sum(item["new_payers"] for item in selection)
        result.append(
            {
                "label": f"{index * 25}%~{index * 25 + 25}%",
                "plans": len(selection),
                "cost": cost,
                "cost_share": cost / total_cost if total_cost else 0.0,
                "roi": recharge / cost if cost else 0.0,
                "cpi": cost / users if users else 0.0,
                "pay_rate": payers / users if users else 0.0,
            }
        )
    return result


def effective_plans(
    rows: list[Row], threshold: float = 0.4, min_cost: float = 50.0
) -> dict[str, Any]:
    grouped = sorted(campaign_totals(rows).values(), key=lambda item: -item["cost"])
    total_cost = sum(item["cost"] for item in grouped)
    good = [
        item
        for item in grouped
        if item["cost"] >= min_cost and item["new_recharge"] / item["cost"] >= threshold
    ]
    good_cost = sum(item["cost"] for item in good)
    running_cost = 0.0
    running_recharge = 0.0
    crossover = 0
    cover80 = 0
    for index, item in enumerate(grouped, start=1):
        running_cost += item["cost"]
        running_recharge += item["new_recharge"]
        if (
            not crossover
            and running_cost
            and running_recharge / running_cost < threshold
        ):
            crossover = index
        if not cover80 and total_cost and running_cost / total_cost >= 0.8:
            cover80 = index
    return {
        "plans": len(good),
        "spend_share": good_cost / total_cost if total_cost else 0.0,
        "crossover_rank": crossover,
        "plans_for_80pct_spend": cover80,
        "total_plans": len(grouped),
    }


def group_by(rows: list[Row], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "cost": 0.0,
            "new_recharge": 0.0,
            "users": 0.0,
            "payers": 0.0,
            "zero_cost": 0.0,
            "plans": 0.0,
        }
    )
    for row in rows:
        cost = num(row.get("cost"))
        if cost <= 0:
            continue
        key = str(row.get(field) or "未知")
        item = grouped[key]
        item["cost"] += cost
        item["new_recharge"] += num(row.get("rechargeNewAmount"))
        item["users"] += num(row.get("activeUserCnt"))
        item["payers"] += num(row.get("rechargeNewUserCnt"))
        item["plans"] += 1
        if num(row.get("rechargeAmount")) <= 0:
            item["zero_cost"] += cost
    total_cost = sum(item["cost"] for item in grouped.values())
    result = []
    for key, item in grouped.items():
        result.append(
            {
                "name": key,
                "cost": item["cost"],
                "cost_share": item["cost"] / total_cost if total_cost else 0.0,
                "roi": item["new_recharge"] / item["cost"] if item["cost"] else 0.0,
                "cpi": item["cost"] / item["users"] if item["users"] else 0.0,
                "plans": int(item["plans"]),
                "zero_order_share": item["zero_cost"] / item["cost"]
                if item["cost"]
                else 0.0,
            }
        )
    return sorted(result, key=lambda item: -item["cost"])


def zero_order(rows: list[Row]) -> dict[str, float]:
    live = [row for row in rows if num(row.get("cost")) > 0]
    cost = sum(num(row.get("cost")) for row in live)
    zero = [row for row in live if num(row.get("rechargeAmount")) <= 0]
    zero_cost = sum(num(row.get("cost")) for row in zero)
    big = [row for row in zero if num(row.get("cost")) >= 20]
    return {
        "plans": float(len(live)),
        "count_share": len(zero) / len(live) if live else 0.0,
        "spend_share": zero_cost / cost if cost else 0.0,
        "avg_cost": zero_cost / len(zero) if zero else 0.0,
        "big_plans": float(len(big)),
        "big_cost": sum(num(row.get("cost")) for row in big),
        "big_share": sum(num(row.get("cost")) for row in big) / cost if cost else 0.0,
    }


def hourly_blocks(hours: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, float]] = defaultdict(
        lambda: {"cost": 0.0, "recharge": 0.0, "users": 0.0, "payers": 0.0}
    )
    for row in hours.get("rows") or []:
        hour_text = str(row.get("hour") or "")
        hour = int(hour_text[11:13]) if len(hour_text) >= 13 else 0
        item = grouped[hour // 4 * 4]
        item["cost"] += num(row.get("cost"))
        item["recharge"] += num(row.get("rechargeAmount"))
        item["users"] += num(row.get("totalNormalUserCnt"))
        item["payers"] += num(row.get("belongPayCnt"))
    total_cost = sum(item["cost"] for item in grouped.values())
    result = []
    for block in HOUR_BLOCKS:
        block_item = grouped.get(block)
        if not block_item:
            continue
        result.append(
            {
                "label": f"{block:02d}-{block + 4:02d}",
                "cost": block_item["cost"],
                "cost_share": block_item["cost"] / total_cost if total_cost else 0.0,
                "roi": block_item["recharge"] / block_item["cost"]
                if block_item["cost"]
                else 0.0,
                "cpi": block_item["cost"] / block_item["users"]
                if block_item["users"]
                else 0.0,
                "pay_rate": block_item["payers"] / block_item["users"]
                if block_item["users"]
                else 0.0,
            }
        )
    return result


def hourly_series(hours: dict[str, Any]) -> dict[str, dict[str, float]]:
    series: dict[str, dict[str, float]] = {}
    for row in hours.get("rows") or []:
        hour_text = str(row.get("hour") or "")
        if len(hour_text) < 13:
            continue
        key = hour_text[11:13]
        item = series.setdefault(key, {"cost": 0.0, "recharge": 0.0})
        item["cost"] += num(row.get("cost"))
        item["recharge"] += num(row.get("rechargeAmount"))
    return series


def hourly_decomposition(
    self_hours: dict[str, Any], bench_hours: dict[str, Any]
) -> dict[str, float]:
    self_series = hourly_series(self_hours)
    bench_series = hourly_series(bench_hours)
    self_cost = sum(item["cost"] for item in self_series.values())
    bench_cost = sum(item["cost"] for item in bench_series.values())
    self_roi = (
        sum(item["recharge"] for item in self_series.values()) / self_cost
        if self_cost
        else 0.0
    )
    hours = sorted(set(self_series) & set(bench_series))
    schedule = 0.0
    efficiency = 0.0
    for hour in hours:
        self_item = self_series[hour]
        bench_item = bench_series[hour]
        self_share = self_item["cost"] / self_cost if self_cost else 0.0
        bench_share = bench_item["cost"] / bench_cost if bench_cost else 0.0
        self_hour_roi = (
            self_item["recharge"] / self_item["cost"] if self_item["cost"] else 0.0
        )
        bench_hour_roi = (
            bench_item["recharge"] / bench_item["cost"] if bench_item["cost"] else 0.0
        )
        schedule += bench_share * self_hour_roi
        efficiency += self_share * bench_hour_roi
    return {
        "self_roi": self_roi,
        "schedule_effect": schedule - self_roi,
        "efficiency_effect": efficiency - self_roi,
    }


def d0_curve(hours: dict[str, Any]) -> list[float]:
    total = hours.get("total") or {}
    return [num(total.get(f"totalD0Nh{hour}Roi")) / 100 for hour in range(1, 25)]


def main() -> int:
    users: list[dict[str, Any]] = CONFIG["users"]
    primary_day: str = CONFIG["primary_day"]
    window: list[str] = CONFIG["daily_window"]
    start = date.fromisoformat(window[0])
    end = date.fromisoformat(window[1])
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor = date.fromordinal(cursor.toordinal() + 1)

    summary: dict[str, Any] = {
        "meta": {
            "day": primary_day,
            "window": window,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "snapshot": CONFIG.get("data_snapshot", ""),
            "users": [{"key": user["key"], "name": user["name"]} for user in users],
        },
        "daily": {},
        "window": {},
        "percentiles": {},
        "spend_percentiles": {},
        "effective": {},
        "accounts": {},
        "languages": {},
        "zero_order": {},
        "hourly_blocks": {},
        "hourly_decomp": {},
        "d0_curve": {},
    }
    for user in users:
        key = str(user["key"])
        day_rows = load_rows(key, primary_day)
        window_rows = [row for day in days for row in load_rows(key, day)]
        hours = load_hours(key)
        summary["daily"][key] = metrics(day_rows)
        summary["window"][key] = metrics(window_rows)
        summary["percentiles"][key] = percentile_buckets(day_rows)
        summary["spend_percentiles"][key] = spend_buckets(day_rows)
        summary["effective"][key] = effective_plans(day_rows)
        summary["accounts"][key] = group_by(day_rows, "advertiserName")
        summary["languages"][key] = group_by(day_rows, "language")
        summary["zero_order"][key] = zero_order(day_rows)
        summary["hourly_blocks"][key] = hourly_blocks(hours)
        summary["d0_curve"][key] = d0_curve(hours)

    self_key = str(users[0]["key"])
    bench_key = str(users[1]["key"])
    summary["hourly_decomp"] = hourly_decomposition(
        load_hours(self_key), load_hours(bench_key)
    )

    window_self = summary["window"][self_key]
    ladder = [
        {
            "cpi": cpi,
            "roi": window_self["pay_rate"] * window_self["arppu"] / cpi if cpi else 0.0,
        }
        for cpi in (1.69, 1.50, 1.40, 1.30, 1.28, 1.20)
    ]
    summary["cpi_ladder"] = ladder
    summary["targets"] = CONFIG["targets"]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"summary -> {OUT / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
