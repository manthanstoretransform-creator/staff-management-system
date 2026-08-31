# Reports API — Projects / Members / Tasks / Apps

Backend for `/dashboard-v2/reports/{projects|members|tasks|apps}`. Implements **Approach B**
(server-side grouping + a paginated detail endpoint) from the integration plan, not Approach A
(one flat `all-logs` array) — see [Why Approach B](#why-approach-b-not-a-flat-all-logs-array)
for what that means for `ReportPage.tsx`.

All endpoints live under `backend/app/react_apis/reports.py`, registered at `/api/v1/reports/*`.

**Update (2026-08-28):** approving a manual time entry now mirrors it into `time_entries`
(`is_manual=true`) instead of staying a separate row forever — see
[Time_Tracking_And_Manual_Entries_API.md §5](Time_Tracking_And_Manual_Entries_API.md#5-approval-workflow).
The queries here already account for this (excluding mirrored `manual_time_entries` rows from
their own separate sums so nothing double counts), so the numbers in this doc are unaffected —
noted here only so `te-`/`mte-` prefixes in `detailed-logs` make sense: an approved entry shows
up as `te-` (its mirror) going forward, not `mte-`, even though it originated as a manual request.

---

## Auth

Every endpoint requires a bearer token and the `time_entries:view_all` permission (the same gate
`/api/v1/time-tracking` already uses for viewing other people's tracked time — held by
manager/org_admin/admin/super_admin roles today, not the plain `employee` role).

```
Authorization: Bearer <token>
```

- No/invalid token → `401 Unauthorized`
- Valid token but missing the permission → `403 Forbidden`

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/reports/projects` | Grouped by project — powers the Projects report's top chart + tiles |
| GET | `/api/v1/reports/members` | Grouped by member |
| GET | `/api/v1/reports/tasks` | Grouped by task |
| GET | `/api/v1/reports/apps` | Grouped by application or by domain (`usage_type`) |
| GET | `/api/v1/reports/detailed-logs` | Paginated row-by-row log — powers every report page's bottom "Detailed Activity" table |

### Shared query parameters (all 5 endpoints)

| Param | Type | Required | Notes |
|---|---|---|---|
| `from` | `YYYY-MM-DD` | yes | Start of range, inclusive |
| `to` | `YYYY-MM-DD` | yes | End of range, inclusive. `400` if `from > to`. |
| `member_id` | int, repeatable | no | `?member_id=1&member_id=2`. Omit for all members. |
| `project_id` | int, repeatable | no | `?project_id=91&project_id=99`. Omit for all projects. |
| `billing_type` | `billable` \| `non-billable` | no | Filters by the **project's** `is_billable` flag. Omit for both. |

There is no hard cap on the date-range span — every endpoint here is either aggregated
(grouped endpoints) or paginated (`detailed-logs`), so an unbounded date range doesn't produce an
unbounded payload the way a flat "all logs" array would have.

---

## Grouped endpoints

### `GET /api/v1/reports/projects`

```
GET /api/v1/reports/projects?from=2026-08-01&to=2026-08-27
```

```json
{
  "start_date": "2026-08-01",
  "end_date": "2026-08-27",
  "summary": {
    "total_hours": 4230.81,
    "total_tracked_seconds": 15230934,
    "total_hours_formatted": "4230h 48m",
    "average_activity_percentage": 64.84,
    "total_members": 38,
    "total_entries": 1970,
    "total_projects": 23,
    "total_tasks": null,
    "total_apps": null
  },
  "grouped_data": [
    {
      "id": 2152,
      "name": "The Fascialab – Hubstaff – WordPress LearnDash Project",
      "tracked_seconds": 1097660,
      "tracked_hours": 304.91,
      "tracked_hours_formatted": "304h 54m",
      "activity_percentage": 63.35,
      "meta_label": "8 members · 6 tasks"
    }
  ]
}
```

### `GET /api/v1/reports/members`

Same shape. `grouped_data[].id` is the user id, `meta_label` is `"N projects, M tasks"`
(matches the example in the original integration request verbatim), `summary.total_projects` is
always `null` here (only the endpoint's own dimension count is populated — see
[`summary` field reference](#summary-field-reference)).

```json
{
  "id": 120,
  "name": "Kirti Yadav",
  "tracked_seconds": 822278,
  "tracked_hours": 228.41,
  "tracked_hours_formatted": "228h 24m",
  "activity_percentage": 64.05,
  "meta_label": "4 projects, 16 tasks"
}
```

### `GET /api/v1/reports/tasks`

`grouped_data[].id` is the task id, `meta_label` is the **project name** the task belongs to
(disambiguates tasks that share a name across projects). `summary.total_tasks` is populated.

```json
{
  "id": 259,
  "name": "Security audit",
  "tracked_seconds": 257242,
  "tracked_hours": 71.46,
  "tracked_hours_formatted": "71h 27m",
  "activity_percentage": 68.27,
  "meta_label": "innovativesourcing-deepu upwork-wordpress"
}
```

### `GET /api/v1/reports/apps`

Extra param: **`usage_type`** = `app` (default) or `url`. `app` groups by application name
(from `time_entry_app_usage`); `url` groups by domain (from `time_entry_url_usage`). These are
genuinely different source tables — call the endpoint twice (once per `usage_type`) to power the
UI's App/URL tab toggle, same as the mock data's `usageTab` state did.

```
GET /api/v1/reports/apps?from=2026-08-20&to=2026-08-27&usage_type=app
```

```json
{
  "summary": {
    "total_hours": 1.97,
    "average_activity_percentage": 66.41,
    "total_members": 2,
    "total_entries": 683,
    "total_apps": 19
  },
  "grouped_data": [
    { "id": "python", "name": "python", "tracked_hours": 0.51, "activity_percentage": 69.6, "meta_label": "2 members" }
  ]
}
```

`grouped_data[].id`/`name` are the app name or domain string itself (there's no numeric id for
an application or a domain).

**Activity % on apps rows is an approximation** — it's the average activity of the *sessions*
during which that app/domain was used, not a per-second-of-that-app-specifically figure (nothing
captures activity at that granularity). Disclosed here rather than silently presented as more
precise than it is.

---

## `GET /api/v1/reports/detailed-logs`

Powers the bottom table on every report page. Extra query params beyond the shared ones:

| Param | Type | Default | Notes |
|---|---|---|---|
| `dimension` | `projects`\|`members`\|`tasks`\|`apps` | `projects` | See [row grain](#detailed-logs-row-grain-matters) below — `projects`/`members`/`tasks` all return identical rows; only `apps` differs. |
| `usage_type` | `app`\|`url` | `app` | Only used when `dimension=apps`. |
| `search` | string | — | Case-insensitive match against member name, project name, task name, and (apps dimension only) app/domain. |
| `sort_by` | `date`\|`member`\|`project`\|`task`\|`hours`\|`activity` | `date` | |
| `sort_desc` | bool | `true` | |
| `page` | int ≥ 1 | `1` | |
| `limit` | int, 1–200 | `50` | |

```
GET /api/v1/reports/detailed-logs?from=2026-08-01&to=2026-08-27&dimension=projects&sort_by=hours&sort_desc=true&page=1&limit=50
```

```json
{
  "start_date": "2026-08-01",
  "end_date": "2026-08-27",
  "items": [
    {
      "id": "te-273",
      "date": "2026-08-24",
      "member_id": 145,
      "member_name": "Hardik Raval",
      "role": "employee",
      "project_id": 93,
      "project_name": "test default project-2",
      "task_id": 189,
      "task_name": "Project Setup / Understanding",
      "app": null,
      "url": null,
      "tracked_hours": 15.8,
      "activity_percentage": 44.5
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 637, "total_pages": 13 }
}
```

`id` prefixes tell you the row's real source table, in case you need it for a detail link or a
React key: `te-` = automatic `time_entries`, `mte-` = approved `manual_time_entries`, `au-` = an
app-usage sample, `uu-` = a URL-usage sample.

### Detailed-logs row grain matters

The mock's `ReportRow` put a single fabricated `app`/`url`/`category` on every daily row,
regardless of which report page it powered. The real data doesn't support that honestly — a work
session can touch several apps, and app/URL usage is captured in separate tables with their own
durations, not tied 1:1 to "the project/task worked on that day." So:

- **`dimension=projects` / `members` / `tasks`** → rows are **session-grain**: one row per
  `time_entries` row (auto-tracked) or approved `manual_time_entries` row, with real
  `tracked_hours` = that session's length. `app` and `url` are always `null` here — a session
  isn't honestly "one app." `activity_percentage` is `null` for manual rows (never
  activity-sampled) and real for auto rows once activity data exists (see caveat below).
- **`dimension=apps`** → rows are **usage-grain**: one row per `time_entry_app_usage` (or
  `time_entry_url_usage`) sample, with `tracked_hours` = that specific app/URL usage's own
  duration. `app` is populated when `usage_type=app`, `url` when `usage_type=url` — never both on
  the same row, since each row comes from only one of those two tables.

If the frontend needs the exact same rows to power all four report pages simultaneously the way
the mock did, that isn't available honestly from the current schema — this was raised and agreed
in scoping (dimension-aware rows was the chosen design over fabricating attribution).

---

## `summary` field reference

Every grouped endpoint returns the same `summary` shape; only the field matching that endpoint's
own dimension is non-null:

| Field | Meaning | Non-null on |
|---|---|---|
| `total_hours` / `total_tracked_seconds` / `total_hours_formatted` | Sum across everything in `grouped_data` | all |
| `average_activity_percentage` | **Sample-weighted** average (not a naive average of per-row averages — a row backed by 500 activity samples counts more than one backed by 1) | all |
| `total_members` | Distinct members with matching data | all |
| `total_entries` | Count of raw log rows behind this result (session rows, or app/url usage rows for `/apps`) | all |
| `total_projects` | Distinct projects | `/reports/projects` only |
| `total_tasks` | Distinct tasks | `/reports/tasks` only |
| `total_apps` | Distinct apps/domains | `/reports/apps` only |

**A project/member/task/app with zero matching hours in range never appears in `grouped_data`**,
even if you explicitly filtered to it by `member_id`/`project_id` — an empty result there is
correct and expected, not a bug.

---

## What's intentionally *not* in the response

- **No `category` (Productive/Neutral/Unproductive) field.** The mock invented this per
  app/URL; there is no classification of any kind in the real schema or backend. Rather than
  fabricate a productivity judgment with no rule behind it, this API omits the field entirely.
  If/when a real categorization feature exists, it can be added as an additive field later.
- **`role` is the raw `role_name`** as stored (`"employee"`, `"leader"`, `"admin"`, ...), not
  title-cased — matches how every other endpoint in this codebase returns it (e.g.
  `/api/v1/members`). Format it for display client-side if needed.

---

## Why Approach B, not a flat `all-logs` array

`ReportPage.tsx` currently does 100% of its grouping/sorting/searching/pagination client-side
over one flat mock array, which is exactly what Approach A's `/reports/all-logs` was designed to
slot into with zero frontend changes. Approach B was chosen instead (server-side aggregation +
pagination) for scale, which means **`ReportPage.tsx`'s client-side `useMemo` grouping, sorting,
search, and pagination logic needs to be replaced with calls to these endpoints** — the "zero UI
changes" framing from the original request doesn't hold under Approach B. Concretely:

- The top "Hours by X" chart's data comes from `grouped_data` on the matching `/reports/{dimension}`
  call instead of a client-side `Map` grouped from `reportRows`.
- The bottom "Detailed Activity" table's rows, sort, search, and pagination all move to
  `/reports/detailed-logs` query params instead of `Array.sort`/`.filter`/`.slice` in the
  component.
- The summary tiles read straight from `summary` instead of being derived from `filtered`.
- CSV export (`handleExport`/`handleExportSummary`) needs to either fetch all pages first or
  export the currently-loaded page — worth deciding explicitly rather than assuming.

Happy to also take a pass at wiring `ReportPage.tsx` itself if useful — flag it and I'll scope
that separately.
