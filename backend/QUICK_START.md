# 🚀 React Projects CRUD API - Quick Start Guide

## 30-Second Overview

You now have a **production-ready CRUD API** for managing projects with:
- ✅ Full Create, Read, Update (full/partial), Delete operations
- ✅ Pagination with 1-100 items per page
- ✅ Advanced filtering (search, status, billable, leader)
- ✅ Flexible sorting (multiple fields, asc/desc)
- ✅ Bearer token authentication
- ✅ Comprehensive error handling

**Base URL**: `/api/v1/react/projects`

---

## 1️⃣ Start the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Server runs at: http://localhost:8000

---

## 2️⃣ View Interactive Documentation

```
http://localhost:8000/docs
```

Or ReDoc version:
```
http://localhost:8000/redoc
```

---

## 3️⃣ Test a Simple Request

```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Replace `YOUR_TOKEN` with a valid bearer token from your auth system.

---

## 📌 The 6 Main Endpoints

| # | Method | Endpoint | What it does |
|---|--------|----------|-------------|
| 1 | **POST** | `/react/projects/` | Create a new project |
| 2 | **GET** | `/react/projects/` | List projects (paginated) |
| 3 | **GET** | `/react/projects/{id}` | Get one project |
| 4 | **PUT** | `/react/projects/{id}` | Update entire project |
| 5 | **PATCH** | `/react/projects/{id}` | Update part of project |
| 6 | **DELETE** | `/react/projects/{id}` | Delete project |

---

## 💡 Quick Examples

### Create a Project
```bash
curl -X POST http://localhost:8000/api/v1/react/projects/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "My Project",
    "organization_id": 1
  }'
```

### List All Projects
```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### List with Filters
```bash
# Active and billable projects
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1&status=active&is_billable=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Search projects
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1&search=website" \
  -H "Authorization: Bearer YOUR_TOKEN"

# With pagination
curl -X GET "http://localhost:8000/api/v1/react/projects/?organization_id=1&page=2&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get One Project
```bash
curl -X GET "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Update Project (All Fields)
```bash
curl -X PUT "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "Updated Name",
    "status": "active"
  }'
```

### Update Project (One Field)
```bash
curl -X PATCH "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### Delete Project
```bash
curl -X DELETE "http://localhost:8000/api/v1/react/projects/123?organization_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🔑 Key Parameters

### Create/Update Body
```json
{
  "project_name": "string (required)",
  "organization_id": "number (required)",
  "description": "string",
  "start_date": "2026-09-01",
  "deadline": "2026-12-31",
  "is_billable": true,
  "billing_type": "free|hourly|fixed",
  "fixed_hours": 200.50,
  "leader_id": 5,
  "status_id": 1
}
```

### List Query Parameters
- `organization_id` (required) - Organization ID
- `page` - Page number (default: 1)
- `limit` - Items per page, max 100 (default: 20)
- `search` - Search term
- `status` - Filter by status
- `is_billable` - Filter by billable
- `leader_id` - Filter by leader
- `sort_by` - Sort field (created_at, project_name, deadline, etc.)
- `sort_order` - asc or desc

---

## 📊 Response Format

### Success Response
```json
{
  "id": 123,
  "organization_id": 1,
  "project_name": "My Project",
  "status": "active",
  ...
}
```

