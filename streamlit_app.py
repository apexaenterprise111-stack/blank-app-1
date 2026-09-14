"""Streamlit front end for the four-platform listing studio.

The app is intentionally upload-first: each platform gets its own current
master workbook, and every generated copy is validated against that same
workbook before it can be downloaded.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd
import streamlit as st

from listing_engine import (
    PLATFORMS,
    SUPPORTED_WORKBOOK_EXTENSIONS,
    build_export_zip,
    build_manifest,
    format_external_validation_report,
    generate_customer_workbook,
    inspect_image_link_zip,
    inspect_sku_source,
    inspect_workbook,
    validate_external_inputs,
)


st.set_page_config(
    page_title="Listing Forge · Marketplace Studio",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# A quiet, editorial UI keeps the many workbook details readable on desktop
# and mobile without hiding the strict data-safety model.
st.markdown(
    """
    <style>
      :root { --ink:#17211b; --muted:#66736b; --line:#dfe7e1; --green:#16734a; --mint:#eaf5ee; --sand:#fbfaf6; }
      .stApp { background: #fbfaf6; }
      [data-testid="stHeader"] { background: rgba(251,250,246,.88); }
      .block-container { padding-top: 2.1rem; padding-bottom: 4rem; max-width: 1440px; }
      .hero { display:flex; align-items:flex-start; justify-content:space-between; gap:2rem; padding: .2rem 0 1.5rem; }
      .eyebrow { color:var(--green); font-size:.74rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; margin-bottom:.55rem; }
      .hero h1 { color:var(--ink); font-size:clamp(2rem,4vw,3.5rem); letter-spacing:-.055em; line-height:.98; margin:0; max-width:780px; }
      .hero p { color:var(--muted); font-size:1.04rem; line-height:1.55; max-width:720px; margin:.85rem 0 0; }
      .hero-mark { border:1px solid #cde4d4; background:var(--mint); color:var(--green); border-radius:18px; min-width:128px; padding:1.1rem 1.15rem; text-align:center; font-weight:800; }
      .hero-mark .big { display:block; font-size:2rem; letter-spacing:-.08em; line-height:1; }
      .hero-mark .small { display:block; font-size:.7rem; letter-spacing:.12em; margin-top:.35rem; text-transform:uppercase; }
      .section-label { color:var(--ink); font-size:1.27rem; font-weight:750; letter-spacing:-.02em; margin:.45rem 0 .15rem; }
      .section-note { color:var(--muted); font-size:.92rem; margin:0 0 1rem; }
      .rule-card { border:1px solid #d8e9dc; background:linear-gradient(135deg,#f2faf4,#fbfaf6); border-radius:16px; padding:1rem 1.1rem; margin:.5rem 0 1.25rem; }
      .rule-card strong { color:#155c3d; }
      .upload-card { border:1px solid var(--line); background:white; border-radius:16px; padding:.7rem .8rem .25rem; min-height:150px; box-shadow:0 4px 18px rgba(22,42,29,.035); }
      .upload-card h4 { margin:.15rem 0 .1rem; color:var(--ink); }
      .platform-chip { display:inline-block; border-radius:999px; padding:.22rem .55rem; font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; font-weight:800; color:var(--green); background:#e9f5ed; }
      .qa-pass { border-left:4px solid #20945a; background:#eff9f1; color:#145e39; padding:.65rem .8rem; border-radius:8px; }
      .qa-warn { border-left:4px solid #ce9c28; background:#fff8e8; color:#795a12; padding:.65rem .8rem; border-radius:8px; }
      .qa-fail { border-left:4px solid #c63d46; background:#fff0f0; color:#852630; padding:.65rem .8rem; border-radius:8px; }
      .mini { color:var(--muted); font-size:.82rem; }
      div[data-testid="stMetric"] { background:white; border:1px solid var(--line); border-radius:14px; padding:.55rem .8rem; }
      div[data-testid="stMetricLabel"] { color:var(--muted); }
      .stButton > button[kind="primary"] { background:#16734a; border-color:#16734a; }
      @media (max-width: 700px) { .hero { flex-direction:column; } .hero-mark { align-self:flex-start; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def _source_signature(uploaded: Any) -> tuple[str, int, str] | None:
    if uploaded is None:
        return None
    data = uploaded.getvalue()
    return uploaded.name, len(data), hashlib.sha256(data).hexdigest()[:16]


@st.cache_data(show_spinner=False)
def cached_inspection(data: bytes, filename: str) -> dict[str, Any]:
    return inspect_workbook(data, filename)


def _platform_records(
    results: list[Any],
    external_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    external_by_platform = {
        item.get("platform"): item
        for item in (external_report or {}).get("platforms", [])
    }
    records: list[dict[str, Any]] = []
    for result in results:
        report = result.report or {}
        records.append(
            {
                "platform": result.platform,
                "customer": f"Customer {result.customer_number:02d}",
                "output_file": result.filename,
                "source_file": report.get("source_filename", ""),
                "data_sheet": report.get("data_sheet", ""),
                "groups": report.get("group_count", ""),
                "rows": report.get("row_count", ""),
                "changed_cells": report.get("changed_cells", ""),
                "reordered_groups": report.get("reordered_groups", False),
                "status": "PASS" if result.success else "FAIL",
                "warnings": " | ".join(result.warnings),
                "errors": " | ".join(result.errors),
                "sku_validation": external_by_platform.get(result.platform, {}).get("sku_status", "not checked"),
                "image_validation": external_by_platform.get(result.platform, {}).get("image_status", "not checked"),
            }
        )
    return records


def _sheet_option(profile: dict[str, Any]) -> tuple[list[str], str | None]:
    names = [sheet["name"] for sheet in profile.get("sheets", [])]
    return names, profile.get("recommended_sheet") or (names[0] if names else None)


def _render_inspection(platform: str, uploaded: Any, profile: dict[str, Any]) -> str | None:
    """Render one workbook's inspection and return the chosen data sheet."""

    if profile.get("error"):
        st.markdown(
            f'<div class="qa-fail"><strong>{platform} could not be opened.</strong><br>{profile["error"]}</div>',
            unsafe_allow_html=True,
        )
        return None

    names, recommended = _sheet_option(profile)
    if not names:
        st.warning("No worksheets were found in this workbook.")
        return None

    with st.expander(f"{platform} · {uploaded.name}", expanded=True):
        chosen = st.selectbox(
            "Data sheet to edit",
            names,
            index=names.index(recommended) if recommended in names else 0,
            key=f"sheet_choice_{platform}",
            help="Only this sheet receives approved content edits. Every other sheet is preserved.",
        )
        selected = next(sheet for sheet in profile["sheets"] if sheet["name"] == chosen)
        if profile.get("compatibility_mode"):
            st.warning(
                f"{uploaded.name} is accepted in compatibility mode. It will be converted to .xlsx for safe editing; review format-specific features after export."
            )
        if profile.get("xml_sanitized"):
            st.warning(
                f"This workbook contains {profile.get('xml_sanitized_count', 0)} invalid XML control character(s). They are normalized to spaces only so the workbook can be opened; review the affected text after export."
            )
        identity = ", ".join(selected.get("product_identities", [])) or "Not detected"
        content = ", ".join(selected.get("content_fields", [])) or "None detected"
        groups = ", ".join(selected.get("group_values", [])[:8]) or "Not detected"
        metrics = st.columns(4)
        metrics[0].metric("Rows", selected.get("row_count", 0))
        metrics[1].metric("Columns", selected.get("column_count", 0))
        metrics[2].metric("Header row", selected.get("header_row") or "—")
        metrics[3].metric("Groups found", len(selected.get("group_values", [])))
        st.markdown(
            f"**Current product identity:** `{identity}`  \n"
            f"**Editable fields detected:** `{content}`  \n"
            f"**Group values:** `{groups}`",
        )
        if selected.get("state") != "visible":
            st.info("This sheet is hidden in the source workbook. It will remain hidden in every customer copy.")
        if selected.get("header_row") is None:
            st.warning("No header row was detected. Choose a different sheet or revise the workbook before generating.")
        if selected.get("validations") or selected.get("merged_ranges") or selected.get("formula_count"):
            st.caption(
                f"Preservation checks: {selected.get('validations', 0)} validation rule(s) · "
                f"{selected.get('merged_ranges', 0)} merged range(s) · "
                f"{selected.get('formula_count', 0)} formula cell(s)"
            )
        preview = selected.get("preview", [])
        if preview:
            headers = [column.get("header", "") for column in selected.get("columns", [])]
            # The preview has the complete worksheet width; pad/truncate the
            # labels so Streamlit shows a useful inspection table.
            width = len(preview[0]) if preview else len(headers)
            labels = headers[:width] + [f"Column {index}" for index in range(len(headers) + 1, width + 1)]
            labels = [label or f"Column {index + 1}" for index, label in enumerate(labels[:width])]
            preview_frame = pd.DataFrame(preview, columns=labels)
            st.dataframe(preview_frame, use_container_width=True, hide_index=True)
        st.caption(
            "The preview is read-only. Price, image, SKU, identifiers, variation fields, and all unrecognized columns are treated as locked."
        )
    return chosen


def _render_sidebar() -> tuple[str, bool, str]:
    with st.sidebar:
        st.markdown("### Listing Forge")
        st.caption("4 platforms · 10 customer versions · one protected master per platform")
        st.divider()
        st.markdown("**Workflow**")
        st.markdown("1. Upload four current master workbooks  \n2. Add SKU input and image-link ZIP  \n3. Inspect each detected structure  \n4. Generate and validate 40 copies  \n5. Download the ZIP and QA manifest")
        st.divider()
        st.markdown("**Strict master safeguards**")
        st.checkbox("Fail closed if locked data changes", value=True, disabled=True)
        st.checkbox("Preserve .xlsm format and VBA", value=True, disabled=True)
        st.checkbox("Keep source images and URLs unchanged", value=True, disabled=True)
        st.checkbox("Use SKU input for validation only", value=True, disabled=True)
        st.checkbox("Use image-link ZIP for validation only", value=True, disabled=True)
        st.divider()
        st.caption("No old product template is used. Each platform is inspected independently from the file you upload.")
    with st.expander("Optional confirmed facts", expanded=False):
        st.write(
            "Use this only for facts supplied separately by you. It is appended as confirmed copy; it is never used to alter price, images, SKU, IDs, variations, or style codes."
        )
        confirmed = st.text_area(
            "Additional confirmed product detail",
            value="",
            max_chars=500,
            placeholder="Example: Fabric: cotton; intended use: daily wear",
            label_visibility="collapsed",
        ).strip()
        if confirmed:
            st.caption("This text will be treated as user-confirmed and may appear in descriptions.")
    return "", True, confirmed


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
      <div>
        <div class="eyebrow">Marketplace content operations</div>
        <h1>One master workbook.<br>Forty upload-ready listings.</h1>
        <p>Generate ten genuinely different customer versions for Amazon, Meesho, Flipkart, and Snapdeal while protecting the current product workbook as the source of truth.</p>
      </div>
      <div class="hero-mark"><span class="big">4 × 10</span><span class="small">strictly validated</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="rule-card"><strong>Current Excel first.</strong> Upload the current Demo/Ready workbook for each platform. The app reads its product identity, sheet names, headers, dropdowns, groups, variations, and locked data before writing only detected Title, Description, Keyword, and Bullet fields.</div>',
    unsafe_allow_html=True,
)

uploads: dict[str, Any] = {}
card_columns = st.columns(2)
for index, platform in enumerate(PLATFORMS):
    with card_columns[index % 2]:
        st.markdown(f'<div class="upload-card"><span class="platform-chip">{platform}</span><h4>Current {platform} master</h4>', unsafe_allow_html=True)
        accepted_types = list(SUPPORTED_WORKBOOK_EXTENSIONS)
        upload_help = (
            "Accepted Excel formats: .xlsx, .xlsm, .xls, .xlsb, .xltx, .xltm, and .xlt. "
            "Legacy/binary formats are converted to .xlsx compatibility copies for safe editing."
        )
        uploads[platform] = st.file_uploader(
            f"Upload {platform} workbook",
            type=accepted_types,
            key=f"upload_{platform}",
            label_visibility="collapsed",
            help=upload_help,
        )
        st.markdown("</div>", unsafe_allow_html=True)

loaded = sum(upload is not None for upload in uploads.values())
metric_columns = st.columns(4)
metric_columns[0].metric("Masters loaded", f"{loaded}/4")
metric_columns[1].metric("Customer files", "40")
metric_columns[2].metric("Per platform", "10")
metric_columns[3].metric("Locked by default", "All other fields")

st.markdown('<div class="section-label">01A · Add locked reference inputs</div>', unsafe_allow_html=True)
st.markdown(
    '<p class="section-note">Provide the SKU list and image-link ZIP you want checked against the four masters. These inputs are validation-only: the tool never replaces SKU cells or image URLs.</p>',
    unsafe_allow_html=True,
)
reference_columns = st.columns(2)
with reference_columns[0]:
    st.markdown("**SKU input**")
    sku_upload = st.file_uploader(
        "SKU file",
        type=list(SUPPORTED_WORKBOOK_EXTENSIONS) + ["csv", "tsv", "txt"],
        key="sku_input_file",
        help="Upload a SKU workbook/CSV/TXT in any supported Excel format, or paste one SKU per line below.",
    )
    pasted_skus = st.text_area(
        "Paste SKU values",
        key="pasted_sku_values",
        placeholder="Paste one SKU per line, or separate values with commas",
        height=96,
    )
with reference_columns[1]:
    st.markdown("**Image-link ZIP**")
    image_link_zip = st.file_uploader(
        "ZIP containing image links",
        type=["zip"],
        key="image_link_zip",
        help="The ZIP may contain TXT/CSV/JSON/link files or a workbook containing HTTP image URLs.",
    )
    st.caption("Existing image links in each master remain the protected source of truth. The ZIP is checked, never copied over them.")

sku_input = inspect_sku_source(
    sku_upload.getvalue() if sku_upload else None,
    sku_upload.name if sku_upload else "",
    pasted_text=pasted_skus,
)
image_input = inspect_image_link_zip(
    image_link_zip.getvalue() if image_link_zip else None,
    image_link_zip.name if image_link_zip else "",
)
reference_status = st.columns(2)
if sku_input.get("ok"):
    reference_status[0].success(f"SKU input ready · {sku_input['count']} unique SKU(s)")
else:
    reference_status[0].info("SKU input pending · upload a file or paste at least one SKU")
    for error in sku_input.get("errors", []):
        reference_status[0].error(error)
if image_input.get("ok"):
    reference_status[1].success(
        f"Image-link ZIP ready · {image_input.get('link_count', 0)} unique link(s) · {len(image_input.get('members', []))} member(s)"
    )
else:
    reference_status[1].info("Image-link ZIP pending · provide a ZIP containing readable image URLs")
    if image_input.get("error") and image_link_zip:
        reference_status[1].error(image_input["error"])

# Clear old output when any source workbook changes.
signature = tuple((platform, _source_signature(uploads[platform])) for platform in PLATFORMS)
reference_signature = (
    _source_signature(sku_upload),
    _source_signature(image_link_zip),
    hashlib.sha256((pasted_skus or "").encode("utf-8")).hexdigest()[:16],
)
if st.session_state.get("source_signature") != signature:
    st.session_state["source_signature"] = signature
    st.session_state.pop("generation_results", None)
    st.session_state.pop("manifest_records", None)
    st.session_state.pop("export_zip", None)
    st.session_state.pop("platform_zips", None)

_, _, confirmed_context = _render_sidebar()

profiles: dict[str, dict[str, Any]] = {}
chosen_sheets: dict[str, str | None] = {}
if loaded:
    st.markdown('<div class="section-label">01 · Inspect current masters</div>', unsafe_allow_html=True)
    st.markdown('<p class="section-note">The product identity shown below comes from each uploaded workbook—not from a filename, old template, or other platform.</p>', unsafe_allow_html=True)
    for platform in PLATFORMS:
        upload = uploads[platform]
        if upload is None:
            st.info(f"Upload the current {platform} master to continue.")
            continue
        raw = upload.getvalue()
        profile = cached_inspection(raw, upload.name)
        profiles[platform] = profile
        chosen_sheets[platform] = _render_inspection(platform, upload, profile)
else:
    st.markdown('<div class="section-label">01 · Upload four current masters</div>', unsafe_allow_html=True)
    st.markdown('<p class="section-note">Nothing is generated until all four current Demo/Ready workbooks are present and inspectable.</p>', unsafe_allow_html=True)

external_report: dict[str, Any] = {}
external_sources_ready = bool(sku_input.get("ok") and image_input.get("ok"))
if external_sources_ready and len(chosen_sheets) == 4 and all(chosen_sheets.get(platform) for platform in PLATFORMS):
    external_report = validate_external_inputs(
        {
            platform: {
                "data": uploads[platform].getvalue(),
                "filename": uploads[platform].name,
                "sheet_name": chosen_sheets[platform],
            }
            for platform in PLATFORMS
        },
        sku_input["values"],
        image_input["links"],
    )
    with st.expander("Reference-input cross-check", expanded=True):
        st.caption("Mismatches are review warnings only. The generated workbook still keeps every source SKU and image field unchanged.")
        crosscheck_rows = []
        for item in external_report.get("platforms", []):
            crosscheck_rows.append(
                {
                    "Platform": item.get("platform"),
                    "Status": item.get("status"),
                    "SKU matched": item.get("matched_skus", 0),
                    "SKU in workbook": item.get("workbook_sku_count", 0),
                    "Images matched": item.get("matched_images", 0),
                    "Images in workbook": item.get("workbook_image_count", 0),
                }
            )
        if crosscheck_rows:
            st.dataframe(pd.DataFrame(crosscheck_rows), use_container_width=True, hide_index=True)
        for warning in external_report.get("warnings", []):
            st.warning(warning)
        for error in external_report.get("errors", []):
            st.error(error)

# A changed sheet choice or confirmed-facts brief is a new generation input;
# never leave a stale ZIP visible after either changes.
configuration_signature = (
    signature,
    reference_signature,
    tuple((platform, chosen_sheets.get(platform)) for platform in PLATFORMS),
    confirmed_context,
)
if st.session_state.get("configuration_signature") not in (None, configuration_signature):
    st.session_state.pop("generation_results", None)
    st.session_state.pop("manifest_records", None)
    st.session_state.pop("export_zip", None)
    st.session_state.pop("platform_zips", None)
st.session_state["configuration_signature"] = configuration_signature

st.markdown('<div class="section-label">02 · Generate, validate, export</div>', unsafe_allow_html=True)
st.markdown('<p class="section-note">Every customer copy is re-opened after saving. If a locked value, validation rule, formula, image relationship, sheet, header, or identifier changes, that workbook fails closed.</p>', unsafe_allow_html=True)

invalid_profiles = [platform for platform, profile in profiles.items() if profile.get("error")]
ready = (
    loaded == 4
    and len(profiles) == 4
    and not invalid_profiles
    and all(chosen_sheets.get(platform) for platform in PLATFORMS)
    and external_sources_ready
    and bool(external_report.get("ok"))
)
if invalid_profiles:
    st.warning("Fix the workbook inspection errors before generating: " + ", ".join(invalid_profiles) + ".")
if not external_sources_ready:
    st.info("Upload a SKU source and an image-link ZIP before generating. Both are locked reference inputs and will be validated without overwriting the masters.")
elif external_report and not external_report.get("ok"):
    st.error("Reference-input validation could not complete. Fix the reported input error before generating.")

if st.button("Generate and validate all 40 files", type="primary", disabled=not ready, use_container_width=True):
    all_results: list[Any] = []
    progress = st.progress(0, text="Starting strict workbook checks…")
    status_box = st.empty()
    failed_platforms: list[str] = []
    total_steps = len(PLATFORMS) * 10
    completed = 0
    for platform in PLATFORMS:
        upload = uploads[platform]
        platform_failed = False
        for customer_number in range(1, 11):
            status_box.write(f"{platform} · Customer {customer_number:02d} — copying, writing approved fields, and validating…")
            result = generate_customer_workbook(
                upload.getvalue(),
                upload.name,
                platform,
                customer_number,
                sheet_name=chosen_sheets[platform],
                confirmed_context=confirmed_context,
            )
            all_results.append(result)
            if not result.success:
                platform_failed = True
            completed += 1
            progress.progress(completed / total_steps, text=f"Validated {completed} of {total_steps} workbooks")
        if platform_failed:
            failed_platforms.append(platform)

    records = _platform_records(all_results, external_report)
    passed = sum(result.success for result in all_results)
    st.session_state["generation_results"] = all_results
    st.session_state["manifest_records"] = records
    external_validation_text = format_external_validation_report(external_report)
    if passed == 40:
        st.session_state["export_zip"] = build_export_zip(
            all_results,
            records,
            external_validation_report=external_validation_text,
        )
        platform_zips: dict[str, bytes] = {}
        for platform in PLATFORMS:
            platform_results = [result for result in all_results if result.platform == platform]
            platform_zips[platform] = build_export_zip(
                platform_results,
                [record for record in records if record["platform"] == platform],
                filename=f"{platform.lower()}_customer_files.zip",
                external_validation_report=external_validation_text,
            )
        st.session_state["platform_zips"] = platform_zips
        status_box.success("All 40 customer workbooks passed strict validation.")
    else:
        status_box.error(f"{passed} of 40 workbooks passed. No all-files ZIP was created; review the failed workbooks below.")
        if failed_platforms:
            st.warning("Platforms with at least one failed customer copy: " + ", ".join(failed_platforms))

results = st.session_state.get("generation_results", [])
if results:
    passed = sum(result.success for result in results)
    st.markdown('<div class="section-label">03 · QA results and downloads</div>', unsafe_allow_html=True)
    if passed == 40:
        st.markdown('<div class="qa-pass"><strong>40/40 passed.</strong> Locked fields and workbook structure were preserved. The ZIP contains 40 separate customer files, a manifest, and a validation report.</div>', unsafe_allow_html=True)
        download_columns = st.columns([2, 1, 1, 1, 1])
        download_columns[0].download_button(
            "Download all 40 files",
            data=st.session_state["export_zip"],
            file_name="marketplace_listing_40_files.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        for index, platform in enumerate(PLATFORMS, start=1):
            download_columns[index].download_button(
                f"{platform} ZIP",
                data=st.session_state["platform_zips"][platform],
                file_name=f"{platform.lower()}_customer_files.zip",
                mime="application/zip",
                use_container_width=True,
            )
    else:
        st.markdown(f'<div class="qa-fail"><strong>{passed}/40 passed.</strong> Failed files are not included in an all-files download. Correct the source workbook or review the specific QA errors below, then regenerate.</div>', unsafe_allow_html=True)

    records = st.session_state.get("manifest_records", [])
    if records:
        frame = pd.DataFrame(records)
        visible_columns = ["platform", "customer", "output_file", "data_sheet", "groups", "rows", "changed_cells", "reordered_groups", "sku_validation", "image_validation", "status"]
        st.dataframe(frame[visible_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Download QA manifest (CSV)",
            data=build_manifest(records),
            file_name="listing_validation_manifest.csv",
            mime="text/csv",
        )

    with st.expander("View warnings and exact validation messages", expanded=False):
        for result in results:
            if result.warnings or result.errors:
                heading = f"{result.platform} · Customer {result.customer_number:02d} · {result.filename}"
                st.markdown(f"**{heading}**")
                for warning in result.warnings:
                    st.markdown(f"- Warning: {warning}")
                for error in result.errors:
                    st.markdown(f"- Error: {error}")

    st.caption(
        "Content uniqueness is generated from confirmed product facts and neutral sentence/ordering variation. "
        "If a workbook exposes only a product identity, the QA warning asks for a manual SEO review rather than inventing material, fit, color, pack, or features."
    )

st.divider()
st.caption("Listing Forge works on uploaded files in the current session. It does not overwrite your source workbooks and does not use a previous product/category as a template.")
