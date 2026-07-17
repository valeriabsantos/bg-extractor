# Skill: bg-extractor

**Trigger:** "extract from BG", "filter by unit", "who is in the BG for [unit]",
"bulletin for [acronym]", "personnel from [unit] in the BG"

---

## What this skill does

Extracts and filters personnel information by unit (OPM) from a PMAM General Bulletin (BG) PDF.
For each personnel record found, it returns:
- Full name
- CI / SI (badge number)
- BG part where the record was found
- Reason / context of the mention

---

## How to use

### Via web interface (index.html)
1. Open `index.html` in a browser
2. Drag and drop the BG PDF or click to select it
3. Type the unit name in the filter field and press **Filtrar**
4. Browse results grouped by bulletin section
5. Click **Exportar Word** or **Exportar PDF** to save the report

### Via command line (extractor.py)

```bash
# List all units in the BG
python extractor.py "BG191.pdf" x --list-units

# Filter by unit and display in terminal
python extractor.py "BG191.pdf" "11ª CICOM"

# Filter and export Word report
python extractor.py "BG191.pdf" "CPA LESTE" --word

# Valid unit examples
python extractor.py "BG191.pdf" "CPA NORTE"
python extractor.py "BG191.pdf" "2º BPCHQ-ROCAM"
python extractor.py "BG191.pdf" "22ª CICOM"
python extractor.py "BG191.pdf" "CPE"
python extractor.py "BG191.pdf" "53.0"
```

---

## Detected occurrence types

| Tag | Colour | Description |
|-----|--------|-------------|
| ABSENCE | Red | Absence from assigned duty (RELAÇÃO DE FALTAS) |
| TRANSFER | Teal | Unit transfer order |
| AGGREGATION | Orange | Aggregation order |
| DISCIPLINE | Amber | FATD — Disciplinary investigation |
| JUDICIAL | Purple | Summons for hearing/testimony |
| COMMENDATION | Green | Individual commendation |
| SERVICE | Blue | Assigned to daily duty |
| TRAINING | Yellow | Courses, training, notices |

---

## BG sections handled

### 1st Part – Daily Services
Detects personnel assigned by shift and policing area.

### 2nd Part – Training
Detects mentions of courses, notices, and training linked to the unit.

### 3rd Part – General Matters
Parses **transfer** and **aggregation** orders, extracting the route
`From [origin] to [destination]` and the affected personnel.

### 4th Part – Justice and Discipline
Four sub-parsers:
- **ABSENCE LIST** — structured table with LOTAÇÃO and OPM columns
- **FATD** — block with INTERESSADO + UNIDADE + SÍNTESE FÁTICA
- **Judicial summons** — `Dia [date], às [time]: RANK PM NAME` blocks
  - Modality: **Presencial** (address, date, time) or **Videoconferência** (date, time, link)
  - Unit matched via OPM numeric code (e.g. `53.0`) with negative lookahead to prevent false matches on matriculation numbers
- **Commendations** — ELOGIO INDIVIDUAL section with name list

### 5th Part – Social Communication
Detects news items that explicitly mention the unit.

---

## Requirements

```bash
# Python (extractor.py)
pip install pdfplumber --break-system-packages

# Web interface (index.html) — no installation required
# Requires internet connection (PDF.js via CDN)
```

---

## Limitations

- **Scanned PDFs** will not work without OCR (e.g. `pytesseract`)
- BG layout may change between editions — adjust regex in `extractor.py` if needed

---

## Project files

```
bg-extractor/
├── index.html                  ← Web interface (open in browser)
├── extractor.py                ← Python CLI script
├── README.md                   ← Project description
├── AGENTS.md                   ← Agent documentation and parsing rules
├── agents.agents.md            ← Agent configuration
└── skills/
    └── bg-extractor/
        └── SKILL.md            ← This file
```
