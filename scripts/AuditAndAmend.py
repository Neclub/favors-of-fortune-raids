"""Check staff forum posts and beta EQResource spell pages, then update the site."""

import configparser
import difflib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, quote_plus, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import forum_writeup
from apply_spell_exclusions import main as apply_exclusions
from build_site_data import load_exclusions
from build_spreadsheet import OUT as WORKBOOK, SLOT_RE, cell_text, flatten, main as build_workbook, spell_details
from spell_notes import ensure_writeup_links, load_spell_notes
from sync_word_effects import main as sync_word

RAIDS_PATH = ROOT / "data" / "raids.json"
WRITEUPS_PATH = ROOT / "Info" / "FoF_Raid_Writeups.txt"
POSTS_DIR = ROOT / "Info" / "Forum Posts"
LOG_DIR = ROOT / "Info" / "Audit Logs"
BACKUP_DIR = ROOT / "Info" / "Backups"
GIT_AUTHOR = ["-c", "user.name=Neclub", "-c", "user.email=18217817+Neclub@users.noreply.github.com"]
MARKS = ["•", "◦", "■", "▪"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
INLINE = {"a", "b", "strong", "em", "i", "u", "span", "img", "br", "font", "s"}
BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "blockquote", "pre", "section", "header", "article", "td", "th"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SEARCH = (
    "https://spells.eqresource.com/spellsearch.php?name={}"
    "&class=&level=1&range=greater&expac=&source=beta&searchname=true&strict=true"
)

class Element:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = {key.lower(): value for key, value in attrs}
        self.children = []

    def attr(self, name):
        return self.attrs.get(name, "")


class HtmlTree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("document", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        self._add(tag, attrs, tag.lower() in VOID)

    def handle_startendtag(self, tag, attrs):
        self._add(tag, attrs, True)

    def _add(self, tag, attrs, void):
        node = Element(tag.lower(), attrs)
        self.stack[-1].children.append(node)
        if not void:
            self.stack.append(node)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def parse_html(html):
    parser = HtmlTree()
    parser.feed(html)
    parser.close()
    return parser.root


def element_children(node):
    return [child for child in node.children if isinstance(child, Element)]


def has_class(node, name):
    return name in node.attr("class").split()


def find_first(node, test):
    if isinstance(node, Element) and test(node):
        return node
    if isinstance(node, str):
        return None
    for child in node.children:
        found = find_first(child, test)
        if found is not None:
            return found
    return None


def inner_text(node, skip_lists=False):
    parts = []

    def walk(item):
        for child in item.children:
            if isinstance(child, str):
                parts.append(child)
                continue
            if child.tag in {"script", "style"} or spoiler_content(child):
                continue
            if skip_lists and child.tag in {"ul", "ol"}:
                continue
            if child.tag == "br":
                parts.append("\n")
                continue
            if child.tag in BLOCK:
                parts.append("\n")
            walk(child)
            if child.tag in BLOCK:
                parts.append("\n")

    walk(node)
    return "".join(parts)


def nested_lists(node):
    found = []
    for child in element_children(node):
        if child.tag == "li":
            continue
        if child.tag in {"ul", "ol"}:
            found.append(child)
        else:
            found.extend(nested_lists(child))
    return found


def walk_list(node, depth, lines):
    number = 1
    ordered = node.tag == "ol"
    for child in element_children(node):
        if child.tag != "li":
            continue
        text = inner_text(child, skip_lists=True)
        if not re.sub(r"\s+", "", text):
            for nested in nested_lists(child):
                walk_list(nested, depth, lines)
            continue
        if ordered and depth == 0:
            emit_lines(lines, text, -1, f"{number}. ")
        else:
            emit_lines(lines, text, depth)
        number += 1
        for nested in nested_lists(child):
            walk_list(nested, depth + 1, lines)


def emit_lines(lines, text, depth, prefix=""):
    first = True
    for raw in str(text or "").splitlines():
        line = raw.replace("\u200b", "").replace("\xa0", " ")
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line or line == "\ufffc":
            continue
        if first and prefix:
            lines.append(f"{prefix}{line}")
        elif depth >= 0 and not any(line.startswith(mark) for mark in MARKS):
            lines.append(f"{MARKS[min(depth, 2)]} {line}")
        else:
            lines.append(line)
        first = False


def join_labels(lines):
    labels = {"Raid Giver:", "Quest Giver:", "Requirements:", "Strategy:"}
    joined = []
    index = 0
    while index < len(lines):
        line = lines[index]
        nxt = lines[index + 1] if index + 1 < len(lines) else ""
        continuation = nxt and not any(nxt.startswith(mark) for mark in MARKS) and not nxt.endswith(":")
        if line in labels and continuation and not nxt.startswith("Stage "):
            joined.append(f"{line} {nxt}")
            index += 2
            continue
        joined.append(line)
        index += 1
    return joined


def join_breaks(lines):
    headings = {
        "Background",
        "Overview",
        "Mechanics",
        "Achievements",
        "Strategy",
        "Mechanic",
        "Effect",
        "Counter",
        "Spoiler",
    }

    def heading(line):
        return (
            line in headings
            or line.startswith("Stage ")
            or line.startswith("Key Mechanics")
            or line.startswith("Encounter ")
        )

    joined = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        while index < len(lines):
            nxt = lines[index]
            if any(nxt.startswith(mark) or line.startswith(mark) for mark in MARKS):
                break
            if line.endswith(":") or heading(line) or heading(nxt):
                break
            if nxt.startswith((".", ",", ";", ":", ")", "]")):
                line += nxt
                index += 1
                continue
            if nxt.startswith("("):
                line = f"{line} {nxt}"
                index += 1
                continue
            if (
                " " in line
                and " " not in nxt
                and len(nxt) <= 30
                and nxt[:1].isalpha()
                and not line.endswith((".", "!", "?"))
                and index + 1 < len(lines)
                and lines[index + 1].startswith((".", ",", ";", ":"))
            ):
                line = f"{line} {nxt}"
                index += 1
                continue
            break
        joined.append(line)
    return joined


def spoiler_content(node):
    classes = node.attr("class").lower()
    return "spoiler-content" in classes or "spoilercontent" in classes


def walk_post(node, lines):
    for child in node.children:
        if isinstance(child, str):
            emit_lines(lines, child, -1)
            continue
        if child.tag in {"script", "style", "br"} or spoiler_content(child):
            continue
        if child.tag == "table":
            summary = summary_table(child)
            if summary:
                lines.extend(summary)
                continue
        if child.tag in {"ul", "ol"}:
            walk_list(child, 0, lines)
            continue
        children = element_children(child)
        lists = [item for item in children if item.tag in {"ul", "ol"}]
        only_inline = all(item.tag in INLINE for item in children)
        if not lists and (only_inline or not children):
            emit_lines(lines, inner_text(child), -1)
            continue
        walk_post(child, lines)


def summary_table(table):
    rows = []

    def add_row(row):
        cells = []
        for cell in element_children(row):
            if cell.tag in {"td", "th"}:
                cells.append(re.sub(r"\s+", " ", inner_text(cell)).strip())
        if any(cells):
            rows.append(cells)

    for child in element_children(table):
        if child.tag == "tr":
            add_row(child)
        elif child.tag in {"thead", "tbody", "tfoot"}:
            for row in element_children(child):
                if row.tag == "tr":
                    add_row(row)
    if not rows or rows[0][:2] != ["Mechanic", "Effect"]:
        return None
    lines = ["Mechanic", "Effect"]
    for row in rows[1:]:
        if len(row) >= 2 and row[0] and row[1]:
            lines.extend((row[0], row[1]))
    return lines


def post_body(tree, post):
    article = None
    if post:
        article = find_first(
            tree,
            lambda node: node.tag == "article" and (
                node.attr("id") == f"js-post-{post}" or node.attr("data-content") == f"post-{post}"
            ),
        )
    if article is None:
        article = find_first(tree, lambda node: node.tag == "article" and has_class(node, "message"))
    scope = article or tree
    return find_first(scope, lambda node: has_class(node, "bbWrapper") or has_class(node, "message-body"))


def slice_post_html(html, post):
    start = 0
    if post:
        marker = re.search(
            rf'(?:id="js-post-{re.escape(post)}"|data-content="post-{re.escape(post)}")',
            html,
        )
        if marker:
            start = marker.start()
    match = re.search(r'<div\b[^>]*class="[^"]*\bbbWrapper\b[^"]*"[^>]*>', html[start:], re.I)
    if not match:
        return ""
    open_at = start + match.start()
    depth = 0
    for token in re.finditer(r"<(/?)div\b[^>]*>", html[open_at:], re.I):
        depth += -1 if token.group(1) else 1
        if depth == 0:
            return html[open_at:open_at + token.end()]
    return html[open_at:]


def post_text(html, post):
    fragment = slice_post_html(html, post)
    if not fragment:
        body = post_body(parse_html(html), post)
        if body is None:
            return ""
        lines = []
        walk_post(body, lines)
        return "\n".join(join_breaks(join_labels(lines)))
    body = find_first(parse_html(fragment), lambda node: has_class(node, "bbWrapper"))
    if body is None:
        return ""
    lines = []
    walk_post(body, lines)
    return "\n".join(join_breaks(join_labels(lines)))


class SignInRequired(Exception):
    pass


def thread_id(url):
    match = re.search(r"\.(\d+)(?:/|#|\?|$)", url)
    return match.group(1) if match else ""


def post_id(url):
    match = re.search(r"post-(\d+)", url)
    return match.group(1) if match else ""


def spell_page(spell_id):
    return f"https://spells.eqresource.com/spells.php?id={spell_id}&source=beta"


def normalize(lines):
    cleaned = []
    for line in lines:
        line = forum_writeup.clean_text(line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned.append(line)
    return cleaned


def line_changes(old, new):
    changes = []
    for line in difflib.ndiff(old, new):
        if line.startswith("- ") or line.startswith("+ "):
            changes.append(line)
    return changes


def bullet_dict(bullet):
    return {
        "text": bullet.text,
        "spell": bullet.link_name or "",
        "children": [bullet_dict(child) for child in bullet.children],
    }


def block_dict(item):
    return {
        "kind": item.kind,
        "title": item.title,
        "spellNames": list(item.links),
        "prose": list(item.prose),
        "bullets": [bullet_dict(bullet) for bullet in item.bullets],
    }


def grouped_details(details):
    groups = {}
    for row in details or []:
        groups.setdefault(row["label"], []).append(row["value"])
    return groups


def icon_from_html(html):
    match = re.search(r"""src=["'](spellicons/[^"']+)["']""", html, re.I)
    if not match:
        return ""
    return "https://spells.eqresource.com/" + quote(match.group(1), safe="/")


def page_fields(html):
    text = flatten(html)
    slots = [cell_text(value) for value in SLOT_RE.findall(text)]
    details = spell_details(text)
    return slots, details


def spell_blocked(html):
    low = html.lower()
    premium = "premium members" in low or "only available to premium" in low
    login = "log in" in low or "sign in" in low or "must be logged" in low
    if not premium and not login:
        return False
    slots, details = page_fields(html)
    return not slots and not details


def forum_blocked(html):
    if "bbWrapper" in html or "message-body" in html:
        return False
    low = html.lower()
    return "log in" in low or "sign in" in low or "must be logged" in low


def load_raids():
    return json.loads(RAIDS_PATH.read_text(encoding="utf-8"))


def raid_index(data):
    found = {}
    for tier in data["tiers"]:
        for raid in tier["raids"]:
            found[thread_id(raid["forum"])] = raid
    return found


def writeup_targets(data):
    by_thread = raid_index(data)
    targets = []
    seen = set()
    for raw in WRITEUPS_PATH.read_text(encoding="utf-8").splitlines():
        url = raw.strip()
        if not url or url.startswith("#"):
            continue
        key = thread_id(url)
        raid = by_thread.get(key)
        if not raid or raid["id"] in seen:
            continue
        seen.add(raid["id"])
        targets.append({"raid": raid, "url": url, "post": post_id(url)})
    return targets


def baseline_lines(raid_id):
    path = POSTS_DIR / f"{raid_id}.txt"
    if path.exists():
        return normalize(path.read_text(encoding="utf-8").splitlines()), True
    source_name = forum_writeup.SOURCE_FILES.get(raid_id)
    source = forum_writeup.TEMP / source_name if source_name else None
    if source and source.exists():
        return normalize(forum_writeup.post_lines(source)), False
    return None, False


def save_post(raid_id, lines):
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    (POSTS_DIR / f"{raid_id}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


class Session:
    def __init__(self, cookies):
        self.cookies = cookies

    def get(self, url):
        parts = urlparse(url)
        request = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": cookie_header(self.cookies, parts.hostname or "", parts.path or "/", parts.scheme == "https"),
        })
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            charset = exc.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def has_stage(lines):
    return any(line.startswith("Stage ") or line == "The Echoes" for line in lines)


def thread_page(url):
    return re.sub(r"/page-\d+(?=/|$)", "", url.split("#")[0])


def post_lines_from(html, post):
    lines = normalize(post_text(html, post).splitlines())
    if lines and lines[0] == "#1":
        lines = lines[1:]
    return lines


def fetch_post_lines(session, url, post):
    html = session.get(url)
    if forum_blocked(html):
        raise SignInRequired("EverQuest forums")
    lines = post_lines_from(html, post)
    if post and not has_stage(lines):
        lines = post_lines_from(html, "")
    root = thread_page(url)
    if not has_stage(lines) and root != url.split("#")[0]:
        html = session.get(root)
        if forum_blocked(html):
            raise SignInRequired("EverQuest forums")
        lines = post_lines_from(html, "")
    return lines, html


def apply_writeup(raid, parsed):
    if not parsed["title"] or not parsed["stages"]:
        return False
    raid["title"] = parsed["title"]
    raid["giver"] = parsed["giver"]
    raid["requirements"] = parsed["requirements"]
    raid["stages"] = [
        {"title": title, "blocks": [block_dict(item) for item in items]}
        for title, items in parsed["stages"]
    ]
    raid["summary"] = [
        {"name": name, "effect": effect}
        for name, effect in parsed["summary"]
        if not name.startswith("Stage ")
    ]
    return True


def audit_forums(session, data, log):
    changed_names = []
    forum_changes = 0
    log.append("Forum posts")
    try:
        targets = writeup_targets(data)
    except OSError as exc:
        log.append(f"  Could not read the writeup list: {exc}")
        return changed_names, forum_changes
    signed_out = False
    console(f"Checking {len(targets)} forum posts...")
    for index, target in enumerate(targets, start=1):
        raid = target["raid"]
        label = raid.get("short") or raid["id"]
        if signed_out:
            break
        console(f"Forum {index}/{len(targets)}: {label}")
        try:
            live, _html = fetch_post_lines(session, target["url"], target["post"])
        except SignInRequired:
            message = "  EverQuest forums need a Firefox login. Sign in with Firefox, choose to stay logged in, and run AuditAndAmend again. No forum posts were changed."
            log.append(message)
            console(message.strip())
            signed_out = True
            break
        except Exception as exc:
            log.append(f"  {label}: could not be read ({exc})")
            continue
        if len(live) < 5 or not any(line.startswith("Stage ") or line == "The Echoes" for line in live):
            log.append(f"  {label}: the post text was incomplete, so the site was left unchanged.")
            continue
        previous, _had_snapshot = baseline_lines(raid["id"])
        if previous is None:
            save_post(raid["id"], live)
            log.append(f"  {label}: saved a baseline. The site was not changed because there was no earlier copy.")
            continue
        changes = line_changes(previous, live)
        if not changes:
            save_post(raid["id"], live)
            log.append(f"  {label}: no change")
            continue
        parsed = forum_writeup.parse_lines(live, target["url"])
        if not apply_writeup(raid, parsed):
            log.append(f"  {label}: the new post did not parse into a writeup, so the site was left unchanged.")
            for line in changes:
                log.append(f"    {line}")
            continue
        save_post(raid["id"], live)
        forum_changes += 1
        log.append(f"  {label}: updated")
        for line in changes:
            log.append(f"    {line}")
        changed_names.extend(parsed["names"])
    if not targets:
        log.append("  No forum posts were listed.")
    return changed_names, forum_changes


def spell_entries(data):
    entries = []
    for name, matches in data["spells"].items():
        for match in matches:
            entries.append((name, match))
    return entries


def update_spell(name, entry, html):
    slots, details = page_fields(html)
    if not slots and not details:
        return None
    changes = []
    old_groups = grouped_details(entry.get("details") or [])
    new_groups = grouped_details(details)
    if details:
        labels = list(dict.fromkeys([*old_groups, *new_groups]))
        detail_changes = []
        for label in labels:
            old_values = old_groups.get(label, [])
            new_values = new_groups.get(label, [])
            if old_values == new_values:
                continue
            detail_changes.append((label, " | ".join(old_values), " | ".join(new_values)))
        if detail_changes:
            entry["details"] = details
            changes.extend(detail_changes)
    if slots and slots != (entry.get("slots") or []):
        old_slots = " | ".join(entry.get("slots") or [])
        entry["slots"] = slots
        changes.append(("Slots", old_slots, " | ".join(slots)))
        if entry.get("effect") != slots[0]:
            changes.append(("Effect", entry.get("effect") or "", slots[0]))
            entry["effect"] = slots[0]
    icon = icon_from_html(html)
    if icon and unquote(icon) != unquote(entry.get("icon") or ""):
        changes.append(("Icon", entry.get("icon") or "", icon))
        entry["icon"] = icon
    return [(name, entry["id"], label, old, new) for label, old, new in changes]


def search_spell_ids(session, name):
    html = session.get(SEARCH.format(quote_plus(name)))
    if spell_blocked(html):
        raise SignInRequired("EQResource")
    wanted = name.casefold()
    found = []
    for attrs, inner in re.findall(r"<a\b([^>]*)>(.*?)</a>", html, re.I | re.S):
        href_match = re.search(r"""href\s*=\s*["']([^"']+)["']""", attrs, re.I)
        if not href_match or "spells.php?id=" not in href_match.group(1):
            continue
        href = unquote(href_match.group(1))
        spell_match = re.search(r"id=(\d+)", href)
        if not spell_match:
            continue
        label = re.sub(r"<[^>]+>", "", inner)
        label = re.sub(r"\s+", " ", label).strip()
        if label.casefold() == wanted:
            found.append((spell_match.group(1), href))
    beta = [spell_id for spell_id, href in found if "source=beta" in href]
    pool = beta or [spell_id for spell_id, _href in found]
    ids = []
    for spell_id in pool:
        if spell_id not in ids:
            ids.append(spell_id)
    return ids


def add_spell(data, name, spell_id, html):
    slots, details = page_fields(html)
    if not slots and not details:
        return False
    match = {
        "id": str(spell_id),
        "icon": icon_from_html(html),
        "effect": slots[0] if slots else "",
        "url": spell_page(spell_id),
        "slots": slots,
        "details": details,
    }
    data["spells"].setdefault(name, [])
    if any(item["id"] == match["id"] for item in data["spells"][name]):
        return False
    data["spells"][name].append(match)
    return True


def audit_spells(session, data, extra_names, log):
    log.append("")
    log.append("Spells")
    skip_ids, skip_names = load_exclusions()
    changes = []
    seen = {match["id"] for _name, match in spell_entries(data)}
    pending = [
        (name, entry)
        for name, entry in spell_entries(data)
        if entry["id"] not in skip_ids
        and name not in skip_names
        and (entry.get("effect") or "") != "Place Holder"
    ]
    signed_out = False
    console(f"Checking {len(pending)} spells...")
    for index, (name, entry) in enumerate(pending, start=1):
        if signed_out:
            break
        console(f"Spell {index}/{len(pending)}: {name} ({entry['id']})")
        try:
            html = session.get(entry.get("url") or spell_page(entry["id"]))
        except Exception as exc:
            log.append(f"  {name} {entry['id']}: could not be read ({exc})")
            continue
        if spell_blocked(html):
            message = "  EQResource beta spell data needs a Firefox login. Sign in with Firefox, choose to stay logged in, and run AuditAndAmend again. Remaining spells were left unchanged."
            log.append(message)
            console(message.strip())
            signed_out = True
            break
        try:
            found = update_spell(name, entry, html)
        except Exception as exc:
            log.append(f"  {name} {entry['id']}: could not be read ({exc})")
            continue
        if found is None:
            log.append(f"  {name} {entry['id']}: the spell page had no details, so it was left unchanged.")
            continue
        changes.extend(found)
    note_spells = load_spell_notes()
    if not signed_out:
        # Prefer IDs from Info note files, then fall back to EQResource search.
        pending_names = list(dict.fromkeys([*extra_names, *note_spells]))
        for name in pending_names:
            if name in skip_names:
                continue
            known_ids = [spell_id for spell_id in note_spells.get(name) or [] if spell_id not in skip_ids]
            existing_ids = {match["id"] for match in data["spells"].get(name) or []}
            needed = [spell_id for spell_id in known_ids if spell_id not in existing_ids and spell_id not in seen]
            if name in data["spells"] and not needed:
                if ensure_writeup_links(data, name):
                    changes.append((name, ",".join(known_ids) or "", "Writeup", "", "linked from note file"))
                continue
            if not needed:
                if name in data["spells"]:
                    continue
                try:
                    console(f"Searching EQResource for {name}...")
                    needed = search_spell_ids(session, name)
                except SignInRequired:
                    log.append("  EQResource beta spell data needs a Firefox login. Sign in with Firefox, choose to stay logged in, and run AuditAndAmend again. New spell names were not added.")
                    break
                except Exception as exc:
                    log.append(f"  {name}: search failed ({exc})")
                    continue
                needed = [spell_id for spell_id in needed if spell_id not in skip_ids and spell_id not in seen]
            if not needed:
                if name not in data["spells"]:
                    log.append(f"  {name}: no beta spell page was found")
                continue
            source = "note file" if known_ids else "updated writeup"
            for spell_id in needed:
                try:
                    html = session.get(spell_page(spell_id))
                except Exception as exc:
                    log.append(f"  {name} {spell_id}: could not be read ({exc})")
                    continue
                if spell_blocked(html):
                    log.append("  EQResource beta spell data needs a Firefox login. Sign in with Firefox, choose to stay logged in, and run AuditAndAmend again. New spell names were not added.")
                    signed_out = True
                    break
                if add_spell(data, name, spell_id, html):
                    seen.add(spell_id)
                    changes.append((name, spell_id, "Spell", "", f"added from the {source}"))
            ensure_writeup_links(data, name)
            if signed_out:
                break
    if not changes:
        log.append("  No spell changes")
    else:
        for name, spell_id, label, old, new in changes:
            log.append(f"  {name} {spell_id} {label}")
            if old:
                log.append(f"    - {old}")
            if new:
                log.append(f"    + {new}")
    return changes


def console(text):
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), flush=True)


