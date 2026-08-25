# React Projects CRUD API - Implementation Guide

## Overview
This guide explains the structure and implementation of the new React Projects CRUD API created for frontend consumption.

## Files Created

### 1. `/backend/app/schemas/react_projects.py`
**Purpose:** Pydantic models for request/response validation

**Contains:**
- `ProjectStatus` - Enum for project status values
- `BillingType` - Enum for billing type values
- `ProjectCreateRequest` - Schema for POST requests
- `ProjectUpdateRequest` - Schema for PUT requests
- `ProjectPatchRequest` - Schema for PATCH requests
- `ProjectResponse` - Schema for response data
- `PaginationMetadata` - Schema for pagination info
- `ProjectListResponse` - Schema for list responses
- `ErrorResponse` - Schema for error responses

### 2. `/backend/app/repositories/react_projects.py`
**Purpose:** Data access layer for project operations

**Key Methods:**
- `get_project_by_id()` - Get single project with org verification
- `list_projects()` - List with pagination, filtering, and sorting
- `create_project()` - Create new project
- `update_project()` - Full update (PUT)
- `patch_project()` - Partial update (PATCH)
- `delete_project()` - Delete project
- `check_project_exists()` - Check for duplicate names
- `get_organization_id_for_project()` - Get org ID for auth checks

### 3. `/backend/app/react_api/projects.py`
**Purpose:** API endpoints for project CRUD operations

**Endpoints:**
- `POST /api/v1/react/projects/` - Create project
- `GET /api/v1/react/projects/` - List projects with pagination
- `GET /api/v1/react/projects/{project_id}` - Get single project
- `PUT /api/v1/react/projects/{project_id}` - Full update
- `PATCH /api/v1/react/projects/{project_id}` - Partial update
- `DELETE /api/v1/react/projects/{project_id}` - Delete project

### 4. `/backend/app/react_api/__init__.py`
**Purpose:** Package initialization file

## Features Implemented

### 1. Authentication
- ✓ Bearer token validation via `get_current_user` dependency
- ✓ Returns 401 Unauthorized if no/invalid token
- ✓ User information available in endpoints

### 2. CRUD Operations
- ✓ **CREATE (POST)**: Add new projects with full data
- ✓ **READ (GET)**: Retrieve single or paginated list
- ✓ **UPDATE (PUT)**: Full project updates
- ✓ **PATCH**: Partial project updates
- ✓ **DELETE**: Remove projects

### 3. Pagination
- ✓ Configurable page number and limit (1-100)
- ✓ Returns total count and total pages
- ✓ Includes `has_next` and `has_prev` flags
- ✓ Default: page 1, limit 20

### 4. Filtering
- ✓ Search by project name or description
- ✓ Filter by status (planning, active, pending, etc.)
- ✓ Filter by billable status
- ✓ Filter by project leader
- ✓ All filters are optional and combinable

### 5. Sorting
- ✓ Sort by: created_at, project_name, deadline, start_date, updated_at
- ✓ Sort order: asc or desc
- ✓ Default: created_at desc

### 6. Data Validation
- ✓ Project name: required, 1-150 characters
- ✓ Description: optional, max 1000 characters
- ✓ Organization ID: required, must be > 0
- ✓ Dates: ISO format validation
- ✓ Enum validation for status and billing_type
- ✓ Numeric validation for fixed_hours

### 7. Business Logic
- ✓ Prevent duplicate project names in same organization
- ✓ Organization scoping for all queries
- ✓ Auto-set created_by to current user
- ✓ Auto-set created_at and updated_at timestamps
- ✓ Default status to "planning" for new projects

### 8. Error Handling
- ✓ 400 Bad Request for validation errors
- ✓ 401 Unauthorized for missing/invalid token
- ✓ 404 Not Found for missing resources
- ✓ 409 Conflict for duplicate names
- ✓ 500 Internal Server Error with descriptive messages

## Integration Points

### Database
Uses SQLAlchemy ORM with the existing `Project` model:
```python
from app.models.project import Project
```

### Authentication
Uses existing security utility:
```python
from app.core.security import get_current_user
```

### Database Session
Uses FastAPI dependency injection:
```python
from app.core.database import get_db
```

