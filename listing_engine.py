"""Safe, workbook-preserving generation utilities for the listing studio.

The engine deliberately works from the workbook that is supplied for each
platform.  It does not have a product catalogue of its own and it never
copies facts from another workbook.  The only cells it writes are columns
identified as title, description, keyword, or bullet content columns.

The functions in this module are kept independent from Streamlit so they can
be tested and reused by a batch job or a future API.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import Counter, OrderedDict
from copy import copy
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter


PLATFORMS = ("Amazon", "Meesho", "Flipkart", "Snapdeal")
NATIVE_WORKBOOK_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}
LEGACY_BIFF_EXTENSIONS = {".xls", ".xlt"}
BINARY_WORKBOOK_EXTENSIONS = {".xlsb"}
SUPPORTED_WORKBOOK_EXTENSIONS = (
    "xlsx",
    "xlsm",
    "xls",
    "xlsb",
    "xltx",
    "xltm",
    "xlt",
)
CONTENT_ROLES = {"title", "description", "keyword", "bullet"}

# Header aliases are intentionally conservative.  A column that is not a
# clear content field is treated as locked, which is safer than guessing.
LOCKED_ROLE_NAMES = {
    "product_name",
    "product_type",
    "group",
    "sku",
    "parent_sku",
    "price",
    "image",
    "identifier",
    "brand",
    "size",
    "color",
    "pack",
    "style_code",
    "parentage",
    "variation",
    "material",
    "fit",
    "pattern",
    "design",
    "construction",
    "coverage",
    "closure",
    "sleeve",
    "neck",
    "usage",
    "occasion",
    "other_details",
}

FACT_ROLES = {
    "product_name",
    "product_type",
    "color",
    "pack",
    "material",
    "fit",
    "pattern",
    "design",
    "construction",
    "coverage",
    "closure",
    "sleeve",
    "neck",
    "usage",
    "occasion",
    "other_details",
    "size",
    "variation",
}

CONTENT_HEADER_WORDS = (
    "title",
    "description",
    "keyword",
    "bullet",
    "feature",
    "search term",
    "generic",
)

_IDENTIFIER_WORDS = (
    "sku",
    "product id",
    "item id",
    "group id",
    "style id",
    "fsn",
    "asin",
    "ean",
    "upc",
    "barcode",
    "catalogue id",
    "catalog id",
)

_FACT_HEADER_WORDS = (
    ("other details", "other_details"),
    ("product details", "other_details"),
    ("material", "material"),
    ("fabric", "material"),
    ("textile", "material"),
    ("fit", "fit"),
    ("pattern", "pattern"),
    ("print", "pattern"),
    ("design", "design"),
    ("construction", "construction"),
    ("coverage", "coverage"),
    ("closure", "closure"),
    ("sleeve", "sleeve"),
    ("neck", "neck"),
    ("occasion", "occasion"),
    ("usage", "usage"),
    ("use case", "usage"),
    ("use", "usage"),
)


@dataclass(frozen=True)
class ColumnSpec:
    """A detected header and its conservative semantic role."""

    index: int
    header: str
    role: str | None
    bullet_number: int | None = None

    @property
    def is_content(self) -> bool:
        return self.role in CONTENT_ROLES or self.role == "bullet"


@dataclass
class GenerationResult:
    """One validated customer workbook or an actionable failure."""

    platform: str
    customer_number: int
    filename: str
    data: bytes | None
    success: bool
    warnings: list[str]
    errors: list[str]
    report: dict[str, Any]


# ---------------------------------------------------------------------------
# Basic value/header helpers
# ---------------------------------------------------------------------------


def normalize_header(value: Any) -> str:
    """Return a stable, whitespace-normalized header for matching."""

    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def display_value(value: Any) -> str:
    """Make a cell value safe for content generation without changing it."""

    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (datetime, date, time)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    text = str(value).replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("=")


def _unique_text(values: Iterable[Any], limit: int = 8) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = display_value(value)
        if not text or is_formula(text):
            continue
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _safe_key(value: Any) -> str:
    """Hashable representation for validation counters."""

    if value is None:
        return "<blank>"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return repr(value)


def _trim(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - 1)].rsplit(" ", 1)[0].rstrip()
    return (cut or text[: limit - 1]).rstrip(" ,;|-") + "…"


def _clean_fragment(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;|-")


# ---------------------------------------------------------------------------
# Header detection and workbook inspection
# ---------------------------------------------------------------------------


def classify_header(header: Any) -> tuple[str | None, int | None]:
    """Classify only fields that can be proven from a header.

    The ordering matters: a "Search Keywords" column must be content, while a
    "Keyword ID" column must remain locked as an identifier.
    """

    raw = display_value(header)
    n = normalize_header(header)
    if not n:
        return None, None

    # Explicit editable content fields.
    if re.search(r"\b(?:bullet|bullet point|key feature|features?|highlight)\b", n):
        match = re.search(r"(?:bullet|feature|highlight)(?: point)?s?\s*([1-9][0-9]*)?", n)
        number = int(match.group(1)) if match and match.group(1) else None
        return "bullet", number
    if "description" in n or n in {"product details text", "long copy", "long description"}:
        return "description", None
    if (
        n in {"title", "product title", "listing title", "item title", "listing name"}
        or n.endswith(" product title")
    ):
        return "title", None
    if (
        "generic keyword" in n
        or "backend keyword" in n
        or "search keyword" in n
        or "search term" in n
        or n in {"keyword", "keywords", "valid keyword", "valid keywords"}
    ):
        return "keyword", None

    # A product name is a source fact, not a title-writing target.  Do this
    # before broad name matching so it cannot be overwritten accidentally.
    if n in {
        "product name",
        "product type",
        "product category",
        "category",
        "category name",
        "item type",
        "catalog product name",
    }:
        return ("product_name" if "name" in n else "product_type"), None

    if "parentage" in n or n in {"parent child", "parent child relationship"}:
        return "parentage", None
    if "parent sku" in n or n in {"parent variant sku", "parent sku id"}:
        return "parent_sku", None
    # Group ID is both a locked identifier and the safest group-order key.
    # Detect it before the broad identifier rule so it can be used for
    # ordering while remaining immutable in generated copies.
    if "group id" in n or n in {"offer group", "group", "grouping"}:
        return "group", None
    if "sku" in n or "seller sku" in n:
        return "sku", None
    if any(word in n for word in _IDENTIFIER_WORDS):
        # Style is a content-adjacent locked identifier, kept separate for
        # reporting.  It is never replaced with SKU.
        if "style" in n:
            return "style_code", None
        return "identifier", None
    if "style" in n and any(token in n for token in ("id", "code", "name", "number")):
        return "style_code", None
    if "image" in n or "photo" in n or "picture" in n:
        return "image", None
    if n == "brand" or n.endswith(" brand") or n.startswith("brand "):
        return "brand", None
    if "price" in n or n in {"mrp", "amount", "selling rate", "offer rate", "return price"}:
        return "price", None
    if re.search(r"\b(?:group|offer group|grouping)\b", n):
        return "group", None
    if "color" in n or "colour" in n:
        return "color", None
    if "pack" in n or "quantity" in n or n in {"count", "pieces", "number of pieces"}:
        return "pack", None
    if n == "size" or n.endswith(" size") or n.startswith("size "):
        return "size", None
    if "variation" in n or "variant" in n:
        return "variation", None
    for phrase, role in _FACT_HEADER_WORDS:
        if phrase in n:
            return role, None

    # A column called just "style" can be a confirmed feature, but a code/id
    # was handled above and remains locked.
    if n == "style" or n == "style name":
        return "design", None

    # Preserve the original header in the locked set by returning None.
    return None, None


def _row_values(ws: Any, row_number: int) -> list[Any]:
    return [ws.cell(row=row_number, column=col).value for col in range(1, ws.max_column + 1)]


def _nonempty(values: Iterable[Any]) -> int:
    return sum(1 for value in values if display_value(value))


def _header_score(values: Sequence[Any]) -> tuple[float, int, int]:
    nonempty = _nonempty(values)
    roles = sum(1 for value in values if classify_header(value)[0] is not None)
    known_words = sum(
        1
        for value in values
        if any(word in normalize_header(value) for word in CONTENT_HEADER_WORDS)
    )
    # A recognizable header row wins over a title/cover row with one or two
    # cells.  The fallback still supports templates with unusual headers.
    score = roles * 7 + known_words * 2 + min(nonempty, 20) * 0.15
    return score, roles, nonempty


def find_header_row(ws: Any, scan_limit: int = 40) -> int | None:
    """Find the most likely header row using semantic header evidence."""

    max_scan = min(max(ws.max_row, 1), scan_limit)
    candidates: list[tuple[float, int, int, int]] = []
    for row_number in range(1, max_scan + 1):
        values = _row_values(ws, row_number)
        score, roles, nonempty = _header_score(values)
        if nonempty >= 2:
            candidates.append((score, roles, nonempty, row_number))
    if not candidates:
        return None
    # Prefer a row with at least one known semantic field.  If none exists,
    # choose the first substantial row so the workbook can still be inspected.
    known = [item for item in candidates if item[1] > 0]
    pool = known or candidates
    pool.sort(key=lambda item: (-item[0], item[3]))
    return pool[0][3]


def _sheet_columns(ws: Any, header_row: int) -> list[ColumnSpec]:
    columns: list[ColumnSpec] = []
    for col in range(1, ws.max_column + 1):
        header = display_value(ws.cell(row=header_row, column=col).value)
        role, number = classify_header(header)
        columns.append(ColumnSpec(col, header, role, number))
    return columns


def data_rows(ws: Any, header_row: int) -> list[int]:
    rows: list[int] = []
    for row_number in range(header_row + 1, ws.max_row + 1):
        if any(ws.cell(row=row_number, column=col).value is not None for col in range(1, ws.max_column + 1)):
            rows.append(row_number)
    return rows


def _content_columns(columns: Sequence[ColumnSpec]) -> list[ColumnSpec]:
    return [column for column in columns if column.is_content]


def _columns_by_role(columns: Sequence[ColumnSpec]) -> dict[str, list[ColumnSpec]]:
    result: dict[str, list[ColumnSpec]] = {}
    for column in columns:
        if column.role:
            result.setdefault(column.role, []).append(column)
    return result


def _sheet_profile(ws: Any) -> dict[str, Any]:
    header_row = find_header_row(ws)
    if header_row is None:
        return {
            "name": ws.title,
            "state": ws.sheet_state,
            "header_row": None,
            "row_count": 0,
            "column_count": ws.max_column,
            "columns": [],
            "content_fields": [],
            "locked_fields": [],
            "recommended": False,
            "preview": [],
            "validations": 0,
            "merged_ranges": 0,
            "formula_count": 0,
            "product_identities": [],
            "group_values": [],
        }

    columns = _sheet_columns(ws, header_row)
    rows = data_rows(ws, header_row)
    by_role = _columns_by_role(columns)
    preview: list[list[str]] = []
    for row_number in rows[:8]:
        preview.append(
            [display_value(ws.cell(row=row_number, column=col).value) for col in range(1, ws.max_column + 1)]
        )

    identities: list[str] = []
    for role in ("product_name", "product_type"):
        for column in by_role.get(role, []):
            identities.extend(
                display_value(ws.cell(row=row, column=column.index).value)
                for row in rows
            )
    identities = _unique_text(identities, limit=5)

    groups: list[str] = []
    for column in by_role.get("group", []):
        groups.extend(display_value(ws.cell(row=row, column=column.index).value) for row in rows)
    groups = _unique_text(groups, limit=12)

    formulas = sum(
        1
        for row in ws.iter_rows()
        for cell in row
        if cell.data_type == "f" or is_formula(cell.value)
    )
    content_fields = [column.header for column in columns if column.is_content and column.header]
    locked_fields = [column.header for column in columns if not column.is_content and column.header]
    recommended = bool(rows) and bool(
        identities
        or by_role.get("sku")
        or by_role.get("group")
        or _content_columns(columns)
    )
    return {
        "name": ws.title,
        "state": ws.sheet_state,
        "header_row": header_row,
        "row_count": len(rows),
        "column_count": ws.max_column,
        "columns": [
            {
                "index": column.index,
                "header": column.header,
                "role": column.role,
                "bullet_number": column.bullet_number,
            }
            for column in columns
        ],
        "content_fields": content_fields,
        "locked_fields": locked_fields,
        "recommended": recommended,
        "preview": preview,
        "validations": len(ws.data_validations.dataValidation),
        "merged_ranges": len(ws.merged_cells.ranges),
        "formula_count": formulas,
        "product_identities": identities,
        "group_values": groups,
        "has_images": bool(getattr(ws, "_images", [])),
    }


def _xls_colour(book: Any, colour_index: Any) -> str | None:
    """Convert a legacy BIFF palette colour to an openpyxl ARGB value."""

    try:
        colour = book.colour_map.get(colour_index)
        if not colour:
            return None
        red, green, blue = colour
        return f"FF{int(red):02X}{int(green):02X}{int(blue):02X}"
    except Exception:
        return None


def _convert_xls_to_xlsx(data: bytes) -> bytes:
    """Convert legacy BIFF .xls bytes to a safe editable .xlsx workbook.

    openpyxl cannot read BIFF files.  xlrd is used only for the legacy input
    path, and the conversion retains sheet names, values, merged ranges,
    basic number formats, widths/heights, visibility, and common cell styles.
    The generated output is intentionally .xlsx because writing a fully
    structure-preserving .xls file is not supported by openpyxl.
    """

    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise ValueError("Legacy .xls support requires the xlrd dependency.") from exc

    try:
        try:
            legacy = xlrd.open_workbook(file_contents=data, formatting_info=True)
        except Exception:
            # Some BIFF files contain incomplete formatting records.  Values
            # are still recoverable with formatting_info disabled.
            legacy = xlrd.open_workbook(file_contents=data, formatting_info=False)
    except Exception as exc:
        raise ValueError(f"Could not read legacy .xls workbook: {exc}") from exc

    converted = Workbook()
    default_sheet = converted.active
    converted.remove(default_sheet)
    for sheet_index in range(legacy.nsheets):
        legacy_sheet = legacy.sheet_by_index(sheet_index)
        safe_sheet_name, _ = _sanitize_cell_text(legacy_sheet.name)
        worksheet = converted.create_sheet(str(safe_sheet_name)[:31] or f"Sheet{sheet_index + 1}")
        visibility = getattr(legacy_sheet, "visibility", 0)
        if visibility == 1:
            worksheet.sheet_state = "hidden"
        elif visibility == 2:
            worksheet.sheet_state = "veryHidden"

        for row_number in range(legacy_sheet.nrows):
            row_info = getattr(legacy_sheet, "rowinfo_map", {}).get(row_number)
            if row_info is not None:
                if getattr(row_info, "height", 0):
                    worksheet.row_dimensions[row_number + 1].height = row_info.height / 20
                if getattr(row_info, "hidden", False):
                    worksheet.row_dimensions[row_number + 1].hidden = True
            for col_number in range(legacy_sheet.ncols):
                source_cell = legacy_sheet.cell(row_number, col_number)
                target = worksheet.cell(row=row_number + 1, column=col_number + 1)
                value = source_cell.value
                if source_cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        value = xlrd.xldate_as_datetime(source_cell.value, legacy.datemode)
                    except Exception:
                        value = source_cell.value
                elif source_cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(source_cell.value)
                elif source_cell.ctype == xlrd.XL_CELL_NUMBER and isinstance(value, float) and value.is_integer():
                    value = int(value)
                elif source_cell.ctype == xlrd.XL_CELL_ERROR:
                    value = f"#ERROR {source_cell.value}"
                elif source_cell.ctype in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
                    value = None
                value, _ = _sanitize_cell_text(value)
                target.value = value

                # Preserve common BIFF formatting where the source exposes it.
                try:
                    xf_index = legacy_sheet.cell_xf_index(row_number, col_number)
                    xf = legacy.xf_list[xf_index]
                    if getattr(xf, "format_key", None) in getattr(legacy, "format_map", {}):
                        target.number_format = legacy.format_map[xf.format_key].format_str
                    font_info = legacy.font_list[xf.font_index]
                    underline = "single" if getattr(font_info, "underlined", False) else None
                    target.font = Font(
                        name=getattr(font_info, "name", "Calibri") or "Calibri",
                        sz=(getattr(font_info, "height", 220) or 220) / 20,
                        bold=bool(getattr(font_info, "bold", False)),
                        italic=bool(getattr(font_info, "italic", False)),
                        underline=underline,
                        color=_xls_colour(legacy, getattr(font_info, "colour_index", None)),
                    )
                    alignment = getattr(xf, "alignment", None)
                    if alignment is not None:
                        target.alignment = Alignment(
                            horizontal=getattr(alignment, "hor_align", None) or None,
                            vertical=getattr(alignment, "vert_align", None) or None,
                            wrap_text=bool(getattr(alignment, "wrap_text", False)),
                        )
                    border_info = getattr(xf, "border", None)
                    if border_info is not None:
                        def side(name: str) -> Side:
                            item = getattr(border_info, name, None)
                            return Side(
                                style=getattr(item, "line_style", None) if item else None,
                                color=_xls_colour(legacy, getattr(item, "colour_index", None)) if item else None,
                            )
                        target.border = Border(
                            left=side("left_line"),
                            right=side("right_line"),
                            top=side("top_line"),
                            bottom=side("bottom_line"),
                        )
                except Exception:
                    # A malformed/unsupported BIFF style should not prevent
                    # the workbook from being accepted; its value remains safe.
                    pass

        for col_number, col_info in getattr(legacy_sheet, "colinfo_map", {}).items():
            if col_number >= 256:
                continue
            if getattr(col_info, "width", 0):
                worksheet.column_dimensions[get_column_letter(col_number + 1)].width = col_info.width / 256
            if getattr(col_info, "hidden", False):
                worksheet.column_dimensions[get_column_letter(col_number + 1)].hidden = True
        for merged in getattr(legacy_sheet, "merged_cells", []):
            try:
                row_start, row_end, col_start, col_end = merged
                worksheet.merge_cells(
                    start_row=row_start + 1,
                    end_row=row_end,
                    start_column=col_start + 1,
                    end_column=col_end,
                )
            except Exception:
                pass

    output = io.BytesIO()
    converted.save(output)
    return output.getvalue()


_ILLEGAL_XML_BYTES_RE = re.compile(rb"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_ILLEGAL_XML_TEXT_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _sanitize_cell_text(value: Any) -> tuple[Any, int]:
    """Normalize invalid XML control characters before openpyxl receives text."""

    if not isinstance(value, str):
        return value, 0
    cleaned, count = _ILLEGAL_XML_TEXT_RE.subn(" ", value)
    return cleaned, count


def _sanitize_ooxml_workbook(data: bytes, filename: str) -> tuple[bytes, dict[str, Any]]:
    """Remove invalid XML 1.0 control bytes from OOXML text parts.

    A few marketplace templates contain a literal vertical-tab/control byte in
    a cell note or long description.  Excel may still open those files, but
    openpyxl correctly rejects them with IllegalCharacterError.  Replacing only
    invalid XML control bytes with a space lets the workbook be inspected and
    edited while preserving all valid text, workbook parts, and VBA binaries.
    The caller surfaces the replacement count as a compatibility warning.
    """

    extension = Path(filename).suffix.lower()
    report = {"changed": False, "removed_count": 0, "members": []}
    if extension not in NATIVE_WORKBOOK_EXTENSIONS or not zipfile.is_zipfile(io.BytesIO(data)):
        return data, report

    output = io.BytesIO()
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as source_archive, zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED
        ) as target_archive:
            for info in source_archive.infolist():
                raw = source_archive.read(info)
                member_extension = Path(info.filename).suffix.lower()
                cleaned = raw
                removed = 0
                if member_extension in {".xml", ".rels"}:
                    cleaned, removed = _ILLEGAL_XML_BYTES_RE.subn(b" ", raw)
                if removed:
                    report["changed"] = True
                    report["removed_count"] += removed
                    report["members"].append(info.filename)
                target_archive.writestr(info, cleaned)
    except (zipfile.BadZipFile, OSError):
        return data, report
    return (output.getvalue() if report["changed"] else data), report


def _convert_xlsb_to_xlsx(data: bytes, filename: str) -> bytes:
    """Convert a binary .xlsb workbook to an editable .xlsx compatibility copy."""

    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise ValueError(".xlsb support requires pandas.") from exc

    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, engine="pyxlsb")
    except Exception as exc:
        raise ValueError(
            f"Could not read binary .xlsb workbook. Install/enable pyxlsb support: {exc}"
        ) from exc

    converted = Workbook()
    converted.remove(converted.active)
    used_names: set[str] = set()
    for sheet_name, frame in sheets.items():
        safe_sheet_name, _ = _sanitize_cell_text(str(sheet_name))
        base_name = re.sub(r"[\\/*?:\[\]]", "_", str(safe_sheet_name))[:31] or "Sheet"
        name = base_name
        suffix = 1
        while name in used_names:
            suffix += 1
            name = f"{base_name[: max(1, 31 - len(str(suffix)) - 1)]}_{suffix}"
        used_names.add(name)
        worksheet = converted.create_sheet(name)
        for row_number, row in enumerate(frame.itertuples(index=False, name=None), start=1):
            for col_number, value in enumerate(row, start=1):
                try:
                    missing = bool(pd.isna(value))
                except (TypeError, ValueError):
                    missing = False
                if missing:
                    value = None
                elif hasattr(value, "item"):
                    try:
                        value = value.item()
                    except Exception:
                        pass
                value, _ = _sanitize_cell_text(value)
                worksheet.cell(row=row_number, column=col_number).value = value

    output = io.BytesIO()
    converted.save(output)
    return output.getvalue()


def _output_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return extension if extension in NATIVE_WORKBOOK_EXTENSIONS else ".xlsx"


def is_compatibility_workbook(filename: str) -> bool:
    return Path(filename).suffix.lower() not in NATIVE_WORKBOOK_EXTENSIONS


def open_source_workbook(data: bytes, filename: str):
    data, _ = _sanitize_ooxml_workbook(data, filename)
    extension = Path(filename).suffix.lower()
    if extension in LEGACY_BIFF_EXTENSIONS:
        data = _convert_xls_to_xlsx(data)
        extension = ".xlsx"
    elif extension in BINARY_WORKBOOK_EXTENSIONS:
        data = _convert_xlsb_to_xlsx(data, filename)
        extension = ".xlsx"
    if extension not in NATIVE_WORKBOOK_EXTENSIONS:
        raise ValueError(
            "Supported workbook formats are .xlsx, .xlsm, .xltx, .xltm, .xls, .xlt, and .xlsb."
        )
    return load_workbook(
        io.BytesIO(data),
        data_only=False,
        keep_vba=extension in {".xlsm", ".xltm"},
    )


def inspect_workbook(data: bytes, filename: str) -> dict[str, Any]:
    """Return a serializable inspection summary without modifying the file."""

    try:
        safe_data, sanitation = _sanitize_ooxml_workbook(data, filename)
        wb = open_source_workbook(safe_data, filename)
        sheets = [_sheet_profile(ws) for ws in wb.worksheets]
        recommended_sheet = next((sheet["name"] for sheet in sheets if sheet["recommended"]), None)
        return {
            "filename": filename,
            "extension": Path(filename).suffix.lower(),
            "sheet_names": [ws.title for ws in wb.worksheets],
            "sheets": sheets,
            "recommended_sheet": recommended_sheet,
            "macro_enabled": Path(filename).suffix.lower() in {".xlsm", ".xltm"},
            "compatibility_mode": is_compatibility_workbook(filename),
            "legacy_xls_converted": Path(filename).suffix.lower() in LEGACY_BIFF_EXTENSIONS,
            "xml_sanitized": sanitation.get("changed", False),
            "xml_sanitized_count": sanitation.get("removed_count", 0),
            "xml_sanitized_members": sanitation.get("members", []),
            "output_extension": _output_extension(filename),
            "error": None,
        }
    except Exception as exc:  # surfaced in the UI with the filename context
        return {
            "filename": filename,
            "extension": Path(filename).suffix.lower(),
            "sheet_names": [],
            "sheets": [],
            "recommended_sheet": None,
            "macro_enabled": False,
            "compatibility_mode": is_compatibility_workbook(filename),
            "legacy_xls_converted": Path(filename).suffix.lower() in LEGACY_BIFF_EXTENSIONS,
            "xml_sanitized": False,
            "xml_sanitized_count": 0,
            "xml_sanitized_members": [],
            "output_extension": _output_extension(filename),
            "error": f"{type(exc).__name__}: {exc}",
        }


def sheet_profile(profile: Mapping[str, Any], sheet_name: str | None) -> Mapping[str, Any] | None:
    name = sheet_name or profile.get("recommended_sheet")
    for sheet in profile.get("sheets", []):
        if sheet.get("name") == name:
            return sheet
    return profile.get("sheets", [None])[0] if profile.get("sheets") else None



# ---------------------------------------------------------------------------
# Operator-provided SKU and image-link inputs
# ---------------------------------------------------------------------------

_SKU_HEADER_NAMES = {
    "sku",
    "sku id",
    "seller sku",
    "seller sku id",
    "child sku",
    "parent sku",
    "parent sku id",
    "sku code",
    "product sku",
}
_TEXT_MEMBER_EXTENSIONS = {
    ".txt",
    ".csv",
    ".tsv",
    ".json",
    ".url",
    ".list",
    ".links",
    ".md",
    ".xml",
    ".html",
    ".htm",
}
_IMAGE_MEMBER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def _sku_key(value: Any) -> str:
    return re.sub(r"\s+", " ", display_value(value)).strip().casefold()


def _clean_sku_candidate(value: Any) -> str:
    text = display_value(value).strip().strip("\"'` ")
    if not text or text.startswith("http://") or text.startswith("https://"):
        return ""
    # Accept convenient pasted forms such as "SKU: ABC-01" without changing
    # the actual SKU stored in the workbook.
    if ":" in text and normalize_header(text.split(":", 1)[0]) in _SKU_HEADER_NAMES:
        text = text.split(":", 1)[1].strip()
    if normalize_header(text) in _SKU_HEADER_NAMES or normalize_header(text) in {
        "sku number",
        "sku numbers",
        "product sku list",
    }:
        return ""
    return text.strip(" ,;|\t")


def parse_sku_text(text: str) -> tuple[list[str], list[str]]:
    """Parse pasted SKU values without applying them to any workbook cell."""

    values: list[str] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            cells = next(csv.reader([line], delimiter="\t")) if "\t" in line else next(csv.reader([line]))
        except (csv.Error, StopIteration):
            cells = [line]
        # A semicolon-delimited paste is common in spreadsheet exports.
        expanded: list[str] = []
        for cell in cells:
            expanded.extend(cell.split(";") if ";" in cell else [cell])
        for cell in expanded:
            candidate = _clean_sku_candidate(cell)
            if not candidate:
                continue
            key = _sku_key(candidate)
            if key in seen:
                duplicates.append(candidate)
            else:
                seen.add(key)
                values.append(candidate)
    return values, duplicates


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def _extract_skus_from_csv_text(text: str) -> tuple[list[str], list[str]]:
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error:
        return parse_sku_text(text)
    if not rows:
        return [], []
    header_indices = [
        index
        for index, value in enumerate(rows[0])
        if normalize_header(value) in _SKU_HEADER_NAMES or "sku" in normalize_header(value)
    ]
    source_rows = rows[1:] if header_indices else rows
    candidates: list[str] = []
    for row in source_rows:
        cells = [row[index] for index in header_indices if index < len(row)] if header_indices else row
        candidates.extend(cells)
    return parse_sku_text("\n".join(candidates))


def _extract_skus_from_workbook(data: bytes, filename: str) -> tuple[list[str], list[str]]:
    workbook = open_source_workbook(data, filename)
    candidates: list[str] = []
    for worksheet in workbook.worksheets:
        header_row = find_header_row(worksheet)
        if header_row is not None:
            columns = _sheet_columns(worksheet, header_row)
            sku_columns = [
                column for column in columns if column.role in {"sku", "parent_sku"}
            ]
            rows = data_rows(worksheet, header_row)
            if sku_columns:
                for row in rows:
                    candidates.extend(
                        worksheet.cell(row=row, column=column.index).value
                        for column in sku_columns
                    )
                continue
        # A raw one-column workbook without headers is still a valid SKU list.
        for row in worksheet.iter_rows():
            candidates.extend(cell.value for cell in row)
    return parse_sku_text("\n".join(display_value(value) for value in candidates))


def inspect_sku_source(
    data: bytes | None = None,
    filename: str = "",
    pasted_text: str = "",
) -> dict[str, Any]:
    """Inspect an operator SKU file and/or pasted SKU list.

    This source is deliberately validation-only.  The generation engine never
    writes these values back into a master workbook.
    """

    values: list[str] = []
    duplicates: list[str] = []
    errors: list[str] = []
    if data:
        try:
            extension = Path(filename).suffix.lower()
            if extension in NATIVE_WORKBOOK_EXTENSIONS | LEGACY_BIFF_EXTENSIONS | BINARY_WORKBOOK_EXTENSIONS:
                file_values, file_duplicates = _extract_skus_from_workbook(data, filename)
            elif extension in {".csv", ".tsv"}:
                file_values, file_duplicates = _extract_skus_from_csv_text(_decode_text(data))
            else:
                file_values, file_duplicates = parse_sku_text(_decode_text(data))
            values.extend(file_values)
            duplicates.extend(file_duplicates)
        except Exception as exc:
            errors.append(f"Could not read SKU source: {type(exc).__name__}: {exc}")
    pasted_values, pasted_duplicates = parse_sku_text(pasted_text)
    values.extend(pasted_values)
    duplicates.extend(pasted_duplicates)

    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _sku_key(value)
        if key in seen:
            duplicates.append(value)
        elif key:
            seen.add(key)
            unique.append(value)
    return {
        "filename": filename or "Pasted SKU input",
        "values": unique,
        "duplicates": _unique_text(duplicates, limit=50),
        "count": len(unique),
        "errors": errors,
        "ok": bool(unique) and not errors,
    }


def _extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in re.findall(r"https?://[^\s<>\"']+", text or "", flags=re.IGNORECASE):
        value = match.rstrip(".,;:)]}>\"")
        if value and value not in urls:
            urls.append(value)
    return urls


def _extract_urls_from_workbook_bytes(data: bytes, filename: str) -> list[str]:
    workbook = open_source_workbook(data, filename)
    urls: list[str] = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                urls.extend(_extract_urls(display_value(cell.value)))
    return list(dict.fromkeys(urls))


def inspect_image_link_zip(data: bytes | None, filename: str = "") -> dict[str, Any]:
    """Read URLs from a supplied ZIP without changing workbook image cells."""

    if not data:
        return {
            "filename": filename,
            "links": [],
            "members": [],
            "image_file_count": 0,
            "error": "No image-link ZIP was supplied.",
            "ok": False,
        }
    links: list[str] = []
    members: list[dict[str, Any]] = []
    image_file_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                member_name = info.filename
                extension = Path(member_name).suffix.lower()
                raw = archive.read(info)
                member_links: list[str] = []
                kind = "binary"
                if extension in NATIVE_WORKBOOK_EXTENSIONS | LEGACY_BIFF_EXTENSIONS | BINARY_WORKBOOK_EXTENSIONS:
                    kind = "workbook"
                    try:
                        member_links = _extract_urls_from_workbook_bytes(raw, member_name)
                    except Exception:
                        member_links = []
                elif extension in _IMAGE_MEMBER_EXTENSIONS:
                    image_file_count += 1
                    kind = "image file"
                elif extension in _TEXT_MEMBER_EXTENSIONS or b"http://" in raw or b"https://" in raw:
                    kind = "link text"
                    decoded = _decode_text(raw)
                    member_links = _extract_urls(decoded)
                links.extend(member_links)
                members.append(
                    {
                        "member": member_name,
                        "kind": kind,
                        "bytes": info.file_size,
                        "link_count": len(member_links),
                        "sample_links": member_links[:3],
                    }
                )
        links = list(dict.fromkeys(links))
        return {
            "filename": filename,
            "links": links,
            "members": members,
            "image_file_count": image_file_count,
            "link_count": len(links),
            "error": None,
            "ok": bool(links),
        }
    except (zipfile.BadZipFile, OSError) as exc:
        return {
            "filename": filename,
            "links": [],
            "members": [],
            "image_file_count": 0,
            "link_count": 0,
            "error": f"Could not read image-link ZIP: {type(exc).__name__}: {exc}",
            "ok": False,
        }


def _workbook_locked_inputs(
    data: bytes,
    filename: str,
    sheet_name: str,
) -> dict[str, Any]:
    workbook = open_source_workbook(data, filename)
    if sheet_name not in workbook.sheetnames:
        raise ValueError(f"Sheet '{sheet_name}' was not found.")
    worksheet = workbook[sheet_name]
    header_row = find_header_row(worksheet)
    if header_row is None:
        raise ValueError("No header row was detected.")
    columns = _sheet_columns(worksheet, header_row)
    rows = data_rows(worksheet, header_row)
    by_role = _columns_by_role(columns)
    sku_values: list[str] = []
    for role in ("sku", "parent_sku"):
        for column in by_role.get(role, []):
            sku_values.extend(
                _clean_sku_candidate(worksheet.cell(row=row, column=column.index).value)
                for row in rows
            )
    image_values: list[str] = []
    image_headers: list[str] = []
    for column in by_role.get("image", []):
        image_headers.append(column.header)
        for row in rows:
            image_values.extend(_extract_urls(display_value(worksheet.cell(row=row, column=column.index).value)))
    return {
        "sku_values": list(dict.fromkeys(value for value in sku_values if value)),
        "image_links": list(dict.fromkeys(image_values)),
        "image_headers": image_headers,
    }


def _set_keys(values: Iterable[str]) -> set[str]:
    return {_sku_key(value) for value in values if _sku_key(value)}


def validate_external_inputs(
    platform_sources: Mapping[str, Mapping[str, Any]],
    sku_values: Sequence[str],
    image_links: Sequence[str],
) -> dict[str, Any]:
    """Cross-check external SKU/link packages against locked master cells."""

    report: dict[str, Any] = {
        "sku_input_count": len(sku_values),
        "image_input_count": len(image_links),
        "platforms": [],
        "errors": [],
        "warnings": [],
        "ok": True,
    }
    supplied_skus = _set_keys(sku_values)
    supplied_images = set(image_links)
    for platform in PLATFORMS:
        source = platform_sources.get(platform, {})
        try:
            locked = _workbook_locked_inputs(
                source["data"],
                source["filename"],
                source["sheet_name"],
            )
            workbook_skus = _set_keys(locked["sku_values"])
            workbook_images = set(locked["image_links"])
            sku_missing = sorted(supplied_skus - workbook_skus)
            sku_workbook_only = sorted(workbook_skus - supplied_skus)
            image_missing = sorted(supplied_images - workbook_images)
            image_workbook_only = sorted(workbook_images - supplied_images)
            platform_report = {
                "platform": platform,
                "sheet_name": source["sheet_name"],
                "workbook_sku_count": len(workbook_skus),
                "workbook_image_count": len(workbook_images),
                "image_headers": locked["image_headers"],
                "matched_skus": len(supplied_skus & workbook_skus),
                "sku_missing_from_workbook": sku_missing,
                "sku_present_only_in_workbook": sku_workbook_only,
                "matched_images": len(supplied_images & workbook_images),
                "image_links_missing_from_workbook": image_missing,
                "image_links_present_only_in_workbook": image_workbook_only,
                "sku_status": "matched" if not sku_missing else "review",
                "image_status": "matched" if not image_missing else "review",
                "status": "matched" if not sku_missing and not image_missing else "review",
                "error": None,
            }
            if sku_missing:
                report["warnings"].append(
                    f"{platform}: {len(sku_missing)} supplied SKU(s) were not found in locked workbook SKU cells."
                )
            if image_missing:
                report["warnings"].append(
                    f"{platform}: {len(image_missing)} supplied image link(s) were not found in locked image-link cells."
                )
            if not locked["sku_values"]:
                report["warnings"].append(f"{platform}: no SKU column values were detected in the selected sheet.")
            if not locked["image_links"]:
                report["warnings"].append(
                    f"{platform}: no HTTP image URLs were detected in image columns; supplied links are not written automatically."
                )
        except Exception as exc:
            platform_report = {
                "platform": platform,
                "sheet_name": source.get("sheet_name", ""),
                "workbook_sku_count": 0,
                "workbook_image_count": 0,
                "matched_skus": 0,
                "matched_images": 0,
                "sku_missing_from_workbook": [],
                "sku_present_only_in_workbook": [],
                "image_links_missing_from_workbook": [],
                "image_links_present_only_in_workbook": [],
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            report["errors"].append(f"{platform}: {platform_report['error']}")
        report["platforms"].append(platform_report)
    report["ok"] = not report["errors"]
    return report


def format_external_validation_report(report: Mapping[str, Any]) -> str:
    lines = [
        "Marketplace Listing Studio — external input validation",
        "",
        "SKU input is validation-only; no SKU cells are overwritten.",
        "Image-link ZIP input is validation-only; no image URL or order is overwritten.",
        f"Supplied unique SKUs: {report.get('sku_input_count', 0)}",
        f"Supplied unique image links: {report.get('image_input_count', 0)}",
        "",
    ]
    for item in report.get("platforms", []):
        lines.append(
            f"{item.get('platform', '')} | {item.get('status', 'unknown')} | "
            f"matched SKU(s): {item.get('matched_skus', 0)} | matched image link(s): {item.get('matched_images', 0)}"
        )
        if item.get("error"):
            lines.append(f"  Error: {item['error']}")
        if item.get("sku_missing_from_workbook"):
            lines.append(f"  SKU not in workbook: {', '.join(item['sku_missing_from_workbook'][:20])}")
        if item.get("image_links_missing_from_workbook"):
            lines.append(
                f"  Image links not in workbook: {len(item['image_links_missing_from_workbook'])}"
            )
    for warning in report.get("warnings", []):
        lines.append(f"Warning: {warning}")
    for error in report.get("errors", []):
        lines.append(f"Error: {error}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Group ordering and fact extraction
# ---------------------------------------------------------------------------


def _first_value(ws: Any, rows: Sequence[int], columns: Sequence[ColumnSpec]) -> str:
    for column in columns:
        values = _unique_text(
            [ws.cell(row=row, column=column.index).value for row in rows],
            limit=1,
        )
        if values:
            return values[0]
    return ""


def _values_for_role(
    ws: Any,
    rows: Sequence[int],
    by_role: Mapping[str, Sequence[ColumnSpec]],
    role: str,
    limit: int = 8,
) -> list[str]:
    values: list[Any] = []
    for column in by_role.get(role, []):
        values.extend(ws.cell(row=row, column=column.index).value for row in rows)
    return _unique_text(values, limit=limit)


def _group_value(ws: Any, row: int, by_role: Mapping[str, Sequence[ColumnSpec]]) -> str:
    value = _first_value(ws, [row], by_role.get("group", []))
    if value:
        return value
    # Amazon templates sometimes use a parent SKU instead of an explicit
    # group column.  This is only a fallback and never changes the SKU.
    value = _first_value(ws, [row], by_role.get("parent_sku", []))
    if value:
        return value
    # If the parent SKU cell is blank on a parent row, its own SKU is the
    # stable group key.  Child rows point to that same value above.
    if _parent_rank(ws, row, by_role) == 0:
        return _first_value(ws, [row], by_role.get("sku", []))
    return ""


def _numeric_group_key(value: str) -> tuple[int, Any]:
    match = re.search(r"\d+", value)
    if match:
        return 0, int(match.group(0))
    return 1, value.casefold()


def _parent_rank(ws: Any, row: int, by_role: Mapping[str, Sequence[ColumnSpec]]) -> int:
    value = _first_value(ws, [row], by_role.get("parentage", []))
    lowered = value.casefold()
    if "parent" in lowered and "child" not in lowered:
        return 0
    if "child" in lowered:
        return 1
    return 2


def build_group_blocks(
    ws: Any,
    rows: Sequence[int],
    columns: Sequence[ColumnSpec],
) -> tuple[list[dict[str, Any]], bool, list[str]]:
    """Return sorted group blocks, whether a reorder is needed, and warnings."""

    by_role = _columns_by_role(columns)
    warnings: list[str] = []
    if not rows:
        return [], False, ["No data rows were found below the detected header row."]

    group_columns = by_role.get("group", [])
    parent_group_available = bool(by_role.get("parent_sku")) and any(
        _group_value(ws, row, by_role) for row in rows
    )
    if not group_columns and not parent_group_available:
        # Without an explicit group field (or Amazon's parent SKU fallback),
        # preserving input order is safer than guessing from SKU.  The report
        # calls this out for manual review.
        return [
            {
                "key": "__all_rows__",
                "label": "Existing row order (no group column detected)",
                "rows": list(rows),
                "original_index": 0,
            }
        ], False, [
            "No explicit Group/Offer Group column was detected; existing row order was preserved."
        ]

    grouped: OrderedDict[str, list[int]] = OrderedDict()
    labels: dict[str, str] = {}
    for row in rows:
        label = _group_value(ws, row, by_role)
        key = label.casefold() if label else f"__blank_{row}"
        grouped.setdefault(key, []).append(row)
        labels.setdefault(key, label or f"Blank group at row {row}")

    original_keys = list(grouped.keys())
    sorted_keys = sorted(
        grouped.keys(),
        key=lambda key: (_numeric_group_key(labels[key]), original_keys.index(key)),
    )
    blocks: list[dict[str, Any]] = []
    for index, key in enumerate(sorted_keys):
        block_rows = sorted(grouped[key], key=lambda row: (_parent_rank(ws, row, by_role), rows.index(row)))
        blocks.append(
            {
                "key": key,
                "label": labels[key],
                "rows": block_rows,
                "original_index": original_keys.index(key),
                "group_index": index,
            }
        )
    desired = [row for block in blocks for row in block["rows"]]
    reorder = list(rows) != desired
    return blocks, reorder, warnings


def _intersects_body_merge(ws: Any, header_row: int) -> bool:
    for merged in ws.merged_cells.ranges:
        if merged.max_row > header_row and merged.min_row <= ws.max_row:
            return True
    return False


def _copy_row_snapshot(ws: Any, row: int) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=row, column=col)
        snapshot.append(
            {
                "value": cell.value,
                "style": copy(cell._style),
                "number_format": cell.number_format,
                "font": copy(cell.font),
                "fill": copy(cell.fill),
                "border": copy(cell.border),
                "alignment": copy(cell.alignment),
                "protection": copy(cell.protection),
                "hyperlink": copy(cell.hyperlink),
                "comment": copy(cell.comment),
            }
        )
    return snapshot


def _restore_row_snapshot(ws: Any, row: int, snapshot: Sequence[Mapping[str, Any]]) -> None:
    for col, source in enumerate(snapshot, start=1):
        cell = ws.cell(row=row, column=col)
        cell.value = source["value"]
        cell._style = copy(source["style"])
        cell.number_format = source["number_format"]
        cell.font = copy(source["font"])
        cell.fill = copy(source["fill"])
        cell.border = copy(source["border"])
        cell.alignment = copy(source["alignment"])
        cell.protection = copy(source["protection"])
        cell.hyperlink = copy(source["hyperlink"])
        cell.comment = copy(source["comment"])


def reorder_group_rows(
    ws: Any,
    header_row: int,
    rows: Sequence[int],
    desired_rows: Sequence[int],
) -> tuple[bool, list[str]]:
    """Reorder complete data rows while retaining their styles and formulas."""

    if list(rows) == list(desired_rows):
        return False, []
    if getattr(ws, "_images", []):
        # Embedded image anchors are not ordinary cell values.  Moving rows
        # without moving those anchors could silently change group/image
        # mapping, so the safe behavior is to preserve the source order and
        # surface a review warning.
        return False, [
            "Group order was not changed because embedded images are anchored in the data body; image mapping was preserved for manual review."
        ]
    if _intersects_body_merge(ws, header_row):
        return False, [
            "Group order was not changed because merged cells intersect the data body; manual review is required."
        ]

    snapshots = {row: _copy_row_snapshot(ws, row) for row in rows}
    dimensions = {
        row: {
            "height": ws.row_dimensions[row].height,
            "hidden": ws.row_dimensions[row].hidden,
            "outlineLevel": ws.row_dimensions[row].outlineLevel,
            "collapsed": ws.row_dimensions[row].collapsed,
        }
        for row in rows
    }
    for destination, source in zip(rows, desired_rows):
        _restore_row_snapshot(ws, destination, snapshots[source])
        source_dimension = dimensions[source]
        ws.row_dimensions[destination].height = source_dimension["height"]
        ws.row_dimensions[destination].hidden = source_dimension["hidden"]
        ws.row_dimensions[destination].outlineLevel = source_dimension["outlineLevel"]
        ws.row_dimensions[destination].collapsed = source_dimension["collapsed"]
    return True, []


def _normalise_color(values: Sequence[str]) -> str:
    lowered = " ".join(values).casefold()
    if len(values) > 1 or "multi color" in lowered or "multicolor" in lowered or "assorted" in lowered:
        return "Multicolor"
    return values[0] if values else ""


def _normalise_pack(values: Sequence[str]) -> str:
    if not values:
        return ""
    value = values[0]
    match = re.search(r"(?:pack\s*(?:of)?|set\s*of|qty|quantity|pieces?|pcs?)\s*[:\-]?\s*(\d+)", value, re.I)
    if match:
        return f"Pack of {match.group(1)}"
    if re.fullmatch(r"\d+(?:\.0)?", value):
        return f"Pack of {value.split('.')[0]}"
    return value


def extract_group_facts(ws: Any, rows: Sequence[int], columns: Sequence[ColumnSpec]) -> dict[str, Any]:
    by_role = _columns_by_role(columns)
    product_values = _values_for_role(ws, rows, by_role, "product_name", limit=3)
    if not product_values:
        product_values = _values_for_role(ws, rows, by_role, "product_type", limit=3)
    product = " / ".join(product_values[:2])
    if not product:
        # A title already present in the current master can be used only as a
        # last-resort source identity.  The UI flags this as a review item.
        product_values = _values_for_role(ws, rows, by_role, "title", limit=1)
        product = product_values[0] if product_values else ""

    color_values = _values_for_role(ws, rows, by_role, "color", limit=8)
    pack_values = _values_for_role(ws, rows, by_role, "pack", limit=4)
    facts: dict[str, Any] = {
        "product": product,
        "product_values": product_values,
        "color": _normalise_color(color_values),
        "color_values": color_values,
        "pack": _normalise_pack(pack_values),
        "pack_values": pack_values,
        "size_values": _values_for_role(ws, rows, by_role, "size", limit=12),
        "confirmed": {},
    }
    for role in FACT_ROLES:
        if role in {"product_name", "product_type", "color", "pack", "size"}:
            continue
        values = _values_for_role(ws, rows, by_role, role, limit=4)
        if values:
            facts[role] = values[0] if len(values) == 1 else ", ".join(values[:3])
            facts[f"{role}_values"] = values
    return facts


def _fact_phrases(facts: Mapping[str, Any]) -> list[tuple[str, str]]:
    phrases: list[tuple[str, str]] = []
    if facts.get("color"):
        phrases.append(("color", str(facts["color"])))
    if facts.get("pack"):
        phrases.append(("pack", str(facts["pack"])))
    for role, label in (
        ("material", "material"),
        ("fit", "fit"),
        ("pattern", "pattern"),
        ("design", "design"),
        ("construction", "construction"),
        ("coverage", "coverage"),
        ("closure", "closure"),
        ("sleeve", "sleeve"),
        ("neck", "neck"),
        ("usage", "use"),
        ("occasion", "occasion"),
        ("other_details", "detail"),
    ):
        if facts.get(role):
            phrases.append((label, str(facts[role])))
    return phrases


def _facts_sentence(facts: Mapping[str, Any], order: int = 0) -> str:
    phrases = _fact_phrases(facts)
    if not phrases:
        return "Product attributes are limited to the identity recorded in the source listing."
    # Rotate the first few confirmed attributes for genuinely different but
    # fact-identical descriptions.
    rotated = phrases[order % len(phrases) :] + phrases[: order % len(phrases)]
    parts: list[str] = []
    for label, value in rotated:
        if label == "color":
            parts.append(f"Color: {value}")
        elif label == "pack":
            parts.append(f"Pack: {value}")
        else:
            parts.append(f"{label.title()}: {value}")
    return "; ".join(parts) + "."


def _title_variants(facts: Mapping[str, Any], variant: int) -> tuple[str, bool]:
    product = _clean_fragment(str(facts.get("product", "")))
    color = _clean_fragment(str(facts.get("color", "")))
    pack = _clean_fragment(str(facts.get("pack", "")))
    material = _clean_fragment(str(facts.get("material", "")))
    fit = _clean_fragment(str(facts.get("fit", "")))
    design = _clean_fragment(str(facts.get("design", "")))
    pieces = [piece for piece in (color, material, fit, design, pack) if piece]
    if not product:
        return "", True

    templates: list[str] = []
    if color and pack:
        templates.extend(
            [
                f"{product} | {color} | {pack}",
                f"{color} {product}, {pack}",
                f"{product} in {color}, {pack}",
                f"{pack} {product} - {color}",
            ]
        )
    if material and color:
        templates.extend(
            [
                f"{material} {product} in {color}",
                f"{product} | {material} | {color}",
            ]
        )
    if fit and color:
        templates.append(f"{product}, {fit} fit, {color}")
    if design and color:
        templates.append(f"{product}, {design} design, {color}")
    if pack:
        templates.extend([f"{product} - {pack}", f"{pack} {product}"])
    if color:
        templates.extend([f"{product} - {color}", f"{color} {product}"])
    templates.extend(
        [
            product,
            f"{product} Product Listing",
            f"{product} Catalog Listing",
            f"{product} Product Details",
            f"{product} Marketplace Listing",
            f"{product} Item Listing",
        ]
    )
    title = templates[variant % len(templates)]
    # If the source contains only the product identity, neutral listing
    # suffixes are used to satisfy the ten-version requirement without adding
    # a product claim.  The caller reports this for manual SEO review.
    used_neutral = not pieces
    return _trim(title, 200), used_neutral


def _description_variants(facts: Mapping[str, Any], variant: int, confirmed_context: str = "") -> str:
    product = _clean_fragment(str(facts.get("product", ""))) or "This product"
    color = _clean_fragment(str(facts.get("color", "")))
    pack = _clean_fragment(str(facts.get("pack", "")))
    material = _clean_fragment(str(facts.get("material", "")))
    fit = _clean_fragment(str(facts.get("fit", "")))
    design = _clean_fragment(str(facts.get("design", "")))
    use = _clean_fragment(str(facts.get("usage", "")))
    detail = _facts_sentence(facts, variant + 1)
    color_pack = ", ".join(piece for piece in (color, pack) if piece)
    if color_pack:
        color_pack = f"{color_pack}."
    else:
        color_pack = ""
    sentences = [
        f"{product} is presented with the confirmed details from this listing. {color_pack} {detail}",
        f"Review the {product} listing for the recorded product identity and variation information. {detail}",
        f"This {product} entry keeps the supplied catalogue details together for a clear product view. {detail}",
        f"The listed {product} is described using the attributes supplied for this group. {detail}",
        f"Find the confirmed version of {product} in the details shown for this listing. {detail}",
        f"Product information for {product} is organized around the source variation data. {detail}",
        f"The product page for {product} uses the recorded attributes without adding unconfirmed specifications. {detail}",
        f"Use the displayed variation fields to review this {product} listing. {detail}",
        f"This listing identifies {product} and retains the supplied group information. {detail}",
        f"The supplied details describe this {product} option in a concise format. {detail}",
    ]
    # Add confirmed fact types only when they are actually present.  These
    # clauses are descriptive, not invented features.
    if material:
        sentences[variant % len(sentences)] += f" Material recorded: {material}."
    elif fit:
        sentences[variant % len(sentences)] += f" Fit recorded: {fit}."
    elif design:
        sentences[variant % len(sentences)] += f" Design recorded: {design}."
    elif use:
        sentences[variant % len(sentences)] += f" Use recorded: {use}."
    if confirmed_context:
        sentences[variant % len(sentences)] += f" {confirmed_context}"
    return _trim(sentences[variant % len(sentences)], 1800)


def _bullet_variants(facts: Mapping[str, Any], variant: int) -> list[str]:
    product = _clean_fragment(str(facts.get("product", ""))) or "Product"
    color = _clean_fragment(str(facts.get("color", "")))
    pack = _clean_fragment(str(facts.get("pack", "")))
    material = _clean_fragment(str(facts.get("material", "")))
    fit = _clean_fragment(str(facts.get("fit", "")))
    design = _clean_fragment(str(facts.get("design", "")))
    pattern = _clean_fragment(str(facts.get("pattern", "")))
    usage = _clean_fragment(str(facts.get("usage", "")))
    size_values = [str(value) for value in facts.get("size_values", [])]
    color_pack = ", ".join(piece for piece in (color, pack) if piece)
    identity_options = [
        f"Product: {product}{'; ' + color_pack if color_pack else ''}.",
        f"{product} listing{': ' + color_pack if color_pack else ''}.",
        f"Confirmed product identity: {product}{' | ' + color_pack if color_pack else ''}.",
        f"Catalogued as {product}{' in ' + color if color else ''}{' | ' + pack if pack else ''}.",
        f"Product details begin with {product}{' and ' + color if color else ''}.",
    ]
    material_or_detail = material or pattern or design
    attribute_options = [
        f"Material recorded in the source: {material}." if material else "Only confirmed source attributes are used in this listing.",
        f"The recorded {('pattern' if pattern else 'design')} is {pattern or design}." if (pattern or design) else "The source workbook remains the reference for product attributes.",
        f"Attribute noted for this version: {material_or_detail}." if material_or_detail else "No additional material or design claim has been added.",
        f"Source attribute: {material_or_detail}." if material_or_detail else "Product specifications are limited to the supplied fields.",
        f"The listing retains the supplied product detail: {material_or_detail}." if material_or_detail else "The product identity is kept exactly from the current master.",
    ]
    fit_options = [
        f"Fit recorded for the product: {fit}." if fit else "Variation information is retained in the supplied rows.",
        f"The confirmed fit field reads {fit}." if fit else "Size and variation fields should be reviewed before ordering.",
        f"Fit detail: {fit}." if fit else "The listing follows the current variation structure.",
        f"Recorded fit information: {fit}." if fit else "No unconfirmed fit claim has been introduced.",
        f"This version uses the fit value supplied in the master: {fit}." if fit else "Check the available variation information on the product page.",
    ]
    use_options = [
        f"Use or occasion recorded: {usage}." if usage else "Use the current master fields to review the remaining details.",
        f"The supplied use information is {usage}." if usage else "Product information is presented without unsupported use claims.",
        f"Confirmed use detail: {usage}." if usage else "Review the product details and variation selection before purchase.",
        f"Usage field retained as supplied: {usage}." if usage else "The displayed fields identify the available product option.",
        f"The source lists this use: {usage}." if usage else "All non-content product fields remain unchanged.",
    ]
    size_text = ", ".join(size_values[:8])
    size_options = [
        f"Size options recorded in the group: {size_text}." if size_text else "Size and variation data remain in the corresponding master rows.",
        f"Review the listed size selection{': ' + size_text if size_text else ''} before ordering.",
        f"Variation size information is supplied as{': ' + size_text if size_text else ' recorded in the listing'}.",
        "Select the size or variation using the values shown on the product page.",
        "The existing size relationship and SKU mapping are retained.",
    ]
    families = [identity_options, attribute_options, fit_options, use_options, size_options]
    result: list[str] = []
    for position, family in enumerate(families):
        result.append(_trim(family[(variant + position) % len(family)], 500))
    return result


def _keyword_variants(facts: Mapping[str, Any], variant: int) -> str:
    product = _clean_fragment(str(facts.get("product", "")))
    color = _clean_fragment(str(facts.get("color", "")))
    pack = _clean_fragment(str(facts.get("pack", "")))
    material = _clean_fragment(str(facts.get("material", "")))
    fit = _clean_fragment(str(facts.get("fit", "")))
    design = _clean_fragment(str(facts.get("design", "")))
    pattern = _clean_fragment(str(facts.get("pattern", "")))
    use = _clean_fragment(str(facts.get("usage", "")))
    if not product:
        return ""
    variants = [
        " ".join(piece for piece in (product, color, material, pack) if piece),
        " ".join(piece for piece in (color, product, pack, fit) if piece),
        " ".join(piece for piece in (material, product, color, design) if piece),
        " ".join(piece for piece in (product, design, pattern, color) if piece),
        " ".join(piece for piece in (product, fit, use, pack) if piece),
        f"buy {product}" + (f" {color}" if color else ""),
        f"{product} online" + (f" {color}" if color else ""),
        f"{product} product details" + (f" {pack}" if pack else ""),
        f"{product} catalogue" + (f" {material}" if material else ""),
        f"{product} listing" + (f" {design}" if design else ""),
    ]
    # Preserve phrase order and remove accidental duplicate whitespace.  The
    # field contains no group number, customer number, SKU, or competitor.
    value = variants[variant % len(variants)]
    return _trim(value, 240)


def _write_if_editable(cell: Any, value: str, warnings: list[str], label: str) -> bool:
    if is_formula(cell.value):
        message = f"Skipped formula cell {label}; formulas were preserved."
        if message not in warnings:
            warnings.append(message)
        return False
    cell.value = value
    return True


def _apply_content(
    ws: Any,
    header_row: int,
    blocks: Sequence[Mapping[str, Any]],
    columns: Sequence[ColumnSpec],
    customer_number: int,
    confirmed_context: str,
    platform: str,
) -> tuple[int, list[str], bool]:
    by_role = _columns_by_role(columns)
    warnings: list[str] = []
    changed = 0
    neutral_title_used = False
    customer_variant = customer_number - 1
    content_columns = _content_columns(columns)
    for group_index, block in enumerate(blocks):
        group_rows = list(block["rows"])
        facts = extract_group_facts(ws, group_rows, columns)
        facts["confirmed"] = confirmed_context
        title, neutral = _title_variants(facts, customer_variant + group_index)
        neutral_title_used = neutral_title_used or neutral
        description = _description_variants(
            facts,
            customer_variant + group_index,
            confirmed_context=confirmed_context,
        )
        if platform.casefold() == "flipkart":
            # Flipkart's marketplace rule explicitly excludes this brand from
            # Description.  It may remain in a locked Brand/Product Name cell.
            description = re.sub(r"\bKSHTABHANJAN\b[\s,:;\-]*", "", description, flags=re.IGNORECASE)
            description = re.sub(r"\s+", " ", description).strip(" .,:;-")
        bullets = _bullet_variants(facts, customer_variant + group_index)
        keyword = _keyword_variants(facts, customer_variant + group_index)
        if not facts.get("product"):
            warnings.append(
                f"Group {block.get('label', group_index + 1)!s} has no Product Name/Product Type or existing Title value."
            )

        for row in group_rows:
            for column in content_columns:
                if column.role == "title":
                    value = title
                elif column.role == "description":
                    value = description
                elif column.role == "keyword":
                    value = keyword
                elif column.role == "bullet":
                    number = column.bullet_number
                    if number is None:
                        # Unnumbered bullet fields follow their column order.
                        bullet_columns = by_role.get("bullet", [])
                        number = bullet_columns.index(column) + 1 if column in bullet_columns else 1
                    value = bullets[min(max(number, 1), 5) - 1]
                else:
                    continue
                if _write_if_editable(
                    ws.cell(row=row, column=column.index),
                    value,
                    warnings,
                    f"{ws.title}!{get_column_letter(column.index)}{row}",
                ):
                    changed += 1

    if neutral_title_used:
        warnings.append(
            "One or more groups had only a product identity available; neutral title structure was used. "
            "Add confirmed material, color, pack, or feature data for stronger SEO variation."
        )
    if not content_columns:
        warnings.append(
            "No editable Title, Description, Keyword, or Bullet columns were detected; the output is a validated copy of the master."
        )
    return changed, warnings, neutral_title_used


# ---------------------------------------------------------------------------
# Preservation validation
# ---------------------------------------------------------------------------


def _validation_signature(ws: Any) -> tuple[Any, ...]:
    validations = []
    for validation in ws.data_validations.dataValidation:
        validations.append(
            (
                validation.type,
                validation.operator,
                validation.formula1,
                validation.formula2,
                str(validation.sqref),
                validation.allow_blank,
                validation.showDropDown,
                validation.error,
                validation.prompt,
            )
        )
    return tuple(sorted(validations, key=repr))


def _table_signature(ws: Any) -> tuple[Any, ...]:
    tables = []
    for table in ws.tables.values():
        tables.append((table.name, table.displayName, table.ref))
    return tuple(sorted(tables, key=repr))


def _formula_counter(wb: Any) -> Counter[str]:
    counter: Counter[str] = Counter()
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f" or is_formula(cell.value):
                    counter[_safe_key(cell.value)] += 1
    return counter


def _outside_body_values(ws: Any, body_rows: set[int], content_indices: set[int]) -> list[tuple[int, int, str]]:
    values: list[tuple[int, int, str]] = []
    max_row = max(ws.max_row, 1)
    max_col = max(ws.max_column, 1)
    for row in range(1, max_row + 1):
        # Body rows can legitimately move when groups are normalized.  Their
        # non-content values are compared as a multiset below; only cells
        # outside the body must remain at the same coordinate.
        if row in body_rows:
            continue
        for col in range(1, max_col + 1):
            cell = ws.cell(row=row, column=col)
            if cell.value is not None:
                values.append((row, col, _safe_key(cell.value)))
    return values


def _body_noncontent_counter(
    ws: Any,
    body_rows: Sequence[int],
    columns: Sequence[ColumnSpec],
) -> Counter[tuple[int, str]]:
    content_indices = {column.index for column in columns if column.is_content}
    counter: Counter[tuple[int, str]] = Counter()
    for row in body_rows:
        for col in range(1, ws.max_column + 1):
            if col in content_indices:
                continue
            value = ws.cell(row=row, column=col).value
            if value is not None:
                counter[(col, _safe_key(value))] += 1
    return counter


def _structural_snapshot(wb: Any) -> dict[str, Any]:
    return {
        "sheets": [ws.title for ws in wb.worksheets],
        "sheet_states": {ws.title: ws.sheet_state for ws in wb.worksheets},
        "validations": {ws.title: _validation_signature(ws) for ws in wb.worksheets},
        "merged": {ws.title: tuple(sorted(str(value) for value in ws.merged_cells.ranges)) for ws in wb.worksheets},
        "tables": {ws.title: _table_signature(ws) for ws in wb.worksheets},
        "freeze": {ws.title: str(ws.freeze_panes) if ws.freeze_panes else "" for ws in wb.worksheets},
        "images": {ws.title: len(getattr(ws, "_images", [])) for ws in wb.worksheets},
        "formulas": _formula_counter(wb),
    }


def validate_preservation(
    source_wb: Any,
    output_wb: Any,
    source_sheet_name: str,
    output_sheet_name: str,
    source_header_row: int,
    output_header_row: int,
    source_columns: Sequence[ColumnSpec],
    source_rows: Sequence[int],
    output_rows: Sequence[int],
) -> dict[str, Any]:
    """Compare everything except the deliberately editable content columns."""

    errors: list[str] = []
    warnings: list[str] = []
    source_structure = _structural_snapshot(source_wb)
    output_structure = _structural_snapshot(output_wb)

    if source_structure["sheets"] != output_structure["sheets"]:
        errors.append("Sheet names/order changed.")
    for key in ("sheet_states", "validations", "merged", "tables", "freeze", "images"):
        if source_structure[key] != output_structure[key]:
            errors.append(f"Workbook structure changed: {key}.")
    if source_structure["formulas"] != output_structure["formulas"]:
        errors.append("Formula cells changed or were lost.")

    if source_sheet_name not in source_wb.sheetnames or output_sheet_name not in output_wb.sheetnames:
        errors.append("Selected data sheet is missing from the generated workbook.")
    else:
        source_ws = source_wb[source_sheet_name]
        output_ws = output_wb[output_sheet_name]
        if source_header_row != output_header_row:
            errors.append("Detected header row changed.")
        source_headers = [_safe_key(cell.value) for cell in source_ws[source_header_row]]
        output_headers = [_safe_key(cell.value) for cell in output_ws[output_header_row]]
        # openpyxl may omit completely empty trailing cells while serializing
        # an otherwise unchanged sheet.  They are not headers/columns and do
        # not constitute a meaningful structure change.
        while source_headers and source_headers[-1] == "<blank>":
            source_headers.pop()
        while output_headers and output_headers[-1] == "<blank>":
            output_headers.pop()
        if source_headers != output_headers:
            errors.append("Header values or column order changed.")

        source_content_indices = {column.index for column in source_columns if column.is_content}
        source_body_set = set(source_rows)
        output_body_set = set(output_rows)
        source_outside = Counter(_outside_body_values(source_ws, source_body_set, source_content_indices))
        output_outside = Counter(_outside_body_values(output_ws, output_body_set, source_content_indices))
        if source_outside != output_outside:
            errors.append("A non-content cell outside the editable listing fields changed.")

        source_noncontent = _body_noncontent_counter(source_ws, source_rows, source_columns)
        output_columns = _sheet_columns(output_ws, output_header_row)
        output_noncontent = _body_noncontent_counter(output_ws, output_rows, output_columns)
        if source_noncontent != output_noncontent:
            errors.append(
                "Locked/non-content values changed. Price, images, SKU, identifiers, variation data, and other master fields must remain unchanged."
            )

        # The source and generated workbooks may have different row positions
        # after group ordering, so verify the group sequence independently.
        output_blocks, _, _ = build_group_blocks(output_ws, output_rows, output_columns)
        labels = [str(block["label"]) for block in output_blocks]
        numeric_keys = [_numeric_group_key(label) for label in labels if label]
        if labels and numeric_keys != sorted(numeric_keys):
            warnings.append("Group order could not be proven numeric after export; review the data sheet.")

    report = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "sheets_preserved": source_structure["sheets"] == output_structure["sheets"],
        "validations_preserved": source_structure["validations"] == output_structure["validations"],
        "formulas_preserved": source_structure["formulas"] == output_structure["formulas"],
        "images_preserved": source_structure["images"] == output_structure["images"],
        "locked_values_preserved": not any(
            "Locked/non-content" in error or "non-content" in error for error in errors
        ),
        "content_columns": [column.header for column in source_columns if column.is_content and column.header],
    }
    return report


# ---------------------------------------------------------------------------
# Generation and export helpers
# ---------------------------------------------------------------------------


def _safe_filename_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value or "master"


def customer_filename(platform: str, customer_number: int, source_filename: str) -> str:
    source = Path(source_filename)
    # OOXML workbooks/templates retain their extension. Legacy BIFF and binary
    # workbooks are converted to .xlsx before any editable copy is written.
    extension = _output_extension(source_filename)
    stem = _safe_filename_part(source.stem)
    return f"{_safe_filename_part(platform)}_Customer_{customer_number:02d}_{stem}{extension}"


def generate_customer_workbook(
    source_data: bytes,
    source_filename: str,
    platform: str,
    customer_number: int,
    sheet_name: str | None = None,
    confirmed_context: str = "",
) -> GenerationResult:
    """Create one customer copy, then fail closed if preservation checks fail."""

    filename = customer_filename(platform, customer_number, source_filename)
    warnings: list[str] = []
    errors: list[str] = []
    if is_compatibility_workbook(source_filename):
        warnings.append(
            f"{Path(source_filename).suffix.lower()} master accepted in compatibility mode and converted to .xlsx for safe editing. Values and readable sheets are carried forward; review format-specific features manually."
        )
    try:
        safe_source_data, sanitation = _sanitize_ooxml_workbook(source_data, source_filename)
        if sanitation.get("changed"):
            warnings.append(
                f"Invalid XML control characters were replaced with spaces in {sanitation.get('removed_count', 0)} cell-text byte(s) so the workbook could be opened. Review members: {', '.join(sanitation.get('members', [])[:5])}."
            )
        source_wb = open_source_workbook(safe_source_data, source_filename)
        selected_name = sheet_name or source_wb.active.title
        if selected_name not in source_wb.sheetnames:
            raise ValueError(f"Data sheet '{selected_name}' was not found in the current workbook.")
        source_ws = source_wb[selected_name]
        header_row = find_header_row(source_ws)
        if header_row is None:
            raise ValueError("No header row could be detected on the selected data sheet.")
        columns = _sheet_columns(source_ws, header_row)
        rows = data_rows(source_ws, header_row)
        blocks, reorder_needed, order_warnings = build_group_blocks(source_ws, rows, columns)
        warnings.extend(order_warnings)
        desired_rows = [row for block in blocks for row in block["rows"]]

        # Work from a fresh copy so the source workbook remains the comparison
        # baseline and never gets mutated by content generation.
        output_wb = open_source_workbook(source_data, source_filename)
        output_ws = output_wb[selected_name]
        output_header_row = find_header_row(output_ws)
        if output_header_row is None:
            raise ValueError("The output workbook no longer contains a detectable header row.")
        output_columns = _sheet_columns(output_ws, output_header_row)
        output_rows = data_rows(output_ws, output_header_row)
        # A body merge prevents safe whole-row movement.  The engine keeps the
        # supplied order in that case and reports it rather than damaging the
        # template.
        reordered, reorder_warnings = reorder_group_rows(
            output_ws,
            output_header_row,
            output_rows,
            desired_rows,
        )
        warnings.extend(reorder_warnings)
        if reorder_needed and not reordered and not reorder_warnings:
            warnings.append("Group order was not changed; the source row sequence was already treated as canonical.")

        # Recompute blocks after any movement, so content is written to the
        # correct group and parent/child rows stay together.
        final_rows = data_rows(output_ws, output_header_row)
        final_blocks, _, final_order_warnings = build_group_blocks(output_ws, final_rows, output_columns)
        warnings.extend(final_order_warnings)
        changed_cells, content_warnings, neutral_titles = _apply_content(
            output_ws,
            output_header_row,
            final_blocks,
            output_columns,
            customer_number,
            _trim(confirmed_context, 500),
            platform,
        )
        warnings.extend(content_warnings)

        # openpyxl keeps the original extension; keep_vba was enabled for xlsm.
        output_buffer = io.BytesIO()
        output_wb.save(output_buffer)
        output_data = output_buffer.getvalue()

        # Re-open the saved bytes.  Validation against the serialized workbook
        # catches errors that are invisible before save (for example, a lost
        # validation rule or embedded image relationship).
        check_source = open_source_workbook(source_data, source_filename)
        check_output = open_source_workbook(output_data, filename)
        check_source_ws = check_source[selected_name]
        check_output_ws = check_output[selected_name]
        check_source_header = find_header_row(check_source_ws)
        check_output_header = find_header_row(check_output_ws)
        if check_source_header is None or check_output_header is None:
            raise ValueError("Could not re-detect headers during post-save validation.")
        check_source_columns = _sheet_columns(check_source_ws, check_source_header)
        check_source_rows = data_rows(check_source_ws, check_source_header)
        check_output_rows = data_rows(check_output_ws, check_output_header)
        report = validate_preservation(
            check_source,
            check_output,
            selected_name,
            selected_name,
            check_source_header,
            check_output_header,
            check_source_columns,
            check_source_rows,
            check_output_rows,
        )
        report.update(
            {
                "changed_cells": changed_cells,
                "customer_number": customer_number,
                "platform": platform,
                "source_filename": source_filename,
                "source_extension": Path(source_filename).suffix.lower(),
                "source_xml_sanitized": sanitation.get("changed", False),
                "source_xml_sanitized_count": sanitation.get("removed_count", 0),
                "output_filename": filename,
                "data_sheet": selected_name,
                "header_row": check_output_header,
                "group_count": len(final_blocks),
                "row_count": len(check_output_rows),
                "reordered_groups": bool(reordered),
                "neutral_titles": bool(neutral_titles),
            }
        )
        warnings.extend(report.get("warnings", []))
        errors.extend(report.get("errors", []))
        success = not errors and bool(report.get("ok"))
        if not success:
            output_data = None
        return GenerationResult(
            platform=platform,
            customer_number=customer_number,
            filename=filename,
            data=output_data,
            success=success,
            warnings=_unique_text(warnings, limit=100),
            errors=_unique_text(errors, limit=100),
            report=report,
        )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        return GenerationResult(
            platform=platform,
            customer_number=customer_number,
            filename=filename,
            data=None,
            success=False,
            warnings=_unique_text(warnings, limit=100),
            errors=_unique_text(errors, limit=100),
            report={"ok": False, "platform": platform, "customer_number": customer_number},
        )


def build_manifest(records: Sequence[Mapping[str, Any]]) -> bytes:
    fields = [
        "platform",
        "customer",
        "output_file",
        "source_file",
        "data_sheet",
        "groups",
        "rows",
        "changed_cells",
        "reordered_groups",
        "status",
        "warnings",
        "errors",
        "sku_validation",
        "image_validation",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for record in records:
        writer.writerow({field: record.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def build_export_zip(
    results: Sequence[GenerationResult],
    manifest_records: Sequence[Mapping[str, Any]],
    filename: str = "marketplace_listing_40_files.zip",
    external_validation_report: str | None = None,
) -> bytes:
    """Package validated workbooks plus workbook and external-input QA reports."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result in results:
            if result.success and result.data:
                archive.writestr(result.filename, result.data)
        archive.writestr("manifest.csv", build_manifest(manifest_records))
        if external_validation_report:
            archive.writestr(
                "external_input_validation.txt",
                external_validation_report.encode("utf-8"),
            )
        qa_lines = [
            "Marketplace Listing Studio — strict QA report",
            "",
            "Only workbooks whose locked/non-content fields and workbook structure passed validation are included.",
            "",
        ]
        for result in results:
            status = "PASS" if result.success else "FAIL"
            qa_lines.append(f"{status} | {result.platform} | Customer {result.customer_number:02d} | {result.filename}")
            for warning in result.warnings:
                qa_lines.append(f"  Warning: {warning}")
            for error in result.errors:
                qa_lines.append(f"  Error: {error}")
        archive.writestr("validation_report.txt", "\n".join(qa_lines).encode("utf-8"))
    return buffer.getvalue()


def mime_for_filename(filename: str) -> str:
    return (
        "application/vnd.ms-excel.sheet.macroEnabled.12"
        if filename.lower().endswith(".xlsm")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