def write_log(lines):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    path = LOG_DIR / f"AuditAndAmend-{stamp}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def backup_site():
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    dest = BACKUP_DIR / stamp
    dest.mkdir(parents=True)
    shutil.copy2(RAIDS_PATH, dest / "raids.json")
    if WORKBOOK.is_file():
        shutil.copy2(WORKBOOK, dest / WORKBOOK.name)
    if POSTS_DIR.is_dir():
        shutil.copytree(POSTS_DIR, dest / "Forum Posts")
    return dest


def backups():
    if not BACKUP_DIR.is_dir():
        return []
    return sorted((path for path in BACKUP_DIR.iterdir() if (path / "raids.json").is_file()), reverse=True)


def restore_backup(folder):
    shutil.copy2(folder / "raids.json", RAIDS_PATH)
    saved_book = folder / WORKBOOK.name
    if saved_book.is_file():
        WORKBOOK.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(saved_book, WORKBOOK)
    saved_posts = folder / "Forum Posts"
    if saved_posts.is_dir():
        if POSTS_DIR.exists():
            shutil.rmtree(POSTS_DIR)
        shutil.copytree(saved_posts, POSTS_DIR)


def ask_yes(prompt):
    console(prompt)
    try:
        answer = input().strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def git(*args, identity=False):
    command = ["git", *GIT_AUTHOR] if identity else ["git"]
    command.extend(args)
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def publish():
    branch = git("branch", "--show-current")
    name = branch.stdout.strip()
    if branch.returncode != 0 or name != "main":
        console("This folder is not on the main branch, so the site was not published.")
        if branch.stderr.strip():
            console(branch.stderr.strip())
        return 1
    added = git(
        "add",
        "--",
        "data/raids.json",
        "Info/FoF_Raid_Spells.xlsx",
        "Info/FoF_Raid_Mechanics.docx",
        "Info/NonFoF_RaidSpells.txt",
        "Info/Forum Posts",
        "Info/Chronicles of War.txt",
        "Info/Scorn, Queen of Thorns.txt",
        "Info/SirenSisters_Missingspells.txt",
        "js/app.js",
        "scripts/AuditAndAmend.py",
        "scripts/sync_word_effects.py",
        "scripts/apply_spell_exclusions.py",
        "scripts/spell_notes.py",
        "css/site.css",
        "index.html",
    )
    if added.returncode != 0:
        console(added.stderr.strip() or "The site files could not be prepared for publishing.")
        return 1
    if git("diff", "--cached", "--quiet").returncode == 0:
        console("There is nothing new to publish.")
        return 0
    committed = git(
        "commit",
        "-m",
        "Update the site from the latest beta forum posts and spell pages.",
        identity=True,
    )
    if committed.returncode != 0:
        console(committed.stderr.strip() or committed.stdout.strip() or "The changes could not be committed.")
        return 1
    console("Publishing to GitHub...")
    pushed = git("push", "origin", "HEAD")
    if pushed.returncode != 0:
        console(pushed.stderr.strip() or pushed.stdout.strip() or "GitHub did not accept the update.")
        console("The commit is saved on this computer, but it was not published.")
        return 1
    console("Published to GitHub.")
    return 0


