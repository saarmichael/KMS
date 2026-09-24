def test_health_reports_db_migrations_and_notify(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["migrations"]["ok"], body["migrations"]
    assert body["notify"]["ok"], body["notify"]
