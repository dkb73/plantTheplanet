import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_auth_workflow():
    unique_email = f"gardener_{pytest.__name__}@test.com"
    # Register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    assert reg_resp.status_code in [201, 400]
    
    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "password123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    token = data["access_token"]

    # Me
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == unique_email


def test_discovery_endpoints():
    # Categories
    cat_resp = client.get("/api/v1/discovery/categories")
    assert cat_resp.status_code == 200
    assert "Vegetable" in cat_resp.json()

    # Recommendations
    rec_resp = client.post(
        "/api/v1/discovery/recommendations",
        json={"latitude": 12.2958, "longitude": 76.6394, "limit": 5},
    )
    assert rec_resp.status_code == 200
    crops = rec_resp.json()
    assert len(crops) > 0
    first_code = crops[0]["ecoport_code"]

    # Crop details
    detail_resp = client.get(f"/api/v1/discovery/crops/{first_code}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["ecoport_code"] == first_code


def test_planting_and_plan_workflow():
    unique_email = f"grower_{id(client)}@test.com"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": "password123"},
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create planting with real crop code (e.g. 289 or first crop)
    rec_resp = client.post(
        "/api/v1/discovery/recommendations",
        json={"latitude": 12.2958, "longitude": 76.6394, "limit": 1},
    )
    crop_code = rec_resp.json()[0]["ecoport_code"]

    plant_resp = client.post(
        "/api/v1/plantings",
        headers=headers,
        json={
            "ecoport_code": crop_code,
            "planting_date": "2026-10-01",
            "latitude": 12.2958,
            "longitude": 76.6394,
            "growing_scale": "home_garden",
        },
    )
    assert plant_resp.status_code == 201
    planting = plant_resp.json()
    planting_id = planting["id"]
    assert planting["ecoport_code"] == crop_code
    assert planting["active_plan"] is not None
    assert len(planting["active_plan"]["stages"]) >= 3

    # List plantings
    list_resp = client.get("/api/v1/plantings", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Toggle a stage
    first_stage = planting["active_plan"]["stages"][0]
    stage_id = first_stage["id"]
    toggle_resp = client.patch(f"/api/v1/plantings/stages/{stage_id}/complete?completed=true", headers=headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_completed"] is True

    # Add observation
    obs_resp = client.post(
        f"/api/v1/plantings/{planting_id}/observations",
        headers=headers,
        json={"note": "First green sprout visible!"},
    )
    assert obs_resp.status_code == 200
    assert obs_resp.json()["note"] == "First green sprout visible!"

    # Plant chat
    chat_resp = client.post(
        f"/api/v1/plantings/{planting_id}/chat",
        headers=headers,
        json={"message": "How often should I water during the first stage?"},
    )
    assert chat_resp.status_code == 200
    assert "content" in chat_resp.json()
    assert len(chat_resp.json()["content"]) > 0

    # Get chat history
    hist_resp = client.get(f"/api/v1/plantings/{planting_id}/chat", headers=headers)
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) >= 2