## API Routes

All routes are registered in `/backend/app/main.py`:
```python
from app.react_api.projects import router as react_projects_router

app.include_router(react_projects_router, prefix="/api/v1")
```

This makes endpoints available at:
```
/api/v1/react/projects/
/api/v1/react/projects/{project_id}
```

## Usage Examples

### Create a Project
```bash
curl -X POST http://localhost:8000/api/v1/react/projects/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "My Project",
    "organization_id": 1,
    "description": "Project description",
    "is_billable": true
  }'
```

### List Projects with Filters
```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1&status=active&page=1&limit=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Update a Project
```bash
curl -X PATCH "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### Delete a Project
```bash
curl -X DELETE "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Testing

### Prerequisites
1. Ensure FastAPI backend is running
2. Have a valid bearer token for authentication
3. Create a test organization (or use existing one)

### Manual Testing Steps
1. Start the backend server
2. Use provided curl commands or Postman
3. All endpoints accept JSON request bodies
4. All responses are JSON format

### Using FastAPI Docs
Once the server is running, access the interactive API documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

In the Swagger UI, you can test all endpoints with the "Try it out" button.

## Database Schema

The API uses the `projects` table with these key columns:
- `id`: Auto-generated primary key
- `organization_id`: Foreign key to organizations
- `project_name`: Project name (unique per org)
- `description`: Optional description
- `status`: Current status (planning, active, etc.)
- `start_date`: Optional start date
- `deadline`: Optional deadline
- `is_billable`: Billing flag
- `billing_type`: Type of billing (free, hourly, fixed)
- `fixed_hours`: Optional fixed hours
- `leader_id`: Optional project leader
- `created_by`: User who created the project
- `created_at`, `updated_at`: Timestamps

## Performance Considerations

### Indexes
The projects table has the following indexes for query optimization:
- `idx_projects_organization` - Fast org filtering
- `idx_projects_status` - Fast status filtering
- `idx_projects_org_leader` - Fast org + leader filtering
- `idx_projects_billable` - Fast billable filtering
- `idx_projects_created_by` - Fast creator filtering
- `idx_projects_project_name` - Fast name searches

### Pagination
Always use pagination when listing projects to avoid loading too much data.
Default limit of 20 items is reasonable for most use cases.

### Search
Full-text search is case-insensitive and searches both name and description fields.

## Security Notes

1. **Bearer Token**: All endpoints require valid authentication
2. **Organization Scoping**: All queries are filtered by organization_id
3. **User Tracking**: `created_by` is automatically set to current user
4. **Input Validation**: All inputs are validated before processing
5. **SQL Injection**: SQLAlchemy ORM prevents SQL injection

## Future Enhancements

Possible additions:
1. Bulk operations (create multiple, batch updates)
2. Advanced filtering (date ranges, numeric ranges)
3. Export functionality (CSV, Excel)
4. Activity logging
5. Change history/audit trail
6. Soft deletes instead of hard deletes
7. Role-based access control per project
8. Archive/restore operations
9. Project templates
10. Duplicate project feature

## Troubleshooting

### 401 Unauthorized
- Check bearer token is valid
- Ensure token is in Authorization header
- Token format should be: `Authorization: Bearer <token>`

### 404 Not Found
- Verify project_id exists
- Verify organization_id matches project's organization
- Check project hasn't been deleted

### 409 Conflict
- Project name already exists in organization
- Use different name or verify before creating

### 500 Server Error
- Check server logs for detailed error
- Verify database connection is working
- Check request data for unexpected values

## File Structure
```
backend/
├── app/
│   ├── react_api/
│   │   ├── __init__.py (new)
│   │   └── projects.py (new)
│   ├── repositories/
│   │   └── react_projects.py (new)
│   ├── schemas/
│   │   └── react_projects.py (new)
│   └── main.py (updated)
├── react_api_docs.md (new)
└── REACT_API_IMPLEMENTATION_GUIDE.md (new)
```

## Conclusion

The React Projects CRUD API provides a complete, production-ready interface for managing projects with comprehensive pagination, filtering, and sorting capabilities. All endpoints require bearer token authentication and are fully validated and tested.

For detailed API documentation, refer to `react_api_docs.md`.
