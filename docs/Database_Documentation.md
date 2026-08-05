# Database Documentation

## Database

PostgreSQL (Neon)

Purpose:

This document describes the existing database schema that powers the Employee Tracking & Productivity Management System.

The goal is to understand the current schema before adding new features.

---

# Database Modules

The database is organized into the following areas:

- Organizations
- Projects
- Employees
- Tasks
- Time Tracking
- Activity Monitoring
- Screenshots
- Application Usage
- URL Usage
- Logs

---

# organizations

Purpose

Stores organization information.

Important Fields

- id
- name
- slug
- logo_url
- timezone
- currency
- created_at
- updated_at

Relationships

Organization

↓

Projects

Project Members

Time Entries

Activity Logs

---

# projects

Purpose

Stores organization projects.

Important Fields

- id
- organization_id
- project_name
- description
- status
- is_billable
- created_by
- created_at

Relationships

Organization

↓

Projects

↓

Tasks

↓

Time Entries

---

# project_members

Purpose

Stores project membership.

Important Fields

- project_id
- organization_id
- user_id
- joined_at

Relationship

One Project

↓

Many Employees

---

# tasks

Purpose

Stores project tasks.

Important Fields

- id
- project_id
- organization_id
- task_name
- description
- due_date
- estimated_hours
- completed_at
- completed_by

Relationship

Project

↓

Many Tasks

↓

Many Time Entries

---

# task_assignees

Purpose

Stores assigned employees.

Important Fields

- task_id
- user_id
- assigned_by
- assigned_at

Relationship

Task

↓

Assigned Employee

---

# time_entries

Purpose

Stores automatic work sessions.

Important Fields

- organization_id
- project_id
- task_id
- user_id
- start_time
- end_time
- duration
- is_billable
- status

Relationship

Time Entry

↓

Activity

↓

Screenshots

↓

Application Usage

↓

Website Usage

---

# manual_time_entries

Purpose

Stores manually entered work sessions.

Important Fields

- organization_id
- project_id
- task_id
- user_id
- work_date
- total_seconds
- approval_status

---

# time_entry_activity

Purpose

Stores productivity statistics.

Contains

- Active Time
- Idle Time
- Productivity %
- Mouse Activity
- Keyboard Activity

---

# time_entry_app_usage

Purpose

Stores application usage.

Examples

- Chrome
- VS Code
- Slack
- Excel

Stores

- App Name
- Duration
- Active Seconds

---

# time_entry_url_usage

Purpose

Stores browser usage.

Stores

- URL
- Domain
- Browser
- Duration

---

# time_entry_screenshots

Purpose

Stores screenshot metadata.

Stores

- Screenshot URL
- Timestamp
- Activity Percentage
- Google Drive URL

Actual image files are stored outside the database.

---

# activity_logs

Purpose

Stores audit logs.

Tracks

- Login
- Logout
- Task Creation
- Project Updates
- Employee Changes

---

# api_error_logs

Purpose

Stores backend errors.

Stores

- API Endpoint
- Request
- Response
- Error Message
- Stack Trace
- User Agent
- IP Address

---

# Database Relationships

Organization
│
├── Projects
│   ├── Tasks
│   │   ├── Task Assignees
│   │   └── Time Entries
│   └── Project Members
│
├── Manual Time Entries
├── Activity Logs
└── API Error Logs

Time Entry
│
├── Activity
├── Screenshots
├── Application Usage
└── Website Usage

---

# Development Rules

Before creating any table:

1. Check whether the table already exists.

2. Reuse existing relationships.

3. Follow naming conventions.

4. Use proper foreign keys.

5. Use Alembic migrations.

6. Never duplicate data.

7. Keep the schema normalized.

---

# Future Database Extensions

Possible future modules:

- Attendance
- Leave Management
- Payroll Integration
- AI Productivity Scoring
- OCR Screenshot Analysis
- AI Daily Summary
- Microsoft Teams Integration
- Jira Integration
- Email Automation
- Calendar Integration

These should only be added after confirming they are not already supported by the existing schema.