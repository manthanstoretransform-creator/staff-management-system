Stack:
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL (Neon)
- Desktop: Python / Electron
- Frontend: React, TypeScript, Tailwind CSS
- Storage: Google Drive (screenshots)

Folder structure:
backend/
  app/
    api/          (routers)
    services/      (business logic)
    repositories/  (DB queries)
    models/        (SQLAlchemy)
    schemas/       (Pydantic)
    core/          (config, security, JWT)
    main.py
  alembic/
desktop/
  auth/
  tracking/
  screenshot/
  sync/
frontend/
  src/
    features/
    api/
    components/
docs/

System flow: Desktop app and React dashboard both talk only to the FastAPI
backend over REST + JWT. Backend is the only thing that talks to Neon and to
Google Drive. See docs/Database_Documentation.md for full schema.