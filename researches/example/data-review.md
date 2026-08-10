# Обзор данных

Найдено CSV: **2**.


## `events.csv`

- Строк (без заголовка): **2164**
- Размер: **135.4 KB**
- Колонки (9): `user_id`, `session_id`, `event_name`, `event_timestamp`, `cart_value`, `cart_item_count`, `app_version`, `is_checkout_redesign`, `traffic_source`

### Пропуски (пустые / null-like)
- `user_id`: 0 (0.0%)
- `session_id`: 0 (0.0%)
- `event_name`: 0 (0.0%)
- `event_timestamp`: 0 (0.0%)
- `cart_value`: 0 (0.0%)
- `cart_item_count`: 0 (0.0%)
- `app_version`: 0 (0.0%)
- `is_checkout_redesign`: 0 (0.0%)
- `traffic_source`: 0 (0.0%)

### Пример строк

| user_id | session_id | event_name | event_timestamp | cart_value | cart_item_count | app_version | is_checkout_redesign | traffic_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u0001 | s00001 | cart | 2026-07-15 11:48:00 | 87.93 | 5 | 5.2.0 | 1 | organic |
| u0001 | s00001 | checkout | 2026-07-15 12:04:20 | 87.93 | 5 | 5.2.0 | 1 | paid |
| u0001 | s00001 | payment | 2026-07-15 12:16:36 | 87.93 | 5 | 5.2.0 | 1 | push |
| u0001 | s00001 | purchase | 2026-07-15 12:26:11 | 87.93 | 5 | 5.2.0 | 1 | organic |
| u0002 | s00002 | cart | 2026-06-12 11:46:00 | 77.91 | 5 | 5.1.3 | 0 | paid |


## `users.csv`

- Строк (без заголовка): **400**
- Размер: **7.9 KB**
- Колонки (3): `user_id`, `first_seen_date`, `prior_purchase_count`

### Пропуски (пустые / null-like)
- `user_id`: 0 (0.0%)
- `first_seen_date`: 0 (0.0%)
- `prior_purchase_count`: 0 (0.0%)

### Пример строк

| user_id | first_seen_date | prior_purchase_count |
| --- | --- | --- |
| u0001 | 2026-07-20 | 0 |
| u0002 | 2026-06-11 | 5 |
| u0003 | 2026-06-27 | 0 |
| u0004 | 2026-06-24 | 0 |
| u0005 | 2026-06-16 | 5 |
