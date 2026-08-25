import requests
import json

# Test creating a project with status_id=2 (pending)
headers = {"Authorization": "Bearer test_token"}  # This might fail auth, but we want to see if the constraint is the issue
data = {
    "project_name": "Website Redesign",
    "description": "Redesign the company website with a modern UI, improved navigation, and mobile responsiveness.",
    "status_id": 2,  # Pending
    "leader_id": 144,
    "employee_ids": [],
    "deadline": "2026-11-27",
    "billing_type": "fixed",
    "fixed_hours": 100
}

try:
    response = requests.post("http://localhost:8000/api/v1/projects", json=data, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
