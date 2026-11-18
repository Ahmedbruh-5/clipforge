from app.core import database
from app.models.clip import Clip
from app.models.job import Job
from app.models.video import Video
from app.services.job_recovery import recover_interrupted_work


def test_recover_interrupted_work(client):
    db = database.SessionLocal()
    try:
        video = Video(
            filename="a.mp4",
            original_filename="a.mp4",
            file_path="/tmp/missing.mp4",
            file_size=1,
            status="ready",
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        clip = Clip(
            video_id=video.id,
            title="Rendering",
            start_time=0,
            end_time=5,
            duration=5,
            status="rendering",
        )
        db.add(clip)
        job = Job(
            job_type="render",
            status="running",
            progress=40,
            video_id=video.id,
            message="in progress",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
        clip_id = clip.id
    finally:
        db.close()

    counts = recover_interrupted_work(reason="test recovery")
    assert counts["jobs"] >= 1
    assert counts["clips"] >= 1

    db = database.SessionLocal()
    try:
        job = db.get(Job, job_id)
        clip = db.get(Clip, clip_id)
        assert job is not None and job.status == "failed"
        assert clip is not None and clip.status == "failed"
        assert "test recovery" in (job.error_message or "")
    finally:
        db.close()
