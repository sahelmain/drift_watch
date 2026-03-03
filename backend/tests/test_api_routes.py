"""API route contract tests — verifies response shapes match frontend expectations."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestAuth:
    async def test_register_returns_token_and_user(self, client: AsyncClient):
        res = await client.post("/api/auth/register", json={
            "email": "new@test.io",
            "password": "pass1234",
            "org_name": "My Org",
        })
        assert res.status_code == 201
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "new@test.io"
        assert body["user"]["role"] == "admin"

    async def test_login_returns_token_and_user(self, auth_client: AsyncClient):
        res = await auth_client.post("/api/auth/login", json={
            "email": "admin@test.io",
            "password": "testpass123",
        })
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["user"]["email"] == "admin@test.io"

    async def test_login_invalid_creds(self, client: AsyncClient):
        res = await client.post("/api/auth/login", json={
            "email": "nobody@test.io",
            "password": "wrong",
        })
        assert res.status_code == 401


class TestSuites:
    async def test_list_suites_returns_paginated(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/suites")
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "pages" in body
        assert isinstance(body["items"], list)

    async def test_create_and_get_suite(self, auth_client: AsyncClient):
        create_res = await auth_client.post("/api/suites", json={
            "name": "Test Suite",
            "description": "A test suite",
            "yaml_content": "tests: []",
        })
        assert create_res.status_code == 201
        suite = create_res.json()
        assert suite["name"] == "Test Suite"
        suite_id = suite["id"]

        get_res = await auth_client.get(f"/api/suites/{suite_id}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Test Suite"

    async def test_update_suite(self, auth_client: AsyncClient):
        create_res = await auth_client.post("/api/suites", json={"name": "Old Name"})
        suite_id = create_res.json()["id"]

        update_res = await auth_client.put(f"/api/suites/{suite_id}", json={"name": "New Name"})
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "New Name"

    async def test_delete_suite(self, auth_client: AsyncClient):
        create_res = await auth_client.post("/api/suites", json={"name": "To Delete"})
        suite_id = create_res.json()["id"]

        del_res = await auth_client.delete(f"/api/suites/{suite_id}")
        assert del_res.status_code == 204


class TestRuns:
    async def test_list_runs_returns_paginated(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/runs")
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 0

    async def test_trigger_run(self, auth_client: AsyncClient):
        suite_res = await auth_client.post("/api/suites", json={"name": "Run Suite"})
        suite_id = suite_res.json()["id"]

        run_res = await auth_client.post(f"/api/suites/{suite_id}/run")
        assert run_res.status_code == 201
        run = run_res.json()
        assert run["suite_id"] == suite_id
        assert run["status"] == "pending"
        assert run["trigger"] == "manual"

    async def test_get_run(self, auth_client: AsyncClient):
        suite_res = await auth_client.post("/api/suites", json={"name": "Run Suite 2"})
        suite_id = suite_res.json()["id"]

        run_res = await auth_client.post(f"/api/suites/{suite_id}/run")
        run_id = run_res.json()["id"]

        get_res = await auth_client.get(f"/api/runs/{run_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == run_id

    async def test_list_runs_with_filters(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/runs?status=pending&page=1&limit=10")
        assert res.status_code == 200
        body = res.json()
        assert body["page"] == 1


class TestAlerts:
    async def test_list_alerts_empty(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/alerts")
        assert res.status_code == 200
        assert res.json() == []

    async def test_create_alert(self, auth_client: AsyncClient):
        res = await auth_client.post("/api/alerts", json={
            "channel": "slack",
            "destination": "https://hooks.slack.com/test",
            "threshold_metric": "pass_rate",
            "threshold_value": 0.8,
            "enabled": True,
        })
        assert res.status_code == 201
        alert = res.json()
        assert alert["channel"] == "slack"
        assert alert["threshold_metric"] == "pass_rate"
        assert alert["threshold_value"] == 0.8

    async def test_update_alert(self, auth_client: AsyncClient):
        create_res = await auth_client.post("/api/alerts", json={
            "channel": "email",
            "destination": "team@test.io",
            "threshold_metric": "pass_rate",
            "threshold_value": 0.9,
        })
        alert_id = create_res.json()["id"]

        update_res = await auth_client.put(f"/api/alerts/{alert_id}", json={
            "threshold_value": 0.7,
        })
        assert update_res.status_code == 200
        assert update_res.json()["threshold_value"] == 0.7

    async def test_delete_alert(self, auth_client: AsyncClient):
        create_res = await auth_client.post("/api/alerts", json={
            "channel": "slack",
            "destination": "https://hooks.slack.com/del",
            "threshold_metric": "pass_rate",
            "threshold_value": 0.5,
        })
        alert_id = create_res.json()["id"]

        del_res = await auth_client.delete(f"/api/alerts/{alert_id}")
        assert del_res.status_code == 204


class TestPolicies:
    async def test_list_policies_empty(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/policies")
        assert res.status_code == 200
        assert res.json() == []

    async def test_create_policy(self, auth_client: AsyncClient):
        res = await auth_client.post("/api/policies", json={
            "name": "Block Low Pass Rate",
            "metric": "pass_rate",
            "operator": "lt",
            "threshold": 0.8,
            "action": "block",
        })
        assert res.status_code == 201
        assert res.json()["name"] == "Block Low Pass Rate"

    async def test_delete_policy(self, auth_client: AsyncClient):
        create_res = await auth_client.post("/api/policies", json={
            "name": "To Delete",
            "metric": "pass_rate",
            "operator": "lt",
            "threshold": 0.5,
        })
        policy_id = create_res.json()["id"]

        del_res = await auth_client.delete(f"/api/policies/{policy_id}")
        assert del_res.status_code == 204


class TestSettings:
    async def test_get_settings_returns_composite(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/settings")
        assert res.status_code == 200
        body = res.json()
        assert "org" in body
        assert body["org"]["name"] == "Test Org"
        assert "members" in body
        assert len(body["members"]) >= 1
        assert "api_keys" in body
        assert "usage" in body
        assert "runs_this_month" in body["usage"]
        assert "suites_count" in body["usage"]
        assert "plan_limit" in body["usage"]

    async def test_create_api_key(self, auth_client: AsyncClient):
        res = await auth_client.post("/api/settings/api-keys", json={
            "name": "CI Key",
        })
        assert res.status_code == 201
        body = res.json()
        assert "raw_key" in body
        assert body["name"] == "CI Key"

    async def test_add_member(self, auth_client: AsyncClient):
        res = await auth_client.post("/api/settings/members", json={
            "email": "member@test.io",
            "password": "pass1234",
            "role": "member",
        })
        assert res.status_code == 201
        assert res.json()["email"] == "member@test.io"


class TestAuditLog:
    async def test_audit_log_returns_paginated(self, auth_client: AsyncClient):
        res = await auth_client.get("/api/audit-log")
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert "total" in body
        assert "pages" in body


class TestSmokeE2E:
    """Full workflow: register -> create suite -> trigger run -> verify run list."""

    async def test_full_flow(self, client: AsyncClient):
        reg = await client.post("/api/auth/register", json={
            "email": "e2e@test.io",
            "password": "e2epass123",
            "org_name": "E2E Org",
        })
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        suite = await client.post("/api/suites", json={
            "name": "E2E Suite",
            "yaml_content": "tests:\n  - name: t1\n    prompt: hello\n",
        }, headers=headers)
        assert suite.status_code == 201
        suite_id = suite.json()["id"]

        run = await client.post(f"/api/suites/{suite_id}/run", headers=headers)
        assert run.status_code == 201
        run_id = run.json()["id"]
        assert run.json()["status"] == "pending"

        runs_list = await client.get("/api/runs", headers=headers)
        assert runs_list.status_code == 200
        items = runs_list.json()["items"]
        assert any(r["id"] == run_id for r in items)

        run_detail = await client.get(f"/api/runs/{run_id}", headers=headers)
        assert run_detail.status_code == 200
        assert run_detail.json()["suite_id"] == suite_id

        settings = await client.get("/api/settings", headers=headers)
        assert settings.status_code == 200
        assert settings.json()["org"]["name"] == "E2E Org"
