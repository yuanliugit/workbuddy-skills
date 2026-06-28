# Excel/XLSX

Excel/XLSX技能，提供相关功能和服务。

---
name: Excel / XLSX
slug: excel-xlsx
version: 1.1.0
homepage: https://clawic.com/skills/excel-xlsx
description: "Create, inspect, and edit Microsoft Excel workbooks and XLSX files with reliable formulas, dates, types, formatting, recalculation, and template preservation. Includes investment-banking-grade financial modeling conventions (color coding, three-statement architecture, DCF/LBO/Merger Model standards). Use when (1) the task is about Excel, `.xlsx`, `.xlsm`, `.xls`, `.csv`, or `.tsv`; (2) formulas, formatting, workbook structure, or compatibility matter; (3) the file must stay reliable after edits."
changelog: Added Financial Modeling Domain Rules v1.1.0: investment banking color conventions, three-statement model architecture, DCF/LBO/Merger Model-specific rules, formula anchoring, audit checklist, and China-specific Excel conventions.
metadata: {"clawdbot":{"emoji":"📗","requires":{"bins":[]},"os":["linux","darwin","win32"]}}
---

## When to Use

Use when the main artifact is a Microsoft Excel workbook or spreadsheet file, especially when formulas, dates, formatting, merged cells, workbook structure, or cross-platform behavior matter.

## Core Rules

### 1. Choose the workflow by job, not by habit

- Use `pandas` for analysis, reshaping, and CSV-like tasks.
- Use `openpyxl` when formulas, styles, sheets, comments, merged cells, or workbook preservation matter.
- Treat CSV as plain data exchange, not as an Excel feature-complete format.
- Reading values, preserving a live workbook, and building a model from scratch are different spreadsheet jobs.

### 2. Dates are serial numbers with legacy quirks

- Excel stores dates as serial numbers, not real date objects.
- The 1900 date system includes the false leap-day bug, and some workbooks use the 1904 system.
- Time is fractional day data, so formatting and conversion both matter.
- Date correctness is not enough if the number format still displays the wrong thing to the user.

### 3. Keep calculations in Excel when the workbook should stay live

