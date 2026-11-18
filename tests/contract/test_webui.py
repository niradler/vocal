"""Contract tests: web UI routes and static assets."""


class TestWebUI:
    def test_root_serves_landing_for_browsers(self, client):
        resp = client.get_httpx_client().get("/", headers={"Accept": "text/html,application/xhtml+xml"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "Vocal" in resp.text
        assert "Speech AI" in resp.text

    def test_root_keeps_json_for_api_clients(self, client):
        resp = client.get_httpx_client().get("/", headers={"Accept": "*/*"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_welcome_route(self, client):
        resp = client.get_httpx_client().get("/welcome")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_console_route(self, client):
        resp = client.get_httpx_client().get("/ui")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "Vocal Console" in resp.text

    def test_static_theme_css(self, client):
        resp = client.get_httpx_client().get("/static/theme.css")
        assert resp.status_code == 200
        assert "--accent-green" in resp.text

    def test_static_app_js(self, client):
        resp = client.get_httpx_client().get("/static/js/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_static_worklet_js(self, client):
        resp = client.get_httpx_client().get("/static/js/pcm-worklet.js")
        assert resp.status_code == 200
        assert "registerProcessor" in resp.text

    def test_landing_is_open_source_project_page(self, client):
        """No pricing / company marketing — Vocal is marketed as open source."""
        resp = client.get_httpx_client().get("/welcome")
        assert resp.status_code == 200
        assert "pricing" not in resp.text.lower()
        assert "Teams running Vocal" not in resp.text
        assert "open source" in resp.text.lower()


class TestHostedConsole:
    """The same webui files must work served by Vocal AND from a static host
    (GitHub Pages), where requests go straight to the user's local server."""

    def test_console_uses_relative_asset_paths(self, client):
        resp = client.get_httpx_client().get("/ui")
        assert resp.status_code == 200
        assert 'href="theme.css"' in resp.text
        assert 'src="js/app.js"' in resp.text
        assert "/static/" not in resp.text

    def test_root_fallback_serves_assets(self, client):
        # Relative URLs from /ui, /welcome and / resolve at the root.
        for path, marker in [("/theme.css", "--accent-green"), ("/js/app.js", "navigate"), ("/og.svg", "<svg")]:
            resp = client.get_httpx_client().get(path)
            assert resp.status_code == 200, path
            assert marker in resp.text, path

    def test_root_fallback_does_not_shadow_api(self, client):
        resp = client.get_httpx_client().get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_private_network_access_preflight(self, client):
        """Chrome requires this header for public-origin -> localhost calls."""
        resp = client.get_httpx_client().options(
            "/v1/settings",
            headers={
                "Origin": "https://niradler.github.io",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-private-network"] == "true"
        assert resp.headers["access-control-allow-origin"] == "https://niradler.github.io"

    def test_regular_preflight_has_no_pna_header(self, client):
        resp = client.get_httpx_client().options(
            "/v1/settings",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert resp.status_code == 200
        assert "access-control-allow-private-network" not in resp.headers