### List Response
```json
{
  "data": [
    { project 1 },
    { project 2 }
  ],
  "pagination": {
    "total": 50,
    "page": 1,
    "limit": 20,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

### Error Response
```json
{
  "status_code": 400,
  "message": "Error message",
  "detail": "Details"
}
```

---

## 🔐 Authentication

All requests require:
```
Authorization: Bearer <token>
```

Get your token from the auth system, then include it in every request.

---

## ✨ Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK (GET, PUT, PATCH) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Bad Request |
| 401 | Unauthorized (missing token) |
| 404 | Not Found |
| 409 | Conflict (duplicate name) |
| 500 | Server Error |

---

## 🎯 Status Values

```
"planning"      - In planning phase
"active"        - Currently active
"pending"       - Paused/pending
"todo"          - Tasks pending
"completed"     - Finished
"cancelled"     - Cancelled
"archived"      - Archived
```

---

## 💰 Billing Types

```
"free"          - No billing
"hourly"        - Hourly rate
"fixed"         - Fixed price
```

---

## 🧪 Test the API

### Option 1: Use Swagger UI
1. Go to http://localhost:8000/docs
2. Click "Authorize" button
3. Enter your bearer token
4. Click "Try it out" on any endpoint

### Option 2: Use Test Script
```bash
python test_react_api.py
```

(Edit test_react_api.py with your token first)

### Option 3: Use cURL
See examples above

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| **REACT_API_README.md** | Overview and quick start |
| **react_api_docs.md** | Complete API documentation |
| **REACT_API_IMPLEMENTATION_GUIDE.md** | Technical details |
| **REACT_API_SUMMARY.md** | Quick reference |
| **SETUP_CHECKLIST.md** | Verification checklist |
| **QUICK_START.md** | This file |

---

## 🗂️ File Locations

```
backend/
├── app/react_api/projects.py          # API endpoints
├── app/repositories/react_projects.py # Database layer
├── app/schemas/react_projects.py      # Validation
├── app/main.py                        # Updated with new routes
│
├── react_api_docs.md                  # Full documentation
├── REACT_API_README.md                # Quick start
├── SETUP_CHECKLIST.md                 # Verification
└── test_react_api.py                  # Test suite
```

---

## ✅ Verification

All files created:
- [x] `app/schemas/react_projects.py` (4.2 KB)
- [x] `app/repositories/react_projects.py` (8.0 KB)
- [x] `app/react_api/projects.py` (16.8 KB)
- [x] `app/react_api/__init__.py` (0.1 KB)
- [x] `app/main.py` (updated)

Documentation:
- [x] `REACT_API_README.md` (11.7 KB)
- [x] `react_api_docs.md` (17.9 KB)
- [x] `REACT_API_IMPLEMENTATION_GUIDE.md` (9.3 KB)
- [x] `REACT_API_SUMMARY.md` (11.7 KB)
- [x] `SETUP_CHECKLIST.md` (11.0 KB)
- [x] `QUICK_START.md` (this file)

Testing:
- [x] `test_react_api.py` (7.5 KB)

---

## 🚨 Common Issues

### 401 Unauthorized
**Problem**: Request returns 401
**Solution**: Check your bearer token is valid and included in Authorization header

### 404 Not Found
**Problem**: Project not found
**Solution**: Verify project_id exists and organization_id matches

### 409 Conflict
**Problem**: Project name already exists
**Solution**: Use a different project name

### Server Not Running
**Problem**: Connection refused
**Solution**: Start the backend with `python -m uvicorn app.main:app --reload`

---

## 🎯 Next Steps

1. **Test the API** - Use curl or Swagger UI to test endpoints
2. **Integrate Frontend** - Use endpoints in React components
3. **Add Features** - Implement UI for filtering, sorting, pagination
4. **Deploy** - Deploy to staging/production

---

## 📞 Quick Help

### View API Docs
```
http://localhost:8000/docs
```

### Check Server Health
```bash
curl http://localhost:8000/health
```

### View All Routes
```
http://localhost:8000/docs
```

---

## 🎓 Learning Order

1. **First**: Read this file (you are here)
2. **Then**: Read `REACT_API_README.md`
3. **Next**: Try examples with Swagger UI or cURL
4. **Deep Dive**: Read `react_api_docs.md`
5. **Technical**: Read `REACT_API_IMPLEMENTATION_GUIDE.md`

---

## 💻 Developer Commands

```bash
# Start backend
cd backend
python -m uvicorn app.main:app --reload

# Run tests
python test_react_api.py

# Check syntax
python -m py_compile app/react_api/projects.py

# View API docs
open http://localhost:8000/docs
```

---

## 🎉 You're Ready!

Your React Projects CRUD API is ready to use. Start with the examples above and refer to the documentation as needed.

**Happy coding!** 🚀

---

**For detailed documentation, see: `react_api_docs.md`**
