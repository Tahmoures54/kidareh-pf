from kidareh import create_app


def test_domain_blueprints_are_registered_with_expected_routes(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "blueprint-test-key",
        "DATABASE_PATH": str(tmp_path / "blueprints.sqlite3"),
    })

    assert {"pages", "auth", "stores", "listings", "system"} <= set(app.blueprints)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/" in rules
    assert "/api/auth/signup" in rules
    assert "/api/stores" in rules
    assert "/api/listings" in rules
    assert "/api/health" in rules


def test_health_endpoint_is_available_through_factory():
    app = create_app({"TESTING": True, "SECRET_KEY": "blueprint-test-key"})
    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "service": "kidareh-pf", "database": "ok", "uploads": "writable"}
