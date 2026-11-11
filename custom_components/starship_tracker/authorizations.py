"""Récapitulatif des autorisations avant décollage (parsers purs, sans réseau).

Sources publiques, toutes « best effort » :
- FAA TFR (NOTAM « SPACE OPERATIONS » à Starbase) : https://tfr.faa.gov/tfrapi/getTfrList
- Licence FAA : non publiée sous forme lisible par machine -> état « à vérifier » + lien
- Avis aux navigateurs NGA (NAVAREA IV, golfe du Mexique) : https://msi.nga.mil/api/...
- Fermetures Highway 4 / plage de Boca Chica : https://www.cameroncountytx.gov/spacex/
"""
from __future__ import annotations

import html as _html
import re
from datetime import date, datetime, timezone
from typing import Any

FAA_TFR_LIST_URL = "https://tfr.faa.gov/tfrapi/getTfrList"
FAA_TFR_TEXT_URL = "https://tfr.faa.gov/tfrapi/getWebText?notamId={notam_id}"
FAA_TFR_DETAIL_URL = "https://tfr.faa.gov/tfr3/?page=detail_{slug}"
FAA_TFR_HOME_URL = "https://tfr.faa.gov/tfr3/"
FAA_STARSHIP_URL = "https://www.faa.gov/space/stakeholder_engagement/spacex_starship"
NGA_WARNINGS_URL = "https://msi.nga.mil/api/publications/broadcast-warn?navArea=4&status=active&output=json"
NGA_HOME_URL = "https://msi.nga.mil/NavWarnings"
CAMERON_URL = "https://www.cameroncountytx.gov/spacex/"

OK = "ok"
PENDING = "pending"
UNKNOWN = "unknown"

LABELS = {
    "faa_license": "FAA launch license",
    "notam": "FAA NOTAM / TFR",
    "navigation": "Navigational warnings",
    "road_closure": "Highway 4 / beach closure",
}

_SITES = ("STARBASE", "BOCA CHICA")
_SHORT_DATE = re.compile(r"\b([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})\b")
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_NAVAREAS = {"4": "NAVAREA IV", "12": "NAVAREA XII", "A": "HYDROLANT", "P": "HYDROPAC", "C": "HYDROARC"}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def _date(text: str) -> date | None:
    """Première date « November 13, 2026 » / « Nov 13, 2026 » d'un texte."""
    match = _SHORT_DATE.search(text or "")
    if not match:
        return None
    month = _MONTHS.get(match.group(1).lower()[:3])
    try:
        return date(int(match.group(3)), month, int(match.group(2))) if month else None
    except ValueError:
        return None


def tfr_url(notam_id: str) -> str:
    """6/7129 -> https://tfr.faa.gov/tfr3/?page=detail_6_7129."""
    return FAA_TFR_DETAIL_URL.format(slug=str(notam_id).replace("/", "_"))


def parse_tfr_list(data: Any) -> list[dict[str, Any]]:
    """NOTAM « SPACE OPERATIONS » de Starbase / Boca Chica, triés par date, dédoublonnés."""
    found: dict[str, dict[str, Any]] = {}
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "").upper()
        desc = str(item.get("description") or "")
        notam_id = str(item.get("notam_id") or "").strip()
        if "SPACE OPERATIONS" not in kind or not notam_id or not any(s in desc.upper() for s in _SITES):
            continue
        day = _date(desc)
        found.setdefault(notam_id, {
            "notam_id": notam_id,
            "facility": item.get("facility"),
            "description": desc[:200],
            "date": day.isoformat() if day else None,
            "modified": item.get("mod_date"),
            "revision": str(item.get("mod_abs_time") or item.get("mod_date") or ""),
            "url": tfr_url(notam_id),
        })
    return sorted(found.values(), key=lambda n: (n["date"] or "9999", n["notam_id"]))


_TFR_TIME = re.compile(
    r"(Beginning|Ending) Date and Time\s*:\s*([A-Z][a-z]+ \d{1,2}, \d{4}) at (\d{2})(\d{2}) UTC")


def parse_tfr_webtext(data: Any) -> dict[str, str]:
    """Début / fin UTC d'un NOTAM depuis getWebText (HTML dans du JSON)."""
    raw = ""
    if isinstance(data, list) and data and isinstance(data[0], dict):
        raw = str(data[0].get("text") or "")
    elif isinstance(data, dict):
        raw = str(data.get("text") or "")
    out: dict[str, str] = {}
    for kind, day, hour, minute in _TFR_TIME.findall(_text(raw)):
        try:
            when = datetime.strptime(f"{day} {hour}{minute}", "%B %d, %Y %H%M").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        out["start" if kind == "Beginning" else "end"] = when.isoformat()
    return out


