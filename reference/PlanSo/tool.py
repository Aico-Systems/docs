#!/usr/bin/env python3
"""
PlanSo power tool (login, sync, query) with robust parsing.

Key ideas
- PlanSo endpoints often return JSON wrappers that contain HTML + JS (for the web UI).
- We "sync" by fetching a list of orders + detail forms, parsing the important fields,
  and storing a normalized snapshot in a local SQLite DB for fast querying.
- Cookie jar is persisted to disk (Netscape format) so you can run unattended.

Safety / privacy
- Only persists: cookie jar (if you pass --cookie-jar) and SQLite DB (if you pass --db).
- Does NOT write anything else unless you pass --raw-dir.

Python deps
  pip install -U requests rich
Optional (improves HTML parsing robustness):
  pip install -U beautifulsoup4 lxml
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import html as _html
import json
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

# ---------- Optional HTML parser (BeautifulSoup) ----------
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

# ---------- Pretty output ----------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except Exception as e:  # pragma: no cover
    print("Missing dependency 'rich'. Install with: pip install -U rich", file=sys.stderr)
    raise

console = Console()


# ======================================================================
# Utilities
# ======================================================================


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_env_file(path: str) -> Dict[str, str]:
    """
    Minimal .env reader (no external deps). Supports lines like:
      KEY=value
      KEY="value"
      KEY='value'
    """
    env: Dict[str, str] = {}
    if not path or not os.path.exists(path):
        return env
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip(";")
        if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
            v = v[1:-1]
        env[k] = v
    return env


def _extract_set_cookie_expiries(set_cookie_headers: Iterable[str]) -> List[Tuple[str, Optional[str], Optional[int]]]:
    """
    Best-effort parsing of Set-Cookie expiry information.
    Returns list of (cookie_name, expires_str, max_age_seconds).
    """
    out: List[Tuple[str, Optional[str], Optional[int]]] = []
    for sc in set_cookie_headers:
        parts = [p.strip() for p in sc.split(";")]
        if not parts:
            continue
        name_val = parts[0]
        if "=" not in name_val:
            continue
        name = name_val.split("=", 1)[0]
        expires = None
        max_age = None
        for p in parts[1:]:
            if p.lower().startswith("expires="):
                expires = p.split("=", 1)[1].strip()
            elif p.lower().startswith("max-age="):
                try:
                    max_age = int(p.split("=", 1)[1].strip())
                except Exception:
                    max_age = None
        out.append((name, expires, max_age))
    return out


def _looks_like_html(s: str) -> bool:
    s2 = s.lstrip()
    return s2.startswith("<!DOCTYPE") or s2.startswith("<html") or s2.startswith("<div") or s2.startswith("<")


def _safe_json_loads(s: str) -> Optional[Any]:
    try:
        return json.loads(s)
    except Exception:
        return None


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _parse_german_date_or_datetime(s: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (iso_date, iso_datetime) where one (or both) may be None.
    Accepts:
      - 16.12.2025
      - 16.12.2025 12:08:59
      - 17.12.2025 13:03:17
      - 2025-12-18
    """
    if not s:
        return None, None
    s = s.strip()
    # ISO date
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s, None
    # DE date
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return _dt.date(y, mo, d).isoformat(), None
        except Exception:
            return None, None
    # DE datetime
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})", s)
    if m:
        d, mo, y, hh, mm, ss = map(int, m.groups())
        try:
            dt = _dt.datetime(y, mo, d, hh, mm, ss)
            return dt.date().isoformat(), dt.isoformat(timespec="seconds")
        except Exception:
            return None, None
    return None, None


def _to_float_de(s: str) -> Optional[float]:
    """
    Convert German decimal strings like '11,30' to float(11.30).
    Returns None if conversion fails.
    """
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")  # crude but works for "1.234,56"
    try:
        return float(t)
    except Exception:
        return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


# ======================================================================
# Network layer
# ======================================================================


@dataclass
class ClientCfg:
    base_url: str
    cookie_jar_path: str
    env_path: str
    user: Optional[str]
    password: Optional[str]
    timeout: int = 30


