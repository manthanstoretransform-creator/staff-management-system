# Staff Management System

A comprehensive system designed to manage workforce activity, track time, log tasks, and capture screenshots.

## Project Structure

This repository is split into three main components:

1. **[Backend](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/backend)**
   - API layer built with **FastAPI** and **SQLAlchemy**.
   - Database migrations managed via **Alembic**, configured to dynamically read connection settings from the `DATABASE_URL_DEV` environment variable.
   - Folder structure conforms to the repository/service layer pattern specified in [architecture.md](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/steering/architecture.md).

2. **[Desktop Client](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/desktop)**
   - Empty scaffolding structure containing modular subfolders for core functionality:
     - `auth/`: User authentication modules.
     - `tracking/`: Active window and app usage tracking.
     - `screenshot/`: Desktop capture and Google Drive upload pipeline.
     - `sync/`: Offline caching and data synchronization.

3. **[Frontend Dashboard](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/frontend)**
   - Web application built with **React**, **TypeScript**, and styled using **Tailwind CSS v4** via **Vite**.
   - Modularized folders: `features/`, `api/`, and `components/`.

## Steering Documentation

Please refer to the [docs/steering](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/steering) directory for full details on the development process, database schema, and project rules:

- **[architecture.md](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/steering/architecture.md)**: Architectural patterns, tech stack, and module structure.
- **[rules.md](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/steering/rules.md)**: Database guidelines, repository constraints, and API design rules.
- **[phases.md](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/steering/phases.md)**: Progression roadmap (currently in Phase 0: Scaffolding).
- **[prd.md](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/steering/prd.md)**: Project requirements and feature definitions.
- **[Database Documentation](file:///c:/Users/PC%20-%209/Desktop/staff-management-system/docs/Database_Documentation.md)**: Database schema reference.
