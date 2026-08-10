#!/usr/bin/env python3
"""Generate demo CSVs for example research — intentionally WITHOUT platform."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "researches" / "example" / "data"
RELEASE = datetime(2026, 7, 1, 0, 0, 0)
PRE_START = RELEASE - timedelta(days=21)
POST_END = RELEASE + timedelta(days=21)

FUNNEL = ["cart", "checkout", "payment", "purchase"]
# Drop probabilities by step index → next (pre vs post). Post is worse to mimic redesign hit.
# Without platform we cannot split mobile/web — that's the point of the test.
DROP_PRE = [0.25, 0.18, 0.12]  # after cart, checkout, payment
DROP_POST = [0.28, 0.32, 0.22]


def _users(n: int, rng: random.Random) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        first = PRE_START + timedelta(days=rng.randint(0, 40))
        rows.append(
            {
                "user_id": f"u{i:04d}",
                "first_seen_date": first.date().isoformat(),
                "prior_purchase_count": rng.choice([0, 0, 0, 1, 2, 5]),
            }
        )
    return rows


def _session_events(
    *,
    user_id: str,
    session_id: str,
    start: datetime,
    drop_rates: list[float],
    redesign: int,
    rng: random.Random,
) -> list[dict]:
    rows = []
    t = start
    cart_value = round(rng.uniform(8, 180), 2)
    items = rng.randint(1, 6)
    for idx, name in enumerate(FUNNEL):
        rows.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "event_name": name,
                "event_timestamp": t.isoformat(sep=" "),
                "cart_value": f"{cart_value:.2f}",
                "cart_item_count": str(items),
                "app_version": "5.2.0" if redesign else "5.1.3",
                "is_checkout_redesign": str(redesign),
                "traffic_source": rng.choice(["organic", "paid", "push", "organic", "paid"]),
            }
        )
        if idx >= len(drop_rates):
            break
        if rng.random() < drop_rates[idx]:
            break
        t += timedelta(minutes=rng.randint(1, 18), seconds=rng.randint(0, 50))
    return rows


def main() -> None:
    rng = random.Random(42)
    OUT.mkdir(parents=True, exist_ok=True)

    users = _users(400, rng)
    events: list[dict] = []
    sid = 0

    for u in users:
        # 1–3 sessions per user across pre/post
        for _ in range(rng.randint(1, 3)):
            sid += 1
            post = rng.random() < 0.55
            if post:
                start = RELEASE + timedelta(
                    days=rng.randint(0, 20),
                    hours=rng.randint(8, 22),
                    minutes=rng.randint(0, 59),
                )
                drops = DROP_POST
                redesign = 1
            else:
                start = PRE_START + timedelta(
                    days=rng.randint(0, 20),
                    hours=rng.randint(8, 22),
                    minutes=rng.randint(0, 59),
                )
                drops = DROP_PRE
                redesign = 0
            events.extend(
                _session_events(
                    user_id=u["user_id"],
                    session_id=f"s{sid:05d}",
                    start=start,
                    drop_rates=drops,
                    redesign=redesign,
                    rng=rng,
                )
            )

    users_path = OUT / "users.csv"
    events_path = OUT / "events.csv"

    with users_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["user_id", "first_seen_date", "prior_purchase_count"]
        )
        w.writeheader()
        w.writerows(users)

    event_fields = [
        "user_id",
        "session_id",
        "event_name",
        "event_timestamp",
        "cart_value",
        "cart_item_count",
        "app_version",
        "is_checkout_redesign",
        "traffic_source",
    ]
    with events_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=event_fields)
        w.writeheader()
        w.writerows(events)

    print(f"Wrote {users_path} ({len(users)} rows)")
    print(f"Wrote {events_path} ({len(events)} rows)")
    print("NOTE: platform column intentionally omitted.")


if __name__ == "__main__":
    main()
