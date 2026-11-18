import re
import uuid
from pathlib import Path


def ensure_storage_dirs(*dirs: Path) -> None:
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^\w.\- ]+", "_", name, flags=re.UNICODE)
    name = name.strip().replace(" ", "_")
    return name or "video"


def unique_storage_name(original_filename: str) -> str:
    stem = Path(sanitize_filename(original_filename)).stem[:80] or "video"
    suffix = Path(original_filename).suffix.lower()
    return f"{stem}_{uuid.uuid4().hex[:12]}{suffix}"


def format_bytes(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{num} B"
