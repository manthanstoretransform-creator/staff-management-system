# Time Tracking & Manual Time Entry API

Covers three things: the existing `/api/v1/time-tracking` endpoints (extended, not replaced), the
existing `/api/v1/manual-time-entries` endpoint (untouched, still works exactly as before), and a
new `/api/v1/manual-time-entry-requests` resource that adds everything the old one never had
(edit, delete, a proper paginated/searchable review screen).

---

## Auth

Every endpoint below requires a bearer token:

```
Authorization: Bearer <token>
```

Two different permissions gate different things:

- **`time_entries:view_all`** — see other people's time (list-all, review-listing, filtering by
  a member other than yourself). Without it, you only ever see your own.
- **`manual_time_entries:approve`** — approve/reject a manual entry request.

Both are held today by manager/org_admin/admin/super_admin roles, not the plain `employee` role.
Creating your own manual entry, viewing your own time, and editing/deleting your own pending
request need no special permission — anyone logged in can do those for themselves.

---

## 1. `GET /api/v1/time-tracking` — unchanged, plus two additive params

Nothing existing changed shape. Two new optional query params:

| Param | Before | Now |
|---|---|---|
| `employee_id` | one int | **repeatable** — `?employee_id=5&employee_id=9` filters to multiple members. A single old-style `?employee_id=5` still works exactly as before. |
| `search` | didn't exist | matches employee name or email, same convention as `search` elsewhere in the app (e.g. `/api/v1/members`). |

Date filtering is unchanged: pass **one of** `range` (`today`/`7d`/`30d`), `date`, or
`start_date`+`end_date` together — not a combination (`400` if you mix them). No filter at all
defaults to `today`.

```
GET /api/v1/time-tracking?start_date=2026-08-24&end_date=2026-08-27&employee_id=145&employee_id=54&search=hardik&page=1&limit=50
```

Response shape is exactly what it was — `{ items: [...], pagination: {...} }` — just possibly
filtered to more than one employee now.

One small, deliberate behavior change: the old single-`employee_id` call used to 404 if that
specific employee didn't exist in your org. The multi-id version doesn't — a non-matching id (or
combination) just returns zero rows, same as any other filter that matches nothing.

## 2. `GET /api/v1/time-tracking/{employee_id}` — one new field

**This is not a "get one time entry by id" endpoint** — `{employee_id}` is a user id, and the
response is that employee's whole date-range breakdown (projects → tasks → entries). There is no
"fetch a single time_entries row by its own id" endpoint in this system.

The only change: every entry object now carries `is_manual`.

```json
{
  "employee": { "id": 54, "name": "KAIRAV PM", "...": "..." },
  "summary": { "total_seconds": 48166, "total_hours": "13h 22m" },
  "projects": [
    {
      "id": 1272, "name": "Loupedirect- Magento M2 Migration",
      "tasks": [
        {
          "id": 239, "name": "Sprint planning",
          "entries": [
            {
              "id": 2593,
              "start_time": "2026-08-10T00:00:00Z",
              "end_time": "2026-08-10T01:00:00Z",
              "duration_seconds": 3600,
              "is_running": false,
              "is_manual": true
            }
          ]
        }
      ]
    }
  ]
}
```

`is_manual: true` means this row exists because an approved manual time entry request was
mirrored in — see §5.

---

## 3. `POST/GET /api/v1/manual-time-entries` — legacy, untouched

Still exactly what it was — do not change how you call this if it's already working for you.

```json
POST /api/v1/manual-time-entries
{ "project_id": 1272, "task_id": 239, "work_date": "2026-08-10", "total_seconds": 3600, "is_billable": true, "description": "..." }
```

`GET /api/v1/manual-time-entries?task_id=239` still returns a bare array, no pagination
envelope, exactly as before.

**Two things now true underneath, without changing this endpoint's shape:**
- `POST` here now also runs the new overlap/conflict check (§4) and accepts the same optional
  `start_time`/`end_time` fields the new endpoint does (§4) — both purely additive, so existing
  callers that never send them see identical behavior to before.
- `PATCH /manual-time-entries/{id}/approve` and `/reject` now also do the mirroring behavior
  described in §5, since both routers share the same service.

---

## 4. `POST /api/v1/manual-time-entry-requests` — create, with a real time slot

```json
{
  "project_id": 1272,
  "task_id": 239,
  "work_date": "2026-08-10",
  "total_seconds": 5400,
  "start_time": "2026-08-10T14:00:00Z",
  "end_time": "2026-08-10T15:30:00Z",
  "description": "Client call ran over, forgot to switch tasks",
  "is_billable": true
}
```

- `start_time`/`end_time` are **optional**. Provide both or neither.
  - **Provided**: that's the real slot. `total_seconds` is recomputed from it (whatever you send
    is ignored/overwritten) — send your best estimate or `0`, it doesn't matter.
  - **Omitted**: falls back to the original behavior — `start_time` = midnight UTC on
    `work_date`, `end_time` = `start_time + total_seconds`.
- `description` is the reason for the request — there's no separate `reason` field, this project
  already had `description` serving that purpose.
- Response is `ManualTimeEntryRead`, same shape as the legacy endpoint plus
  `mirrored_time_entry_id` (see §5).

### Conflict/overlap validation

A request is rejected with **`409 Conflict`** if its `[start_time, end_time)` slot overlaps:

