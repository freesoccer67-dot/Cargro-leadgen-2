from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .config import OUTPUT_DIR
from .discovery import CANDIDATE_COLUMNS
from .outreach import recommended_pitch


EXPORT_COLUMNS = [
    "lead_id",
    "company_name",
    "website",
    "category",
    "city",
    "country",
    "generic_email",
    "phone",
    "contact_url",
    "delivery_url",
    "returns_url",
    "opportunity_type",
    "lead_score",
    "lead_priority",
    "bulky_product_signals",
    "delivery_signals",
    "return_signals",
    "own_delivery_signal",
    "showroom_signal",
    "possible_pain_points",
    "recommended_pitch",
    "evidence_snippets",
    "source_urls",
    "date_added",
    "status",
    "notes",
]


def leads_to_dataframe(leads: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for index, lead in enumerate(leads, start=1):
        row = dict(lead)
        row["lead_id"] = row.get("lead_id") or f"LEAD-{index:04d}"
        row["recommended_pitch"] = row.get("recommended_pitch") or recommended_pitch(row)
        rows.append({column: _cell_value(row.get(column, "")) for column in EXPORT_COLUMNS})
    return pd.DataFrame(rows, columns=EXPORT_COLUMNS)


def write_exports(
    leads: list[dict[str, Any]],
    csv_path: Path | None = None,
    xlsx_path: Path | None = None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = csv_path or OUTPUT_DIR / "leads.csv"
    xlsx_path = xlsx_path or OUTPUT_DIR / "leads.xlsx"
    df = leads_to_dataframe(leads)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False)
    return csv_path, xlsx_path


def crawl_log_to_dataframe(rows: list[Any]) -> pd.DataFrame:
    data = []
    for row in rows:
        data.append(
            {
                "website": getattr(row, "website", ""),
                "url": getattr(row, "url", ""),
                "status_code": getattr(row, "status_code", ""),
                "fetched_with": getattr(row, "fetched_with", ""),
                "error": getattr(row, "error", ""),
            }
        )
    return pd.DataFrame(data)


def write_crawl_log(rows: list[Any], path: Path | None = None) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = path or OUTPUT_DIR / "crawl_log.csv"
    crawl_log_to_dataframe(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_candidate_exports(
    candidates: pd.DataFrame,
    csv_path: Path | None = None,
    xlsx_path: Path | None = None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = csv_path or OUTPUT_DIR / "candidate_urls.csv"
    xlsx_path = xlsx_path or OUTPUT_DIR / "candidate_urls.xlsx"
    export_df = candidates.reindex(columns=CANDIDATE_COLUMNS).fillna("")
    export_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    export_df.to_excel(xlsx_path, index=False)
    return csv_path, xlsx_path


def _cell_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return value
