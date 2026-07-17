"""
extractor.py — Extrator de Boletim Geral
Uso: python extractor.py <arquivo.pdf> <unidade> [--word]

Exemplos:
  python extractor.py "BG123.pdf" "11ª CICOM"
  python extractor.py "BG123.pdf" "CPA LESTE" --word
"""

import re
import sys
import json
import argparse
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Instale: pip install pdfplumber --break-system-packages")
    sys.exit(1)

# ── Partes do BG ──────────────────────────────────────────────
PARTS = [
    ("p1", "PRIMEIRA PARTE", "1ª Parte – Serviços Diários"),
    ("p2", "SEGUNDA PARTE",  "2ª Parte – Instrução"),
    ("p3", "TERCEIRA PARTE", "3ª Parte – Assuntos Gerais"),
    ("p4", "QUARTA PARTE",   "4ª Parte – Justiça e Disciplina"),
    ("p5", "QUINTA PARTE",   "5ª Parte – Comunicação Social"),
]

# ── Padrões de rank militar ──────────────────────────────────
RANK_TOKENS = (
    r"CEL|TEN\s*CEL|MAJ|CAP|1[°º]?\s*TEN|2[°º]?\s*TEN|"
    r"SUB\s*TEN|SUBTEN|ST|1[°º]?\s*SGT|2[°º]?\s*SGT|3[°º]?\s*SGT|CB|SD"
)

EMP_RE = re.compile(
    rf"({RANK_TOKENS})\s+(?:Q[A-Z]+PM\s+|PM\s+)?"
    r"([A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ][A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ\s]{4,60}?)"
    r"\s+(\d{4,5})\b",
    re.IGNORECASE,
)

# Formato numérico de OPM: RANK PM 53.0 NAME (CI)
OPM_EMP_RE = re.compile(
    rf"({RANK_TOKENS})\s+PM\s+"
    r"(\d{1,3}\.\d)\s+"
    r"([\s\S]+?)"
    r"\s*\((\d{4,5})\)",
    re.IGNORECASE,
)

# ── Padrões de unidades ───────────────────────────────────────
UNIT_PATTERNS = [
    r"\d+[ªº°a]\s*CICOM(?:\/[A-Z]+)?",
    r"\d+[°º]\s*BPM(?:[\s\-][A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ]+)*",
    r"CPA\s+(?:NORTE|SUL|LESTE|OESTE|C-SUL\/C-OESTE|CENTRO-SUL\/C-OESTE|CENTRO(?:-SUL)?)",
    r"CPE\b", r"BPGDA\b", r"\d*[°º]?\s*BPCHQ(?:[-\s]ROCAM)?",
    r"CIA\s+(?:CG|PMAM)\b", r"CMPM\s+(?:I{1,3}|IV|VI{0,3}|IX|X{0,3}|\d+)",
    r"RMP\s+PMAM\b", r"COPAMB\b", r"\d+[ªº°a]\s*CIPM",
    r"DPA(?:-\d+)?(?:\/[A-Z]+)*", r"SSP[-\s]?AM\b",
    r"\b(?:CPM|ROCAM|CECOPOM|COPE|MARTE)\b", r"\d+[°º]\s*GPM(?:\/[A-Z]+)*",
]


# ─────────────────────────────────────────────────────────────
def extract_text(pdf_path: str) -> str:
    """Extrai texto completo do PDF preservando linhas."""
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                lines.append(text)
    return "\n".join(lines)


def split_parts(text: str) -> list[dict]:
    """Divide o texto nas 5 partes do BG."""
    indices = []
    for key, marker, label in PARTS:
        m = re.search(marker.replace(" ", r"\s+"), text, re.IGNORECASE)
        indices.append((key, label, m.start() if m else -1))

    parts = []
    for i, (key, label, idx) in enumerate(indices):
        if idx == -1:
            parts.append({"key": key, "label": label, "text": ""})
            continue
        next_idx = next((indices[j][2] for j in range(i + 1, len(indices)) if indices[j][2] != -1), len(text))
        parts.append({"key": key, "label": label, "text": text[idx:next_idx]})
    return parts


