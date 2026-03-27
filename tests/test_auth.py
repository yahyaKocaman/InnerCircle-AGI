"""
Test: Authentication & Security
─────────────────────────────────
Tests the full auth lifecycle:
  - Registration (validation, duplicate detection)
  - Login (success, invalid credentials)
  - JWT token verification (/me endpoint)
  - Security: unauthorized access rejection
"""


class TestRegister:
    def test_register_success(self, client):
        """Valid registration returns 201 with user data."""
        response = client.post("/auth/register", json={
            "username":  "newuser",
            "email":     "new@example.com",
            "full_name": "New User",
            "password":  "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        # 🔒 Security: password must NEVER be returned
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_username(self, client, registered_user):
        """Registering an existing username returns 400."""
        response = client.post("/auth/register", json={
            "username": "testuser",         # already registered via fixture
            "email":    "other@example.com",
            "password": "password123",
        })
        assert response.status_code == 400
        assert "Username" in response.json()["detail"]

    def test_register_duplicate_email(self, client, registered_user):
        """Registering an existing email returns 400."""
        response = client.post("/auth/register", json={
            "username": "differentuser",
            "email":    "testuser@example.com",  # same email as fixture
            "password": "password123",
        })
        assert response.status_code == 400

    def test_register_short_username_rejected(self, client):
        """Usernames shorter than 3 chars should be rejected."""
        response = client.post("/auth/register", json={
            "username": "ab",
            "email":    "short@example.com",
            "password": "password123",
        })
        assert response.status_code == 422   # Pydantic validation error

    def test_register_short_password_rejected(self, client):
        """Passwords shorter than 6 chars should be rejected."""
        response = client.post("/auth/register", json={
            "username": "validuser",
            "email":    "valid@example.com",
            "password": "123",
        })
        assert response.status_code == 422


class TestLogin:
    def test_login_success_returns_token(self, client, registered_user):
        """Valid credentials return a JWT token."""
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    def test_login_includes_user_object(self, client, registered_user):
        """Login response must include the user profile object."""
        data = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass123",
        }).json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"

    def test_login_invalid_password(self, client, registered_user):
        """Wrong password returns 401 Unauthorized."""
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Login for unknown user returns 401."""
        response = client.post("/auth/login", json={
            "username": "ghost",
            "password": "doesntmatter",
        })
        assert response.status_code == 401


class TestAuthProtection:
    def test_me_requires_token(self, client):
        """GET /auth/me without token returns 401."""
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_me_with_valid_token(self, client, auth_headers):
        """GET /auth/me with valid token returns user profile."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"

    def test_me_with_invalid_token(self, client):
        """GET /auth/me with forged token returns 401."""
        response = client.get("/auth/me", headers={
            "Authorization": "Bearer this.is.a.forged.token"
        })
        assert response.status_code == 401
