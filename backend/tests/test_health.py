def test_health_reports_phase_7(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["phase"] == "7"
    assert "range_streaming" in data["features"]
    assert "job_recovery" in data["features"]


def test_dashboard_empty(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["total_videos"] == 0
    assert data["total_clips"] == 0
    assert data["scheduled_uploads"] == 0