def extract_all_units(text: str) -> list[str]:
    """Detecta todas as unidades mencionadas no documento."""
    found = set()
    for pat in UNIT_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            u = re.sub(r"\s+", " ", m.group()).strip().upper()
            if len(u) > 2:
                found.add(u)
    return sorted(found)


def build_unit_re(unit: str) -> re.Pattern:
    escaped = re.escape(unit).replace(r"\ ", r"\s*").replace(r"\°", r"[°º]").replace(r"\º", r"[°º]")
    return re.compile(escaped + r"(?!\d)", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
def extract_employees(part: dict, unit: str) -> list[dict]:
    """Extrai funcionários de uma parte para a unidade escolhida."""
    text    = part["text"]
    key     = part["key"]
    unit_re = build_unit_re(unit)
    results = []
    seen    = set()

    def add(records):
        for r in records:
            # Judicial entries may repeat for the same person on different dates
            extra = r.get("date", "")
            k = r["name"].strip() + "|" + r["ci"] + "|" + extra
            if k not in seen and len(r["name"].strip()) > 4:
                seen.add(k)
                results.append(r)

    # Run specific parsers FIRST so their tags (FALTA, TRANSF...) take priority
    if key == "p4":
        add(_parse_faltas(text, unit_re))
        add(_parse_fatd(text, unit_re))
        add(_parse_judicial(text, unit_re))
        add(_parse_elogio(text, unit_re))
    if key == "p3":
        add(_parse_portarias(text, unit_re))
        add(_parse_lts(text, unit_re))
    if key == "p1":
        add(_parse_servicos(text, unit_re))

    # Strip sections already handled by specific parsers before generic scan
    scan_text = _remove_structured_sections(text)
    add(_scan_blocks(scan_text, unit_re, key))

    return results


def _remove_structured_sections(text: str) -> str:
    """Remove RELAÇÃO DE FALTAS e ELOGIO INDIVIDUAL do texto antes do scan genérico."""
    # Remove faltas table
    m0 = re.search(r"RELA[ÇC][ÃA]O\s+DE\s+FALTAS", text, re.IGNORECASE)
    if m0:
        m1 = re.search(r"Em\s+consequ[êe]ncia", text[m0.start():], re.IGNORECASE)
        end = m0.start() + m1.end() if m1 else m0.start() + 4000
        text = text[:m0.start()] + text[end:]
    # Remove elogio section (handled by _parse_elogio)
    me = re.search(r"ELOGIO\s+INDIVIDUAL", text, re.IGNORECASE)
    if me:
        text = text[:me.start()]
    return text


def _scan_blocks(text, unit_re, key):
    """Varre blocos que mencionam a unidade (contexto restrito para evitar falsos positivos)."""
    found = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        if not unit_re.search(line):
            continue
        # Skip structured table rows (faltas/elogio tables handled by specific parsers)
        if re.search(r"\b(LOTAÇÃO|OPM|ORD\s+P/G)\b", line, re.IGNORECASE):
            continue
        # Use a tight window (4 lines before, 8 after) around the unit mention
        ctx = "\n".join(lines[max(0, i - 4): min(len(lines), i + 9)])
        found.extend(_parse_employees_block(ctx, key))

    return found


def _parse_employees_block(block, key):
    emps = []
    for m in EMP_RE.finditer(block):
        rank = m.group(1).strip()
        name = re.sub(r"\b(?:Q[A-Z]+PM|PM)\b", "", m.group(2), flags=re.IGNORECASE).strip()
        ci   = m.group(3)
        if len(name) < 5 or name[0].isdigit():
            continue
        ctx_s = max(0, m.start() - 200)
        ctx_e = min(len(block), m.end() + 300)
        ctx   = block[ctx_s:ctx_e]
        emps.append({"rank": rank, "name": name, "ci": ci,
                     "reason": _reason(ctx, key), "tag": _tag(ctx, key)})
    return emps


def _parse_faltas(text, unit_re):
    """RELAÇÃO DE FALTAS table."""
    results = []
    m0 = re.search(r"RELA[ÇC][ÃA]O\s+DE\s+FALTAS", text, re.IGNORECASE)
    if not m0:
        return results
    # Search for "Em consequência" AFTER the table header
    m1 = re.search(r"Em\s+consequ[êe]ncia", text[m0.start():], re.IGNORECASE)
    end = m0.start() + m1.start() if m1 else m0.start() + 4000
    table = text[m0.start(): end]

    row_re = re.compile(
        r"^(\d+)\s+((?:SD|CB|1[°º]?\s*SGT|2[°º]?\s*SGT|3[°º]?\s*SGT|"
        r"SUBTEN|SUB\s*TEN|CAP|MAJ|1[°º]?\s*TEN|2[°º]?\s*TEN|TEN\s*CEL|CEL)\s+PM)\s+"
        r"([A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ][A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ\s]+?)\s+(\d{4,5})\s+"
        r"(.+?)\s+(\d{1,2}\/\w{2,3})\s+((?:\d+[°º]\s*TURNO|ÚNICO))\s+(.+)$",
        re.IGNORECASE,
    )
    for line in table.splitlines():
        m = row_re.match(line.strip())
        if not m:
            continue
        lotacao, opm = m.group(5).strip().upper(), m.group(8).strip().upper()
        if not unit_re.search(lotacao) and not unit_re.search(opm):
            continue
        results.append({
            "rank":   m.group(2).strip(),
            "name":   m.group(3).strip(),
            "ci":     m.group(4),
            "reason": f"Falta ao serviço em {m.group(6)} — {m.group(7).strip()} | Lotação: {lotacao} | OPM: {opm}",
            "tag":    "falta",
        })
    return results


def _parse_fatd(text, unit_re):
    """FATD — Formulário de Apuração de Transgressão Disciplinar."""
    results = []
    for ms in re.finditer(r"FATD\s+N[°º\.]", text, re.IGNORECASE):
        block = text[ms.start(): ms.start() + 2000]
        if not unit_re.search(block):
            continue
        mi = re.search(
            r"INTERESSADO[^:]*:\s*([A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ][^\-\n]+?)\s*[-–]\s*[\w°º\s]+?CI[:\s]+(\d{4,5})",
            block, re.IGNORECASE,
        )
        if not mi:
            continue
        ms2 = (re.search(r"1\.1\.\s+([\s\S]{20,1500}?)(?:\n\s*\n|\n\s*1\.2\.|\Z)", block, re.IGNORECASE)
               or re.search(r"SINT[EÉ]SE[^:]*:\s*([\s\S]{20,1500}?)(?:\n\s*\n|\Z)", block, re.IGNORECASE))
        reason = ("FATD — " + re.sub(r"\s+", " ", ms2.group(1)).strip()[:250]
                  if ms2 else "Apuração de transgressão disciplinar (FATD)")
        results.append({"rank": "", "name": mi.group(1).strip(), "ci": mi.group(2),
                         "reason": reason, "tag": "disciplina"})
    return results


def _parse_portarias(text, unit_re):
    """Portarias de transferência / agregação."""
    results = []
    for ms in re.finditer(r"PORTARIA\s+N[°º]", text, re.IGNORECASE):
        block = text[ms.start(): ms.start() + 2000]
        if not unit_re.search(block):
            continue
        ri = block.find("RESOLVE")
        rb = block[ri:] if ri != -1 else block
        action = ("Transferência" if re.search(r"TRANSFERIR", block, re.IGNORECASE)
                  else "Agregação" if re.search(r"AGREGAR", block, re.IGNORECASE)
                  else "Portaria")
        mov = re.search(r"Da?\s+([\w\s\/°ºª]+?)\s+para\s+(?:o|a)?\s+([\w\s\/°ºª\.]+)", rb, re.IGNORECASE)
        move = (f"{action}: de {mov.group(1).strip()} para {mov.group(2).strip()}" if mov else action)
        emp_re = re.compile(
            rf"({RANK_TOKENS})\s+Q[A-Z]+PM\s+"
            r"([A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ][A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ\s]+?)\s+(\d{4,5})",
            re.IGNORECASE,
        )
        for em in emp_re.finditer(rb):
            name = em.group(2).strip()
            if len(name) < 5:
                continue
            results.append({"rank": em.group(1).strip(), "name": name, "ci": em.group(3),
                             "reason": move, "tag": "transf"})
    return results


_COURT_RE  = re.compile(
    r"(?:JU[IÍ]ZO|VARA|COMARCA|TRIBUNAL|AUDITORIA|CORREGEDORIA|DELEGACIA)[^\n]{5,100}",
    re.IGNORECASE,
)
_ADDR_RE   = re.compile(
    r"(?:Av\.|Rua\b|\bR\.\s|Travessa|Tv\.|Alameda|Al\.|Praça|F[oó]rum)[^\n]{10,200}",
    re.IGNORECASE,
)
_HORA_RE   = re.compile(
    r"às\s+(?:(\d{1,2})\s+horas?\s*(?:e\s+(\d{1,2})\s+minutos?)?|(\d{1,2})h(?:[:h]?(\d{2}))?(?:min)?)",
    re.IGNORECASE,
)
_MEET_RE   = re.compile(r"https?://\S+", re.IGNORECASE)


def _parse_judicial(text, unit_re):
    """Intimações judiciais com local, horário, modalidade, link e deduplicação por (ci, data)."""
    results  = []
    lines    = text.split("\n")
    n_lines  = len(lines)

    # Varredura stateful: mantém o juízo e endereço mais recentes
    cur_court   = ""
    cur_address = ""

    # Índices de linhas "Dia …"
    dia_idxs = [i for i, ln in enumerate(lines)
                if re.match(r"^\s*Dia\s+\d+\s+de\s+\w+", ln, re.IGNORECASE)]

    for k, dia_i in enumerate(dia_idxs):
        # Atualiza court/address com as linhas antes deste "Dia" (até o "Dia" anterior)
        prev = dia_idxs[k - 1] + 1 if k > 0 else max(0, dia_i - 15)
        for ln in lines[prev:dia_i]:
            cm = _COURT_RE.search(ln)
            if cm and "@" not in cm.group(0) and "http" not in cm.group(0).lower():
                cur_court = cm.group(0).strip()
            am = _ADDR_RE.search(ln)
            if am and "@" not in am.group(0):
                cur_address = am.group(0).strip()

        # Bloco do "Dia": até o próximo "Dia" (max 40 linhas)
        end_i = dia_idxs[k + 1] if k + 1 < len(dia_idxs) else min(dia_i + 40, n_lines)
        block = "\n".join(lines[dia_i:end_i])

        if not unit_re.search(block):
            continue

        # ── Data ────────────────────────────────────────────────
        date_m   = re.search(r"Dia\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", block, re.IGNORECASE)
        date_str = date_m.group(1).strip() if date_m else ""

        # ── Horário (dois formatos) ──────────────────────────────
        hm = _HORA_RE.search(block)
        if hm:
            if hm.group(1):                        # "X horas e Y minutos"
                mins = hm.group(2) or "00"
                hora_str = f"{hm.group(1)}h" + (mins if mins != "00" else "")
            else:                                   # "09h45" / "13h"
                mins = hm.group(4) or ""
                hora_str = f"{hm.group(3)}h{mins}"
        else:
            hora_str = ""

        # ── Modalidade ───────────────────────────────────────────
        blk_lc = block.lower()
        if "google meet" in blk_lc:
            modalidade = "Videoconferência (Google Meet)"
        elif "videoconferência" in blk_lc or "videoconferencia" in blk_lc:
            modalidade = "Videoconferência"
        elif "presencial" in blk_lc:
            modalidade = "Presencial"
        else:
            modalidade = ""

        # ── Link (Google Meet ou outro link de videoconferência) ─
        link_str = ""
        lm = _MEET_RE.search(block)
        if lm:
            link_str = lm.group(0).rstrip(".,;)")

        # ── Processo ─────────────────────────────────────────────
        proc    = re.search(r"processo\s+n[°º]?\s*([\d\-\.\/]+)", block, re.IGNORECASE)
        proc_str = proc.group(1).strip() if proc else ""

        # ── Reason ───────────────────────────────────────────────
        is_video = modalidade and ("meet" in modalidade.lower() or "videoconferência" in modalidade.lower())
        parts_r = []
        if is_video:
            parts_r.append("Videoconferência")
            if date_str:  parts_r.append(date_str)
            if hora_str:  parts_r.append(hora_str)
            if link_str:  parts_r.append(f"Link: {link_str}")
        else:
            parts_r.append("Presencial")
            if cur_address: parts_r.append(cur_address)
            if date_str:    parts_r.append(date_str)
            if hora_str:    parts_r.append(hora_str)
        reason = " — ".join(parts_r)

        # ── Funcionários ─────────────────────────────────────────
        seen_ci = set()

        for m in EMP_RE.finditer(block):
            name = re.sub(r"\b(?:Q[A-Z]+PM|PM)\b", "", m.group(2), flags=re.IGNORECASE).strip()
            if len(name) < 5 or m.group(3) in seen_ci:
                continue
            seen_ci.add(m.group(3))
            results.append({"rank": m.group(1).strip(), "name": name, "ci": m.group(3),
                             "date": date_str, "hora": hora_str, "modalidade": modalidade,
                             "reason": reason, "tag": "justica"})

        for m in OPM_EMP_RE.finditer(block):
            if not unit_re.search(m.group(2)):
                continue
            if m.group(4) in seen_ci:
                continue
            name = re.sub(r"\s+", " ", m.group(3)).strip()
            if len(name) < 5:
                continue
            seen_ci.add(m.group(4))
            results.append({"rank": m.group(1).strip() + " PM", "name": name, "ci": m.group(4),
                             "date": date_str, "hora": hora_str, "modalidade": modalidade,
                             "reason": reason, "tag": "justica"})
    return results
def _parse_elogio(text, unit_re):
    """Elogios individuais."""
    results = []
    mi = re.search(r"ELOGIO\s+INDIVIDUAL", text, re.IGNORECASE)
    if not mi:
        return results
    block = text[mi.start(): mi.start() + 3000]
    if not unit_re.search(block):
        return results
    excerpt = " ".join(block.split("\n")[:5])[:200]
    for m in EMP_RE.finditer(block):
        name = re.sub(r"\b(?:Q[A-Z]+PM|PM)\b", "", m.group(2), flags=re.IGNORECASE).strip()
        if len(name) < 5:
            continue
        results.append({"rank": m.group(1).strip(), "name": name, "ci": m.group(3),
                         "reason": f"Elogio — {excerpt}", "tag": "elogio"})
    return results


def _parse_servicos(text, unit_re):
    """Serviços diários escalados."""
    results = []
    for line in text.splitlines():
        if not unit_re.search(line):
            continue
        nm = re.search(r"([A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ][a-záêîôúàèìòùãõçé]+(?:\s+[A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ][a-záêîôúàèìòùãõçé]+){1,4})\s*(?:\((\d{4,5})\))?$", line)
        if not nm or len(nm.group(1).split()) < 2:
            continue
        turno = re.search(r"\d+[°º]?\s*Turno|ÚNICO", line, re.IGNORECASE)
        hora  = re.search(r"\d+h\s*às\s*\d+h", line, re.IGNORECASE)
        results.append({
            "rank":   "",
            "name":   nm.group(1).strip(),
            "ci":     nm.group(2) or "—",
            "reason": "Serviço escalado — " + (turno.group() + " " if turno else "") + (hora.group() if hora else ""),
            "tag":    "servico",
        })
    return results


def _parse_lts(text, unit_re):
    """Licenças: nome está SEMPRE na linha ANTERIOR ao row RANK PM OPM ... CI."""
    results = []
    lines = text.split("\n")
    NAME_RE = re.compile(r'^[A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ]{2,}(?:\s+[A-ZÁÊÎÔÚÀÈÌÒÙÃÕÇÉ]{2,}){1,7}\s*$')
    SKIP_RE = re.compile(
        r'^\s*(?:POR:|OBS:|TÉRMINO|RECOMENDAÇÕES:|AL\s|CB\s|SD\s|SGT|TEN|CAP|MAJ|CEL|\d{4,5}\s*$|$)',
        re.IGNORECASE,
    )
    ROW_RE = re.compile(
        rf'^\s*(?:AL\s+(?:OF\s+)?)?({RANK_TOKENS})\s+PM\s+(\d{{1,3}}\.\d)\s+.*?(\d{{4,5}})\s*$',
        re.IGNORECASE,
    )
    LIC_HDR_RE = re.compile(
        r'LICEN[ÇC]A\s+(?:PARA\s+TRATAMENTO\s+DE\s+SA[ÚU]DE\s*(?:PR[ÓO]PRIO|FAMILIAR)?'
        r'|ESPECIAL|PR[EÊ]MIO|PATERNIDADE|MATERNIDADE|GESTANTE)',
        re.IGNORECASE,
    )
    LIC_ABBR_RE = re.compile(r'\b(L\.T\.S\.P\.?|L\.T\.S\.F\.?|T\.L\.E\.?|LTS[PF]?)\b', re.IGNORECASE)

    for i, line in enumerate(lines):
        m = ROW_RE.match(line)
        if not m:
            continue
        if not unit_re.search(m.group(2)):
            continue

        rank = m.group(1).strip() + " PM"
        ci   = m.group(3)

        # Name: scan backward up to 6 lines
        name = None
        for j in range(i - 1, max(i - 6, -1), -1):
            c = lines[j].strip()
            if not c or SKIP_RE.match(c):
                continue
            if NAME_RE.match(c) and len(c.split()) >= 2:
                name = c
                break

        # License type: nearest header above (up to 50 lines)
        lic_type = "Licença para Tratamento de Saúde (LTS)"
        for j in range(i - 1, max(i - 50, -1), -1):
            hm = LIC_HDR_RE.search(lines[j])
            if hm:
                lic_type = hm.group(0).strip().title()
                am = LIC_ABBR_RE.search(lines[j])
                abbr = am.group(0).replace('.', '').upper() if am else ''
                if abbr and abbr.upper() not in lic_type.upper():
                    lic_type += f' ({abbr})'
                break

        # POR: on the row line or within the next 5 lines
        por = ""
        for ln in [line] + lines[i + 1: min(len(lines), i + 5)]:
            mp = re.search(
                r"POR:\s+(\d+\s*\([^)]+\)\s*DIA(?:S|\(S\))?\s+A/C\s+DE\s+[\d./]+)",
                ln, re.IGNORECASE,
            )
            if mp:
                por = mp.group(1).strip()
                break

        # END DATE: within the next 4 lines
        enddate = ""
        for ln in lines[i + 1: min(len(lines), i + 5)]:
            tm = re.search(r"TÉRMINO:\s*([\d./]+)", ln, re.IGNORECASE)
            if tm:
                enddate = tm.group(1).strip()
                break

        parts_r = [lic_type]
        if por:
            parts_r.append(por)
        if enddate:
            parts_r.append(f"End date: {enddate}")

        results.append({
            "rank":   rank,
            "name":   name or f"Militar CI:{ci}",
            "ci":     ci,
            "reason": " — ".join(parts_r),
            "tag":    "geral",
        })
    return results

def _reason(ctx, key):
    lc = ctx.lower()
    if "transferir" in lc or "transferência" in lc:
        m = re.search(r"Da?\s+([\w\s\/°ºª]+?)\s+para\s+(?:o|a)?\s+([\w\s\/°ºª\.]+)", ctx, re.IGNORECASE)
        return f"Transferência: de {m.group(1).strip()} para {m.group(2).strip()}" if m else "Transferência de unidade"
    if "agregar" in lc: return "Agregação por determinação legal"
    if "falta"   in lc: return "Falta ao serviço escalado"
    if "elogio"  in lc or "recompensa" in lc: return "Elogio/Recompensa — " + ctx[:180]
    if "audiência" in lc or "tribunal" in lc or "vara" in lc:
        p = re.search(r"processo\s+n[°º]?\s*([\d\-\.\/]+)", ctx, re.IGNORECASE)
        return "Comparecimento judicial" + (f" — Processo {p.group(1)}" if p else "")
    if "transgressão" in lc or "disciplinar" in lc: return "Apuração de transgressão disciplinar"
    if key == "p1": return "Serviço diário escalado"
    return re.sub(r"\s+", " ", ctx).strip()[:200]


def _tag(ctx, key):
    lc = ctx.lower()
    if "falta"           in lc: return "falta"
    if "transfer"        in lc: return "transf"
    if "agregar"         in lc: return "agregacao"
    if "elogio"          in lc: return "elogio"
    if "audiência"       in lc or "vara" in lc or "tribunal" in lc: return "justica"
    if "transgressão"    in lc or "disciplinar" in lc: return "disciplina"
    if key == "p1":              return "servico"
    if key == "p2":              return "instrucao"
    return "geral"


# ─────────────────────────────────────────────────────────────
def print_results(results: list[dict], unit: str, bg_num: str):
    TAG_LABELS = {
        "falta": "FALTA", "transf": "TRANSFERÊNCIA", "agregacao": "AGREGAÇÃO",
        "elogio": "ELOGIO", "justica": "JUDICIAL", "disciplina": "DISCIPLINA",
        "servico": "SERVIÇO", "instrucao": "INSTRUÇÃO", "geral": "GERAL",
    }
    print(f"\n{'='*70}")
    print(f"  BOLETIM GERAL Nº {bg_num} — UNIDADE: {unit}")
    print(f"{'='*70}")
    total = sum(len(r["employees"]) for r in results)
    print(f"  Total de ocorrências encontradas: {total}\n")

    for sec in results:
        if not sec["employees"]:
            continue
        print(f"\n  ── {sec['label']} ({len(sec['employees'])} funcionário(s)) ──")
        print(f"  {'NOME':<35} {'CI':<8} {'TIPO':<15} {'MOTIVO'}")
        print(f"  {'-'*90}")
        for e in sec["employees"]:
            tag    = TAG_LABELS.get(e["tag"], "GERAL")
            reason = e["reason"][:55] + "..." if len(e["reason"]) > 55 else e["reason"]
            print(f"  {e['name']:<35} {e['ci']:<8} {tag:<15} {reason}")
    print()



TAG_LABELS = {
    "falta":      "FALTA",
    "transf":     "TRANSFERÊNCIA",
    "agregacao":  "AGREGAÇÃO",
    "disciplina": "DISCIPLINA",
    "justica":    "JUDICIAL",
    "elogio":     "ELOGIO",
    "servico":    "SERVIÇO",
    "instrucao":  "INSTRUÇÃO",
    "geral":      "GERAL",
}


def export_word(results, unit, bg_num, bg_date, out_path):
    """Gera arquivo .doc (HTML-Word) com os resultados."""
    rows = []
    for sec in results:
        for e in sec["employees"]:
            tag    = TAG_LABELS.get(e["tag"], e["tag"].upper())
            reason = e["reason"] or "—"
            rows.append(
                f"<tr>"
                f"<td><b>{e['name']}</b><br><small style='color:#555'>{e['rank']}</small></td>"
                f"<td>{e['ci']}</td>"
                f"<td>{tag}</td>"
                f"<td>{reason}</td>"
                f"</tr>"
            )
    body  = "\n".join(rows)
    total = sum(len(s["employees"]) for s in results)
    html  = (
        "<html xmlns:o=\'urn:schemas-microsoft-com:office:office\'"
        " xmlns:w=\'urn:schemas-microsoft-com:office:word\'"
        " xmlns=\'http://www.w3.org/TR/REC-html40\'>\n"
        "<head><meta charset=\'utf-8\'>"
        f"<title>BG {bg_num} - {unit}</title>\n"
        "<style>\n"
        "body{font-family:Arial,sans-serif;font-size:10pt}\n"
        "h2{font-size:13pt;margin-bottom:4px}\n"
        "p{font-size:9pt;color:#555;margin-bottom:12px}\n"
        "table{border-collapse:collapse;width:100%}\n"
        "th{background:#1a4a80;color:#fff;padding:6px 10px;text-align:left;font-size:9pt}\n"
        "td{padding:6px 10px;border-bottom:1px solid #ddd;font-size:9pt;vertical-align:top}\n"
        "tr:nth-child(even) td{background:#f5f8ff}\n"
        "</style></head>\n<body>\n"
        f"<h2>Boletim Geral N&ordm; {bg_num} &mdash; Unidade: {unit}</h2>\n"
        f"<p>Data: {bg_date} &nbsp;|&nbsp; Total de ocorr&ecirc;ncias: {total}</p>\n"
        "<table><thead><tr>"
        "<th>Nome / Posto</th><th>CI</th><th>Tipo</th><th>Motivo</th>"
        f"</tr></thead><tbody>{body}</tbody></table>\n"
        "</body></html>"
    )
    out_path.write_text(html, encoding="utf-8-sig")
    print(f"\n  Arquivo exportado: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extrai funcionários de um Boletim Geral por unidade."
    )
    parser.add_argument("pdf",  help="Caminho para o arquivo PDF do BG")
    parser.add_argument("unit", help='Unidade (ex: "11ª CICOM", "53.0", "CPA LESTE")')
    parser.add_argument("--word",       action="store_true", help="Exportar resultado em .doc")
    parser.add_argument("--list-units", action="store_true",
                        help="Listar todas as unidades detectadas no BG")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Erro: arquivo não encontrado — {pdf_path}")
        import sys; sys.exit(1)

    print(f"\nExtraindo texto de: {pdf_path.name} ...")
    text  = extract_text(pdf_path)
    parts = split_parts(text)

    if args.list_units:
        units = extract_all_units(text)
        print(f"\nUnidades detectadas ({len(units)}):")
        for u in units:
            print(f"  • {u}")
        return

    _m = re.search(r"BG[_\s]*(\d+)", pdf_path.name, re.IGNORECASE)
    if not _m:
        _m = re.search(r"BOLETIM GERAL(?:\s+OSTENSIVO)?\s+N[°º]\s*(\d+)", text, re.IGNORECASE)
    bg_num = _m.group(1) if _m else "?"

    _d = re.search(r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", text, re.IGNORECASE)
    bg_date = _d.group(1) if _d else "?"

    results = [
        {"key": p["key"], "label": p["label"], "employees": extract_employees(p, args.unit)}
        for p in parts
    ]

    print_results(results, args.unit, bg_num)

    if args.word:
        safe_unit = re.sub(r'[\s/\\:*?"<>|]', "_", args.unit)
        out_path  = pdf_path.parent / f"BG_{bg_num}_{safe_unit}.doc"
        export_word(results, args.unit, bg_num, bg_date, out_path)


if __name__ == "__main__":
    main()
