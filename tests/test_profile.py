"""
Test: Profile API
───────────────────────────────────
Tests user profile CRUD operations:
  - Create profile
  - Update profile
  - Get profile
  - Auth protection
"""


class TestProfileCreate:
    def test_create_profile_success(self, client, auth_headers):
        """POST /profile/ creates user profile."""
        response = client.post("/profile/", json={
            "age": 28,
            "occupation": "Software Engineer",
            "goals": ["Finansal özgürlük", "Sağlıklı yaşam"],
            "interests": ["Teknoloji", "Yatırım"],
            "risk_tolerance": "medium",
            "career_stage": "mid",
        }, headers=auth_headers)
        assert response.status_code in (200, 201)
        data = response.json()
        assert data["age"] == 28
        assert data["occupation"] == "Software Engineer"

    def test_create_profile_requires_auth(self, client):
        """POST /profile/ without token returns 401."""
        response = client.post("/profile/", json={"age": 25})
        assert response.status_code == 401


class TestProfileGet:
    def test_get_profile_requires_auth(self, client):
        """GET /profile/ without token returns 401."""
        response = client.get("/profile/")
        assert response.status_code == 401


class TestProfileUpdate:
    def test_update_profile(self, client, auth_headers):
        """PUT /profile/ updates existing profile fields."""
        # First create
        client.post("/profile/", json={
            "age": 30,
            "occupation": "Engineer",
        }, headers=auth_headers)

        # Then update
        response = client.put("/profile/", json={
            "age": 31,
            "occupation": "Senior Engineer",
            "career_stage": "senior",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["age"] == 31
        assert data["career_stage"] == "senior"