def audit(session):
    started = datetime.now().strftime("%Y-%m-%d %H:%M")
    log = [f"AuditAndAmend {started}", ""]
    console("Backing up the current site...")
    backup = backup_site()
    data = load_raids()
    names, forum_changes = audit_forums(session, data, log)
    spell_changes = audit_spells(session, data, names, log)
    changed = bool(forum_changes or spell_changes)
    log.append("")
    if changed:
        RAIDS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        console("Applying spell exclusions...")
        apply_exclusions()
        console("Rebuilding the spreadsheet...")
        build_workbook()
        console("Updating the Word writeup...")
        sync_word()
        log.append("Updated the webpage data, spreadsheet, and Word writeup.")
        log.append(f"Backup: {backup}")
        log.append("Run RestoreBackup.bat to put the site back to this backup.")
    else:
        shutil.rmtree(backup, ignore_errors=True)
        log.append("No changes. The webpage and spreadsheet were left as they were.")
    path = write_log(log)
    console("")
    console("\n".join(log))
    console(f"\nLog: {path}")
    if changed and ask_yes("Publish these changes to GitHub? (Y/N) "):
        publish()
    elif changed:
        console("The changes are saved on this computer. They were not published.")
        console(f"Backup: {backup}")
        console("Run RestoreBackup.bat to put the site back.")
    return 0