- Any of your own automatic `time_entries` rows, or
- Any of your own **other** manual requests still `pending` or `approved` (a `rejected` one
  isn't a real time commitment, so it's ignored).

The check runs again at approval time too, in case something else got tracked in the meantime —
so a request that was conflict-free when filed can still come back `409` when someone tries to
approve it later.

---

## 5. Approval workflow

Statuses are **`pending` → `approved` | `rejected`** (not `confirmed` — that's not a value this
system uses anywhere; the DB's CHECK constraint only allows pending/approved/rejected).

```
PATCH /api/v1/manual-time-entry-requests/{id}/approve
PATCH /api/v1/manual-time-entry-requests/{id}/reject
```

Both require `manual_time_entries:approve`. Both `404` if the entry doesn't exist in your org (or
was soft-deleted), and `409` if it's already been decided — a decision is final, there's no
un-approve/un-reject.

**On approval**, a mirrored row is inserted into `time_entries` (`is_manual=true`,
`status='stopped'`, same project/task/user/time/billable/description), and the manual entry's
`mirrored_time_entry_id` is set to that new row's id, atomically with the status change. This is
why `is_manual` shows up in §2's response — an approved manual entry becomes a real, visible
`time_entries` row.

**On rejection**, nothing is mirrored — the request stays as history with `approval_status:
"rejected"`, contributing zero tracked/billable hours anywhere.

**Reporting note:** the [Reports API](Reports_API.md)'s "routed hours" sums `time_entries` +
any *unmirrored* approved manual entries (`mirrored_time_entry_id IS NULL`) — that second half
only exists to still count entries that were approved before this mirroring feature shipped.
Every entry approved from now on is counted exactly once, via its mirror in `time_entries`.

---

## 6. `GET /api/v1/manual-time-entry-requests` — review listing

The reviewer's screen: paginated, searchable, filterable.

| Param | Notes |
|---|---|
| `approval_status` | `pending` \| `approved` \| `rejected` |
| `project_id`, `task_id`, `user_id` | int filters. `user_id` is ignored (forced to yourself) if you lack `time_entries:view_all`. |
| `start_date`, `end_date` | filters on `work_date` |
| `search` | matches the entry's `description`/reason |
| `page`, `limit` | `limit` 1–100, default 20 |

```json
{
  "items": [
    {
      "id": 18, "user_id": 135, "project_id": 1364, "task_id": 248,
      "work_date": "2026-08-07",
      "start_time": "2026-08-07T09:00:00Z", "end_time": "2026-08-07T12:27:01Z",
      "total_seconds": 12421, "description": "...", "is_billable": false,
      "approval_status": "pending", "approved_by": null, "approved_at": null,
      "mirrored_time_entry_id": null,
      "member_name": "Rahul Makhija", "member_email": "rahul@storetransform.ca",
      "project_name": "Hotelkungstradgarden.se SEO Activity", "task_name": "Performance optimization",
      "has_conflict": true
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 16, "total_pages": 1 }
}
```

`has_conflict: true` (computed only for `pending` rows) means this request currently overlaps an
existing `time_entries` row — a heads-up for the reviewer before they approve it; it doesn't
block viewing, only approving.

---

## 7. Edit — `PATCH /api/v1/manual-time-entry-requests/{id}`

Only while `approval_status == "pending"`, only by the entry's own creator (not even an approver
can edit someone else's). `409` once it's been decided, `403` if you're not the owner.

Partial update — send only the fields you're changing:

```json
{ "description": "Updated reason" }
```

Changing any time-related field (`start_time`, `end_time`, `work_date`, or `total_seconds`)
re-runs the same conflict check as create (excluding the entry's own previous slot from the
overlap check, so editing an entry doesn't conflict with itself).

## 8. Delete — `DELETE /api/v1/manual-time-entry-requests/{id}`

Soft delete, `204 No Content`. Only while `pending`; a decided entry is immutable history and
can't be deleted by anyone. Allowed for the entry's own creator (withdrawing their own request)
**or** anyone holding `manual_time_entries:approve` (a reviewer clearing out a stale request).
`403` for anyone else, `409` if it's not pending.

Soft-deleted entries never appear in `GET /api/v1/manual-time-entry-requests` or the legacy
`GET /api/v1/manual-time-entries` — they're gone from every listing, just not physically removed
from the table.

---

## Quick reference

| What | Endpoint |
|---|---|
| List time (existing, extended) | `GET /api/v1/time-tracking` |
| One employee's breakdown (existing, +`is_manual`) | `GET /api/v1/time-tracking/{employee_id}` |
| Create/list manual entry (legacy, unchanged shape) | `POST`/`GET /api/v1/manual-time-entries` |
| Create manual entry (new, supports real start/end) | `POST /api/v1/manual-time-entry-requests` |
| Review manual entries (new, paginated+searchable) | `GET /api/v1/manual-time-entry-requests` |
| Get one manual entry | `GET /api/v1/manual-time-entry-requests/{id}` |
| Edit a pending manual entry | `PATCH /api/v1/manual-time-entry-requests/{id}` |
| Approve / reject | `PATCH /api/v1/manual-time-entry-requests/{id}/approve` \| `/reject` |
| Withdraw a pending manual entry | `DELETE /api/v1/manual-time-entry-requests/{id}` |