def parse_nga_warnings(data: Any) -> list[dict[str, Any]]:
    """Avis aux navigateurs « ROCKET LAUNCHING » au large du Texas / de Boca Chica."""
    if isinstance(data, dict):
        data = data.get("broadcast-warn", data.get("results"))
    found: list[dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").upper()
        if str(item.get("status") or "A").upper() != "A":
            continue
        if not any(k in text for k in ("ROCKET LAUNCH", "SPACE DEBRIS", "SPACE OPERATIONS")):
            continue
        if not any(k in text for k in ("BOCA CHICA", "STARBASE", "TEXAS")):
            continue
        area = _NAVAREAS.get(str(item.get("navArea") or ""), str(item.get("navArea") or ""))
        try:
            ref = f"{area} {int(item['msgNumber'])}/{int(item['msgYear']) % 100:02d}".strip()
        except (KeyError, TypeError, ValueError):
            ref = area or "?"
        found.append({"id": ref, "issued": item.get("issueDate"), "text": re.sub(r"\s+", " ", text)[:300]})
    return found


def parse_cameron_closures(page: str, today: date) -> list[dict[str, Any]]:
    """Lignes du tableau « Temp. Closure Date » de Cameron County, à partir d'aujourd'hui."""
    rows: list[dict[str, Any]] = []
    for table in re.findall(r"<table.*?</table>", page or "", flags=re.S | re.I):
        if "closure date" not in _text(table).lower():
            continue
        for tr in re.findall(r"<tr.*?</tr>", table, flags=re.S | re.I):
            cells = [_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)]
            if len(cells) < 3 or not (day := _date(cells[1])) or day < today:
                continue
            status = cells[3] if len(cells) > 3 else ""
            rows.append({
                "kind": cells[0][:40],
                "date": day.isoformat(),
                "time": cells[2][:60],
                "status": status[:120],
                "scheduled": bool(re.search(r"(?i)scheduled|will be closed", status))
                and not re.search(r"(?i)cancel", status),
            })
    return sorted(rows, key=lambda r: str(r["date"]))


def _item(key: str, status: str, detail: str, url: str, updated: str | None, **extra: Any) -> dict[str, Any]:
    return {"key": key, "label": LABELS[key], "status": status, "detail": detail, "url": url,
            "updated": updated, **extra}


def build_items(
    *,
    notams: list[dict[str, Any]] | None,
    notams_updated: str | None,
    closures: list[dict[str, Any]] | None,
    closures_updated: str | None,
    navigation: list[dict[str, Any]] | None,
    navigation_updated: str | None,
    faa_page_updated: str | None = None,
) -> list[dict[str, Any]]:
    """Liste ordonnée des autorisations. None = source jamais lue (élément « inconnu »)."""
    license_detail = "Not published in machine-readable form, check the FAA page"
    if faa_page_updated:
        license_detail += f" (updated {faa_page_updated})"
    items = [_item("faa_license", UNKNOWN, license_detail, FAA_STARSHIP_URL, None, page_updated=faa_page_updated)]

    if notams is None:
        items.append(_item("notam", UNKNOWN, "Source unavailable", FAA_TFR_HOME_URL, notams_updated))
    elif notams:
        first = notams[0]
        when = first.get("start") or first.get("date") or ""
        extra = f" (+{len(notams) - 1})" if len(notams) > 1 else ""
        items.append(_item("notam", OK, f"NOTAM {first['notam_id']}{extra} · {when}".strip(" ·"),
                           first["url"], notams_updated, notams=notams[:8]))
    else:
        items.append(_item("notam", PENDING, "No Starbase space operations NOTAM yet", FAA_TFR_HOME_URL,
                           notams_updated, notams=[]))

    if navigation is not None:  # source NGA : omise tant qu'elle n'a jamais répondu
        if navigation:
            extra = f" (+{len(navigation) - 1})" if len(navigation) > 1 else ""
            items.append(_item("navigation", OK, f"{navigation[0]['id']}{extra}", NGA_HOME_URL,
                               navigation_updated, warnings=navigation[:5]))
        else:
            items.append(_item("navigation", PENDING, "No rocket launching warning off Texas", NGA_HOME_URL,
                               navigation_updated, warnings=[]))

    if closures is None:
        items.append(_item("road_closure", UNKNOWN, "Source unavailable", CAMERON_URL, closures_updated))
    else:
        scheduled = [c for c in closures if c.get("scheduled")]
        if scheduled:
            first = scheduled[0]
            items.append(_item("road_closure", OK, f"{first['date']} {first['time']}".strip(), CAMERON_URL,
                               closures_updated, closures=closures[:6]))
        elif closures:
            first = closures[0]
            items.append(_item("road_closure", PENDING, f"Possible {first['date']} {first['time']}".strip(),
                               CAMERON_URL, closures_updated, closures=closures[:6]))
        else:
            items.append(_item("road_closure", PENDING, "No closure announced", CAMERON_URL,
                               closures_updated, closures=[]))
    return items


def overall(items: list[dict[str, Any]]) -> str:
    """ready = tout est confirmé ; partial = au moins un élément ; pending = rien encore."""
    ok = sum(1 for i in items if i["status"] == OK)
    if items and ok == len(items):
        return "ready"
    return "partial" if ok else "pending"


_FAA_UPDATED = re.compile(r"Last updated:\s*(?:[A-Z][a-z]+,\s*)?([A-Z][a-z]+ \d{1,2}, \d{4})")


def parse_faa_page_updated(page: str) -> str | None:
    """« Last updated: Tuesday, November 10, 2026 » -> 2026-11-10."""
    match = _FAA_UPDATED.search(_text(page))
    day = _date(match.group(1)) if match else None
    return day.isoformat() if day else None
