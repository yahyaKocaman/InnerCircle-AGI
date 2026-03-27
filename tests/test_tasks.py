"""
Test: Task CRUD & AI Integration
───────────────────────────────────
Tests the full task lifecycle:
  - Create (with AI priority assignment)
  - List (with filtering)
  - Get by ID
  - Update
  - Complete
  - Delete
  - Statistics
  - Authorization (users can't access each other's tasks)
"""


class TestCreateTask:
    def test_create_task_success(self, client, auth_headers):
        """POST /tasks/ creates a task and returns it."""
        response = client.post("/tasks/", json={
            "title":       "Finish the project report",
            "description": "Must be done urgently before the deadline",
        }, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Finish the project report"
        assert "id" in data
        assert "priority" in data
        assert "status" in data
        assert data["status"] == "TODO"

    def test_ai_assigns_high_priority_for_urgent(self, client, auth_headers):
        """AI should detect 'urgent'/'acil' and assign HIGH or CRITICAL priority."""
        response = client.post("/tasks/", json={
            "title":       "Acil müşteri sunumu",
            "description": "Bu sunum acil tamamlanmalı",
        }, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["priority"] in ("HIGH", "CRITICAL")

    def test_ai_assigns_low_priority_for_normal(self, client, auth_headers):
        """Normal task text should receive LOW priority."""
        response = client.post("/tasks/", json={
            "title":       "Kitap oku",
            "description": "Boş vakitte okumak için",
        }, headers=auth_headers)

        assert response.status_code == 201
        assert response.json()["priority"] == "LOW"

    def test_create_task_requires_auth(self, client):
        """Task creation without token returns 401."""
        response = client.post("/tasks/", json={"title": "No auth task"})
        assert response.status_code == 401

    def test_create_task_empty_title_rejected(self, client, auth_headers):
        """Empty title should be rejected by validation."""
        response = client.post("/tasks/", json={"title": "   "}, headers=auth_headers)
        assert response.status_code == 422


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_headers):
        """New user has no tasks — returns empty list."""
        response = client.get("/tasks/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_tasks_after_create(self, client, auth_headers):
        """Lists tasks belonging to authenticated user."""
        client.post("/tasks/", json={"title": "Task 1"}, headers=auth_headers)
        client.post("/tasks/", json={"title": "Task 2"}, headers=auth_headers)

        response = client.get("/tasks/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_tasks_requires_auth(self, client):
        """Listing tasks without token returns 401."""
        assert client.get("/tasks/").status_code == 401


class TestGetTask:
    def test_get_task_by_id(self, client, auth_headers):
        """GET /tasks/{id} returns correct task."""
        created = client.post("/tasks/", json={
            "title": "Specific task"
        }, headers=auth_headers).json()

        response = client.get(f"/tasks/{created['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Specific task"

    def test_get_nonexistent_task(self, client, auth_headers):
        """GET /tasks/99999 returns 404."""
        response = client.get("/tasks/99999", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, auth_headers):
        """PUT /tasks/{id} updates task fields."""
        task_id = client.post("/tasks/", json={
            "title": "Old title"
        }, headers=auth_headers).json()["id"]

        response = client.put(f"/tasks/{task_id}", json={
            "title": "New title"
        }, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["title"] == "New title"

    def test_update_task_status(self, client, auth_headers):
        """Can change task status to IN_PROGRESS."""
        task_id = client.post("/tasks/", json={
            "title": "Status test"
        }, headers=auth_headers).json()["id"]

        response = client.put(f"/tasks/{task_id}", json={
            "status": "IN_PROGRESS"
        }, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"


class TestCompleteTask:
    def test_complete_task(self, client, auth_headers):
        """POST /tasks/{id}/complete marks task as DONE."""
        task_id = client.post("/tasks/", json={
            "title": "Complete me"
        }, headers=auth_headers).json()["id"]

        response = client.post(f"/tasks/{task_id}/complete", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["is_completed"] is True
        assert data["status"] == "DONE"
        assert data["completed_at"] is not None


class TestDeleteTask:
    def test_delete_task(self, client, auth_headers):
        """DELETE /tasks/{id} removes the task."""
        task_id = client.post("/tasks/", json={
            "title": "Delete me"
        }, headers=auth_headers).json()["id"]

        response = client.delete(f"/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify it's gone
        assert client.get(f"/tasks/{task_id}", headers=auth_headers).status_code == 404

    def test_delete_nonexistent_task(self, client, auth_headers):
        """Deleting a non-existent task returns 404."""
        assert client.delete("/tasks/99999", headers=auth_headers).status_code == 404


class TestTaskStats:
    def test_stats_empty(self, client, auth_headers):
        """Stats for new user should return all zeros."""
        data = client.get("/tasks/stats", headers=auth_headers).json()
        assert data["total"] == 0
        assert data["todo"] == 0
        assert data["done"] == 0

    def test_stats_after_tasks(self, client, auth_headers):
        """Stats correctly count tasks and completed today."""
        task_id = client.post("/tasks/", json={
            "title": "Stats task"
        }, headers=auth_headers).json()["id"]

        client.post(f"/tasks/{task_id}/complete", headers=auth_headers)

        data = client.get("/tasks/stats", headers=auth_headers).json()
        assert data["total"] == 1
        assert data["done"] == 1
        assert data["completed_today"] == 1


class TestUserIsolation:
    def test_users_cannot_see_each_others_tasks(self, client, auth_headers):
        """🔒 Security: tasks are scoped to the owning user."""
        # User A creates a task
        task_id = client.post("/tasks/", json={
            "title": "User A's private task"
        }, headers=auth_headers).json()["id"]

        # Register + login as User B
        client.post("/auth/register", json={
            "username": "userb",
            "email":    "userb@example.com",
            "password": "password123",
        })
        token_b = client.post("/auth/login", json={
            "username": "userb",
            "password": "password123",
        }).json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B should NOT see User A's task
        response = client.get(f"/tasks/{task_id}", headers=headers_b)
        assert response.status_code == 404
