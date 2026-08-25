# React Projects CRUD API Documentation

## Overview
This document provides complete API documentation for the React Projects CRUD endpoints. All endpoints are located under `/api/v1/react/projects/` and require bearer token authentication.

## Base URL
```
/api/v1/react/projects
```

## Authentication
All endpoints require a valid bearer token in the Authorization header:
```
Authorization: Bearer <token>
```

If no bearer token is provided or the token is invalid, all endpoints will return:
- **Status Code:** 401 Unauthorized
- **Response:**
```json
{
  "status_code": 401,
  "message": "Not authenticated",
  "detail": null
}
```

---

## API Endpoints

### 1. CREATE PROJECT (POST)
Create a new project for an organization.

**Endpoint:** `POST /api/v1/react/projects/`

**Status Code:** 201 Created

**Request Body:**
```json
{
  "project_name": "Website Redesign",
  "description": "Complete redesign of the company website",
  "organization_id": 1,
  "start_date": "2026-09-01",
  "deadline": "2026-12-31",
  "is_billable": true,
  "billing_type": "fixed",
  "fixed_hours": 200.50,
  "leader_id": 5,
  "status_id": 1
}
```

**Request Body Parameters:**

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|-----------|-------------|
| project_name | string | ✓ | 1-150 chars | Name of the project |
| organization_id | integer | ✓ | > 0 | Organization ID |
| description | string | ✗ | max 1000 chars | Project description |
| start_date | date | ✗ | ISO format | Project start date |
| deadline | date | ✗ | ISO format | Project deadline |
| is_billable | boolean | ✗ | - | Billable flag (default: true) |
| billing_type | string | ✗ | free\|hourly\|fixed | Billing type (default: free) |
| fixed_hours | number | ✗ | > 0 | Fixed hours for project |
| leader_id | integer | ✗ | > 0 | Project leader user ID |
| status_id | integer | ✗ | > 0 | Project status ID |

**Response (201 Created):**
```json
{
  "id": 123,
  "organization_id": 1,
  "project_name": "Website Redesign",
  "description": "Complete redesign of the company website",
  "status": "planning",
  "status_id": 1,
  "leader_id": 5,
  "deadline": "2026-12-31",
  "billing_type": "fixed",
  "fixed_hours": 200.50,
  "start_date": "2026-09-01",
  "completed_at": null,
  "is_billable": true,
  "time_tracked_seconds": 0,
  "created_by": 10,
  "created_at": "2026-08-25T14:30:00Z",
  "updated_at": "2026-08-25T14:30:00Z"
}
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Bad Request | Invalid request parameters |
| 409 | Conflict | Project with same name already exists in organization |
| 401 | Unauthorized | No/invalid bearer token |
| 500 | Server Error | Internal server error |

**Example cURL:**
```bash
curl -X POST http://localhost:8000/api/v1/react/projects/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "Website Redesign",
    "description": "Complete redesign of the company website",
    "organization_id": 1,
    "start_date": "2026-09-01",
    "deadline": "2026-12-31",
    "is_billable": true,
    "billing_type": "fixed",
    "fixed_hours": 200.50,
    "leader_id": 5
  }'
```

---

### 2. LIST PROJECTS (GET with Pagination)
List all projects with advanced filtering, sorting, and pagination.

**Endpoint:** `GET /api/v1/react/projects/?organization_id=1&page=1&limit=20`

**Status Code:** 200 OK

**Query Parameters:**

| Parameter | Type | Required | Default | Validation | Description |
|-----------|------|----------|---------|-----------|-------------|
| organization_id | integer | ✓ | - | > 0 | Organization ID to filter by |
| page | integer | ✗ | 1 | >= 1 | Page number (1-indexed) |
| limit | integer | ✗ | 20 | 1-100 | Items per page |
| search | string | ✗ | null | max 100 chars | Search projects by name/description |
| status | string | ✗ | null | planning\|active\|pending\|todo\|completed\|cancelled\|archived | Filter by status |
| is_billable | boolean | ✗ | null | - | Filter by billable status |
| leader_id | integer | ✗ | null | > 0 | Filter by project leader |
| sort_by | string | ✗ | created_at | created_at\|project_name\|deadline\|start_date\|updated_at | Sort field |
| sort_order | string | ✗ | desc | asc\|desc | Sort order |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": 123,
      "organization_id": 1,
      "project_name": "Website Redesign",
      "description": "Complete redesign of the company website",
      "status": "active",
      "status_id": 1,
      "leader_id": 5,
      "deadline": "2026-12-31",
      "billing_type": "fixed",
      "fixed_hours": 200.50,
      "start_date": "2026-09-01",
      "completed_at": null,
      "is_billable": true,
      "time_tracked_seconds": 3600,
      "created_by": 10,
      "created_at": "2026-08-25T14:30:00Z",
      "updated_at": "2026-08-25T14:30:00Z"
    },
    {
      "id": 124,
      "organization_id": 1,
      "project_name": "Mobile App Development",
      "description": "Develop iOS and Android app",
      "status": "planning",
      "status_id": null,
      "leader_id": 6,
      "deadline": "2026-10-31",
      "billing_type": "hourly",
      "fixed_hours": null,
      "start_date": "2026-09-15",
      "completed_at": null,
      "is_billable": true,
      "time_tracked_seconds": 0,
      "created_by": 10,
      "created_at": "2026-08-24T10:15:00Z",
      "updated_at": "2026-08-24T10:15:00Z"
    }
  ],
  "pagination": {
    "total": 2,
    "page": 1,
    "limit": 20,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

**Filter Examples:**

1. **Search projects:**
```
GET /api/v1/react/projects/?organization_id=1&search=website
```

2. **Filter by status and billable:**
```
GET /api/v1/react/projects/?organization_id=1&status=active&is_billable=true
```

3. **Filter by leader and sort by deadline:**
```
GET /api/v1/react/projects/?organization_id=1&leader_id=5&sort_by=deadline&sort_order=asc
```

4. **Paginate with 10 items per page:**
```
GET /api/v1/react/projects/?organization_id=1&page=2&limit=10
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Bad Request | Invalid sort_by or sort_order |
| 401 | Unauthorized | No/invalid bearer token |
| 500 | Server Error | Internal server error |

**Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1&page=1&limit=20&sort_by=created_at&sort_order=desc" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 3. GET SINGLE PROJECT (GET)
Retrieve details of a specific project.

**Endpoint:** `GET /api/v1/react/projects/{project_id}?organization_id=1`

**Status Code:** 200 OK

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| project_id | integer | ✓ | Project ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| organization_id | integer | ✓ | Organization ID |

**Response (200 OK):**
```json
{
  "id": 123,
  "organization_id": 1,
  "project_name": "Website Redesign",
  "description": "Complete redesign of the company website",
  "status": "active",
  "status_id": 1,
  "leader_id": 5,
  "deadline": "2026-12-31",
  "billing_type": "fixed",
  "fixed_hours": 200.50,
  "start_date": "2026-09-01",
  "completed_at": null,
  "is_billable": true,
  "time_tracked_seconds": 3600,
  "created_by": 10,
  "created_at": "2026-08-25T14:30:00Z",
  "updated_at": "2026-08-25T14:30:00Z"
}
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | Not Found | Project not found |
| 401 | Unauthorized | No/invalid bearer token |
| 500 | Server Error | Internal server error |

**Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 4. UPDATE PROJECT (PUT)
Perform a full update of a project. All fields in the request body are processed.

**Endpoint:** `PUT /api/v1/react/projects/{project_id}?organization_id=1`

**Status Code:** 200 OK

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| project_id | integer | ✓ | Project ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| organization_id | integer | ✓ | Organization ID |

**Request Body:**
```json
{
  "project_name": "Website Redesign - Updated",
  "description": "Complete redesign with new features",
  "start_date": "2026-09-01",
  "deadline": "2027-01-31",
  "completed_at": null,
  "is_billable": true,
  "status": "active",
  "billing_type": "fixed",
  "fixed_hours": 250.00,
  "leader_id": 5,
  "status_id": 1
}
```

**Request Body Parameters:** (All optional)

| Parameter | Type | Validation | Description |
|-----------|------|-----------|-------------|
| project_name | string | 1-150 chars | Project name |
| description | string | max 1000 chars | Project description |
| start_date | date | ISO format | Start date |
| deadline | date | ISO format | Deadline |
| completed_at | datetime | ISO format | Completion time |
| is_billable | boolean | - | Billable flag |
| status | string | planning\|active\|pending\|todo\|completed\|cancelled\|archived | Status |
| billing_type | string | free\|hourly\|fixed | Billing type |
| fixed_hours | number | > 0 | Fixed hours |
| leader_id | integer | > 0 | Project leader ID |
| status_id | integer | > 0 | Status ID |

**Response (200 OK):**
```json
{
  "id": 123,
  "organization_id": 1,
  "project_name": "Website Redesign - Updated",
  "description": "Complete redesign with new features",
  "status": "active",
  "status_id": 1,
  "leader_id": 5,
  "deadline": "2027-01-31",
  "billing_type": "fixed",
  "fixed_hours": 250.00,
  "start_date": "2026-09-01",
  "completed_at": null,
  "is_billable": true,
  "time_tracked_seconds": 3600,
  "created_by": 10,
  "created_at": "2026-08-25T14:30:00Z",
  "updated_at": "2026-08-25T15:45:00Z"
}
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | Not Found | Project not found |
| 409 | Conflict | Project name already exists |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | No/invalid bearer token |
| 500 | Server Error | Internal server error |

**Example cURL:**
```bash
curl -X PUT "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "Website Redesign - Updated",
    "deadline": "2027-01-31",
    "fixed_hours": 250.00,
    "status": "active"
  }'
```

---

### 5. PARTIAL UPDATE PROJECT (PATCH)
Perform a partial update of a project. Only fields provided in the request body are updated.

