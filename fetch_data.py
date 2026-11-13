#!/usr/bin/env python3
"""按 config.json 拉取 NetShort 投放数据到 data/。

用法：
  python3 fetch_data.py                 # 拉主日 + 六日窗口 + 小时数据
  python3 fetch_data.py --mode hours    # 只拉小时数据
  python3 fetch_data.py --start 2026-11-01 --end 2026-11-12
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONFIG: dict[str, Any] = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(Path.home() / "netshort-scripts"))
import netshort_auth  # type: ignore[import-not-found]  # noqa: E402

BASE = "https://admin.netshort.com/prod-api/put/dashboard"
PAGE_SIZE = 200


def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "authorization": netshort_auth.authorization(),
            "content-type": "application/json;charset=UTF-8",
            "timezone": "+0",
            "cookie": netshort_auth.cookies(),
            "user-agent": "Mozilla/5.0",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
                data: dict[str, Any] = json.loads(response.read())
                return data
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            last_error = exc
        if attempt == 2:
            break
    raise RuntimeError(f"接口请求失败：{last_error}")


def cost_payload(emp_id: str, day: str, page: int) -> dict[str, Any]:
    return {
        "appType": 1,
        "type": 1,
        "nHour": 14,
        "pageNum": page,
        "pageSize": PAGE_SIZE,
        "today": day,
        "createBy": emp_id,
        "deptIds": [],
        "linkTypes": [],
        "videoIds": [],
        "videoRemarks": [],
        "linkIds": [],
        "shortPlayTypes": [],
        "mediaList": [],
        "language": "",
        "adTimeZoneList": [],
        "channelNos": [],
        "advertiserIds": [],
        "campaignIds": [],
        "status": "",
        "weatherNewShortPlay": "",
        "weatherMeetStandard": "",
        "weatherTestLink": "",
        "channelNoFilterType": 1,
        "copyrightTypes": [],
    }


def fetch_day(emp_id: str, day: str) -> tuple[int, list[dict[str, Any]]]:
    url = f"{BASE}/cost_list"
    first = post(url, cost_payload(emp_id, day, 1))
    total = int(first.get("total") or 0)
    rows: list[dict[str, Any]] = list(first.get("rows") or [])
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if pages > 1:
        with ThreadPoolExecutor(max_workers=8) as pool:
            batches = pool.map(
                lambda page: list(
                    post(url, cost_payload(emp_id, day, page)).get("rows") or []
                ),
                range(2, pages + 1),
            )
            for batch in batches:
                rows.extend(batch)
    return total, rows


def hours_payload(emp_id: str, start: str, end: str) -> dict[str, Any]:
    return {
        "appType": 1,
        "type": 1,
        "pageNum": 1,
        "pageSize": 2000,
        "startDate": start,
        "endDate": end,
        "createBy": emp_id,
        "deptIds": [],
        "linkTypes": [],
        "videoIds": [],
        "videoRemarks": [],
        "linkIds": [],
        "shortPlayTypes": [],
        "mediaList": [],
        "language": "",
        "adTimeZoneList": [],
        "channelNos": [],
        "advertiserIds": [],
        "status": "",
        "os": "",
        "weatherNewShortPlay": "",
        "weatherMeetStandard": "",
        "channelNoFilterType": 1,
        "timeRange": [start, end],
        "nHour": 14,
        "today": end,
        "campaignIds": [],
        "weatherTestLink": "",
        "copyrightTypes": [],
    }


def fetch_hours(emp_id: str, start: str, end: str) -> dict[str, Any]:
    return post(f"{BASE}/hours/roi", hours_payload(emp_id, start, end))


def day_range(start: str, end: str) -> list[str]:
    current, last = date.fromisoformat(start), date.fromisoformat(end)
    days: list[str] = []
    while current <= last:
        days.append(current.isoformat())
        current = date.fromordinal(current.toordinal() + 1)
    return days


def selected_users(target: str) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = CONFIG["users"]
    if target == "all":
        return users
    return [user for user in users if user["key"] == target]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["cost", "hours", "all"], default="all")
    parser.add_argument("--user", default="all", help="kahui | benchmark | all")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    args = parser.parse_args()

    start = args.start or CONFIG["daily_window"][0]
    end = args.end or CONFIG["daily_window"][1]
    days = day_range(start, end)
    primary = str(CONFIG["primary_day"])
    if primary not in days:
        days.append(primary)
    days = sorted(set(days))

    for user in selected_users(args.user):
        key, emp_id = str(user["key"]), str(user["emp_id"])
        target_dir = DATA / key
        target_dir.mkdir(parents=True, exist_ok=True)
        if args.mode in ("cost", "all"):
            for day in days:
                total, rows = fetch_day(emp_id, day)
                with gzip.open(
                    target_dir / f"{day}.json.gz", "wt", encoding="utf-8"
                ) as handle:
                    json.dump(
                        {"total": total, "rows": rows}, handle, ensure_ascii=False
                    )
                print(f"{key} {day} rows={len(rows)} total={total}")
        if args.mode in ("hours", "all"):
            h_start, h_end = CONFIG["hourly_window"]
            data = fetch_hours(emp_id, str(h_start), str(h_end))
            with gzip.open(
                target_dir / "hours.json.gz", "wt", encoding="utf-8"
            ) as handle:
                json.dump(data, handle, ensure_ascii=False)
            print(f"{key} hours rows={len(data.get('roiStatisticsVos') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
