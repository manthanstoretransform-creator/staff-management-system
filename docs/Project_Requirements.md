# Employee Tracking & Productivity Management System

## Project Overview

The Employee Tracking & Productivity Management System is a desktop-based workforce monitoring solution that helps organizations track employee work hours, project progress, productivity, and application usage in real time.

The system consists of three major components:

1. Desktop Application
2. Backend API
3. React Admin Dashboard

The desktop application continuously monitors employee activity and securely sends tracking data to the backend server.

The backend processes, stores, and exposes APIs for the React dashboard, allowing administrators and managers to monitor productivity and generate reports.

---

# Project Objectives

The system should:

- Track employee work sessions
- Track projects and assigned tasks
- Record application usage
- Record website usage
- Capture screenshots automatically
- Track keyboard and mouse activity
- Generate productivity statistics
- Maintain complete work history
- Provide reports for managers
- Support multiple organizations

---

# Core Modules

## Authentication

- Login
- Logout
- JWT Authentication
- Refresh Token
- Role Based Access Control

---

## Organization Management

- Create Organization
- Update Organization
- Delete Organization
- Manage Organization Settings

---

## Employee Management

- Employee Registration
- Employee Login
- Employee Profile
- Employee Status
- Active/Inactive Users

---

## Project Management

- Create Project
- Update Project
- Archive Project
- Project Listing
- Project Members

---

## Task Management

- Create Task
- Assign Task
- Update Task
- Complete Task
- Task Reports

---

## Time Tracking

Automatic Timer

Manual Time Entry

Work Sessions

Daily Hours

Weekly Hours

Monthly Hours

---

## Activity Tracking

Track:

- Keyboard Activity
- Mouse Activity
- Idle Time
- Active Time
- Productivity Percentage

---

## Screenshot Monitoring

Automatically capture screenshots at configurable intervals.

Store:

- Screenshot URL
- Timestamp
- Organization
- Project
- Task

---

## Application Usage Tracking

Track desktop applications including:

- VS Code
- Chrome
- Slack
- Teams
- Excel
- Word
- Outlook

Store:

- Application Name
- Duration
- Active Time

---

## Website Usage Tracking

Track browser URLs including:

- Domain
- Full URL
- Browser
- Duration

---

## Reports

Dashboard Reports

Daily Reports

Weekly Reports

Monthly Reports

Employee Reports

Project Reports

Task Reports

Application Usage Reports

Website Usage Reports

---

## Notifications

Future Support:

- Email Notifications
- Teams Notifications
- Desktop Notifications

---

# Technology Stack

Desktop

- Electron
- React
- TypeScript

Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic
- JWT Authentication

Database

- PostgreSQL
- Neon Database

Frontend

- React
- TypeScript
- Tailwind CSS

Storage

- Google Drive (Screenshots)

---

# User Roles

## Super Admin

- Full System Access

## Organization Admin

- Manage Organization
- Manage Employees
- Manage Projects

## Manager

- Manage Team
- View Reports
- Assign Tasks

## Employee

- Track Work
- View Own Data

---

# Development Goals

The project should follow:

- Clean Architecture
- REST APIs
- Modular Folder Structure
- Repository Pattern
- Service Layer
- Secure Authentication
- Proper Logging
- Error Handling
- Scalable Database Design

---

# Important Rule

Always reuse the existing database structure whenever possible.

Only add new tables or columns if required by new business requirements.

Never duplicate existing functionality.