**Endpoint:** `PATCH /api/v1/react/projects/{project_id}?organization_id=1`

**Status Code:** 200 OK

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| project_id | integer | ✓ | Project ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| organization_id | integer | ✓ | Organization ID |

**Request Body:**
```json
{
  "status": "completed",
  "completed_at": "2026-12-31T17:00:00Z"
}
```

**Request Body Parameters:** (All optional - only send fields to update)

| Parameter | Type | Validation | Description |
|-----------|------|-----------|-------------|
| project_name | string | 1-150 chars | Project name |
| description | string | max 1000 chars | Project description |
| start_date | date | ISO format | Start date |
| deadline | date | ISO format | Deadline |
| completed_at | datetime | ISO format | Completion time |
| is_billable | boolean | - | Billable flag |
| status | string | planning\|active\|pending\|todo\|completed\|cancelled\|archived | Status |
| billing_type | string | free\|hourly\|fixed | Billing type |
| fixed_hours | number | > 0 | Fixed hours |
| leader_id | integer | > 0 | Project leader ID |
| status_id | integer | > 0 | Status ID |

**Response (200 OK):**
```json
{
  "id": 123,
  "organization_id": 1,
  "project_name": "Website Redesign",
  "description": "Complete redesign of the company website",
  "status": "completed",
  "status_id": 1,
  "leader_id": 5,
  "deadline": "2026-12-31",
  "billing_type": "fixed",
  "fixed_hours": 200.50,
  "start_date": "2026-09-01",
  "completed_at": "2026-12-31T17:00:00Z",
  "is_billable": true,
  "time_tracked_seconds": 3600,
  "created_by": 10,
  "created_at": "2026-08-25T14:30:00Z",
  "updated_at": "2026-08-25T16:00:00Z"
}
```

**Differences from PUT:**
- PATCH only updates fields explicitly provided in the request body
- Omitted fields are not modified
- PUT requires all fields and updates everything

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | Not Found | Project not found |
| 409 | Conflict | Project name already exists |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | No/invalid bearer token |
| 500 | Server Error | Internal server error |

**Example cURL:**
```bash
curl -X PATCH "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "completed_at": "2026-12-31T17:00:00Z"
  }'
```

---

### 6. DELETE PROJECT (DELETE)
Delete a project permanently.

**Endpoint:** `DELETE /api/v1/react/projects/{project_id}?organization_id=1`

**Status Code:** 204 No Content

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| project_id | integer | ✓ | Project ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| organization_id | integer | ✓ | Organization ID |

**Response (204 No Content):**
```
(Empty body)
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 404 | Not Found | Project not found |
| 401 | Unauthorized | No/invalid bearer token |
| 500 | Server Error | Internal server error |

**Example cURL:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Error Response Format

All error responses follow this format:

```json
{
  "status_code": 400,
  "message": "Error message",
  "detail": "Additional details about the error"
}
```

---

## Status Codes Reference

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid parameters or validation error |
| 401 | Unauthorized | Missing or invalid bearer token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate unique constraint (e.g., project name) |
| 500 | Server Error | Internal server error |

---

## Project Status Values

| Status | Description |
|--------|-------------|
| planning | Project is in planning phase |
| active | Project is actively in progress |
| pending | Project is pending (paused) |
| todo | Project has tasks pending |
| completed | Project is completed |
| cancelled | Project has been cancelled |
| archived | Project has been archived |

---

## Billing Type Values

| Type | Description |
|------|-------------|
| free | No billing |
| hourly | Hourly billing rate |
| fixed | Fixed price project |

---

## Important Notes

1. **Pagination:** When listing projects, the API always returns pagination metadata including `total`, `page`, `limit`, `total_pages`, `has_next`, and `has_prev`.

2. **Bearer Token:** All requests must include a valid bearer token in the Authorization header. The token is verified on the server side.

3. **Organization Scoping:** All projects are scoped to an organization. The `organization_id` must be provided for listing and retrieval operations.

4. **Timestamps:** All timestamps are returned in ISO 8601 format with timezone information (UTC).

5. **Unique Constraint:** Project names must be unique within an organization. Attempting to create or update a project with a duplicate name will result in a 409 Conflict error.

6. **Default Values:**
   - `status`: "planning"
   - `is_billable`: true
   - `billing_type`: "free"
   - `time_tracked_seconds`: 0

7. **Read-Only Fields:** The following fields are automatically managed and cannot be set in requests:
   - `id` (auto-generated)
   - `created_by` (set to current user)
   - `created_at` (set to current timestamp)
   - `updated_at` (set to current timestamp, updated on changes)

---

## Quick Examples

### Create a simple project
```bash
curl -X POST http://localhost:8000/api/v1/react/projects/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "New Project",
    "organization_id": 1
  }'
```

### Get all active projects sorted by name
```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1&status=active&sort_by=project_name&sort_order=asc" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Update project status only
```bash
curl -X PATCH "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed"
  }'
```

### Delete a project
```bash
curl -X DELETE "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```
