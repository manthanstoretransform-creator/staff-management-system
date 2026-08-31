# Member Usage API — Details + Daily Activity/App/URL Usage

Backend for a member details page: profile info plus daily keyboard/mouse activity,
application usage, and URL/browser usage for one member.

Lives at `backend/app/react_apis/member_usage.py`, registered at `/api/v1/members/*` — a
separate router from `backend/app/api/members.py` (the members CRUD API), since `/details` is a
distinct path suffix from that router's `/api/v1/members/{member_id}`, not a collision.

---

## Auth

Requires a bearer token and the `view_employees` permission (same gate as
`GET /api/v1/members/{member_id}` and `GET /api/v1/employees/{user_id}`). Every role that has
`view_employees` also has `time_entries:view_all` today (`app/core/permissions.py`), so this
doesn't relax who can see a member's tracked-time detail — it uses the permission that matches
this endpoint's own framing as a member-details page.

```
Authorization: Bearer <token>
```

- No/invalid token → `401 Unauthorized`
- Valid token but missing `view_employees` → `403 Forbidden`
- `member_id` not found, or belongs to another organization → `404 Not Found`

---

## `GET /api/v1/members/{member_id}/details`

| Param | Type | Required | Notes |
|---|---|---|---|
| `date` | `YYYY-MM-DD` | one of `date` or the range, always required | Restrict usage to a single day. Mutually exclusive with `start_date`/`end_date` (`400` if both given). |
| `start_date` / `end_date` | `YYYY-MM-DD` | one of `date` or the range, always required | Inclusive date range; must be given together (`400` if only one is set, or `start_date > end_date`). Capped at **31 days** — `400` if the span is longer. |

Unlike `/api/v1/reports/project-task-summary`, a date filter is **mandatory** here, and range
length is capped. That endpoint returns aggregated sums (bounded response size regardless of
range); this one returns an unpaginated per-day breakdown of every distinct application and URL,
so an unbounded range could return years of nested detail in a single response.

```
GET /api/v1/members/123/details?start_date=2026-08-01&end_date=2026-08-31
```

```json
{
  "member": {
    "id": 123,
    "name": "John Doe",
    "email": "john@example.com",
    "role": "employee",
    "status": "active",
    "designation": "Software Engineer",
    "date_of_joining": "2025-01-15",
    "date_of_birth": "1995-06-20",
    "created_at": "2025-01-15T09:00:00Z",
    "updated_at": "2026-08-20T12:00:00Z",
    "organization": { "id": 10, "name": "Example Organization" }
  },
  "start_date": "2026-08-01",
  "end_date": "2026-08-31",
  "daily_activity": [
    { "date": "2026-08-31", "keyboard_strokes": 1250, "mouse_clicks": 340, "mouse_movements": 890, "activity_percentage": 72 }
  ],
  "application_usage": [
    {
      "date": "2026-08-31",
      "applications": [
        { "application_name": "Google Chrome", "duration_seconds": 7200, "duration": "2h 0m", "usage_percentage": 60 },
        { "application_name": "Visual Studio Code", "duration_seconds": 3600, "duration": "1h 0m", "usage_percentage": 30 },
        { "application_name": "Slack", "duration_seconds": 1200, "duration": "20m", "usage_percentage": 10 }
      ]
    }
  ],
  "url_usage": [
    {
      "date": "2026-08-31",
      "urls": [
        { "browser_name": "Chrome", "domain": "github.com", "url": "https://github.com/org/repo", "page_title": "GitHub", "duration_seconds": 5400, "duration": "1h 30m", "usage_percentage": 50 }
      ]
    }
  ]
}
```

### `member`

Everything the existing `MemberResponse` (`app/api/members.py`) already exposes, plus
`organization` — looked up with a small raw-SQL read (`SELECT name FROM organizations WHERE id = :id`),
mirroring the exact pattern `app/services/auth.py` already uses for this table. There's no
SQLAlchemy `Organization` model: `app/models/user.py` registers `organizations` as a bare stub
`Table(id)` so `User`'s FK can resolve, and mapping a second declarative model over that same
table name would collide with it.

### `daily_activity`

One entry per day with data, summed `keyboard_strokes`/`mouse_clicks`/`mouse_movements` and the
average `activity_percentage` (rounded to a whole number) across all `time_entry_activity` rows
that day, joined through `time_entries` to this member. **Expect this to come back `[]` for
essentially every member today** — per `docs/Database_Documentation.md` and the model's own
docstring, `time_entry_activity` has no writer wired up yet (CLAUDE.md §5.1, a known open item:
the desktop's activity batch-sync endpoint doesn't exist). The query is correct and will start
returning real rows once that pipeline ships; this isn't a bug in this endpoint.

### `application_usage`

One entry per day, `applications` aggregated **by application name** (every session/window of
that app that day summed into one row), sorted by `duration_seconds` descending.
`usage_percentage = that app's seconds / total tracked-app seconds that day × 100`, rounded to a
whole number. `duration` is formatted with the same `Xh Ym` helper `/api/v1/reports/*` already
uses (`TimeTrackingService._hours`) — note it isn't zero-padded (`"2h 0m"`, not `"2h 00m"`),
reusing the existing convention rather than introducing a second formatter.

### `url_usage`

One entry per day, `urls` kept **per distinct URL/page** (not aggregated up to one row per
domain) — grouped by `(day, browser_name, domain, url, page_title)`, sorted by
`duration_seconds` descending. `usage_percentage` is computed against that day's total URL
seconds, same rounding as application usage. A frontend that wants a domain-level rollup can sum
these client-side without losing the per-page detail this shape preserves.

---

## Performance

- Every query aggregates in SQL (`GROUP BY` day, or day + dimension) and joins to `time_entries`
  only to reach `user_id` — no raw sample rows are pulled into Python to be summed there.
- Each of the three tables is filtered by its own `organization_id` and by `recorded_at` range
  before the join, and the join itself is on `time_entry_id` — the indexed columns the spec
  called out.
- Three queries total (one per table) regardless of date-range length or number of
  distinct apps/domains — no N+1 across days.
