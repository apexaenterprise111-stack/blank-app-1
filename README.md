# Listing Forge — 4 × 10 Marketplace Listing Studio

A Streamlit workspace for producing **40 separate, validated customer workbooks**:

- 10 Amazon files
- 10 Meesho files
- 10 Flipkart files
- 10 Snapdeal files

The app is upload-first by design. Each platform receives its own current Demo/Ready `.xlsx` or `.xlsm` master. It inspects that workbook independently and never uses an older product workbook, a filename, or another platform's structure as a template.

## What it does

1. **Inspects before editing** — sheet names, header row, product identity, groups, content columns, formulas, merged ranges, and data-validation counts are shown before generation.
2. **Accepts locked reference inputs** — upload a SKU workbook/CSV/TXT or paste SKUs, then upload a ZIP containing image-link text/CSV/JSON files or a workbook of links. The tool cross-checks both inputs against every platform master.
3. **Writes only approved listing fields** — detected Title, Description, Keyword/Search Keyword, and Bullet columns. Unrecognized columns are treated as locked.
4. **Keeps master data protected** — price fields, images/image URLs, SKUs, IDs, size/color/pack/variation data, brand, style codes, formulas, dropdowns, sheet names, and formatting are not regenerated. External SKU/image inputs are validation-only and are never copied over existing cells.
5. **Normalizes group order safely** — numeric groups are kept together; Amazon parent/child rows remain together. Embedded-image or merged-body layouts are not reordered when doing so could break image mapping; the app reports that manual review is needed.
6. **Creates deterministic unique copy** — ten title, description, keyword, and bullet variants are generated from confirmed workbook facts only. Unsupported material, fit, color, pack, or feature claims are not invented.
7. **Validates after saving** — every serialized workbook is re-opened and checked for sheet structure, headers, formulas, data validations, merged ranges, image relationships, and all non-content/locked values. A failed file is excluded from the all-files ZIP.
8. **Exports safely** — a ZIP contains separate customer workbooks, `manifest.csv`, `validation_report.txt`, and `external_input_validation.txt`. `.xlsm` masters remain `.xlsm` and are loaded with VBA preservation enabled.

Flipkart descriptions also remove the explicitly prohibited `KSHTABHANJAN` string while leaving locked Brand/Product Name cells untouched.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The application listens on Streamlit's default port `8501`. For the Arena preview, bind to all interfaces:

```bash
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Legacy `.xls` files are not accepted because preserving their original workbook structure requires a different writer. Save them as `.xlsx` before upload.

## Validation notes

- The generated copy is compared with the uploaded master at workbook level; row movement is compared as a multiset of non-content values so group normalization does not appear as a locked-data change.
- Existing formulas in editable columns are not overwritten; they are preserved and called out in QA warnings.
- An optional **Additional confirmed product detail** field is available in the sidebar. Use it only for facts supplied separately by the operator; the text is appended to descriptions and cannot alter locked catalog data.
- The source workbooks are never overwritten and no generated Excel files are stored in the repository.