def firefox_profile():
    root = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
    ini_path = root / "profiles.ini"
    if not ini_path.is_file():
        return None
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read(ini_path, encoding="utf-8")

    def resolve(path, relative):
        folder = Path(path)
        if relative and not folder.is_absolute():
            folder = root / folder
        return folder if (folder / "cookies.sqlite").is_file() else None

    for section in parser.sections():
        if section.startswith("Install") and parser.has_option(section, "Default"):
            found = resolve(parser.get(section, "Default"), True)
            if found:
                return found
    for section in parser.sections():
        if not parser.has_option(section, "Path"):
            continue
        if parser.has_option(section, "Default") and parser.get(section, "Default") == "1":
            relative = parser.get(section, "IsRelative", fallback="1") == "1"
            found = resolve(parser.get(section, "Path"), relative)
            if found:
                return found
    for section in parser.sections():
        if parser.has_option(section, "Path") and parser.get(section, "Name", fallback="") == "default-release":
            relative = parser.get(section, "IsRelative", fallback="1") == "1"
            found = resolve(parser.get(section, "Path"), relative)
            if found:
                return found
    return None


def load_cookies(profile):
    try:
        return cookie_rows(profile, copied=True)
    except (OSError, sqlite3.OperationalError):
        return cookie_rows(profile, copied=False)


