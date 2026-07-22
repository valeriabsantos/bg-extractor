# BG Extractor — General Bulletin Filter

A browser-based tool to extract and filter personnel information General Bulletins (Boletim Geral) published in PDF format.

## Live Demo

🔗 [https://valeriabsantos.github.io/bg-extractor/](https://valeriabsantos.github.io/bg-extractor/)

## Overview

Each General Bulletin is a multi-section PDF document listing all personnel-related events for the day — transfers, judicial hearings, disciplinary actions, medical leave, commendations, and more. This tool parses the raw PDF text and lets the user filter results by unit, displaying only the relevant personnel.

## Features

- 📄 **PDF parsing in the browser** — no server, no upload, no data leaves your machine
- 🔍 **Filter by unit** — supports partial matches, accents, and ordinal variations (e.g. `11ª CICOM`, `ROCAM`, `53.0`, `2º BPM`)
- 📋 **Covers all 5 bulletin sections:**
  - Parte 1 — Personnel movements and transfers
  - Parte 2 — Aggregations and attachments
  - Parte 3 — General matters (medical leave with licence type, duration, and end date)
  - Parte 4 — Justice and discipline (judicial hearings with modality, address, date, and time)
  - Parte 5 — Commendations and service orders
- 📝 **Export to Word (.doc)** — formatted table per section
- 🗒️ **Export to PDF** — print-ready A4 layout via browser print dialog
- ✅ **Works entirely offline** after first load (PDF.js cached by browser)

## How to Use

1. Open the [live site](https://valeriabsantos.github.io/bg-extractor/) in any modern browser
2. Drag and drop (or click to select) a General Bulletin PDF
3. Type the unit name in the filter field and press **Filtrar**
4. Browse results grouped by bulletin section
5. Export to Word or PDF as needed

## Technical Details

- Pure HTML + CSS + JavaScript — single file, zero dependencies to install
- PDF text extraction via [PDF.js](https://mozilla.github.io/pdf.js/) (loaded from CDN)
- Regex-based parsing engine tailored to the PMAM bulletin format
- Stateful address and court tracking across hearing blocks
- Unit matching uses negative lookahead (`(?!\d)`) to prevent false positives on matriculation numbers

## Project Structure

```
bg-extractor/
├── .claude/
│   └── skills/
│       └── SKILL.md        # AI skill definition for Claude
├── index.html              # Complete web application (UI + parser + export logic)
├── extractor.py            # Python CLI alternative
├── AGENTS.md               # Agent documentation and parsing rules
├── agents.agents.md        # AI agent configuration and execution flows
└── README.md
```

## Author

Valéria Bezerra  
[github.com/valeriabsantos](https://github.com/valeriabsantos)
