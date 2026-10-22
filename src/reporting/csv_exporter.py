from datetime import datetime
from pathlib import Path
import re
import pandas as pd
from src.utils.file_safety import atomic_write

def unique_csv_path(path: str | Path, run_id: str | None = None, now: datetime | None = None) -> Path:
    target = Path(path)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")
    safe_run_id = re.sub(r"[^A-Za-z0-9_-]", "", str(run_id or ""))
    run_part = f"_{safe_run_id}" if safe_run_id else ""
    candidate = target.with_name(f"{target.stem}_{stamp}{run_part}{target.suffix}")
    sequence = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}_{stamp}{run_part}_{sequence}{target.suffix}")
        sequence += 1
    return candidate

def export_csv(data: pd.DataFrame | list[dict], path: str | Path, run_id: str | None = None) -> Path:
    frame = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    target = unique_csv_path(path, run_id)
    return atomic_write(target, lambda temp: frame.to_csv(temp, index=False, encoding="utf-8-sig"))
