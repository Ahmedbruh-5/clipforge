from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.utils.streaming import range_file_response


def test_range_helpers(tmp_path):
    path = tmp_path / "clip.bin"
    path.write_bytes(bytes(range(100)))

    app = FastAPI()

    @app.get("/f")
    def serve(request: Request):
        return range_file_response(path, request, media_type="application/octet-stream")

    client = TestClient(app)

    full = client.get("/f")
    assert full.status_code == 200
    assert len(full.content) == 100
    assert full.headers["accept-ranges"] == "bytes"

    part = client.get("/f", headers={"Range": "bytes=10-19"})
    assert part.status_code == 206
    assert part.content == bytes(range(10, 20))
    assert part.headers["content-range"] == "bytes 10-19/100"

    bad = client.get("/f", headers={"Range": "bytes=200-300"})
    assert bad.status_code == 416