def cookie_rows(profile, copied):
    temp = None
    if copied:
        temp = Path(tempfile.mkdtemp(prefix="fof-cookies-"))
        try:
            for name in ("cookies.sqlite", "cookies.sqlite-wal", "cookies.sqlite-shm"):
                source = profile / name
                if source.is_file():
                    shutil.copy2(source, temp / name)
            if not (temp / "cookies.sqlite").is_file():
                raise FileNotFoundError(profile / "cookies.sqlite")
            database = sqlite3.connect(temp / "cookies.sqlite")
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            raise
    else:
        database = sqlite3.connect(f"{(profile / 'cookies.sqlite').as_uri()}?mode=ro&nolock=1", uri=True)
    try:
        columns = {row[1] for row in database.execute("PRAGMA table_info(moz_cookies)")}
        needed = {"host", "name", "value", "path", "expiry", "isSecure"}
        if not needed.issubset(columns):
            raise sqlite3.OperationalError("Firefox cookie table is missing columns")
        accessed = "lastAccessed" if "lastAccessed" in columns else "expiry"
        rows = database.execute(
            f"""
            SELECT host, name, value, path, expiry, isSecure, {accessed}
            FROM moz_cookies
            WHERE host LIKE '%everquest.com' OR host LIKE '%eqresource.com'
            """
        )
        cookies = []
        now = time.time()
        for host, name, value, path, expiry, secure, last_accessed in rows:
            if expiry and expiry < now:
                continue
            if not name:
                continue
            cookies.append({
                "host": host or "",
                "name": name,
                "value": value or "",
                "path": path or "/",
                "secure": bool(secure),
                "accessed": last_accessed or 0,
            })
    finally:
        database.close()
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)
    cookies.sort(key=lambda cookie: cookie["accessed"], reverse=True)
    return cookies


