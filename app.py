from __future__ import annotations

import io
import logging
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

from leadgen.config import DEFAULT_STATUS_OPTIONS, INPUT_DIR, OUTPUT_DIR, Settings
from leadgen.crawler import crawl_many
from leadgen.discovery import discover_candidate_websites, import_candidate_urls
from leadgen.exporter import (
    crawl_log_to_dataframe,
    leads_to_dataframe,
    write_candidate_exports,
    write_crawl_log,
    write_exports,
)
from leadgen.extractor import extract_lead
from leadgen.outreach import generate_outreach_draft
from leadgen.scorer import score_and_classify
from leadgen.search_api import discover_urls
from leadgen.utils import normalize_url


logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def main() -> None:
    st.set_page_config(page_title="Cargro Lead Generation", layout="wide")
    inject_netflix_theme()
    render_app_header()

    settings = settings_with_streamlit_secrets(Settings())
    ensure_session_state()

    analysis_tab, discovery_tab = st.tabs(["Analyze Leads", "Discover Websites"])
    with analysis_tab:
        show_analysis_tab(settings)
    with discovery_tab:
        show_discovery_tab(settings)


def show_analysis_tab(settings: Settings) -> None:
    section_heading("Analyze Leads", "Crawl public company pages, extract logistics signals, and score fit.")
    left_controls, right_controls = st.columns([1, 1])
    with left_controls:
        keywords_file = st.file_uploader("Search keywords CSV", type=["csv"], key="analysis_keywords")
        limit_per_keyword = st.number_input("Search results per keyword", min_value=1, max_value=20, value=5)
    with right_controls:
        manual_file = st.file_uploader("Manual URLs CSV", type=["csv"], key="analysis_manual_urls")
        max_urls = st.number_input("Maximum URLs this run", min_value=1, max_value=200, value=20)
        st.caption(f"Provider: {settings.search_provider}")

    keywords_df = read_csv_or_default(keywords_file, INPUT_DIR / "search_keywords.csv")
    manual_df = read_csv_or_default(manual_file, INPUT_DIR / "manual_urls.csv")
    if not st.session_state.discovery_analysis_urls.empty:
        manual_df = pd.concat([manual_df, st.session_state.discovery_analysis_urls], ignore_index=True)

    urls_df = build_url_dataframe(keywords_df, manual_df, settings, int(limit_per_keyword))
    metric_strip(
        [
            ("Keywords", len(keywords_df)),
            ("Manual URLs", len(manual_df)),
            ("Candidates", min(len(urls_df), int(max_urls))),
            ("Provider", settings.search_provider),
        ]
    )

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Search keywords")
        st.dataframe(keywords_df, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Manual URLs")
        st.dataframe(manual_df, use_container_width=True, hide_index=True)

    st.subheader("Candidate URLs")
    st.dataframe(urls_df.head(int(max_urls)), use_container_width=True, hide_index=True)

    if st.button("Run crawling and scoring", type="primary", disabled=urls_df.empty):
        run_pipeline(urls_df.head(int(max_urls)), settings)

    if st.session_state.leads:
        show_results()


def show_discovery_tab(settings: Settings) -> None:
    section_heading("Discover Websites", "Find likely company websites and export clean candidate URL files.")
    st.info(
        "This feature finds potential company websites from search keywords. It does not contact companies "
        "automatically. After discovery, review the candidate websites manually and then run the normal lead analysis."
    )
    with st.expander("Where do these websites come from?", expanded=True):
        st.write(
            "The system discovers potential company websites using search keywords related to bulky e-commerce "
            "categories such as garden furniture, fitness equipment, beds, furniture, and home/garden products. "
            "If a search API is configured, it collects public search results, filters out irrelevant pages, "
            "removes duplicates, and creates a clean candidate website list. These websites are then analyzed "
            "separately for logistics signals such as delivery, returns, webshop activity, heavy products, and "
            "contact details."
        )

    controls_left, controls_right = st.columns([1, 1])
    with controls_left:
        keywords_file = st.file_uploader("Upload search_keywords.csv", type=["csv"], key="discover_keywords")
        provider = st.selectbox(
            "Search provider",
            ["manual", "brave", "bing", "serpapi"],
            index=["manual", "brave", "bing", "serpapi"].index(settings.search_provider)
            if settings.search_provider in {"manual", "brave", "bing", "serpapi"}
            else 0,
        )
        provider_api_key = ""
        if provider in {"brave", "bing", "serpapi"}:
            configured_key = provider_key_for_settings(settings, provider)
            if configured_key:
                provider_api_key = configured_key
                st.success(f"Permanent {provider} API key configured.")
            else:
                provider_api_key = st.text_input(
                    "API key",
                    type="password",
                    help="Use this when the website server does not have the provider key configured.",
                ).strip()
        max_results = st.number_input("Max results per keyword", min_value=1, max_value=50, value=20)
    with controls_right:
        import_file = st.file_uploader(
            "Upload candidate or directory URLs CSV",
            type=["csv"],
            key="discover_candidate_import",
            help="Use columns such as url, category, source. Directory pages are imported as URLs; the app does not crawl directories automatically.",
        )
        st.caption("Manual directory/import mode is supported without API keys.")

    keywords_df = read_csv_or_default(keywords_file, INPUT_DIR / "search_keywords.csv")
    imported_df = read_csv_or_default(import_file, INPUT_DIR / "candidate_urls_example.csv") if import_file else pd.DataFrame()

    st.subheader("Search keywords")
    st.dataframe(keywords_df, use_container_width=True, hide_index=True)
    metric_strip(
        [
            ("Keywords", len(keywords_df)),
            ("Provider", provider),
            ("Max results", int(max_results)),
            ("Imported", len(imported_df)),
        ]
    )

    discover_settings = settings_for_provider(settings, provider, provider_api_key)
    if provider == "manual":
        st.info("No search provider configured. You can still use manual URL mode or upload a candidate URL CSV.")

    run_left, run_right = st.columns([1, 1])
    with run_left:
        run_discovery = st.button("Find candidate websites", type="primary", disabled=provider == "manual")
    with run_right:
        import_candidates = st.button("Import uploaded candidate URLs", disabled=import_file is None)

    warnings: list[str] = []
    if run_discovery:
        candidates, warnings = discover_candidate_websites(keywords_df, discover_settings, int(max_results))
        st.session_state.candidate_urls = candidates
        if not candidates.empty:
            csv_path, xlsx_path = write_candidate_exports(candidates)
            st.success(f"Saved {csv_path.name} and {xlsx_path.name} in {OUTPUT_DIR}.")
    if import_candidates:
        candidates = import_candidate_urls(imported_df)
        st.session_state.candidate_urls = candidates
        if not candidates.empty:
            csv_path, xlsx_path = write_candidate_exports(candidates)
            st.success(f"Saved {csv_path.name} and {xlsx_path.name} in {OUTPUT_DIR}.")

    for warning in warnings:
        st.info(warning)

    candidates_df = st.session_state.candidate_urls
    if not candidates_df.empty:
        metric_strip(
            [
                ("Candidates", len(candidates_df)),
                ("Best score", int(pd.to_numeric(candidates_df["confidence_score"]).max())),
                ("Domains", candidates_df["domain"].nunique()),
                ("Status", "Ready"),
            ]
        )
    st.subheader("Discovered websites")
    st.dataframe(candidates_df, use_container_width=True, hide_index=True)

    if not candidates_df.empty:
        csv_bytes = candidates_df.to_csv(index=False).encode("utf-8-sig")
        xlsx_buffer = io.BytesIO()
        candidates_df.to_excel(xlsx_buffer, index=False)
        download_left, download_middle, download_right = st.columns(3)
        with download_left:
            st.download_button("Download candidate URLs CSV", csv_bytes, "candidate_urls.csv", "text/csv")
        with download_middle:
            st.download_button(
                "Download candidate URLs XLSX",
                xlsx_buffer.getvalue(),
                "candidate_urls.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with download_right:
            if st.button("Send candidates to analysis"):
                st.session_state.discovery_analysis_urls = candidates_df[["url", "category"]].copy()
                st.success("Candidates are available in the Analyze Leads tab.")


def ensure_session_state() -> None:
    st.session_state.setdefault("leads", [])
    st.session_state.setdefault("crawl_log", pd.DataFrame())
    st.session_state.setdefault("candidate_urls", pd.DataFrame())
    st.session_state.setdefault("discovery_analysis_urls", pd.DataFrame(columns=["url", "category"]))


def settings_with_streamlit_secrets(settings: Settings) -> Settings:
    return settings_with_secret_values(settings, read_streamlit_secret_values())


def settings_with_secret_values(settings: Settings, secrets: dict[str, str]) -> Settings:
    search_provider = secrets.get("SEARCH_PROVIDER", "").strip().lower()
    brave_key = secrets.get("BRAVE_SEARCH_API_KEY", "").strip()
    bing_key = secrets.get("BING_SEARCH_API_KEY", "").strip()
    serpapi_key = (
        secrets.get("SERPAPI_API_KEY", "").strip() or secrets.get("SERPAPI_KEY", "").strip()
    )

    updates = {}
    if search_provider:
        updates["search_provider"] = search_provider
    elif settings.search_provider == "manual" and serpapi_key:
        updates["search_provider"] = "serpapi"
    if brave_key:
        updates["brave_search_api_key"] = brave_key
    if bing_key:
        updates["bing_search_api_key"] = bing_key
    if serpapi_key:
        updates["serpapi_api_key"] = serpapi_key
    return replace(settings, **updates) if updates else settings


def read_streamlit_secret_values() -> dict[str, str]:
    keys = [
        "SEARCH_PROVIDER",
        "BRAVE_SEARCH_API_KEY",
        "BING_SEARCH_API_KEY",
        "SERPAPI_API_KEY",
        "SERPAPI_KEY",
    ]
    values: dict[str, str] = {}
    try:
        secret_store = st.secrets
    except Exception:
        return values

    for key in keys:
        try:
            value = secret_store.get(key, "")
        except Exception:
            value = ""
        if value:
            values[key] = str(value)

    try:
        search_secrets = secret_store.get("search", {})
    except Exception:
        search_secrets = {}
    for key in keys:
        try:
            value = search_secrets.get(key, "") if search_secrets else ""
        except AttributeError:
            value = ""
        if value:
            values[key] = str(value)
    return values


def provider_key_for_settings(settings: Settings, provider: str) -> str:
    if provider == "brave":
        return settings.brave_search_api_key
    if provider == "bing":
        return settings.bing_search_api_key
    if provider == "serpapi":
        return settings.serpapi_api_key
    return ""


def settings_for_provider(settings: Settings, provider: str, api_key: str = "") -> Settings:
    updates = {"search_provider": provider}
    if provider == "brave":
        updates["brave_search_api_key"] = api_key
    elif provider == "bing":
        updates["bing_search_api_key"] = api_key
    elif provider == "serpapi":
        updates["serpapi_api_key"] = api_key
    return replace(settings, **updates)


def inject_netflix_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --cargro-bg: #050505;
            --cargro-panel: #111111;
            --cargro-panel-2: #171717;
            --cargro-border: rgba(255, 255, 255, 0.12);
            --cargro-muted: #a7a7a7;
            --cargro-text: #f5f5f1;
            --cargro-red: #e50914;
            --cargro-red-dark: #b20710;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(229, 9, 20, 0.18), transparent 32rem),
                linear-gradient(180deg, #050505 0%, #0a0a0a 45%, #050505 100%);
            color: var(--cargro-text);
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1380px;
        }

        .cargro-hero {
            border-bottom: 1px solid var(--cargro-border);
            margin-bottom: 1.4rem;
            padding: 0.8rem 0 1.3rem;
        }

        .cargro-brand {
            color: var(--cargro-red);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.16rem;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }

        .cargro-title {
            color: var(--cargro-text);
            font-size: 2.35rem;
            font-weight: 850;
            line-height: 1.05;
            margin: 0;
        }

        .cargro-subtitle {
            color: var(--cargro-muted);
            font-size: 1rem;
            margin-top: 0.55rem;
            max-width: 58rem;
        }

        .section-kicker {
            color: var(--cargro-red);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.14rem;
            text-transform: uppercase;
            margin: 0.35rem 0 0.2rem;
        }

        .section-title {
            color: var(--cargro-text);
            font-size: 1.45rem;
            font-weight: 800;
            margin: 0;
        }

        .section-copy {
            color: var(--cargro-muted);
            margin: 0.25rem 0 1rem;
        }

        .metric-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 1rem 0 1.2rem;
        }

        .metric-tile {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.035));
            border: 1px solid var(--cargro-border);
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            min-height: 4.8rem;
        }

        .metric-label {
            color: var(--cargro-muted);
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08rem;
        }

        .metric-value {
            color: var(--cargro-text);
            font-size: 1.45rem;
            font-weight: 850;
            line-height: 1.2;
            margin-top: 0.35rem;
            overflow-wrap: anywhere;
        }

        div[data-testid="stTabs"] [role="tablist"] {
            gap: 0.35rem;
            border-bottom: 1px solid var(--cargro-border);
        }

        div[data-testid="stTabs"] button[role="tab"] {
            background: transparent;
            border-radius: 0;
            color: var(--cargro-muted);
            font-weight: 800;
            padding: 0.8rem 1.05rem;
        }

        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--cargro-text);
            border-bottom: 3px solid var(--cargro-red);
        }

        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stDataFrame"]),
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stDataEditor"]) {
            border: 1px solid var(--cargro-border);
            border-radius: 8px;
            overflow: hidden;
            background: var(--cargro-panel);
        }

        div[data-testid="stFileUploader"],
        div[data-testid="stNumberInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stTextInput"],
        div[data-testid="stMultiSelect"],
        div[data-testid="stSlider"],
        div[data-testid="stTextArea"] {
            background: rgba(255, 255, 255, 0.035);
            border: 1px solid var(--cargro-border);
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
        }

        div[data-testid="stAlert"] {
            background: rgba(229, 9, 20, 0.10);
            border: 1px solid rgba(229, 9, 20, 0.35);
            border-radius: 8px;
            color: var(--cargro-text);
        }

        details[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.035);
            border: 1px solid var(--cargro-border);
            border-radius: 8px;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            background: #202020;
            color: var(--cargro-text);
            font-weight: 800;
            min-height: 2.75rem;
        }

        .stButton > button[kind="primary"] {
            background: var(--cargro-red);
            border-color: var(--cargro-red);
            color: #ffffff;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: var(--cargro-red);
            color: #ffffff;
        }

        .stButton > button[kind="primary"]:hover {
            background: var(--cargro-red-dark);
            border-color: var(--cargro-red-dark);
        }

        h2, h3 {
            color: var(--cargro-text);
            font-weight: 800;
        }

        p, label, span {
            color: inherit;
        }

        @media (max-width: 850px) {
            .cargro-title {
                font-size: 1.75rem;
            }

            .metric-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_header() -> None:
    st.markdown(
        """
        <div class="cargro-hero">
            <div class="cargro-brand">CARGRO</div>
            <h1 class="cargro-title">Lead Generation Studio</h1>
            <div class="cargro-subtitle">
                Discover bulky e-commerce prospects, prepare candidate URL lists, and score logistics opportunities.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_heading(title: str, detail: str) -> None:
    st.markdown(
        f"""
        <div class="section-kicker">Workspace</div>
        <h2 class="section-title">{title}</h2>
        <div class="section-copy">{detail}</div>
        """,
        unsafe_allow_html=True,
    )


def metric_strip(items: list[tuple[str, object]]) -> None:
    tiles = []
    for label, value in items:
        tiles.append(
            f"""
            <div class="metric-tile">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            """
        )
    st.markdown(f"<div class=\"metric-strip\">{''.join(tiles)}</div>", unsafe_allow_html=True)


def read_csv_or_default(uploaded_file, default_path: Path) -> pd.DataFrame:
    try:
        if uploaded_file is not None:
            return pd.read_csv(uploaded_file).fillna("")
        if default_path.exists():
            return pd.read_csv(default_path).fillna("")
    except Exception as exc:  # noqa: BLE001 - show friendly Streamlit error
        st.error(f"Could not read CSV: {exc}")
    return pd.DataFrame()


def build_url_dataframe(
    keywords_df: pd.DataFrame,
    manual_df: pd.DataFrame,
    settings: Settings,
    limit_per_keyword: int,
    use_search_api: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    if not manual_df.empty and "url" in manual_df.columns:
        for _, row in manual_df.iterrows():
            url = normalize_url(str(row.get("url", "")))
            if url:
                rows.append(
                    {
                        "url": url,
                        "category": str(row.get("category", "")),
                        "source": "manual",
                        "keyword": "",
                    }
                )

    if use_search_api and not keywords_df.empty and "keyword" in keywords_df.columns:
        keywords = [str(value).strip() for value in keywords_df["keyword"].tolist() if str(value).strip()]
        results, warnings = discover_urls(keywords, settings, limit_per_keyword=limit_per_keyword)
        for warning in warnings:
            st.info(warning)
        category_by_keyword = {
            str(row.get("keyword", "")): str(row.get("category", "")) for _, row in keywords_df.iterrows()
        }
        for result in results:
            rows.append(
                {
                    "url": result.url,
                    "category": category_by_keyword.get(result.keyword, ""),
                    "source": result.provider,
                    "keyword": result.keyword,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["url", "category", "source", "keyword"])

    df = pd.DataFrame(rows).drop_duplicates(subset=["url"]).reset_index(drop=True)
    return df[["url", "category", "source", "keyword"]]


def run_pipeline(urls_df: pd.DataFrame, settings: Settings) -> None:
    progress = st.progress(0)
    status = st.empty()

    urls = urls_df["url"].tolist()
    categories = dict(zip(urls_df["url"], urls_df.get("category", pd.Series([""] * len(urls_df)))))
    status.write("Crawling public pages...")
    pages_by_site, crawl_log = crawl_many(urls, settings)
    progress.progress(45)

    leads = []
    for index, (website, pages) in enumerate(pages_by_site.items(), start=1):
        status.write(f"Extracting and scoring {website}...")
        lead = extract_lead(website, pages, categories.get(website, ""))
        lead["lead_id"] = f"LEAD-{index:04d}"
        lead = score_and_classify(lead)
        leads.append(lead)
        progress.progress(45 + int(index / max(len(pages_by_site), 1) * 45))

    csv_path, xlsx_path = write_exports(leads)
    log_path = write_crawl_log(crawl_log)
    st.session_state.leads = leads
    st.session_state.crawl_log = crawl_log_to_dataframe(crawl_log)
    progress.progress(100)
    status.success(f"Saved {csv_path.name}, {xlsx_path.name}, and {log_path.name} in {OUTPUT_DIR}.")


def show_results() -> None:
    st.subheader("Leads")
    df = leads_to_dataframe(st.session_state.leads)

    categories = sorted([item for item in df["category"].dropna().unique().tolist() if item])
    selected_categories = st.multiselect("Category", categories)
    score_range = st.slider("Lead score", 0, 100, (0, 100))
    opportunity_filter = st.text_input("Opportunity contains")

    filtered = df.copy()
    if selected_categories:
        filtered = filtered[filtered["category"].isin(selected_categories)]
    filtered = filtered[
        (filtered["lead_score"].astype(int) >= score_range[0])
        & (filtered["lead_score"].astype(int) <= score_range[1])
    ]
    if opportunity_filter:
        filtered = filtered[
            filtered["opportunity_type"].str.contains(opportunity_filter, case=False, na=False)
        ]

    edited = st.data_editor(
        filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "website": st.column_config.LinkColumn("website"),
            "contact_url": st.column_config.LinkColumn("contact_url"),
            "delivery_url": st.column_config.LinkColumn("delivery_url"),
            "returns_url": st.column_config.LinkColumn("returns_url"),
            "status": st.column_config.SelectboxColumn("status", options=DEFAULT_STATUS_OPTIONS),
        },
        disabled=[
            column
            for column in filtered.columns
            if column not in {"status", "notes"}
        ],
    )

    selected_lead_id = st.selectbox("Outreach draft lead", edited["lead_id"].tolist())
    if selected_lead_id:
        lead = next((item for item in st.session_state.leads if item.get("lead_id") == selected_lead_id), None)
        if lead is None:
            row = edited[edited["lead_id"] == selected_lead_id].iloc[0].to_dict()
            lead = row
        st.text_area("Manual Dutch outreach draft", generate_outreach_draft(lead), height=260)

    csv_bytes = edited.to_csv(index=False).encode("utf-8-sig")
    xlsx_buffer = io.BytesIO()
    edited.to_excel(xlsx_buffer, index=False)

    download_left, download_right = st.columns(2)
    with download_left:
        st.download_button("Download filtered CSV", csv_bytes, "cargro_leads_filtered.csv", "text/csv")
    with download_right:
        st.download_button(
            "Download filtered XLSX",
            xlsx_buffer.getvalue(),
            "cargro_leads_filtered.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("Crawl log"):
        st.dataframe(st.session_state.crawl_log, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
