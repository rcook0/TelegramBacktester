from __future__ import annotations
import os, time, shutil
from datetime import datetime, timezone
from typing import Optional

def rotate_reports(out_dir: str, *, retention_days: int = 30, archive_dir: Optional[str] = None) -> int:
    """Move report artifacts older than retention_days into an archive folder. Returns count moved."""
    if not os.path.isdir(out_dir):
        return 0
    archive_dir = archive_dir or os.path.join(out_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    now = time.time()
    cutoff = now - (retention_days * 86400)
    moved = 0

    for fn in os.listdir(out_dir):
        if fn == "archive":
            continue
        path = os.path.join(out_dir, fn)
        if not os.path.isfile(path):
            continue
        # only rotate typical artifacts
        if not any(fn.endswith(ext) for ext in (".csv",".json",".html",".log")):
            continue
        st = os.stat(path)
        if st.st_mtime >= cutoff:
            continue
        # archive by year-week
        dt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        wk = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
        dest_dir = os.path.join(archive_dir, wk)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(path, os.path.join(dest_dir, fn))
        moved += 1
    return moved
