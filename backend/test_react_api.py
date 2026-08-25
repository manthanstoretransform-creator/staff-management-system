"""
Integration tests for React Projects CRUD API
This file can be used to test the API endpoints locally.

To use this file:
1. Start the backend server: python -m uvicorn app.main:app --reload
2. Replace YOUR_TOKEN with a valid bearer token from your auth system
3. Run this file: python test_react_api.py

Or run individual test functions as needed.
"""

import requests
import json
from datetime import date, datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
BEARER_TOKEN = "YOUR_TOKEN_HERE"  # Replace with valid token
ORG_ID = 1  # Replace with your organization ID

# Helper function to make requests
def make_request(method, endpoint, data=None, params=None, token=BEARER_TOKEN):
    """Helper function to make API requests"""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    if method == "GET":
        response = requests.get(url, headers=headers, params=params)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PUT":
        response = requests.put(url, headers=headers, json=data)
    elif method == "PATCH":
        response = requests.patch(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return response

# Test functions
def test_create_project():
    """Test creating a new project"""
    print("\n=== TEST: Create Project ===")
    
    data = {
        "project_name": f"Test Project {datetime.now().timestamp()}",
        "description": "This is a test project",
        "organization_id": ORG_ID,
        "start_date": str(date.today()),
        "deadline": str(date.today() + timedelta(days=90)),
        "is_billable": True,
        "billing_type": "fixed",
        "fixed_hours": 100.0
    }
    
    response = make_request("POST", "/react/projects/", data=data)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 201:
        project = response.json()
        print(f"✓ Project created successfully!")
        print(f"  ID: {project['id']}")
        print(f"  Name: {project['project_name']}")
        return project['id']
    else:
        print(f"✗ Failed to create project")
        print(f"  Response: {response.text}")
        return None

def test_list_projects():
    """Test listing projects"""
    print("\n=== TEST: List Projects ===")
    
    params = {
        "organization_id": ORG_ID,
        "page": 1,
        "limit": 10,
        "sort_by": "created_at",
        "sort_order": "desc"
    }
    
    response = make_request("GET", "/react/projects/", params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Projects retrieved successfully!")
        print(f"  Total projects: {data['pagination']['total']}")
        print(f"  Current page: {data['pagination']['page']}")
        print(f"  Items in response: {len(data['data'])}")
        
        if data['data']:
            print(f"\n  First project:")
            print(f"    ID: {data['data'][0]['id']}")
            print(f"    Name: {data['data'][0]['project_name']}")
            print(f"    Status: {data['data'][0]['status']}")
    else:
        print(f"✗ Failed to retrieve projects")
        print(f"  Response: {response.text}")

def test_get_project(project_id):
    """Test getting a single project"""
    print("\n=== TEST: Get Single Project ===")
    
    params = {"organization_id": ORG_ID}
    response = make_request("GET", f"/react/projects/{project_id}", params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        project = response.json()
        print(f"✓ Project retrieved successfully!")
        print(f"  ID: {project['id']}")
        print(f"  Name: {project['project_name']}")
        print(f"  Status: {project['status']}")
        print(f"  Billable: {project['is_billable']}")
    else:
        print(f"✗ Failed to retrieve project")
        print(f"  Response: {response.text}")

def test_update_project(project_id):
    """Test updating a project (PUT)"""
    print("\n=== TEST: Update Project (PUT) ===")
    
    data = {
        "project_name": f"Updated Project {datetime.now().timestamp()}",
        "description": "Updated description",
        "status": "active"
    }
    
    params = {"organization_id": ORG_ID}
    response = make_request("PUT", f"/react/projects/{project_id}", data=data, params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        project = response.json()
        print(f"✓ Project updated successfully!")
        print(f"  New name: {project['project_name']}")
        print(f"  New status: {project['status']}")
    else:
        print(f"✗ Failed to update project")
        print(f"  Response: {response.text}")

def test_patch_project(project_id):
    """Test partial update of a project (PATCH)"""
    print("\n=== TEST: Partial Update Project (PATCH) ===")
    
    data = {
        "status": "completed",
        "completed_at": datetime.now().isoformat() + "Z"
    }
    
    params = {"organization_id": ORG_ID}
    response = make_request("PATCH", f"/react/projects/{project_id}", data=data, params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        project = response.json()
        print(f"✓ Project patched successfully!")
        print(f"  Status: {project['status']}")
        print(f"  Completed at: {project['completed_at']}")
    else:
        print(f"✗ Failed to patch project")
        print(f"  Response: {response.text}")

def test_list_with_filters():
    """Test listing projects with filters"""
    print("\n=== TEST: List Projects with Filters ===")
    
    params = {
        "organization_id": ORG_ID,
        "status": "active",
        "is_billable": True,
        "page": 1,
        "limit": 5
    }
    
    response = make_request("GET", "/react/projects/", params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Filtered projects retrieved!")
        print(f"  Total matching projects: {data['pagination']['total']}")
        print(f"  Items in response: {len(data['data'])}")
    else:
        print(f"✗ Failed to retrieve filtered projects")
        print(f"  Response: {response.text}")

def test_search_projects():
    """Test searching projects"""
    print("\n=== TEST: Search Projects ===")
    
    params = {
        "organization_id": ORG_ID,
        "search": "test",
        "page": 1,
        "limit": 10
    }
    
    response = make_request("GET", "/react/projects/", params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Search completed!")
        print(f"  Results found: {data['pagination']['total']}")
        print(f"  Items in response: {len(data['data'])}")
    else:
        print(f"✗ Search failed")
        print(f"  Response: {response.text}")

def test_delete_project(project_id):
    """Test deleting a project"""
    print("\n=== TEST: Delete Project ===")
    
    params = {"organization_id": ORG_ID}
    response = make_request("DELETE", f"/react/projects/{project_id}", params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 204:
        print(f"✓ Project deleted successfully!")
    else:
        print(f"✗ Failed to delete project")
        print(f"  Response: {response.text}")

def test_unauthorized():
    """Test authorization failure"""
    print("\n=== TEST: Unauthorized Request ===")
    
    response = make_request("GET", "/react/projects/", params={"organization_id": ORG_ID}, token="invalid_token")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 401:
        print(f"✓ Correctly rejected unauthorized request")
    else:
        print(f"✗ Should have returned 401 Unauthorized")

def test_not_found():
    """Test 404 error"""
    print("\n=== TEST: Not Found (404) ===")
    
    params = {"organization_id": ORG_ID}
    response = make_request("GET", "/react/projects/999999", params=params)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 404:
        print(f"✓ Correctly returned 404 Not Found")
    else:
        print(f"✗ Should have returned 404")

def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("REACT PROJECTS API TEST SUITE")
    print("=" * 50)
    
    # Check if token is set
    if BEARER_TOKEN == "YOUR_TOKEN_HERE":
        print("\n⚠️  WARNING: BEARER_TOKEN is not set!")
        print("   Update the BEARER_TOKEN variable with a valid token from your auth system")
        return
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/../..")
    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Cannot connect to backend!")
        print(f"   Make sure the backend is running on {BASE_URL}")
        return
    
    # Run tests
    print(f"\nUsing Organization ID: {ORG_ID}")
    print(f"Base URL: {BASE_URL}")
    
    # Test 1: Create a project
    project_id = test_create_project()
    
    # Test 2: List projects
    test_list_projects()
    
    # Test 3: Test error cases
    test_unauthorized()
    test_not_found()
    
    # Test 4: Only run tests with valid project ID
    if project_id:
        test_get_project(project_id)
        test_update_project(project_id)
        test_patch_project(project_id)
        test_list_with_filters()
        test_search_projects()
        test_delete_project(project_id)
    
    print("\n" + "=" * 50)
    print("TEST SUITE COMPLETED")
    print("=" * 50)

if __name__ == "__main__":
    run_all_tests()
