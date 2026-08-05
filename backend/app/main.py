from fastapi import FastAPI

app = FastAPI(
    title="Staff Management System API",
    description="Backend API for Staff Management System",
    version="0.1.0"
)

@app.get("/")
def read_root():
    return {"message": "Staff Management System API is running."}