def cookie_matches(cookie, host, path, secure):
    if cookie["secure"] and not secure:
        return False
    cookie_host = cookie["host"].lower()
    host = host.lower()
    if cookie_host.startswith("."):
        base = cookie_host[1:]
        if host != base and not host.endswith("." + base):
            return False
    elif cookie_host != host:
        return False
    cookie_path = cookie["path"] or "/"
    if cookie_path != "/" and path != cookie_path and not path.startswith(cookie_path.rstrip("/") + "/"):
        return False
    return True


def cookie_header(cookies, host, path, secure):
    chosen = {}
    for cookie in cookies:
        if not cookie_matches(cookie, host, path, secure):
            continue
        if cookie["name"] not in chosen:
            chosen[cookie["name"]] = cookie["value"]
    return "; ".join(f"{name}={value}" for name, value in chosen.items())


def stop(lines):
    for line in lines:
        console(line)
    path = write_log([
        f"AuditAndAmend {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        *lines,
        "",
        "No changes. The webpage and spreadsheet were left as they were.",
    ])
    console(f"Log: {path}")
    return 1


def restore_main():
    found = backups()
    if not found:
        console("There are no backups to restore.")
        return 1
    console("Backups, newest first:")
    for index, path in enumerate(found, start=1):
        console(f"  {index}. {path.name}")
    console("Restore which backup? [1]")
    try:
        answer = input().strip()
    except EOFError:
        answer = ""
    if not answer:
        choice = 1
    elif answer.isdigit():
        choice = int(answer)
    else:
        choice = 0
    if not 1 <= choice <= len(found):
        console("That backup was not restored.")
        return 1
    folder = found[choice - 1]
    try:
        restore_backup(folder)
    except PermissionError:
        console("A site file is open in another program. Close it, then run RestoreBackup again.")
        return 1
    console(f"Restored the site from {folder.name}.")
    if ask_yes("Publish the restored site to GitHub? (Y/N) "):
        return publish()
    console("The restored site is on this computer. It was not published.")
    return 0


def main():
    if "--restore" in sys.argv:
        return restore_main()
    profile = firefox_profile()
    if not profile:
        return stop([
            "Firefox does not have a saved login to read.",
            "Sign in with Firefox and choose to stay logged in, then run AuditAndAmend again.",
        ])
    try:
        cookies = load_cookies(profile)
    except sqlite3.OperationalError:
        return stop([
            "Firefox's saved login could not be read.",
            "Close Firefox, then run AuditAndAmend again.",
        ])
    forum_login = any("everquest.com" in cookie["host"] for cookie in cookies)
    spell_login = any("eqresource.com" in cookie["host"] for cookie in cookies)
    if not forum_login and not spell_login:
        return stop([
            "Firefox has no saved login for the EverQuest forums or EQResource.",
            "Sign in with Firefox and choose to stay logged in, then run AuditAndAmend again.",
        ])
    try:
        return audit(Session(cookies))
    except Exception as exc:
        console(f"AuditAndAmend failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
