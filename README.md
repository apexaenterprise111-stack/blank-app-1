# Listing Forge — 1–4 × 10 Marketplace Listing Studio

A Streamlit workspace for producing **10 validated customer workbooks per uploaded platform** (up to 40 total):

- 10 Amazon files when Amazon is uploaded
- 10 Meesho files when Meesho is uploaded
- 10 Flipkart files when Flipkart is uploaded
- 10 Snapdeal files when Snapdeal is uploaded

The app is upload-first by design. One master uploader accepts any subset of the four platform Demo/Ready Excel files, from one through four workbooks. Every platform accepts `.xlsx`, `.xlsm`, `.xls`, `.xlsb`, `.xltx`, `.xltm`, or `.xlt`. Native OOXML files retain their format; legacy/binary files are converted to `.xlsx` compatibility copies with a review warning. Each workbook is inspected independently and never uses an older product workbook, a filename, or another platform's structure as a template.

## What it does

1. **Inspects before editing** — sheet names, header row, product identity, groups, content columns, formulas, merged ranges, and data-validation counts are shown before generation.
2. **Accepts locked reference inputs** — enter one or more SKUs in the single SKU input box and upload one image-link file in the single image-link box. The image file is cross-checked only; existing master image URLs and their order remain locked and are never overwritten.
3. **Writes only approved listing fields** — detected Title, Description, Keyword/Search Keyword, and Bullet columns. Unrecognized columns are treated as locked.
4. **Keeps master data protected** — price fields, images/image URLs, SKUs, IDs, size/color/pack/variation data, brand, style codes, formulas, dropdowns, sheet names, and formatting are not regenerated. The external SKU input is validation-only and is never copied over existing cells.
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

Legacy `.xls`/`.xlt` and binary `.xlsb` files are accepted for each submitted portal. Because openpyxl cannot safely write those source formats, the app converts them to `.xlsx` before editing while carrying forward readable sheets and values (and common BIFF formatting where available). Generated files from those sources are `.xlsx`; review format-specific features manually. `.xlsx`, `.xlsm`, `.xltx`, and `.xltm` stay in their native OOXML format, including VBA preservation for macro-enabled files.

## Validation notes

- The generated copy is compared with the uploaded master at workbook level; row movement is compared as a multiset of non-content values so group normalization does not appear as a locked-data change.
- Existing formulas in editable columns are not overwritten; they are preserved and called out in QA warnings.
- An optional **Additional confirmed product detail** field is available in the sidebar. Use it only for facts supplied separately by the operator; the text is appended to descriptions and cannot alter locked catalog data.
- The source workbooks are never overwritten and no generated Excel files are stored in the repository.
