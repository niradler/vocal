"""Contract tests: health and system endpoints."""

from vocal_sdk.api.health import health_health_get


class TestHealth:
    def test_health_ok(self, client):
        resp = health_health_get.sync_detailed(client=client)
        assert resp.status_code == 200

    def test_health_body(self, client):
        import json

        resp = health_health_get.sync_detailed(client=client)
        body = json.loads(resp.content)
        assert body["status"] == "healthy"
        assert "api_version" in body

    def test_root_ok(self, client):
        resp = client.get_httpx_client().get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_device_info(self, client):
        resp = client.get_httpx_client().get("/v1/system/device")
        assert resp.status_code == 200
        body = resp.json()
        assert "platform" in body
        assert "cpu_count" in body
        assert "cuda_available" in body
