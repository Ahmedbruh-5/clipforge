def test_reject_unsupported_extension(client):
    response = client.post(
        "/api/videos/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_list_videos_empty(client):
    response = client.get("/api/videos")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_get_missing_video(client):
    response = client.get("/api/videos/999")
    assert response.status_code == 404


def test_stream_missing_video(client):
    response = client.get("/api/videos/999/stream")
    assert response.status_code == 404