- Write formulas into cells instead of hardcoding derived results from Python.
- Use references to assumption cells instead of magic numbers inside formulas.
- Cached formula values can be stale, so do not trust them blindly after edits.
- Check copied formulas for wrong ranges, wrong sheets, and silent off-by-one drift before delivery.
- Absolute and relative references are part of the logic, so copied formulas can be wrong even when they still "work".
- Test new formulas on a few representative cells before filling them across a whole block.
- Verify denominators, named ranges, and precedent cells before shipping formulas that depend on them.
- A workbook should ship with zero formula errors, not with known `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, or circular-reference fallout left for the user to fix.
- For model-style work, document non-obvious hardcodes, assumptions, or source inputs in comments or nearby notes.

### 4. Protect data types before Excel mangles them

- Long identifiers, phone numbers, ZIP codes, and leading-zero values should usually be stored as text.
- Excel silently truncates numeric precision past 15 digits.
- Mixed text-number columns need explicit handling on read and on write.
- Scientific notation, auto-parsed dates, and stripped leading zeros are common corruption, not cosmetic issues.

### 5. Preserve workbook structure before changing content

- Existing templates override generic styling advice.
- Only the top-left cell of a merged range stores the value.
- Hidden rows, hidden columns, named ranges, and external references can still affect formulas and outputs.
- Shared strings, defined names, and sheet-level conventions can matter even when the visible cells look simple.
- Match styles for newly filled cells instead of quietly introducing a new visual system.
- If the workbook is a template, preserve sheet order, widths, freezes, filters, print settings, validations, and visual conventions unless the task explicitly changes them.
- Conditional formatting, filters, print areas, and data validation often carry business meaning even when users only mention the numbers.
- If there is no existing style guide and the file is a model, keep editable inputs visually distinguishable from formulas, but never override an established template to force a generic house style.

### 6. Recalculate and review before delivery

- Formula strings alone are not enough if the recipient needs current values.
- `openpyxl` preserves formulas but does not calculate them.
- Verify no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, or circular-reference fallout remains.
- If layout matters, render or visually review the workbook before calling it finished.
- Be careful with read modes: opening a workbook for values only and then saving can flatten formulas into static values.
- If assumptions or hardcoded overrides must stay, make them obvious enough that the next editor can audit the workbook.

### 7. Scale the workflow to the file size

- Large workbooks can fail for boring reasons: memory spikes, padded empty rows, and slow full-sheet reads.
- Use streaming or chunked reads when the file is big enough that loading everything at once becomes fragile.
- Large-file workflows also need narrower reads, explicit dtypes, and sheet targeting to avoid accidental damage.

## Common Traps

- Type inference on read can leave numbers as text or convert IDs into damaged numeric values.
- Column indexing varies across tools, so off-by-one mistakes are common in generated formulas.
- Newlines in cells need wrapping to display correctly.
- External references break easily when source files move.
- Password protection in old Excel workflows is not serious security.
- `.xlsm` can contain macros, and `.xls` remains a tighter legacy format.
- Large files may need streaming reads or more careful memory handling.
- Google Sheets and LibreOffice can reinterpret dates, formulas, or styling differently from Excel.
- Dynamic array or newer Excel functions like `FILTER`, `XLOOKUP`, `SORT`, or `SEQUENCE` may fail or degrade in older viewers.
- A workbook can look fine while still carrying stale cached values from a prior recalculation.
- Saving the wrong workbook view can replace formulas with cached values and quietly destroy a live model.
- Copying formulas without checking relative references can push one bad range across an entire block.
- Hidden sheets, named ranges, validations, and merged areas often keep business logic that is invisible in a quick skim.
- A workbook can appear numerically correct while still failing because filters, conditional formats, print settings, or data validation were stripped.
- A workbook can be numerically correct and still fail visually because wrapped text, clipped labels, or narrow columns were never reviewed.

## Related Skills

## Financial Modeling Domain Rules（新增 v1.1.0）

When building or editing financial models (DCF, LBO, Merger Model, Three-Statement Model), apply these investment-banking-grade conventions in addition to the core rules above.

### 1. Color Coding Convention (投行颜色约定)

All financial model cells must follow this strict color convention — it is the universal language of investment banking Excel models:

| Cell Type | Font Color | Background | Example |
|-----------|-----------|------------|---------|
| Hard-coded inputs / assumptions | **Blue** (#0000FF) | Yellow (#FFFF00) light | Revenue growth rate: 5.0% |
| Formulas / calculations | **Black** (#000000) | None (white) | =B12*(1+$C$5) |
| Cross-sheet references | **Green** (#006100) | None (white) | ='Assumptions'!$C$12 |
| External links (other workbooks) | **Red** (#FF0000) | None (white) | ='[CompData.xlsx]Sheet1'!$A$1 |
| Outputs / key metrics (always black) | **Black** (#000000) | Light grey (#F2F2F2) | IRR: 22.5% |

**Rule**: If it's not blue, green, or red, it should be a formula. Never hardcode a number into a formula cell — reference the assumption cell instead.

### 2. Three-Statement Model Architecture (三表联动建模)

When building integrated financial models:

**Sheet Order (mandatory)**:
1. `Assumptions` — All hardcoded inputs in one place
2. `Income Statement` — Revenue → Net Income
3. `Balance Sheet` — Must balance (A = L + E, with check row)
4. `Cash Flow` — Indirect method, links to BS changes
5. `Debt Schedule` — If applicable (LBO/Project Finance)
6. `Returns / Valuation` — IRR, MOIC, DCF output
7. `Sensitivity` — Data tables, scenario manager

**Balance Check Row**: Every balance sheet must have a check row: `Total Assets - (Total Liabilities + Total Equity)`. Value must be zero (or < 0.01 for rounding tolerance). Flag any non-zero with conditional formatting (red fill).

**Circular Reference Handling**: Interest expense depends on debt balance, which depends on cash flow, which depends on interest expense. Solutions:
- Use a "circuit breaker" (copy/paste values macro, or iterative calc enabled)
- Use average debt balance: `Interest = (Beginning Debt + Ending Debt) / 2 × Rate`
- Set Excel iteration to On (File → Options → Formulas → Enable iterative calculation)

**Surplus Cash / Revolver Logic**:
```
=IF(Ending Cash > Min Cash, Ending Cash - Min Cash, 0)  → Surplus cash (pay down debt)
=IF(Ending Cash < Min Cash, Min Cash - Ending Cash, 0)  → Revolver draw
```

### 3. DCF Model-Specific Rules

- **WACC calculation**: Always reference live cells from `Assumptions` sheet — never embed 4.5%, 5.5%, etc. in formulas
- **Terminal value**: Use both Gordon Growth AND Exit Multiple methods; take midpoint; flag if TV > 85% of total EV
- **FCFF components**: D&A, CapEx, and NWC change must each have their own assumption row, not buried in a single cell
- **PV factors**: Use `=1/(1+WACC)^YearNumber` rather than `=POWER(1+WACC, -YearNumber)` for auditability

### 4. LBO Model-Specific Rules

- **Debt Schedule**: Each tranche gets its own section with: Beginning Balance, (+) Draws, (-) Mandatory Amort, (-) Optional Prepay, (=) Ending Balance
- **Cash Sweep**: Define sweep percentage in `Assumptions`; model with MIN/MAX logic
- **IRR**: Use `=IRR(range, guess)` or `=XIRR(values, dates, guess)` for irregular timing
- **MOIC**: Simple division `=Total Return / Total Investment` — never a complex formula
- **Covenant checks**: Include `Interest Coverage` and `Leverage` ratio rows with conditional formatting for breaches

### 5. Merger Model-Specific Rules

- **Purchase Price Allocation (PPA)**: Separate into Tangible Asset Step-up, Identifiable Intangibles, Goodwill
- **Amortization of intangibles**: Default 10-year straight-line unless specific asset life known
- **Accretion/Dilution output**: Always show both Year 1 AND Year 2 (synergies often take 12-18 months)
- **Payment mix**: Model 0% / 50% / 100% cash scenarios; show EPS sensitivity to financing structure

### 6. Formula Anchoring in Financial Models

- **Absolute references for assumptions**: `=$C$5` — every assumption reference should be absolute (F4-locked)
- **Row-only absolute for time-series**: `=B$10` — lock the row when copying across years
- **Column-only absolute for vertical fills**: `=$B10` — lock the column when filling down
- **Named ranges for key drivers**: Define names like `WACC`, `Tax_Rate`, `Terminal_Growth` for readability

### 7. Model Audit Checklist (交付前必查)

Before delivering any financial model:

- [ ] Color convention enforced (blue=inputs, black=formulas, green=cross-ref)
- [ ] No hardcoded numbers inside formula cells
- [ ] Balance sheet balances (±0.01 tolerance)
- [ ] Cash flow statement: ending cash matches balance sheet cash
- [ ] Zero `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?` errors
- [ ] Circular references resolved (interest/debt loop)
- [ ] Sensitivity tables recalculated (Ctrl+Alt+F9)
- [ ] Key assumptions documented in cell comments
- [ ] Print areas set (landscape, fit-to-width for wide models)
- [ ] File saved as `.xlsx` (not `.xlsm` unless macros needed)

### 8. China-Specific Excel Conventions

- **Number format**: `#,##0.00` (Chinese thousands separator)
- **Currency**: Use ¥ symbol with custom format `¥#,##0.00`
- **Date format**: `YYYY-MM-DD` or `YYYY年M月D日`
- **Percentage**: `0.00%` (two decimal places)
- **Negative numbers**: Red font or parentheses `(1,000)` — Chinese convention prefers red font for negatives in financial context
- **Sheet names in Chinese**: 假设条件 / 利润表 / 资产负债表 / 现金流量表 / 估值汇总
- **WACC / Ke / Kd**: Label in both Chinese and English for audit trail
Install with `clawhub install <slug>` if user confirms:
- `csv` — Plain-text tabular import and export workflows.
- `data` — General data handling patterns before spreadsheet output.
- `data-analysis` — Higher-level analysis that can feed workbook deliverables.

## Feedback

- If useful: `clawhub star excel-xlsx`
- Stay updated: `clawhub sync`
