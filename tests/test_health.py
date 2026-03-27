"""
Test: System Health & Observability
─────────────────────────────────────
Verifies the /health endpoint returns correct structure
and all required component statuses.
"""


class TestHealth:
    def test_health_returns_200(self, client):
        """GET /health should always return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_ok(self, client):
        """Health status should be 'ok' when DB is reachable."""
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_has_version(self, client):
        """Health response must include application version."""
        data = client.get("/health").json()
        assert "version" in data
        assert len(data["version"]) > 0

    def test_health_has_timestamp(self, client):
        """Health response must include ISO 8601 timestamp."""
        data = client.get("/health").json()
        assert "timestamp" in data

    def test_health_components_present(self, client):
        """Health response must include all component statuses."""
        data = client.get("/health").json()
        assert "components" in data
        assert "api"      in data["components"]
        assert "database" in data["components"]

    def test_health_database_ok(self, client):
        """Database component should report 'ok' in tests."""
        data = client.get("/health").json()
        assert data["components"]["database"] == "ok"

    def test_metrics_endpoint_accessible(self, client):
        """GET /metrics should return Prometheus text format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