def _mk_session(cfg: ClientCfg) -> requests.Session:
    s = requests.Session()
    # Browser-ish headers help; some endpoints require X-Requested-With
    s.headers.update(
        {
            "User-Agent": "PlanSoTool/1.0 (requests)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    # Load cookie jar if present
    cj = MozillaCookieJar(cfg.cookie_jar_path)
    if cfg.cookie_jar_path and os.path.exists(cfg.cookie_jar_path):
        try:
            cj.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
    s.cookies = cj  # type: ignore
    return s


_thread_local = threading.local()


def _get_thread_session(cfg: ClientCfg) -> requests.Session:
    sess = getattr(_thread_local, "sess", None)
    if sess is None:
        sess = _mk_session(cfg)
        _thread_local.sess = sess
    return sess


def _save_cookies(sess: requests.Session, path: str) -> None:
    if not path:
        return
    cj = sess.cookies
    if isinstance(cj, MozillaCookieJar):
        cj.save(path, ignore_discard=True, ignore_expires=True)
    else:
        # Convert
        out = MozillaCookieJar(path)
        for c in cj:
            out.set_cookie(c)
        out.save(path, ignore_discard=True, ignore_expires=True)


def _url(cfg: ClientCfg, path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return cfg.base_url.rstrip("/") + "/" + path_or_url.lstrip("/")


def _req(
    sess: requests.Session,
    cfg: ClientCfg,
    method: str,
    path_or_url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    allow_redirects: bool = True,
) -> requests.Response:
    url = _url(cfg, path_or_url)
    resp = sess.request(
        method.upper(),
        url,
        params=params,
        data=data,
        headers=headers,
        timeout=cfg.timeout,
        allow_redirects=allow_redirects,
    )
    return resp


def login(cfg: ClientCfg) -> int:
    env = _load_env_file(cfg.env_path)
    user = cfg.user or env.get("PLANSO_USER") or env.get("USER")
    pw = cfg.password or env.get("PLANSO_PASS") or env.get("PASSWORD")

    if not user or not pw:
        console.print("[red]Missing credentials.[/red] Provide --user/--password or PLANSO_USER/PLANSO_PASS in .env")
        return 2

    sess = _mk_session(cfg)

    # 1) GET /app to establish a session cookie
    r0 = _req(sess, cfg, "GET", "/app", headers={"Accept": "text/html"})
    set_cookie = r0.headers.get("set-cookie")
    if set_cookie:
        exp = _extract_set_cookie_expiries([h.strip() for h in set_cookie.split(", PHPSESSID=") if h])
        # The split above is imperfect; best-effort only.
    # 2) POST login form
    payload = {
        "system_login_username": user,
        "system_login_password": pw,
        "user_lat": "",
        "user_lng": "",
        "user_accuracy": "",
    }
    r1 = _req(
        sess,
        cfg,
        "POST",
        "/app",
        data=payload,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": cfg.base_url,
            "Referer": _url(cfg, "/app"),
            "Upgrade-Insecure-Requests": "1",
        },
        allow_redirects=True,
    )

    # Determine if login "worked" (PlanSo often returns 200 with app HTML)
    body = (r1.text or "")[:2000].lower()
    ok = ("system_login_username" not in body) and ("passwort" not in body)
    if not ok:
        console.print("[red]Login may have failed.[/red] Response still looks like the login form.")
        return 3

    _save_cookies(sess, cfg.cookie_jar_path)
    console.print(f"[green]OK[/green] logged in. Cookies saved to {cfg.cookie_jar_path}")
    # Print expiries if present
    if "set-cookie" in r1.headers:
        expiries = _extract_set_cookie_expiries(
            r1.headers.get_all("set-cookie") if hasattr(r1.headers, "get_all") else [r1.headers["set-cookie"]]
        )
        if expiries:
            t = Table(title="Set-Cookie expiries (best-effort)")
            t.add_column("Cookie")
            t.add_column("Expires")
            t.add_column("Max-Age (s)")
            for name, expires, max_age in expiries:
                t.add_row(name, str(expires or ""), str(max_age or ""))
            console.print(t)
    return 0


# ======================================================================
# Parsing PlanSo responses
# ======================================================================


def parse_projects_payload(payload: Any) -> List[Dict[str, Any]]:
    """
    /do?m=resourceplanner_get_project_stations returns a dict like:
      { "0": {...}, "1": {...}, ..., "execution_time": 0.34 }
    We must ignore non-dict values (e.g. floats).
    """
    projects: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            if isinstance(v, dict) and ("ID" in v or "short_name" in v):
                projects.append(v)
    elif isinstance(payload, list):
        for v in payload:
            if isinstance(v, dict) and ("ID" in v or "short_name" in v):
                projects.append(v)
    return projects


def parse_station(s: str) -> Tuple[Optional[int], Optional[str]]:
    """
    station looks like "2@active" or "4@finished" or "6@active".
    Returns (station_id, station_state).
    """
    if not s:
        return None, None
    m = re.fullmatch(r"(\d+)\@([a-zA-Z_]+)", str(s).strip())
    if not m:
        return None, None
    return int(m.group(1)), m.group(2).lower()


def parse_visual_forms_plain_fields(center_content_html: str) -> Dict[str, str]:
    """
    Parse the HTML form from visual_forms_plain and return label -> value.
    Uses BeautifulSoup if available; otherwise falls back to regex heuristics.
    """
    html = center_content_html or ""
    html = _html.unescape(html)

    if BeautifulSoup is None:
        # Fallback: extremely conservative regex extraction
        # Extract blocks that look like: <label ...>X</label> ... value="Y"
        out: Dict[str, str] = {}
        for m in re.finditer(
            r"<label[^>]*>(.*?)</label>.*?(?:value=\"(.*?)\"|<textarea[^>]*>(.*?)</textarea>)",
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            label = _normalize_whitespace(re.sub(r"<[^>]+>", "", m.group(1) or ""))
            val = m.group(2) if m.group(2) is not None else (m.group(3) or "")
            val = _normalize_whitespace(re.sub(r"<[^>]+>", "", val))
            if label and label not in out:
                out[label] = val
        return out

    soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")

    out: Dict[str, str] = {}

    # Fields are typically inside .field blocks.
    field_divs = soup.select(".field") or soup.find_all("div", class_=re.compile(r"\bfield\b"))
    for field in field_divs:
        lab = field.find("label")
        if not lab:
            continue
        label = _normalize_whitespace(lab.get_text(" ", strip=True))
        if not label:
            continue

        # Find first input/select/textarea after label within this field container
        val: str = ""

        # Prefer selected option text
        sel = field.find("select")
        if sel:
            opt = sel.find("option", selected=True) or sel.find("option")
            if opt:
                val = _normalize_whitespace(opt.get_text(" ", strip=True) or opt.get("value", "") or "")
        else:
            inp = field.find("input")
            if inp:
                t = (inp.get("type") or "").lower()
                if t in ("checkbox", "radio"):
                    val = "True" if inp.has_attr("checked") else "False"
                else:
                    val = inp.get("value") or ""
            else:
                ta = field.find("textarea")
                if ta:
                    val = ta.get_text(" ", strip=True) or ""

        out[label] = _normalize_whitespace(val)

    return out


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "")


def _extract_data_attrs_from_tag(tag_or_html: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if BeautifulSoup is not None and hasattr(tag_or_html, "attrs"):
        for k, v in tag_or_html.attrs.items():
            if not k.startswith("data-"):
                continue
            if isinstance(v, list):
                v = " ".join([str(x) for x in v])
            out[k] = _normalize_whitespace(str(v))
        return out
    if isinstance(tag_or_html, str):
        for m in re.finditer(r'(data-[a-zA-Z0-9_-]+)="([^"]*)"', tag_or_html):
            out[m.group(1)] = _normalize_whitespace(m.group(2))
    return out


def _parse_html_label_value_pairs(html: str) -> Dict[str, str]:
    html = _html.unescape(html or "")
    out: Dict[str, str] = {}

    if BeautifulSoup is None:
        for m in re.finditer(
            r"<label[^>]*>(?P<label>.*?)</label>(?P<after>.{0,600})",
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            label = _normalize_whitespace(_strip_tags(m.group("label") or ""))
            if not label or label in out:
                continue
            after = m.group("after") or ""
            val = ""
            mi = re.search(r'<input[^>]*value="([^"]*)"', after, re.IGNORECASE)
            if mi:
                val = mi.group(1)
            ms = re.search(r"<select[^>]*>.*?<option[^>]*selected[^>]*>(.*?)</option>", after, re.IGNORECASE | re.DOTALL)
            if not val and ms:
                val = _strip_tags(ms.group(1) or "")
            mt = re.search(r"<textarea[^>]*>(.*?)</textarea>", after, re.IGNORECASE | re.DOTALL)
            if not val and mt:
                val = _strip_tags(mt.group(1) or "")
            val = _normalize_whitespace(val)
            if val:
                out[label] = val
        return out

    soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")

    def value_from_control(ctrl: Any) -> str:
        if ctrl.name == "select":
            opt = ctrl.find("option", selected=True) or ctrl.find("option")
            if opt:
                return _normalize_whitespace(opt.get_text(" ", strip=True) or opt.get("value", "") or "")
        elif ctrl.name == "textarea":
            return _normalize_whitespace(ctrl.get_text(" ", strip=True) or "")
        elif ctrl.name == "input":
            t = (ctrl.get("type") or "").lower()
            if t in ("checkbox", "radio"):
                return "True" if ctrl.has_attr("checked") else "False"
            return _normalize_whitespace(ctrl.get("value") or "")
        return ""

    for lab in soup.find_all("label"):
        label = _normalize_whitespace(lab.get_text(" ", strip=True))
        if not label or label in out:
            continue

        ctrl = None
        lab_for = lab.get("for")
        if lab_for:
            ctrl = soup.find(id=lab_for)
        if ctrl is None:
            ctrl = lab.find(["input", "select", "textarea"])
        if ctrl is None and lab.parent is not None:
            ctrl = lab.parent.find(["input", "select", "textarea"])
        if ctrl is None:
            ctrl = lab.find_next(["input", "select", "textarea"])

        if ctrl is None:
            continue
        val = value_from_control(ctrl)
        if val:
            out[label] = val
    return out


def _parse_html_tables(html: str) -> List[Dict[str, Any]]:
    html = _html.unescape(html or "")
    tables: List[Dict[str, Any]] = []

    if BeautifulSoup is None:
        for table_html in re.findall(r"<table[^>]*>.*?</table>", html, re.IGNORECASE | re.DOTALL):
            headers = [
                _normalize_whitespace(_strip_tags(h))
                for h in re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.IGNORECASE | re.DOTALL)
            ]
            rows = []
            for row_html in re.findall(r"<tr[^>]*>.*?</tr>", table_html, re.IGNORECASE | re.DOTALL):
                tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.IGNORECASE | re.DOTALL)
                if not tds:
                    continue
                vals = [_normalize_whitespace(_strip_tags(td)) for td in tds]
                if headers and len(headers) == len(vals):
                    row = {headers[i] or f"col_{i}": vals[i] for i in range(len(vals))}
                else:
                    row = {f"col_{i}": vals[i] for i in range(len(vals))}
                row_attrs = _extract_data_attrs_from_tag(row_html)
                if row_attrs:
                    row["_attrs"] = row_attrs
                rows.append(row)
            if rows:
                tables.append(
                    {
                        "headers": headers,
                        "rows": rows,
                        "table_attrs": _extract_data_attrs_from_tag(table_html),
                    }
                )
        return tables

    soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")
    for table in soup.find_all("table"):
        headers = [_normalize_whitespace(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            vals = [_normalize_whitespace(td.get_text(" ", strip=True)) for td in tds]
            if headers and len(headers) == len(vals):
                row = {headers[i] or f"col_{i}": vals[i] for i in range(len(vals))}
            else:
                row = {f"col_{i}": vals[i] for i in range(len(vals))}
            row_attrs = _extract_data_attrs_from_tag(tr)
            if row_attrs:
                row["_attrs"] = row_attrs
            rows.append(row)
        if rows:
            tables.append(
                {
                    "headers": headers,
                    "rows": rows,
                    "table_attrs": _extract_data_attrs_from_tag(table),
                }
            )
    return tables


def _parse_html_links_images(html: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    html = _html.unescape(html or "")
    links: List[Dict[str, str]] = []
    images: List[Dict[str, str]] = []

    if BeautifulSoup is None:
        for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            links.append({"href": href, "text": _normalize_whitespace(_strip_tags(label))})
        for src, alt in re.findall(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"', html, re.IGNORECASE):
            images.append({"src": src, "alt": alt})
        if not images:
            for src in re.findall(r'<img[^>]+src="([^"]+)"', html, re.IGNORECASE):
                images.append({"src": src, "alt": ""})
        return links, images

    soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")
    for a in soup.find_all("a", href=True):
        links.append({"href": a.get("href", ""), "text": _normalize_whitespace(a.get_text(" ", strip=True))})
    for img in soup.find_all("img", src=True):
        images.append({"src": img.get("src", ""), "alt": _normalize_whitespace(img.get("alt") or "")})
    return links, images


def _parse_html_snapshot(html: str) -> Dict[str, Any]:
    html = _html.unescape(html or "")
    try:
        fields = _parse_html_label_value_pairs(html)
        tables = _parse_html_tables(html)
        links, images = _parse_html_links_images(html)
        background_images = re.findall(r"background-image:url\\([\"']?([^\\)\"']+)", html, re.IGNORECASE)
    except re.error as e:
        return {"parse_error": f"regex error: {e}"}
    data_attrs: List[Dict[str, Any]] = []

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")
        for tag in soup.find_all(attrs=lambda attrs: any(k.startswith("data-") for k in attrs)):
            attrs = _extract_data_attrs_from_tag(tag)
            if not attrs:
                continue
            entry = {"tag": tag.name, "attrs": attrs}
            if tag.get("id"):
                entry["id"] = tag.get("id")
            if tag.get("class"):
                entry["class"] = " ".join(tag.get("class", []))
            data_attrs.append(entry)
            if len(data_attrs) >= 200:
                break

    out: Dict[str, Any] = {}
    if fields:
        out["fields"] = fields
    if tables:
        out["tables"] = tables
    if links:
        out["links"] = links
    if images:
        out["images"] = images
    if background_images:
        out["background_images"] = background_images
    if data_attrs:
        out["data_attrs"] = data_attrs
    return out


def extract_employee_map_from_html(html: str) -> Dict[str, str]:
    """
    From shop_view_single content (or similar), employee options appear like:
      <input class="rspSv_todo_list_employee_option" ... value="166" ... /><small> phika</small>
    Returns { "166": "phika", ... }
    """
    html = _html.unescape(html or "")
    out: Dict[str, str] = {}
    # robust-ish regex: value="123" ... <small>NAME</small>
    for m in re.finditer(
        r'rspSv_todo_list_employee_option[^>]*\bvalue="(?P<id>\d+)"[^>]*>.*?</label>\s*</div>\s*</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        chunk = m.group(0)
        id_ = m.group("id")
        sm = re.search(r"<small>\s*(.*?)\s*</small>", chunk, re.IGNORECASE | re.DOTALL)
        if not sm:
            continue
        name = _normalize_whitespace(re.sub(r"<[^>]+>", "", sm.group(1)))
        if id_ and name:
            out[id_] = name
    # Simpler regex fallback
    if not out:
        for m in re.finditer(
            r'rspSv_todo_list_employee_option[^>]*\bvalue="(\d+)"[^>]*>.*?<small>\s*(.*?)\s*</small>',
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            id_ = m.group(1)
            name = _normalize_whitespace(re.sub(r"<[^>]+>", "", m.group(2)))
            if id_ and name:
                out[id_] = name
    return out


def extract_candidate_endpoints_from_js(js: str) -> List[str]:
    """
    Scan JS blobs for "/do?m=..." endpoints.
    """
    js = js or ""
    eps = set(re.findall(r"['\"](/do\?m=[^'\"\\]+)", js))
    return sorted(eps)


def parse_json_wrapper(resp_text: str) -> Optional[Dict[str, Any]]:
    j = _safe_json_loads(resp_text)
    if isinstance(j, dict):
        return j
    return None


def _build_section_payload(text: str, content_type: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"content_type": content_type, "raw_text": text}
    data_json: Dict[str, Any] = {}

    j = None
    if "application/json" in (content_type or "").lower() or text.strip().startswith(("{", "[")):
        j = _safe_json_loads(text)

    if isinstance(j, dict):
        html = j.get("html")
        if isinstance(html, str):
            data_json["parsed"] = _parse_html_snapshot(html)
            meta = {k: v for k, v in j.items() if k != "html"}
            if meta:
                data_json["meta"] = meta
        elif isinstance(html, dict):
            sections: Dict[str, Any] = {}
            for k, v in html.items():
                if isinstance(v, dict):
                    content = v.get("content") or ""
                    sections[k] = {
                        "meta": {kk: vv for kk, vv in v.items() if kk != "content"},
                        "parsed": _parse_html_snapshot(content),
                    }
                else:
                    sections[k] = v
            data_json["sections"] = sections
            meta = {k: v for k, v in j.items() if k != "html"}
            if meta:
                data_json["meta"] = meta
        else:
            data_json["json"] = j
    elif isinstance(j, list):
        data_json["json"] = j
    elif _looks_like_html(text):
        data_json["parsed"] = _parse_html_snapshot(text)
    else:
        data_json["text"] = text

    payload["data_json"] = data_json
    return payload


# ======================================================================
# Database
# ======================================================================

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS orders (
  id              INTEGER PRIMARY KEY,
  short_name      TEXT,
  plate           TEXT,
  person          TEXT,
  phone           TEXT,
  email           TEXT,

  damage          TEXT,
  project_status  TEXT,
  station_id      INTEGER,
  station_state   TEXT,

  shop_date       TEXT,
  repair_date     TEXT,
  finish_date     TEXT,
  planned_delivery_date TEXT,

  parts_status    TEXT,
  missing_parts   INTEGER DEFAULT 0,

  est_hours_karo  REAL,
  est_hours_lack  REAL,
  est_hours_mech  REAL,

  fields_json     TEXT, -- visual_forms_plain label->value
  vehicle_json    TEXT, -- if discovered elsewhere
  last_synced_at  TEXT
);

CREATE TABLE IF NOT EXISTS employees (
  id TEXT PRIMARY KEY,
  name TEXT
);

CREATE TABLE IF NOT EXISTS parts (
  order_id INTEGER,
  part_no TEXT,
  description TEXT,
  lead_no TEXT,
  order_no TEXT,
  row_id TEXT,
  part_id TEXT,
  qty REAL,
  price_each REAL,
  price_total REAL,
  status TEXT,
  status_code TEXT,
  status_icon TEXT,
  order_date TEXT,
  delivery_date TEXT,
  eta_date TEXT,
  is_missing INTEGER DEFAULT 0,
  is_to_order INTEGER DEFAULT 0,
  is_ordered INTEGER DEFAULT 0,
  is_delivered INTEGER DEFAULT 0,
  is_backorder INTEGER DEFAULT 0,
  is_mandatory INTEGER DEFAULT 0,
  is_price_checked INTEGER DEFAULT 0,
  raw_json TEXT,
  PRIMARY KEY (order_id, part_no, description)
);

CREATE TABLE IF NOT EXISTS order_sections (
  order_id INTEGER,
  section TEXT,
  content_type TEXT,
  raw_text TEXT,
  data_json TEXT,
  last_synced_at TEXT,
  PRIMARY KEY (order_id, section)
);

CREATE VIRTUAL TABLE IF NOT EXISTS orders_fts USING fts5(
  short_name, plate, person, phone, email, damage, project_status, parts_status,
  content='orders', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS orders_ai AFTER INSERT ON orders BEGIN
  INSERT INTO orders_fts(rowid, short_name, plate, person, phone, email, damage, project_status, parts_status)
  VALUES (new.id, new.short_name, new.plate, new.person, new.phone, new.email, new.damage, new.project_status, new.parts_status);
END;

CREATE TRIGGER IF NOT EXISTS orders_ad AFTER DELETE ON orders BEGIN
  INSERT INTO orders_fts(orders_fts, rowid, short_name, plate, person, phone, email, damage, project_status, parts_status)
  VALUES('delete', old.id, old.short_name, old.plate, old.person, old.phone, old.email, old.damage, old.project_status, old.parts_status);
END;

CREATE TRIGGER IF NOT EXISTS orders_au AFTER UPDATE ON orders BEGIN
  INSERT INTO orders_fts(orders_fts, rowid, short_name, plate, person, phone, email, damage, project_status, parts_status)
  VALUES('delete', old.id, old.short_name, old.plate, old.person, old.phone, old.email, old.damage, old.project_status, old.parts_status);
  INSERT INTO orders_fts(rowid, short_name, plate, person, phone, email, damage, project_status, parts_status)
  VALUES (new.id, new.short_name, new.plate, new.person, new.phone, new.email, new.damage, new.project_status, new.parts_status);
END;
"""


def db_connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    _ensure_table_columns(
        con,
        "parts",
        {
            "lead_no": "TEXT",
            "order_no": "TEXT",
            "row_id": "TEXT",
            "part_id": "TEXT",
            "price_each": "REAL",
            "price_total": "REAL",
            "status_code": "TEXT",
            "status_icon": "TEXT",
            "order_date": "TEXT",
            "is_to_order": "INTEGER DEFAULT 0",
            "is_ordered": "INTEGER DEFAULT 0",
            "is_delivered": "INTEGER DEFAULT 0",
            "is_backorder": "INTEGER DEFAULT 0",
            "is_mandatory": "INTEGER DEFAULT 0",
            "is_price_checked": "INTEGER DEFAULT 0",
        },
    )
    return con


def _ensure_table_columns(con: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    existing = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
    for col, ddl in columns.items():
        if col in existing:
            continue
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def db_upsert_order(con: sqlite3.Connection, row: Dict[str, Any]) -> None:
    cols = sorted(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    update = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "id"])
    sql = f"""
    INSERT INTO orders ({", ".join(cols)})
    VALUES ({placeholders})
    ON CONFLICT(id) DO UPDATE SET {update}
    """
    con.execute(sql, [row[c] for c in cols])


def db_upsert_employees(con: sqlite3.Connection, emp: Dict[str, str]) -> None:
    for k, v in emp.items():
        con.execute(
            "INSERT INTO employees(id,name) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",
            (k, v),
        )


def db_replace_parts(con: sqlite3.Connection, order_id: int, parts: List[Dict[str, Any]]) -> None:
    con.execute("DELETE FROM parts WHERE order_id=?", (order_id,))
    for p in parts:
        con.execute(
            """
            INSERT OR REPLACE INTO parts(
              order_id, part_no, description, lead_no, order_no, row_id, part_id,
              qty, price_each, price_total, status, status_code, status_icon,
              order_date, delivery_date, eta_date,
              is_missing, is_to_order, is_ordered, is_delivered, is_backorder, is_mandatory, is_price_checked,
              raw_json
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                order_id,
                p.get("part_no") or "",
                p.get("description") or "",
                p.get("lead_no"),
                p.get("order_no"),
                p.get("row_id"),
                p.get("part_id"),
                p.get("qty"),
                p.get("price_each"),
                p.get("price_total"),
                p.get("status"),
                p.get("status_code"),
                p.get("status_icon"),
                p.get("order_date"),
                p.get("delivery_date"),
                p.get("eta_date"),
                int(bool(p.get("is_missing"))),
                int(bool(p.get("is_to_order"))),
                int(bool(p.get("is_ordered"))),
                int(bool(p.get("is_delivered"))),
                int(bool(p.get("is_backorder"))),
                int(bool(p.get("is_mandatory"))),
                int(bool(p.get("is_price_checked"))),
                json.dumps(p.get("raw", {}), ensure_ascii=False),
            ),
        )


def db_upsert_sections(con: sqlite3.Connection, order_id: int, sections: Dict[str, Dict[str, Any]]) -> None:
    for name, payload in sections.items():
        con.execute(
            """
            INSERT OR REPLACE INTO order_sections(
              order_id, section, content_type, raw_text, data_json, last_synced_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                order_id,
                name,
                payload.get("content_type") or "",
                payload.get("raw_text") or "",
                json.dumps(payload.get("data_json") or {}, ensure_ascii=False),
                _now_iso(),
            ),
        )


# ======================================================================
# Fetchers
# ======================================================================


def fetch_project_stations(sess: requests.Session, cfg: ClientCfg) -> List[Dict[str, Any]]:
    r = _req(sess, cfg, "POST", "/do", params={"m": "resourceplanner_get_project_stations", "filterID": ""}, data={})
    if r.status_code != 200:
        raise RuntimeError(f"project_stations HTTP {r.status_code}")
    j = _safe_json_loads(r.text)
    if j is None:
        raise RuntimeError("project_stations: non-JSON response (likely not logged in?)")
    return parse_projects_payload(j)


def fetch_shop_view_single(sess: requests.Session, cfg: ClientCfg, project_id: int) -> Dict[str, Any]:
    r = _req(
        sess,
        cfg,
        "GET",
        "/do",
        params={"m": "resourceplanner_shop_view_single", "svsurl": "false", "ID": str(project_id), "opentab": ""},
    )
    if r.status_code != 200:
        raise RuntimeError(f"shop_view_single HTTP {r.status_code}")
    j = _safe_json_loads(r.text)
    if not isinstance(j, dict):
        raise RuntimeError("shop_view_single: non-JSON response (likely not logged in?)")
    return j


def fetch_visual_forms_plain(
    sess: requests.Session, cfg: ClientCfg, project_id: int, table_id: int = 12565
) -> Dict[str, Any]:
    # Your HAR shows this is POST with these query params
    r = _req(
        sess,
        cfg,
        "POST",
        "/do",
        params={
            "m": "visual_forms_plain",
            "tableID": str(table_id),
            "submode": "update",
            "dataID": str(project_id),
            "call_back_class": "resourceplanner_single_project_wrapper",
            "callback": "",
        },
        data={},  # real POST often includes fields=... when saving; for read, empty works for many installs
    )
    if r.status_code != 200:
        raise RuntimeError(f"visual_forms_plain HTTP {r.status_code}")
    j = _safe_json_loads(r.text)
    if not isinstance(j, dict):
        raise RuntimeError("visual_forms_plain: non-JSON response")
    return j


def fetch_parts_tab(sess: requests.Session, cfg: ClientCfg, project_id: int) -> Dict[str, Any]:
    r = _req(sess, cfg, "GET", "/do", params={"m": "resourceplanner_shop_view_get_parts", "ID": str(project_id)})
    if r.status_code != 200:
        raise RuntimeError(f"get_parts HTTP {r.status_code}")
    j = _safe_json_loads(r.text)
    if not isinstance(j, dict):
        raise RuntimeError("get_parts: non-JSON response")
    return j


def _header_index(headers: List[str], include: Iterable[str], exclude: Iterable[str] = ()) -> Optional[int]:
    inc = [s.lower() for s in include]
    exc = [s.lower() for s in exclude]
    for i, h in enumerate(headers):
        h2 = h.lower()
        if all(x in h2 for x in inc) and all(x not in h2 for x in exc):
            return i
    return None


def _parse_parts_date_values(text: str, titles: List[str]) -> Tuple[str, str]:
    def norm(s: str) -> str:
        d, dt = _parse_german_date_or_datetime(s)
        return d or dt or s

    def extract_candidates(s: str) -> List[str]:
        if not s:
            return []
        cleaned = _normalize_whitespace(
            s.replace("Array", " ").replace("\xa0", " ").replace("\u00a0", " ")
        )
        candidates = []
        candidates.extend(re.findall(r"\d{4}-\d{2}-\d{2}", cleaned))
        candidates.extend(
            re.findall(r"\d{1,2}\.\d{1,2}\.\d{4}(?:\s+\d{1,2}:\d{2}:\d{2})?", cleaned)
        )
        return candidates

    order_date = ""
    delivery_date = ""
    if titles:
        date_tokens: List[str] = []
        for t in titles:
            date_tokens.extend(extract_candidates(t))
        if len(date_tokens) >= 2:
            order_date = norm(date_tokens[0])
            delivery_date = norm(date_tokens[1])
        elif len(date_tokens) == 1:
            delivery_date = norm(date_tokens[0])

    if text:
        date_tokens = extract_candidates(text)
        if len(date_tokens) >= 2:
            if not order_date:
                order_date = norm(date_tokens[0])
            if not delivery_date:
                delivery_date = norm(date_tokens[1])
            return order_date, delivery_date
        if len(date_tokens) == 1 and not delivery_date:
            delivery_date = norm(date_tokens[0])
            return order_date, delivery_date

        cleaned = _normalize_whitespace(
            text.replace("Array", " ").replace("\xa0", " ").replace("\u00a0", " ")
        )
        parts = [p.strip() for p in cleaned.split("/") if p.strip()]
        if len(parts) >= 2:
            if not order_date and parts[0] != "-":
                order_date = norm(parts[0])
            if not delivery_date and parts[1] != "-":
                delivery_date = norm(parts[1])
        elif len(parts) == 1 and not delivery_date and parts[0] != "-":
            delivery_date = norm(parts[0])
    return order_date, delivery_date


def _parse_parts_from_html(html: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Best-effort parsing of parts lists from HTML fragments.
    Different installations render parts in different ways; this tries a few patterns.

    Returns (parts_list, meta) where:
      parts_list: list of dicts for each part
      meta: table-level data attributes (vin, make, etc) when present
    """
    html = _html.unescape(html or "")
    parts: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}

    # 1) PlanSo parts table (rich status flags)
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")
        table = soup.find("table", class_=re.compile(r"parts_table|rsp_parts_table|psrs_parts_table", re.I))
        if table:
            meta = _extract_data_attrs_from_tag(table)
            headers = [_normalize_whitespace(th.get_text(" ", strip=True)) for th in table.find_all("th")]

            idx_desc = _header_index(headers, ["teil"], exclude=["teile nr"])
            idx_part_no = _header_index(headers, ["teile", "nr"])
            idx_lead_no = _header_index(headers, ["leit", "nr"])
            idx_price_each = _header_index(headers, ["e.preis"])
            idx_qty = _header_index(headers, ["menge"])
            idx_total = _header_index(headers, ["g.preis"])
            idx_date = _header_index(headers, ["datum"])
            idx_order_no = _header_index(headers, ["a.nummer"])

            for tr in table.find_all("tr", class_=re.compile(r"parts_single_row", re.I)):
                tds = tr.find_all("td")
                if not tds:
                    continue
                vals = [_normalize_whitespace(td.get_text(" ", strip=True)) for td in tds]

                desc = vals[idx_desc] if idx_desc is not None and idx_desc < len(vals) else ""
                part_no_cell = (
                    tds[idx_part_no] if idx_part_no is not None and idx_part_no < len(tds) else None
                )
                part_no = ""
                if part_no_cell is not None:
                    part_no = part_no_cell.get("data-prtnumber") or _normalize_whitespace(
                        part_no_cell.get_text(" ", strip=True)
                    )
                lead_no = vals[idx_lead_no] if idx_lead_no is not None and idx_lead_no < len(vals) else ""
                qty = _to_float_de(vals[idx_qty]) if idx_qty is not None and idx_qty < len(vals) else None
                price_each = (
                    _to_float_de(vals[idx_price_each]) if idx_price_each is not None and idx_price_each < len(vals) else None
                )
                price_total = (
                    _to_float_de(vals[idx_total]) if idx_total is not None and idx_total < len(vals) else None
                )
                order_no = vals[idx_order_no] if idx_order_no is not None and idx_order_no < len(vals) else ""

                date_cell = tds[idx_date] if idx_date is not None and idx_date < len(tds) else None
                titles = [t for t in [span.get("title") for span in (date_cell.find_all("span") if date_cell else [])] if t]
                order_date, delivery_date = _parse_parts_date_values(
                    date_cell.get_text(" ", strip=True) if date_cell else "", titles
                )

                status_flags: Dict[str, bool] = {}
                for inp in tr.find_all("input", class_=re.compile(r"spare_part_status", re.I)):
                    action = (inp.get("data-action") or "").strip()
                    if action:
                        status_flags[action] = inp.has_attr("checked")

                status_icon = ""
                status_td = tr.find("td", class_=re.compile(r"spare_part_main_status", re.I))
                if status_td:
                    icon = status_td.find("i", title=True)
                    if icon:
                        status_icon = _normalize_whitespace(icon.get("title") or "")

                status_code = _normalize_whitespace(tr.get("data-status") or "")
                row_attrs = _extract_data_attrs_from_tag(tr)

                is_to_order = bool(status_flags.get("order_parts"))
                is_ordered = bool(status_flags.get("bestellt"))
                is_delivered = bool(status_flags.get("delivered"))
                is_backorder = bool(status_flags.get("ruckstand"))
                is_mandatory = bool(status_flags.get("mandatory"))
                is_price_checked = bool(status_flags.get("price_checked"))

                status_text = status_icon or status_code
                is_missing = bool(is_backorder or (not is_delivered and (is_to_order or is_ordered)))
                if not is_missing and re.search(r"(offen|fehlt|rückstand|backorder)", status_text, re.IGNORECASE):
                    is_missing = True
                if is_delivered and not is_backorder:
                    is_missing = False

                parts.append(
                    {
                        "part_no": part_no,
                        "description": desc,
                        "lead_no": lead_no,
                        "order_no": order_no,
                        "row_id": row_attrs.get("data-id"),
                        "part_id": row_attrs.get("data-partid"),
                        "qty": qty,
                        "price_each": price_each,
                        "price_total": price_total,
                        "status": status_text,
                        "status_code": status_code,
                        "status_icon": status_icon,
                        "order_date": order_date,
                        "delivery_date": delivery_date,
                        "eta_date": "",
                        "is_missing": is_missing,
                        "is_to_order": is_to_order,
                        "is_ordered": is_ordered,
                        "is_delivered": is_delivered,
                        "is_backorder": is_backorder,
                        "is_mandatory": is_mandatory,
                        "is_price_checked": is_price_checked,
                        "raw": {
                            "headers": headers,
                            "row_attrs": row_attrs,
                            "status_flags": status_flags,
                            "values": vals,
                        },
                    }
                )

    if not parts and BeautifulSoup is None:
        table_match = re.search(r'<table[^>]*class="[^"]*parts_table[^"]*"[^>]*>', html, re.IGNORECASE)
        if table_match:
            meta = _extract_data_attrs_from_tag(table_match.group(0))
        headers = [
            _normalize_whitespace(_strip_tags(h))
            for h in re.findall(r"<th[^>]*>(.*?)</th>", html, re.IGNORECASE | re.DOTALL)
        ]
        idx_desc = _header_index(headers, ["teil"], exclude=["teile nr"])
        idx_part_no = _header_index(headers, ["teile", "nr"])
        idx_lead_no = _header_index(headers, ["leit", "nr"])
        idx_price_each = _header_index(headers, ["e.preis"])
        idx_qty = _header_index(headers, ["menge"])
        idx_total = _header_index(headers, ["g.preis"])
        idx_date = _header_index(headers, ["datum"])
        idx_order_no = _header_index(headers, ["a.nummer"])

        for row_html in re.findall(
            r"<tr[^>]*class=\"[^\"]*parts_single_row[^\"]*\"[^>]*>.*?</tr>",
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.IGNORECASE | re.DOTALL)
            if not tds:
                continue
            vals = [_normalize_whitespace(_strip_tags(td)) for td in tds]
            row_attrs = _extract_data_attrs_from_tag(row_html)

            desc = vals[idx_desc] if idx_desc is not None and idx_desc < len(vals) else ""
            part_no = ""
            if idx_part_no is not None and idx_part_no < len(tds):
                cell_html = tds[idx_part_no]
                m_prt = re.search(r'data-prtnumber="([^"]+)"', cell_html)
                part_no = m_prt.group(1) if m_prt else _normalize_whitespace(_strip_tags(cell_html))
            lead_no = vals[idx_lead_no] if idx_lead_no is not None and idx_lead_no < len(vals) else ""
            qty = _to_float_de(vals[idx_qty]) if idx_qty is not None and idx_qty < len(vals) else None
            price_each = (
                _to_float_de(vals[idx_price_each]) if idx_price_each is not None and idx_price_each < len(vals) else None
            )
            price_total = (
                _to_float_de(vals[idx_total]) if idx_total is not None and idx_total < len(vals) else None
            )
            order_no = vals[idx_order_no] if idx_order_no is not None and idx_order_no < len(vals) else ""

            date_cell_html = tds[idx_date] if idx_date is not None and idx_date < len(tds) else ""
            titles = re.findall(r'title="([^"]+)"', date_cell_html)
            order_date, delivery_date = _parse_parts_date_values(
                _normalize_whitespace(_strip_tags(date_cell_html)), titles
            )

            status_flags: Dict[str, bool] = {}
            for inp in re.findall(r"<input[^>]+>", row_html, re.IGNORECASE):
                cls = re.search(r'class="([^"]+)"', inp)
                if not cls or "spare_part_status" not in cls.group(1):
                    continue
                action = re.search(r'data-action="([^"]+)"', inp)
                checked = "checked" in inp.lower()
                if action:
                    status_flags[action.group(1)] = checked

            status_icon = ""
            m_icon = re.search(
                r'class="[^"]*spare_part_main_status[^"]*"[^>]*>.*?<i[^>]*title="([^"]+)"',
                row_html,
                re.IGNORECASE | re.DOTALL,
            )
            if m_icon:
                status_icon = _normalize_whitespace(m_icon.group(1))

            status_code = _normalize_whitespace(row_attrs.get("data-status") or "")

            is_to_order = bool(status_flags.get("order_parts"))
            is_ordered = bool(status_flags.get("bestellt"))
            is_delivered = bool(status_flags.get("delivered"))
            is_backorder = bool(status_flags.get("ruckstand"))
            is_mandatory = bool(status_flags.get("mandatory"))
            is_price_checked = bool(status_flags.get("price_checked"))

            status_text = status_icon or status_code
            is_missing = bool(is_backorder or (not is_delivered and (is_to_order or is_ordered)))
            if not is_missing and re.search(r"(offen|fehlt|rückstand|backorder)", status_text, re.IGNORECASE):
                is_missing = True
            if is_delivered and not is_backorder:
                is_missing = False

            parts.append(
                {
                    "part_no": part_no,
                    "description": desc,
                    "lead_no": lead_no,
                    "order_no": order_no,
                    "row_id": row_attrs.get("data-id"),
                    "part_id": row_attrs.get("data-partid"),
                    "qty": qty,
                    "price_each": price_each,
                    "price_total": price_total,
                    "status": status_text,
                    "status_code": status_code,
                    "status_icon": status_icon,
                    "order_date": order_date,
                    "delivery_date": delivery_date,
                    "eta_date": "",
                    "is_missing": is_missing,
                    "is_to_order": is_to_order,
                    "is_ordered": is_ordered,
                    "is_delivered": is_delivered,
                    "is_backorder": is_backorder,
                    "is_mandatory": is_mandatory,
                    "is_price_checked": is_price_checked,
                    "raw": {
                        "headers": headers,
                        "row_attrs": row_attrs,
                        "status_flags": status_flags,
                        "values": vals,
                    },
                }
            )

    if parts:
        uniq: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for p in parts:
            key = (p.get("part_no") or "", p.get("description") or "")
            if key not in uniq:
                uniq[key] = p
        return list(uniq.values()), meta

    # 2) Generic table parsing
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "lxml" if "lxml" in getattr(BeautifulSoup, "__module__", "") else "html.parser")
        tables = soup.find_all("table")
        for t in tables:
            headers = [_normalize_whitespace(th.get_text(" ", strip=True)) for th in t.find_all("th")]
            rows = t.find_all("tr")
            for tr in rows:
                tds = tr.find_all("td")
                if not tds:
                    continue
                vals = [_normalize_whitespace(td.get_text(" ", strip=True)) for td in tds]
                if headers and len(headers) == len(vals):
                    row = dict(zip(headers, vals))
                else:
                    row = {f"col_{i}": v for i, v in enumerate(vals)}
                part_no = (
                    row.get("Teilenummer")
                    or row.get("Teile-Nr.")
                    or row.get("Teilenr.")
                    or row.get("Part")
                    or row.get("col_0")
                    or ""
                )
                desc = (
                    row.get("Bezeichnung")
                    or row.get("Beschreibung")
                    or row.get("Description")
                    or row.get("col_1")
                    or ""
                )
                qty = _to_float_de(row.get("Menge") or row.get("Qty") or row.get("col_2") or "")
                status = row.get("Status") or row.get("col_3") or ""
                delivery_date = row.get("Lieferdatum") or row.get("Geliefert") or row.get("Delivery") or ""
                eta = row.get("ETA") or row.get("Liefertermin") or ""
                if part_no or desc:
                    parts.append(
                        {
                            "part_no": part_no,
                            "description": desc,
                            "lead_no": "",
                            "order_no": "",
                            "row_id": "",
                            "part_id": "",
                            "qty": qty,
                            "price_each": None,
                            "price_total": None,
                            "status": status,
                            "status_code": "",
                            "status_icon": "",
                            "order_date": "",
                            "delivery_date": _parse_german_date_or_datetime(delivery_date)[0] or delivery_date,
                            "eta_date": _parse_german_date_or_datetime(eta)[0] or eta,
                            "is_missing": bool(
                                re.search(r"(offen|fehlt|rückstand|backorder|nicht.*gelief)", status, re.IGNORECASE)
                            ),
                            "is_to_order": False,
                            "is_ordered": False,
                            "is_delivered": False,
                            "is_backorder": False,
                            "is_mandatory": False,
                            "is_price_checked": False,
                            "raw": row,
                        }
                    )

    # 3) Regex pattern: data attributes only
    if not parts:
        for m in re.finditer(r'data-part(no|_no)?="([^"]+)"', html, re.IGNORECASE):
            parts.append(
                {
                    "part_no": m.group(2),
                    "description": "",
                    "lead_no": "",
                    "order_no": "",
                    "row_id": "",
                    "part_id": "",
                    "qty": None,
                    "price_each": None,
                    "price_total": None,
                    "status": "",
                    "status_code": "",
                    "status_icon": "",
                    "order_date": "",
                    "delivery_date": "",
                    "eta_date": "",
                    "is_missing": 0,
                    "is_to_order": False,
                    "is_ordered": False,
                    "is_delivered": False,
                    "is_backorder": False,
                    "is_mandatory": False,
                    "is_price_checked": False,
                    "raw": {},
                }
            )

    uniq = {(p.get("part_no") or "", p.get("description") or ""): p for p in parts}
    return list(uniq.values()), meta


def _safe_parse_parts_html(html: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        return _parse_parts_from_html(html)
    except re.error as e:
        return [], {"parse_error": f"regex error: {e}"}


def fetch_parts_deep(
    sess: requests.Session, cfg: ClientCfg, project_id: int
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Return (parts_status, parts_list, parts_meta, parts_payload).
    - parts_status: short human status (best-effort)
    - parts_list: detailed parts if an endpoint yields a list
    - parts_meta: table-level metadata (vin, make, etc) if present
    - parts_payload: raw JSON payload from parts tab (if fetched)
    """
    parts_status = ""
    parts_list: List[Dict[str, Any]] = []
    parts_meta: Dict[str, Any] = {}

    tab = fetch_parts_tab(sess, cfg, project_id)
    html = tab.get("html", "") or ""
    js = tab.get("js", "") or tab.get("functions", "") or ""
    parts_payload: Optional[Dict[str, Any]] = tab if isinstance(tab, dict) else None

    # parts status sometimes is visible as button text near a dropdown; try a few heuristics
    m = re.search(r"rsvgp_status_dropdown[^>]*>\s*([^<]+)\s*<", html, re.IGNORECASE)
    if m:
        parts_status = _normalize_whitespace(m.group(1))
    else:
        # look for selected option in a status select
        if BeautifulSoup is not None:
            soup = BeautifulSoup(_html.unescape(html), "html.parser")
            sel = soup.find("select", attrs={"name": re.compile("status", re.I)})
            if sel:
                opt = sel.find("option", selected=True)
                if opt:
                    parts_status = _normalize_whitespace(opt.get_text(" ", strip=True))
    parts_status = parts_status or ""

    if html:
        pl, meta = _safe_parse_parts_html(html)
        if pl:
            parts_list = pl
        if meta:
            parts_meta = meta

    # Candidate endpoints discovered in JS (not always present in HAR)
    candidates = extract_candidate_endpoints_from_js(js)
    # We specifically care about export / availability endpoints if present:
    preferred = [c for c in candidates if "parts_export" in c or "parts_availability" in c or "parts" in c]
    preferred = preferred[:10]  # don't go crazy

    # Try preferred endpoints with simple GET params
    for ep in preferred:
        # common patterns: ...&projectID= or ...&ID=
        for params in (
            {"projectID": str(project_id)},
            {"ID": str(project_id)},
            {"id": str(project_id)},
        ):
            try:
                r = _req(sess, cfg, "GET", ep, params=params)
                if r.status_code != 200:
                    continue
                ct = (r.headers.get("content-type") or "").lower()
                text = r.text or ""
                # If JSON wrapper
                if "application/json" in ct or text.strip().startswith("{"):
                    j = _safe_json_loads(text)
                    if isinstance(j, dict):
                        # some endpoints return {"html": "..."}; parse it
                        if "html" in j and isinstance(j["html"], str):
                            pl, meta = _safe_parse_parts_html(j["html"])
                            if pl:
                                parts_list = pl
                                parts_meta = meta or parts_meta
                                return parts_status, parts_list, parts_meta, parts_payload
                        # other endpoints might return raw rows
                        if "data" in j and isinstance(j["data"], list):
                            # try to normalize
                            for row in j["data"]:
                                if isinstance(row, dict):
                                    parts_list.append(
                                        {
                                            "part_no": row.get("part_no") or row.get("number") or "",
                                            "description": row.get("desc") or row.get("description") or "",
                                            "qty": row.get("qty"),
                                            "status": row.get("status") or "",
                                            "delivery_date": row.get("delivery_date") or "",
                                            "eta_date": row.get("eta_date") or "",
                                            "is_missing": 0,
                                            "is_to_order": False,
                                            "is_ordered": False,
                                            "is_delivered": False,
                                            "is_backorder": False,
                                            "is_mandatory": False,
                                            "is_price_checked": False,
                                            "raw": row,
                                        }
                                    )
                            if parts_list:
                                return parts_status, parts_list, parts_meta, parts_payload
                # CSV export
                if "text/csv" in ct or (";" in text and "Teile" in text[:200]):
                    # try csv sniff
                    reader = csv.DictReader(text.splitlines(), delimiter=";")
                    for row in reader:
                        parts_list.append(
                            {
                                "part_no": row.get("Teilenummer") or row.get("PartNo") or "",
                                "description": row.get("Bezeichnung") or row.get("Description") or "",
                                "qty": _to_float_de(row.get("Menge") or row.get("Qty") or ""),
                                "status": row.get("Status") or "",
                                "delivery_date": _parse_german_date_or_datetime(row.get("Lieferdatum") or "")[0]
                                or (row.get("Lieferdatum") or ""),
                                "eta_date": _parse_german_date_or_datetime(row.get("ETA") or "")[0]
                                or (row.get("ETA") or ""),
                                "is_missing": bool(
                                    re.search(
                                        r"(offen|fehlt|rückstand|backorder|nicht.*gelief)",
                                        (row.get("Status") or ""),
                                        re.IGNORECASE,
                                    )
                                ),
                                "is_to_order": False,
                                "is_ordered": False,
                                "is_delivered": False,
                                "is_backorder": False,
                                "is_mandatory": False,
                                "is_price_checked": False,
                                "raw": row,
                            }
                        )
                    if parts_list:
                        return parts_status, parts_list, parts_meta, parts_payload
                # HTML
                if _looks_like_html(text):
                    pl, meta = _safe_parse_parts_html(text)
                    if pl:
                        parts_list = pl
                        parts_meta = meta or parts_meta
                        return parts_status, parts_list, parts_meta, parts_payload
            except Exception:
                continue

    # Nothing detailed found; return status only
    return parts_status, parts_list, parts_meta, parts_payload


def _normalize_iso_date(s: str) -> Optional[str]:
    if not s:
        return None
    iso, _ = _parse_german_date_or_datetime(s)
    return iso or (s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s.strip()) else None)


def _month_range(iso_date: str) -> Tuple[str, str]:
    d = _dt.date.fromisoformat(iso_date)
    start = d.replace(day=1)
    next_month = (start + _dt.timedelta(days=32)).replace(day=1)
    return start.isoformat(), next_month.isoformat()


def fetch_order_sections(
    sess: requests.Session,
    cfg: ClientCfg,
    project_id: int,
    shop_date: Optional[str],
    prefetched: Optional[Dict[str, Dict[str, Any]]] = None,
    table_id: int = 12565,
    include_binaries: bool = False,
) -> Dict[str, Dict[str, Any]]:
    sections: Dict[str, Dict[str, Any]] = {}
    pid = str(project_id)

    date_iso = _normalize_iso_date(shop_date or "")
    month_from = month_to = None
    if date_iso:
        month_from, month_to = _month_range(date_iso)

    def add_section(name: str, method: str, params: Dict[str, str]) -> None:
        if not include_binaries and name in {"images", "documents"}:
            return
        if prefetched and name in prefetched:
            text = json.dumps(prefetched[name], ensure_ascii=False)
            sections[name] = _build_section_payload(text, "application/json")
            return
        try:
            r = _req(sess, cfg, method, "/do", params=params)
            if r.status_code != 200:
                return
            sections[name] = _build_section_payload(r.text or "", r.headers.get("content-type") or "")
        except Exception:
            return

    add_section("shop_view_single", "GET", {"m": "resourceplanner_shop_view_single", "svsurl": "false", "ID": pid, "opentab": ""})
    add_section(
        "visual_forms_plain",
        "POST",
        {
            "m": "visual_forms_plain",
            "tableID": str(table_id),
            "submode": "update",
            "dataID": pid,
            "call_back_class": "resourceplanner_single_project_wrapper",
            "callback": "",
        },
    )
    add_section("shop_view", "GET", {"m": "resourceplanner_get_shop_view", "get_fields": "false", "ID": pid})
    add_section("damaged_areas", "GET", {"m": "resourceplanner_shop_view_get_damagedareas", "ID": pid})
    add_section("details", "GET", {"m": "resourceplanner_shop_view_get_details", "ID": pid})
    add_section("documents", "GET", {"m": "resourceplanner_shop_view_get_documents", "ID": pid})
    add_section("images", "GET", {"m": "resourceplanner_shop_view_get_images", "ID": pid})
    add_section("invoice", "GET", {"m": "resourceplanner_shop_view_get_invoice", "ID": pid})
    add_section("parts", "GET", {"m": "resourceplanner_shop_view_get_parts", "ID": pid})
    add_section("planung", "GET", {"m": "resourceplanner_shop_view_get_planung", "ID": pid})
    add_section("projects", "GET", {"m": "resourceplanner_shop_view_get_projects", "ID": pid})
    add_section("rental_car", "GET", {"m": "resourceplanner_shop_view_get_rental_car", "ID": pid})
    add_section("setting", "GET", {"m": "resourceplanner_shop_view_get_setting", "ID": pid})
    add_section("stamped_timings", "GET", {"m": "resourceplanner_shop_view_get_stamped_timings", "ID": pid})
    add_section("stats", "GET", {"m": "resourceplanner_shop_view_get_stats", "ID": pid})
    add_section("todo_list", "GET", {"m": "resourceplanner_shop_view_get_todo_list", "ID": pid})
    add_section("work", "GET", {"m": "resourceplanner_shop_view_get_work", "ID": pid})
    add_section("zusammenfassung", "GET", {"m": "resourceplanner_shop_view_get_zusammenfassung", "ID": pid})

    if date_iso:
        add_section(
            "distribution",
            "GET",
            {"m": "resourceplanner_shop_view_get_dist_html", "shop_date": date_iso, "projectID": pid},
        )

    if month_from and month_to:
        add_section(
            "rental_car_data",
            "GET",
            {
                "m": "resourceplanner_shop_view_get_rental_car_data",
                "booked_lei_id": "",
                "projectID": pid,
                "timeshift": "-60",
                "from": month_from,
                "to": month_to,
            },
        )

    return sections


# ======================================================================
# Core logic: normalize order record
# ======================================================================


def _extract_vehicle_info(visual_fields: Dict[str, str], parts_meta: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    mapping = {
        "VIN": "vin",
        "KBA": "kba",
        "Farbe Nummer": "color_code",
        "Farbton": "color_name",
        "Kennzeichen": "plate",
        "Kilometerstand": "mileage",
        "Fahrzeug": "vehicle",
        "Klasse": "class",
        "Leasing/Flotte": "leasing",
    }
    for label, key in mapping.items():
        val = visual_fields.get(label) or ""
        if val:
            out[key] = val

    if parts_meta:
        if parts_meta.get("data-vin") and "vin" not in out:
            out["vin"] = str(parts_meta.get("data-vin"))
        if parts_meta.get("data-make") and "make" not in out:
            out["make"] = str(parts_meta.get("data-make"))
        if parts_meta.get("data-number_plate") and "plate" not in out:
            out["plate"] = str(parts_meta.get("data-number_plate"))
        if parts_meta.get("data-pnum") and "order_no" not in out:
            out["order_no"] = str(parts_meta.get("data-pnum"))
    return out


def build_order_row(
    proj: Dict[str, Any],
    visual_fields: Dict[str, str],
    *,
    parts_status: str = "",
    parts_list: Optional[List[Dict[str, Any]]] = None,
    parts_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pid = int(proj.get("ID"))
    short_name = str(proj.get("short_name") or "").strip()

    station_id, station_state = parse_station(str(proj.get("station") or ""))

    # Pull common fields from visual_forms_plain labels (German)
    person = visual_fields.get("Fahrername") or visual_fields.get("Halter") or ""
    phone = visual_fields.get("Telefon") or visual_fields.get("Telefonnummer") or ""
    email = visual_fields.get("Kunden E-Mail") or visual_fields.get("E-Mail") or ""

    damage = visual_fields.get("Kategorie") or visual_fields.get("Damage") or str(proj.get("finish_date") or "")
    project_status = visual_fields.get("Projekt-Status") or ""

    shop_date = (
        _parse_german_date_or_datetime(visual_fields.get("Werkstattstart") or "")[0]
        or visual_fields.get("Werkstattstart")
        or ""
    )
    repair_date = (
        _parse_german_date_or_datetime(
            visual_fields.get("Fahrzeugeingang (Soll)") or visual_fields.get("Fahrzeugeingang (Ist)") or ""
        )[0]
        or ""
    )

    finish_date = (
        _parse_german_date_or_datetime(visual_fields.get("Termin Fertigstellung") or "")[0]
        or visual_fields.get("Termin Fertigstellung")
        or ""
    )
    planned_delivery = (
        _parse_german_date_or_datetime(visual_fields.get("Plan Auslieferung") or "")[0]
        or visual_fields.get("Plan Auslieferung")
        or ""
    )

    # "missing parts" heuristics:
    eparts_status = visual_fields.get("E-Teile Status") or ""
    parts_status_final = parts_status or eparts_status
    missing_parts = 0
    if re.search(r"(ohne e-?teile)", parts_status_final, re.IGNORECASE):
        missing_parts = 0
    elif re.search(
        r"(fehlt|offen|rückstand|wartet|nicht.*da|backorder|unvollständig)", parts_status_final, re.IGNORECASE
    ):
        missing_parts = 1
    # if we have a parts_list, refine
    if parts_list:
        if any(bool(p.get("is_missing")) for p in parts_list):
            missing_parts = 1

    # Estimate hours
    est_karo = _to_float_de(visual_fields.get("Sollstunden Karo") or "")
    est_lack = _to_float_de(visual_fields.get("Sollstunden Lack") or "")
    est_mech = _to_float_de(visual_fields.get("Sollstunden Mech") or "")

    plate = visual_fields.get("Kennzeichen") or visual_fields.get("Fahrzeug") or short_name
    vehicle_info = _extract_vehicle_info(visual_fields, parts_meta)

    row = {
        "id": pid,
        "short_name": short_name,
        "plate": plate,
        "person": person,
        "phone": phone,
        "email": email,
        "damage": damage,
        "project_status": project_status,
        "station_id": station_id,
        "station_state": station_state,
        "shop_date": shop_date,
        "repair_date": repair_date,
        "finish_date": finish_date,
        "planned_delivery_date": planned_delivery,
        "parts_status": parts_status_final,
        "missing_parts": int(bool(missing_parts)),
        "est_hours_karo": est_karo,
        "est_hours_lack": est_lack,
        "est_hours_mech": est_mech,
        "fields_json": json.dumps(visual_fields, ensure_ascii=False),
        "vehicle_json": json.dumps(vehicle_info, ensure_ascii=False),
        "last_synced_at": _now_iso(),
    }
    return row


# ======================================================================
# CLI commands
# ======================================================================


def cmd_map_har(args: argparse.Namespace) -> int:
    har = _read_json(args.har)
    entries = har.get("log", {}).get("entries", [])
    # Map: endpoint -> {methods, kinds, count, example_post}
    m: Dict[str, Dict[str, Any]] = {}

    def kind(resp: Dict[str, Any]) -> str:
        mt = (resp.get("content", {}) or {}).get("mimeType", "") or ""
        txt = (resp.get("content", {}) or {}).get("text", "") or ""
        if "application/json" in mt:
            j = _safe_json_loads(txt)
            if isinstance(j, dict):
                keys = set(j.keys())
                if {"center", "functions"} & keys:
                    return "json_wrapper_html/js"
                return "json_data"
            return "unknown"
        if "text/html" in mt:
            return "html"
        if "octet-stream" in mt:
            return "binary/octet-stream"
        return mt or "unknown"

    for e in entries:
        req = e.get("request", {})
        url = req.get("url", "")
        method = req.get("method", "")
        if not url:
            continue
        # normalize endpoint: strip scheme, keep host+path+query
        endpoint = re.sub(r"^https?://", "", url)
        resp = e.get("response", {})
        k = kind(resp)
        post_text = ""
        pd = (req.get("postData", {}) or {}).get("text")
        if pd and isinstance(pd, str):
            post_text = pd[:120]
        bucket = m.setdefault(endpoint, {"methods": set(), "kinds": set(), "count": 0, "example_post": ""})
        bucket["methods"].add(method)
        bucket["kinds"].add(k)
        bucket["count"] += 1
        if method.upper() == "POST" and not bucket["example_post"] and post_text:
            bucket["example_post"] = post_text

    t = Table(title=f"Endpoint map from {args.har}")
    t.add_column("Endpoint")
    t.add_column("Methods")
    t.add_column("Kinds")
    t.add_column("Count", justify="right")
    t.add_column("Example POST (if any)")

    for endpoint, info in sorted(m.items(), key=lambda kv: kv[0]):
        t.add_row(
            endpoint,
            ", ".join(sorted(info["methods"])),
            ", ".join(sorted(info["kinds"])),
            str(info["count"]),
            info["example_post"] or "",
        )
    console.print(t)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cfg = args._cfg
    sess = _mk_session(cfg)
    projects = fetch_project_stations(sess, cfg)
    t = Table(title=f"Orders ({len(projects)})")
    t.add_column("ID", justify="right")
    t.add_column("short_name")
    t.add_column("station")
    t.add_column("employeeID")
    t.add_column("theorder")
    for p in projects:
        t.add_row(
            str(p.get("ID")),
            str(p.get("short_name", "")),
            str(p.get("station", "")),
            str(p.get("employeeID", "")),
            str(p.get("theorder", "")),
        )
    console.print(t)
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    cfg = args._cfg
    con = db_connect(args.db)

    sess = _mk_session(cfg)
    projects = fetch_project_stations(sess, cfg)
    total = len(projects)
    console.print(Panel.fit(f"Syncing {total} orders into {args.db}", title="PlanSo Sync"))

    ok = 0
    fail = 0

    def sync_one(proj: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(proj.get("ID"))
        short_name = str(proj.get("short_name", ""))
        sess_local = _get_thread_session(cfg)
        try:
            sv = fetch_shop_view_single(sess_local, cfg, pid)
            center_html = ""
            if isinstance(sv.get("center"), dict):
                center_html = sv["center"].get("content", "") or ""

            emp_map = extract_employee_map_from_html(center_html)

            vf = fetch_visual_forms_plain(sess_local, cfg, pid)
            center = vf.get("center", {}) or {}
            vf_html = center.get("content", "") if isinstance(center, dict) else ""
            try:
                fields = parse_visual_forms_plain_fields(vf_html)
            except re.error as e:
                fields = {}
                warn = f"regex parse error in visual_forms_plain: {e}"
            else:
                warn = ""

            parts_status = ""
            parts_list: List[Dict[str, Any]] = []
            parts_meta: Dict[str, Any] = {}
            parts_payload: Optional[Dict[str, Any]] = None
            if args.with_parts or args.full:
                parts_status, parts_list, parts_meta, parts_payload = fetch_parts_deep(sess_local, cfg, pid)

            row = build_order_row(
                proj,
                fields,
                parts_status=parts_status,
                parts_list=parts_list,
                parts_meta=parts_meta,
            )

            sections: Dict[str, Dict[str, Any]] = {}
            if args.full:
                prefetched: Dict[str, Dict[str, Any]] = {}
                if isinstance(sv, dict):
                    prefetched["shop_view_single"] = sv
                if isinstance(vf, dict):
                    prefetched["visual_forms_plain"] = vf
                if isinstance(parts_payload, dict):
                    prefetched["parts"] = parts_payload
                sections = fetch_order_sections(
                    sess_local,
                    cfg,
                    pid,
                    row.get("shop_date") or row.get("repair_date") or "",
                    prefetched=prefetched,
                    include_binaries=args.include_binary,
                )

            return {
                "ok": True,
                "pid": pid,
                "short_name": short_name,
                "row": row,
                "emp_map": emp_map,
                "parts_list": parts_list,
                "sections": sections,
                "warn": warn,
            }
        except Exception as e:
            return {"ok": False, "pid": pid, "short_name": short_name, "error": str(e)}

    if args.jobs <= 1:
        for i, p in enumerate(projects, start=1):
            res = sync_one(p)
            pid = res.get("pid")
            short_name = res.get("short_name")
            if res.get("ok"):
                if res.get("warn"):
                    console.print(f"[yellow]WARN[/yellow] {short_name} (ID={pid}): {res['warn']}")
                emp_map = res.get("emp_map") or {}
                if emp_map:
                    db_upsert_employees(con, emp_map)
                parts_list = res.get("parts_list") or []
                if parts_list:
                    db_replace_parts(con, pid, parts_list)
                sections = res.get("sections") or {}
                if sections:
                    db_upsert_sections(con, pid, sections)
                db_upsert_order(con, res["row"])
                con.commit()
                person = res["row"].get("person") or ""
                console.print(
                    f"[{i}/{total}] [green]OK[/green] {short_name} | {res['row'].get('plate', '')} | {person}"
                )
                ok += 1
            else:
                fail += 1
                console.print(f"[{i}/{total}] [red]FAIL[/red] {short_name} (ID={pid}): {res.get('error')}")
            if args.sleep:
                time.sleep(float(args.sleep))
    else:
        with ThreadPoolExecutor(max_workers=int(args.jobs)) as ex:
            futures = []
            for p in projects:
                futures.append(ex.submit(sync_one, p))
                if args.sleep:
                    time.sleep(float(args.sleep))
            for i, fut in enumerate(as_completed(futures), start=1):
                res = fut.result()
                pid = res.get("pid")
                short_name = res.get("short_name")
                if res.get("ok"):
                    if res.get("warn"):
                        console.print(f"[yellow]WARN[/yellow] {short_name} (ID={pid}): {res['warn']}")
                    emp_map = res.get("emp_map") or {}
                    if emp_map:
                        db_upsert_employees(con, emp_map)
                    parts_list = res.get("parts_list") or []
                    if parts_list:
                        db_replace_parts(con, pid, parts_list)
                    sections = res.get("sections") or {}
                    if sections:
                        db_upsert_sections(con, pid, sections)
                    db_upsert_order(con, res["row"])
                    con.commit()
                    person = res["row"].get("person") or ""
                    console.print(
                        f"[{i}/{total}] [green]OK[/green] {short_name} | {res['row'].get('plate', '')} | {person}"
                    )
                    ok += 1
                else:
                    fail += 1
                    console.print(f"[{i}/{total}] [red]FAIL[/red] {short_name} (ID={pid}): {res.get('error')}")

    console.print(Panel.fit(f"Done. OK={ok} FAIL={fail}", title="Sync Finished"))
    return 0 if fail == 0 else 1


def _render_results(rows: List[sqlite3.Row]) -> None:
    t = Table(title=f"Query results ({len(rows)} rows)")
    t.add_column("ID", justify="right")
    t.add_column("short_name")
    t.add_column("plate")
    t.add_column("person")
    t.add_column("phone")
    t.add_column("shop_date")
    t.add_column("finish_date")
    t.add_column("status")
    t.add_column("missing_parts", justify="right")

    for r in rows:
        t.add_row(
            str(r["id"]),
            r["short_name"] or "",
            r["plate"] or "",
            (r["person"] or "")[:40],
            r["phone"] or "",
            r["shop_date"] or "",
            r["finish_date"] or "",
            f"{r['project_status'] or ''} / {r['station_id'] or ''}@{r['station_state'] or ''}",
            str(r["missing_parts"] or 0),
        )
    console.print(t)
    console.print("Tip: use 'show --db <db> --id <ID>' for full details.")


def cmd_query(args: argparse.Namespace) -> int:
    con = db_connect(args.db)

    where = []
    params: List[Any] = []

    def like(col: str, val: str) -> None:
        where.append(f"{col} LIKE ?")
        params.append(f"%{val}%")

    if args.plate:
        like("plate", args.plate)
    if args.person:
        like("person", args.person)
    if args.phone:
        like("phone", args.phone)
    if args.email:
        like("email", args.email)
    if args.status:
        like("project_status", args.status)
    if args.damage:
        like("damage", args.damage)
    if args.station is not None:
        where.append("station_id = ?")
        params.append(int(args.station))
    if args.missing_parts:
        where.append("missing_parts = 1")

    if args.after:
        where.append("shop_date >= ?")
        params.append(args.after)
    if args.before:
        where.append("shop_date <= ?")
        params.append(args.before)

    if args.finish_after:
        where.append("finish_date >= ?")
        params.append(args.finish_after)
    if args.finish_before:
        where.append("finish_date <= ?")
        params.append(args.finish_before)

    # Free text: use FTS (safe; no SQL injection; also avoids '-' / special syntax pitfalls)
    fts_rows: Optional[List[int]] = None
    if args.text:
        raw = args.text.strip()
        # Tokenize conservatively, then quote each token for FTS.
        # This prevents queries like 'BB-SK 2307' from being interpreted as FTS operators.
        tokens = re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", raw)
        if tokens:
            fts_q = " AND ".join([f'"{tok}"' for tok in tokens])
            try:
                res = con.execute(
                    "SELECT rowid FROM orders_fts WHERE orders_fts MATCH ? LIMIT 200",
                    (fts_q,),
                )
                fts_rows = [int(r[0]) for r in res.fetchall()]
            except sqlite3.OperationalError:
                fts_rows = None

        if not tokens or fts_rows == [] or fts_rows is None:
            # fallback to LIKE across a few cols
            where.append("(short_name LIKE ? OR plate LIKE ? OR person LIKE ? OR phone LIKE ? OR email LIKE ?)")
            params.extend([f"%{raw}%"] * 5)

    sql = "SELECT * FROM orders"
    if fts_rows is not None and fts_rows:
        where.append(f"id IN ({','.join(['?'] * len(fts_rows))})")
        params.extend(fts_rows)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY shop_date DESC, id DESC LIMIT ?"
    params.append(int(args.limit))

    rows = con.execute(sql, params).fetchall()
    _render_results(rows)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    con = db_connect(args.db)
    row = con.execute("SELECT * FROM orders WHERE id=?", (int(args.id),)).fetchone()
    if not row:
        console.print(f"[red]No order with id={args.id}[/red]")
        return 1

    header = f"{row['short_name']}  ID={row['id']}"
    body = f"{row['plate']} • station={row['station_id']}@{row['station_state']} • status={row['project_status']} • missing_parts={row['missing_parts']}"
    console.print(Panel(body, title="Order"))

    # Crucial fields table
    t = Table(title="Crucial Fields")
    t.add_column("Field")
    t.add_column("Value")
    t.add_row("Person", row["person"] or "")
    t.add_row("Phone", row["phone"] or "")
    t.add_row("Email", row["email"] or "")
    t.add_row("Shop date", row["shop_date"] or "")
    t.add_row("Repair date", row["repair_date"] or "")
    t.add_row("Finish date", row["finish_date"] or "")
    t.add_row("Planned delivery", row["planned_delivery_date"] or "")
    t.add_row("Damage", row["damage"] or "")
    t.add_row("Parts status", row["parts_status"] or "")
    t.add_row("Est hours Karo", str(row["est_hours_karo"] or ""))
    t.add_row("Est hours Lack", str(row["est_hours_lack"] or ""))
    t.add_row("Est hours Mech", str(row["est_hours_mech"] or ""))
    console.print(t)

    # Parts
    if args.parts:
        parts = con.execute(
            "SELECT * FROM parts WHERE order_id=? ORDER BY is_missing DESC, part_no", (int(args.id),)
        ).fetchall()
        tp = Table(title=f"Parts ({len(parts)})")
        tp.add_column("Part No")
        tp.add_column("Description")
        tp.add_column("Qty", justify="right")
        tp.add_column("Status")
        tp.add_column("To order", justify="right")
        tp.add_column("Ordered", justify="right")
        tp.add_column("Delivered", justify="right")
        tp.add_column("Backorder", justify="right")
        tp.add_column("Delivery")
        tp.add_column("ETA")
        tp.add_column("Missing", justify="right")
        for p in parts:
            tp.add_row(
                p["part_no"] or "",
                (p["description"] or "")[:60],
                str(p["qty"] or ""),
                p["status"] or "",
                str(p["is_to_order"] or 0),
                str(p["is_ordered"] or 0),
                str(p["is_delivered"] or 0),
                str(p["is_backorder"] or 0),
                p["delivery_date"] or "",
                p["eta_date"] or "",
                str(p["is_missing"] or 0),
            )
        console.print(tp)

    if args.all_fields:
        fields = json.loads(row["fields_json"] or "{}")
        tf = Table(title="All visual_forms_plain fields (by label)")
        tf.add_column("Label")
        tf.add_column("Value")
        for k, v in sorted(fields.items(), key=lambda kv: kv[0].lower()):
            tf.add_row(k, str(v))
        console.print(tf)

    if args.sections or args.section:
        if args.section:
            sec = con.execute(
                "SELECT section, content_type, data_json FROM order_sections WHERE order_id=? AND section=?",
                (int(args.id), args.section),
            ).fetchone()
            if not sec:
                console.print(f"[red]No section '{args.section}' for id={args.id}[/red]")
            else:
                console.print(Panel(f"{sec['section']} • {sec['content_type']}", title="Section"))
                try:
                    console.print_json(data=json.loads(sec["data_json"] or "{}"))
                except Exception:
                    console.print(sec["data_json"] or "")
        else:
            sec_rows = con.execute(
                "SELECT section, content_type, length(raw_text) AS size FROM order_sections WHERE order_id=? ORDER BY section",
                (int(args.id),),
            ).fetchall()
            tsec = Table(title=f"Sections ({len(sec_rows)})")
            tsec.add_column("Section")
            tsec.add_column("Content-Type")
            tsec.add_column("Raw size", justify="right")
            for s in sec_rows:
                tsec.add_row(s["section"], s["content_type"] or "", str(s["size"] or 0))
            console.print(tsec)

    return 0


def cmd_find(args: argparse.Namespace) -> int:
    """
    Backwards-compatible convenience wrapper around query.
    """
    args2 = argparse.Namespace(
        db=args.db,
        text=args.query,
        plate=None,
        person=None,
        phone=None,
        email=None,
        status=None,
        damage=None,
        station=None,
        missing_parts=False,
        after=None,
        before=None,
        finish_after=None,
        finish_before=None,
        limit=args.limit,
    )
    return cmd_query(args2)


# ======================================================================
# Argparse: accept global args both before *and* after subcommand
# ======================================================================

GLOBAL_FLAGS = {"--base-url", "--cookie-jar", "--env", "--user", "--password", "--timeout"}


def _extract_global_args(argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Allows:
      tool.py --base-url ... login
    AND:
      tool.py login --base-url ...
    by extracting known global flags wherever they appear.
    """
    g: Dict[str, Any] = {}
    rest: List[str] = []
    it = iter(range(len(argv)))
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in GLOBAL_FLAGS:
            if i + 1 >= len(argv):
                raise SystemExit(f"Missing value for {a}")
            val = argv[i + 1]
            if a == "--base-url":
                g["base_url"] = val
            elif a == "--cookie-jar":
                g["cookie_jar"] = val
            elif a == "--env":
                g["env"] = val
            elif a == "--user":
                g["user"] = val
            elif a == "--password":
                g["password"] = val
            elif a == "--timeout":
                g["timeout"] = int(val)
            i += 2
            continue
        rest.append(a)
        i += 1
    return g, rest


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tool.py", add_help=True)
    p.add_argument("--base-url", default="https://reit.planso.de", help="Base URL, e.g. https://reit.planso.de")
    p.add_argument("--cookie-jar", default=".planso_cookies.txt", help="Cookie jar path (Netscape format)")
    p.add_argument("--env", default=".env", help="Path to .env containing PLANSO_USER/PLANSO_PASS")
    p.add_argument("--user", default=None, help="Override PLANSO_USER")
    p.add_argument("--password", default=None, help="Override PLANSO_PASS")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("map-har", help="Map endpoints from a HAR file")
    sp.add_argument("--har", required=True, help="Path to HAR JSON (e.g. temp.json)")
    sp.set_defaults(func=cmd_map_har)

    sp = sub.add_parser("login", help="Login and save cookies to --cookie-jar (reads .env by default)")
    sp.set_defaults(func=lambda a: login(a._cfg))

    sp = sub.add_parser("list", help="List current orders from resourceplanner_get_project_stations")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("sync", help="Sync orders into a local SQLite DB for fast querying")
    sp.add_argument("--db", required=True, help="SQLite DB path (e.g. planso.db)")
    sp.add_argument(
        "--with-parts",
        action="store_true",
        help="Fetch parts tab and store detailed parts rows",
    )
    sp.add_argument(
        "--full",
        action="store_true",
        help="Fetch all known shop_view tabs and store section snapshots (includes --with-parts, skips images/docs)",
    )
    sp.add_argument(
        "--include-binary",
        action="store_true",
        help="Include image/document tabs in --full (default skips)",
    )
    sp.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel orders to sync (I/O bound; default 1)",
    )
    sp.add_argument("--sleep", type=float, default=0.0, help="Sleep between orders (seconds)")
    sp.set_defaults(func=cmd_sync)

    sp = sub.add_parser("query", help="Query local DB")
    sp.add_argument("text", nargs="?", default=None, help="Free-text query (FTS)")
    sp.add_argument("--db", required=True, help="SQLite DB path")
    sp.add_argument("--plate", default=None)
    sp.add_argument("--person", default=None)
    sp.add_argument("--phone", default=None)
    sp.add_argument("--email", default=None)
    sp.add_argument("--status", default=None, help="Project status (e.g. Karo)")
    sp.add_argument("--damage", default=None, help="Damage category (e.g. KL 2-3)")
    sp.add_argument("--station", type=int, default=None)
    sp.add_argument("--missing-parts", action="store_true")
    sp.add_argument("--after", default=None, help="shop_date >= YYYY-MM-DD")
    sp.add_argument("--before", default=None, help="shop_date <= YYYY-MM-DD")
    sp.add_argument("--finish-after", default=None, help="finish_date >= YYYY-MM-DD")
    sp.add_argument("--finish-before", default=None, help="finish_date <= YYYY-MM-DD")
    sp.add_argument("--limit", type=int, default=200)
    sp.set_defaults(func=cmd_query)

    sp = sub.add_parser("show", help="Show one order from DB")
    sp.add_argument("--db", required=True, help="SQLite DB path")
    sp.add_argument("--id", required=True, type=int)
    sp.add_argument("--all-fields", action="store_true", help="Print all parsed visual_forms_plain fields")
    sp.add_argument("--parts", action="store_true", help="Print parts rows (if synced with --with-parts)")
    sp.add_argument("--sections", action="store_true", help="List stored section snapshots (if synced with --full)")
    sp.add_argument("--section", default=None, help="Show parsed data for one section name")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("find", help="(compat) find <text> in local DB (uses FTS)")
    sp.add_argument("--db", required=True, help="SQLite DB path")
    sp.add_argument("query", help="Search text")
    sp.add_argument("--limit", type=int, default=200)
    sp.set_defaults(func=cmd_find)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    g, rest = _extract_global_args(argv)
    p = build_parser()
    args = p.parse_args(rest)

    cfg = ClientCfg(
        base_url=g.get("base_url", args.base_url),
        cookie_jar_path=g.get("cookie_jar", args.cookie_jar),
        env_path=g.get("env", args.env),
        user=g.get("user", args.user),
        password=g.get("password", args.password),
        timeout=g.get("timeout", args.timeout),
    )
    args._cfg = cfg  # attach

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
