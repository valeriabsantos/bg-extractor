# agents.agents.md — Project Agent Configuration

## bg-extractor-agent

**Description:** Main BG extraction agent. Receives a PDF and a unit name,
returns the list of personnel mentioned with their reasons.

**Trigger:** User provides a BG PDF file + unit acronym (e.g. `11ª CICOM`, `53.0`)

**Available tools:**
- `Read` — read PDF and local files
- `Bash` — run `extractor.py`
- `Write` — save reports

**Execution flow:**

```
1. Receive PDF + unit
   ↓
2. Run: python extractor.py <pdf> <unit> --list-units
   → Confirm the unit exists in the document
   ↓
3. Run: python extractor.py <pdf> <unit> --word
   → Generate Word report
   ↓
4. Present summary to user:
   - Total occurrences per part
   - Path of the generated file
```

**System prompt:**

```
You are the General Bulletin extractor agent.
Your role is to filter personnel by unit from BG PDFs.

When receiving a PDF and a unit:
1. Check if the unit exists in the document using --list-units
2. Run the full extraction with --word
3. Present a clear summary of results per BG part
4. Highlight absence, transfer, and disciplinary cases

Be precise and objective. Do not invent information not present in the PDF.
```

---

## unit-lookup-agent

**Description:** Auxiliary agent that identifies all units present in a BG
and suggests the most relevant one to the user.

**Trigger:** User does not know the exact unit acronym

**Flow:**
```
1. Run: python extractor.py <pdf> x --list-units
2. Present formatted list
3. Ask which unit the user wants to filter
4. Call bg-extractor-agent with the chosen unit
```

---

## report-formatter-agent

**Description:** Agent that formats the results JSON into a Word or HTML report.
Can be called directly if the user already has the extracted data.

**Expected input:**
```json
{
  "bg_number": "191",
  "bg_date": "13 de outubro de 2025",
  "unit": "11ª CICOM",
  "results": [
    {
      "label": "4ª Parte – Justiça e Disciplina",
      "employees": [
        {
          "name": "ADAM KEVIN ALBUQUERQUE SILVA",
          "ci": "26128",
          "rank": "SD PM",
          "reason": "Absence from duty on 09/out — 2nd SHIFT | OPM: CPA LESTE",
          "tag": "falta"
        }
      ]
    }
  ]
}
```

**Output:** Formatted `.doc` or `.html` file

---

## Agent dependencies

```
unit-lookup-agent
      ↓
bg-extractor-agent
      ↓
report-formatter-agent
```

Agents can be called individually or in automatic sequence.
