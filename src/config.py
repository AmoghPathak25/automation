from pathlib import Path
from typing import Any
import yaml
ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path, default: Any = None) -> Any:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    with config_path.open("r", encoding="utf-8") as stream:
        result = yaml.safe_load(stream)
    return default if result is None else result

def ensure_directories() -> None:
    for relative in (
        "data/input/stock_exports", "data/input/price_lists",
        "data/input/customer_lists", "data/input/email_attachments",
        "data/working", "data/output/validation_reports",
        "data/output/clearance_candidates", "data/output/offer_drafts",
        "data/archive",
    ):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
