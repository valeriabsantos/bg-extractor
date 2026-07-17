# AGENTS.md — PMAM General Bulletin Extractor

## Overview

This agent extracts and filters personnel information by unit (OPM) from General Bulletins (BG)
of the Polícia Militar do Amazonas (PMAM), published daily in PDF format.

---

## General Bulletin Structure

Each BG is divided into **5 fixed parts**. The agent handles each one specifically:

| Part | Official Name | What to Extract |
|------|--------------|-----------------|
| 1st  | SERVIÇOS DIÁRIOS | Personnel on duty by shift/area |
| 2nd  | INSTRUÇÃO | Notices, courses, training notes |
| 3rd  | ASSUNTOS GERAIS | Transfer, aggregation, and secondment orders |
| 4th  | JUSTIÇA E DISCIPLINA | Absences, FATDs, judicial summons, commendations, disciplinary actions |
| 5th  | COMUNICAÇÃO SOCIAL | Institutional news, birthdays |

---

## Unit Identification

Units are identified by acronyms/codes in the text:

- **CICOMs** — `1ª CICOM`, `11ª CICOM`, `22ª CICOM`...
- **BPMs** — `1º BPM`, `5º BPM-Coari`, `11º BPM PARI`...
- **CPAs** — `CPA NORTE`, `CPA SUL`, `CPA LESTE`, `CPA OESTE`, `CPA C-SUL/C-OESTE`
- **Specialised** — `CPE`, `BPGDA`, `2º BPCHQ-ROCAM`, `ROCAM`, `CECOPOM`
- **Support** — `CIA CG`, `DPA`, `DPA-5/SSP`, `SSP AM`, `CPM`, `RMP PMAM`
- **Schools** — `CMPM I`, `CMPM III`, `CMPM V`, `CMPM VI`...
- **OPM numeric codes** — `53.0`, `11.0`, `22.0` (used in judicial summons blocks to identify units)

---

## Personnel Patterns

The agent recognises the following military identification patterns:

```
RANK [QXPM] FULL_NAME NUMERIC_CI
```

Examples:
- `SD PM IVAN MAURICIO DE SOUZA RAMIREZ 24957`
- `CB QPPM ANDRE MATOS DE BRITO 23209`
- `3º SGT QPPM FRANKLIN BARBOZA DA SILVA 19063`
- `Cap PM Caio Cesar (23700)`

---

## Section-Specific Parsers

### 3rd Part — Orders
- Detects `PORTARIA Nº ...` blocks
- Extracts `Da [ORIGIN] para [DESTINATION]` and the affected personnel
- Classifies as: `TRANSFER`, `AGGREGATION`, `SECONDMENT`

### 4th Part — ABSENCE LIST
Structured table format:
```
ORD  P/G        NAME                    CI     UNIT        DATE    SHIFT   OPM
1    SD PM      IVAN MAURICIO...        24957  2º BPCHQ   08/out  ÚNICO   CPE
```
- Filters by `LOTAÇÃO` column (home unit) **or** `OPM` (where assigned)

### 4th Part — FATD
- Detects `FATD Nº ...` blocks
- Extracts `INTERESSADO`, `CI`, `UNIDADE` and excerpt from `SÍNTESE FÁTICA`

### 4th Part — Judicial Summons
- Detects `Dia [DATE], às [TIME]: RANK PM ...` blocks
- Extracts name, CI, case number and court
- Identifies modality: **Presencial** (address + date + time) or **Videoconferência** (date + time + link)
- Unit matched via OPM numeric code (e.g. `53.0`) or textual unit name

### 4th Part — Commendations
- Detects `ELOGIO INDIVIDUAL` section
- Extracts names listed and the reason for commendation

---

## Outputs

| Format | How to generate |
|--------|----------------|
| Terminal | `python extractor.py <pdf> <unit>` |
| Word report | `python extractor.py <pdf> <unit> --word` |
| Web interface | Open `index.html` in a browser |
| List units | `python extractor.py <pdf> x --list-units` |

---

## Known Limitations

1. **Numeric codes in judicial summons** — Format `CB PM 53.0 NAME` uses OPM numeric code.
   The agent captures the personnel record and matches numeric codes to filter units correctly,
   using a negative lookahead (`(?!\d)`) to prevent false positives on matriculation numbers.

2. **Scanned PDFs** — Requires external OCR (e.g. `tesseract`). The agent expects native text.

3. **Future layouts** — PMAM may change the BG layout. Adjust regex in `extractor.py` if needed.

---

## Dependencies

```bash
pip install pdfplumber --break-system-packages
```

Web interface: no installation required — uses PDF.js via CDN (requires internet connection).
