"""
Test: Council API & Agent Routing
───────────────────────────────────
Tests the core council functionality:
  - Agent listing
  - Council ask (requires auth)
  - Session CRUD
  - Routing logic verification
"""

import pytest


class TestListAgents:
    def test_list_agents_requires_auth(self, client):
        """GET /council/agents without token returns 401."""
        response = client.get("/council/agents")
        assert response.status_code == 401

    def test_list_agents_returns_all_agents(self, client, auth_headers):
        """GET /council/agents returns metadata for all 6 agents."""
        response = client.get("/council/agents", headers=auth_headers)
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 6

    def test_agent_roles_complete(self, client, auth_headers):
        """All 6 expected roles must be present."""
        agents = client.get("/council/agents", headers=auth_headers).json()
        roles = {a["role"] for a in agents}
        expected = {"life_coach", "investment", "performance", "career", "health", "synthesizer"}
        assert roles == expected

    def test_agent_metadata_has_required_fields(self, client, auth_headers):
        """Each agent must have name, color, icon, title, description."""
        agents = client.get("/council/agents", headers=auth_headers).json()
        for agent in agents:
            assert "name" in agent
            assert "color" in agent
            assert "icon" in agent
            assert "title" in agent
            assert "description" in agent
            assert agent["color"].startswith("#")


class TestAskCouncil:
    def test_ask_requires_auth(self, client):
        """POST /council/ask without token returns 401."""
        response = client.post("/council/ask", json={"message": "Merhaba"})
        assert response.status_code == 401

    def test_ask_empty_message_rejected(self, client, auth_headers):
        """Empty message should be rejected by validation."""
        response = client.post("/council/ask", json={"message": "   "}, headers=auth_headers)
        assert response.status_code == 422

    def test_ask_message_too_long_rejected(self, client, auth_headers):
        """Messages exceeding 4000 chars should be rejected."""
        long_msg = "x" * 4001
        response = client.post("/council/ask", json={"message": long_msg}, headers=auth_headers)
        assert response.status_code == 422


class TestSessions:
    def test_list_sessions_empty(self, client, auth_headers):
        """New user has no sessions — returns empty list."""
        response = client.get("/council/sessions", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_sessions_requires_auth(self, client):
        """GET /council/sessions without token returns 401."""
        response = client.get("/council/sessions")
        assert response.status_code == 401

    def test_get_nonexistent_session(self, client, auth_headers):
        """GET /council/sessions/99999 returns 404."""
        response = client.get("/council/sessions/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_nonexistent_session(self, client, auth_headers):
        """DELETE /council/sessions/99999 returns 404."""
        response = client.delete("/council/sessions/99999", headers=auth_headers)
        assert response.status_code == 404


class TestRouting:
    """Test the keyword-based routing logic (unit-level)."""

    def test_routing_investment_keywords(self):
        from app.agents.council import routing_node, CouncilState
        state: CouncilState = {
            "user_id": 1,
            "message": "Borsa yatırımı hakkında ne düşünüyorsun?",
            "requested_role": None,
            "resolved_role": None,
            "profile_context": "",
            "history": [],
            "response": None,
            "error": None,
        }
        result = routing_node(state)
        assert result["resolved_role"] == "investment"

    def test_routing_health_keywords(self):
        from app.agents.council import routing_node, CouncilState
        state: CouncilState = {
            "user_id": 1,
            "message": "Uyku kalitemi nasıl artırabilirim? Çok stres yapıyorum.",
            "requested_role": None,
            "resolved_role": None,
            "profile_context": "",
            "history": [],
            "response": None,
            "error": None,
        }
        result = routing_node(state)
        assert result["resolved_role"] == "health"

    def test_routing_career_keywords(self):
        from app.agents.council import routing_node, CouncilState
        state: CouncilState = {
            "user_id": 1,
            "message": "Kariyer değişikliği yapmak istiyorum, mülakat hazırlığı.",
            "requested_role": None,
            "resolved_role": None,
            "profile_context": "",
            "history": [],
            "response": None,
            "error": None,
        }
        result = routing_node(state)
        assert result["resolved_role"] == "career"

    def test_routing_explicit_role_overrides(self):
        from app.agents.council import routing_node, CouncilState
        state: CouncilState = {
            "user_id": 1,
            "message": "Borsa hakkında bilgi ver",
            "requested_role": "health",      # explicit override
            "resolved_role": None,
            "profile_context": "",
            "history": [],
            "response": None,
            "error": None,
        }
        result = routing_node(state)
        assert result["resolved_role"] == "health"

    def test_routing_unknown_defaults_to_synthesizer(self):
        from app.agents.council import routing_node, CouncilState
        state: CouncilState = {
            "user_id": 1,
            "message": "Bugün hava güzel, değil mi?",
            "requested_role": None,
            "resolved_role": None,
            "profile_context": "",
            "history": [],
            "response": None,
            "error": None,
        }
        result = routing_node(state)
        assert result["resolved_role"] == "synthesizer"
