"""Parse a Favors of Fortune staff post into raid stages."""

import os
import re
from pathlib import Path

TEMP = Path(os.environ.get("TEMP", "")) / "fof-posts"

SOURCE_FILES = {
    "siren": "05_Tier_1_-_Plane_of_Desire_Raid_1_-_Siren_Sisters_EverQuest_Forums.txt",
    "dipuc": "08_Tier_1_-_Plane_of_Desire_Raid_2_-_Dipuc_General_of_Scorn_EverQuest_Forums.txt",
    "love": "03_love_page1.txt",
    "moruuk": "04_Tier_2_-_Plane_of_Greed_Raid_1_-_Moruuk_and_Sorshkah_EverQuest_Forums.txt",
    "taurlton": "11_Tier_2_-_Plane_of_Greed_Raid_2_-_Taurlton_The_Doorman_EverQuest_Forums_-_Memory_.txt",
    "vazaelle": "10_Tier_2_-_Plane_of_Madness_Raid_1_-_Fractured_Vazaelle_EverQuest_Forums.txt",
    "chronicles": "02_Tier_3_-_Plane_of_Guile_Raid_1_-_Chronicles_of_War_EverQuest_Forums_-_Memory_usa.txt",
    "eriak": "07_Tier_3_Plane_of_Guile_Raid_2_Eriak_Zek_EverQuest_Forums.txt",
    "xev": "06_Tier_3_-_Plane_of_Luck_Raid_1_-_Xev_Tests_Fate_EverQuest_Forums.txt",
}

BULLET_MARKS = {"•": 1, "◦": 2, "■": 3, "▪": 4, "∙": 1}
NAME_RE = re.compile(
    r"[A-Z][A-Za-z'’\-]*(?:(?:\s+(?:(?:of|the|a|an)\s+)*)[A-Z][A-Za-z'’\-]*){0,6}"
)
CAST_RE = re.compile(
    r"\b(?i:casts?|causes|causing|via|incurs|using|uses|casting|followup|spawns|with|for)\s+"
    r"(?i:either\s+)?(" + NAME_RE.pattern + r")"
)
OR_RE = re.compile(r"\b(?i:or)\s+(" + NAME_RE.pattern + r")")
WITH_RE = re.compile(r"\b(?i:afflicted with|hit with)\s+(" + NAME_RE.pattern + r")")
PAREN_RE = re.compile(r"\((" + NAME_RE.pattern + r")\)")

EFFECT_RE = re.compile(
    r"(?i)^("
    r"occurs|continues|continue\b|applies|deals|deal\b|reduces|reduce\b|"
    r"targets|target\b|players|player\b|if\b|after\b|moving|spawns|spawn\b|"
    r"summoned|this\b|the\b|a\b|an\b|when\b|once\b|only\b|while\b|lasts|"
    r"cannot|starts|will\b|dot\b|poison|frontal|back-to-back|short\b|"
    r"greatly|removes|don.?t|three\b|more\b|dmg\b|at\b|each\b|gores|aoe\b|"
    r"massive|stacking|shield\b|jump\b|relatively|random\b|failure|slowly|"
    r"orders|that\b|hitting|increased|decreases|decreased|melee\b|caster\b|"
    r"hybrid\b|lvl\b|escalating|drains|becomes|can\b|reflects|targeted|"
    r"every\b|turn\b|similar|four\b|in\b|anyone|picks|creates|fires|"
    r"teleports|pulse|protects|throughout|remaining|goons|scattered|"
    r"these\b|who\b|allow|avoid|keep\b|watch\b|there\b|one\b|two\b|no\b|"
    r"it\b|he\b|damage\b|attacks|focuses|throws|improves|rapidly|marks|"
    r"uses\b|highest|light\b|cone\b|pbaoe|single\b|inflicts|several|"
    r"pools\b|corruption|increases|absorbs|transfers|taking|"
    r"help\b|as\b|all\b|however|using\b|groups\b|sometimes|timing|"
    r"failing|area\b|counter-|eriak\b|doom\b|charmed|adds\b|most\b|"
    r"for\b|kill\b|solve|eliminate|tank\b|puzzle|weapons|visual|"
    r"combines|copy\b|intensity|immunit|netted|10\b|5\b|4\b|3\b|2\b|1\b|"
    r"~|hp\b|xev\b|moruuk\b|wagerlings|amalgamations|communication|"
    r"adapt|manage|cleanup|prepare|victory|60\b|slowly|that\b|"
    r"casts|curses|knocks|singles|she\b|silences|continue to"
    r")"
)

ADD_NAMES = {
    "books",
    "paper cyclones",
    "denizens",
    "hulking bruiser",
    "hulking bodyguard",
    "quicksand golem",
    "lava golems",
    "lava golem",
    "wagerlings",
    "bramble sentinels",
    "repair crew",
    "builders",
    "steamworks obliterator",
    "tick-tock bomb",
    "lucksworn",
    "lucksworn greed",
    "lucksworn doubt",
    "lucksworn hope",
    "lucksworn control",
    "lucksworn bookie",
    "fans and devotees",
    "statues",
    "harassers and bruisers",
    "scorn-touched satyrs and scornful dryads",
    "lifelike masterpiece",
    "superior wagerlings",
}

CATEGORIES = {
    "core boss mechanics",
    "the weapon system",
    "add management",
    "weapon transitions",
    "the water sort puzzle",
    "anti-archetype adds",
    "increased puzzle pressure",
    "escalating threats",
    "critical phase",
    "critical strategy",
    "the weapon trap",
    "add explosions",
    "strategic considerations",
    "charming strategy (the desire switch)",
    "the problem - greed gateways",
    "spells",
    "greed coins",
    "'helpful' banker",
    "helpful banker",
    "doom mechanic",
}

SPAWN_RE = re.compile(
    r"(?i)^(spawn every|spawns every|spawns ever|summoned every|"
    r"continue to spawn|jump into|stationary)\b"
)
PARENT_NAME_RE = re.compile(
    r"(?i)(following|one of|either\b|spells are cast|spells \(selected|random effects will)"
)
CC_SUFFIX = {"mezzable", "charmable", "rootable"}
CLASS_LEFT = {"melee", "caster", "hybrid"}
STOP_NAMES = {
    "help",
    "spells",
    "stage",
    "this",
    "one",
    "two",
    "three",
    "the",
    "players",
    "player",
    "eriak",
    "xev",
    "moruuk",
    "books",
}


def clean_text(text):
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\ufffc", "")
    text = text.replace("\xa0", " ")
    return text


def spell_url(name):
    return SPELL.format(quote_plus(name.strip()))


def spell_page(spell_id):
    return f"https://spells.eqresource.com/spells.php?id={spell_id}&source=beta"


def load_lookup():
    global LOOKUP
    path = TEMP / "spell_lookup.json"
    if path.exists():
        LOOKUP = json.loads(path.read_text(encoding="utf-8"))
    else:
        LOOKUP = {}


def icon_file(icon_src):
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    leaf = icon_src.split("/")[-1].replace(" ", "_")
    if leaf.lower().endswith(".jpe"):
        leaf = leaf[:-4] + ".jpg"
    dest = ICON_DIR / leaf
    if not dest.exists() or dest.stat().st_size < 20:
        url = "https://spells.eqresource.com/" + icon_src.replace(" ", "%20")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            dest.write_bytes(response.read())
    return dest


def matches_for(name):
    info = LOOKUP.get(name)
    if not info:
        return []
    return info.get("matches") or []


def bullet_level(line):
    if not line:
        return None
    mark = line[0]
    if mark in BULLET_MARKS:
        return BULLET_MARKS[mark]
    return None


def bullet_text(line):
    return line[1:].strip()


def is_effect(text):
    stripped = text.strip()
    if not stripped:
        return True
    if stripped[0].isdigit():
        return True
    if stripped.lower().startswith("hp >"):
        return True
    if EFFECT_RE.match(stripped):
        return True
    if len(stripped) > 90 and " - " not in stripped[:40]:
        return True
    return False


def word_count(line):
    return len(re.findall(r"[A-Za-z0-9']+", line))


def is_label(line):
    if bullet_level(line) is not None:
        return False
    if len(line) > 95 or word_count(line) > 11:
        return False
    if line.endswith((".", "!", "?")):
        return False
    if line.startswith(("This is a 54", "**", "{", "Last edited", "Reactions")):
        return False
    if re.match(r"(?i)^(continue to|several |scattered |this is |xev is |say that|when eriak)", line):
        return False
    if "post raid story" in line.lower() or "Secret" in line:
        return False
    if line in {"Mechanic", "Effect", "Like", "Report", "Share", "New"}:
        return False
    low = line.lower()
    if low.startswith("remove formatting") or low.startswith("font "):
        return False
    return True


def is_structural_keyword(line):
    low = line.lower().rstrip(":")
    return low in {
        "overview",
        "background",
        "encounter overview",
        "mechanics",
        "achievements",
        "key mechanics summary",
    } or line.startswith("Strategy:") or line.startswith("Stage ") or line == "The Echoes"


def strip_colon(name):
    return name.strip().rstrip(":").strip()


def strip_wrapping_quotes(name):
    if len(name) >= 2 and name[0] in "'\"“" and name[-1] in "'\"”":
        return name[1:-1].strip()
    return name


def looks_like_actor_prefix(left):
    if len(left) > 28:
        return False
    if any(ch.isdigit() for ch in left):
        return False
    # Ability phrases use "of", "the", or several content words.
    low = left.lower()
    if low.startswith(("the ", "a ", "aura", "damage", "back", "not ")):
        return False
    return True


def link_targets(title):
    """Return (display_title, [spell names to link])."""
    display = strip_colon(title)
    core = display
    match = re.match(r"^(.+?)\s+\((.+)\)\s*$", core)
    if match and "roll the dice" not in match.group(1).lower():
        core = match.group(1).strip()
    if re.search(r"\s+or\s+", core, re.I):
        parts = [strip_wrapping_quotes(p.strip()) for p in re.split(r"\s+or\s+", core, flags=re.I)]
        if all(" " in part for part in parts):
            return display, [p for p in parts if p]
    if " / " in core:
        parts = [strip_wrapping_quotes(p.strip()) for p in core.split(" / ")]
        return display, [p for p in parts if p]
    split = re.match(r"^(.+?) - (.+)$", core)
    if split and looks_like_actor_prefix(split.group(1)):
        ability = strip_wrapping_quotes(split.group(2).strip())
        return display, [ability]
    return display, [strip_wrapping_quotes(core)]


def is_add(name, first_bullet):
    low = strip_colon(name).lower()
    if low in ADD_NAMES or low in CATEGORIES:
        return True
    if first_bullet and SPAWN_RE.match(first_bullet):
        return True
    if re.search(r"(?i)\b(bruiser|sentinel|wagerling|bodyguard)\b", low):
        return True
    return False


def is_category(name):
    return strip_colon(name).lower() in CATEGORIES


def looks_like_title(text):
    words = re.split(r"[\s:/]+", text.strip())
    small = {"of", "the", "a", "an", "or", "and", "&"}
    caps = 0
    for word in words:
        word = word.strip("',.()\"")
        if not word or word in small:
            continue
        if not word[0].isupper():
            return False
        caps += 1
    return 1 <= caps <= 8


def dash_name(text):
    split = re.match(r"^([A-Z][^.]{0,45}?) - (.+)$", text.strip())
    if not split:
        return None
    left, right = split.group(1).strip(), split.group(2).strip()
    if left.lower() in CLASS_LEFT or right.lower() in CC_SUFFIX or is_effect(left):
        return None
    if not looks_like_title(left):
        return None
    return strip_wrapping_quotes(left)


def name_from_bullet(text):
    """If this bullet is a spell name, return the name. Otherwise None."""
    text = text.strip()
    if is_effect(text) or text.lower().startswith("hp >"):
        return None
    dashed = dash_name(text)
    if dashed:
        return dashed
    if looks_like_title(text) and len(text) <= 55 and not text.endswith("."):
        return strip_wrapping_quotes(text)
    return None


def parent_invites_names(parent_text):
    return bool(parent_text and PARENT_NAME_RE.search(parent_text))


class Bullet:
    def __init__(self, text, level):
        self.text = text
        self.level = level
        self.children = []
        self.link_name = None


class Item:
    def __init__(self, kind, title, links, prose, bullets):
        self.kind = kind
        self.title = title
        self.links = links
        self.prose = prose
        self.bullets = bullets


def consume_bullets(lines, index, min_level):
    nodes = []
    while index < len(lines):
        level = bullet_level(lines[index])
        if level is None or level < min_level:
            break
        if level > min_level:
            break
        node = Bullet(bullet_text(lines[index]), level)
        index += 1
        if index < len(lines):
            child_level = bullet_level(lines[index])
            if child_level is not None and child_level > level:
                node.children, index = consume_bullets(lines, index, child_level)
        nodes.append(node)
    return nodes, index


def annotate_bullets(bullets, parent_text):
    building = bool(parent_text and re.search(r"(?i)\b(build|creations)\b", parent_text))
    for bullet in bullets:
        dashed = dash_name(bullet.text)
        invited = (not building) and (parent_invites_names(parent_text) or bool(bullet.children))
        if dashed and dashed.lower() not in STOP_NAMES:
            bullet.link_name = dashed
        elif invited:
            candidate = name_from_bullet(bullet.text)
            if candidate and candidate.lower() not in STOP_NAMES and looks_like_title(candidate):
                bullet.link_name = candidate
        annotate_bullets(bullet.children, bullet.text)
    nest_name_effects(bullets)


def nest_name_effects(bullets):
    """Attach a following effect line to a named spell that has no children yet."""
    index = 0
    kept = []
    while index < len(bullets):
        bullet = bullets[index]
        if bullet.link_name and not bullet.children:
            index += 1
            while index < len(bullets) and not bullets[index].link_name and is_effect(bullets[index].text) and not bullets[index].children:
                bullet.children.append(bullets[index])
                index += 1
            kept.append(bullet)
            continue
        kept.append(bullet)
        index += 1
    bullets[:] = kept


def first_bullet_text(bullets):
    if not bullets:
        return ""
    return bullets[0].text


def parse_region(lines):
    items = []
    index = 0
    while index < len(lines):
        line = lines[index]
        low = line.lower().rstrip(":")
        if low in {"overview", "background", "encounter overview"}:
            index += 1
            while index < len(lines) and not is_structural_keyword(lines[index]) and not is_label(lines[index]) and bullet_level(lines[index]) is None:
                index += 1
            continue
        if line == "Mechanics" or line.startswith("Strategy:"):
            index += 1
            continue
        if not is_label(line):
            index += 1
            continue
        raw_name = line
        index += 1
        prose = []
        while index < len(lines) and bullet_level(lines[index]) is None and not is_label(lines[index]) and not is_structural_keyword(lines[index]) and not lines[index].startswith("Strategy:"):
            prose.append(lines[index])
            index += 1
        bullets = []
        if index < len(lines) and bullet_level(lines[index]) is not None:
            bullets, index = consume_bullets(lines, index, bullet_level(lines[index]))
        annotate_bullets(bullets, "")
        title, links = link_targets(raw_name)
        fb = first_bullet_text(bullets)
        if is_category(title) or (is_add(title, fb) and title.lower() in ADD_NAMES or is_add(title, fb)):
            # Categories and adds stay unlinked. Spawn-pattern adds too.
            if is_category(title) or is_add(title, fb):
                kind = "add" if is_add(title, fb) and not is_category(title) else "group"
                if is_add(title, fb) and not is_category(title):
                    kind = "add"
                elif is_category(title):
                    kind = "group"
                else:
                    kind = "add"
                items.append(Item(kind, title, [], prose, bullets))
                continue
        if not bullets and not prose:
            items.append(Item("actor", title, [], [], []))
            continue
        if not bullets and prose:
            blob = " ".join(prose)
            flavor = re.match(
                r"(?i)^(as a|as the|the first|say that|hatchet|throughout|goons that|"
                r"more than|the banker|the general|remaining |xev thought|three gateways|"
                r"eriak is|xev is|several |this is )",
                blob,
            )
            if flavor or len(blob) > 180:
                items.append(Item("actor", title, [], prose, []))
            else:
                items.append(Item("mechanic", title, links, prose, []))
            continue
        # Has bullets. Actor prefixes become part of the displayed title;
        # the ability portion is what gets linked.
        if is_add(title, fb):
            items.append(Item("add", title, [], prose, bullets))
        else:
            items.append(Item("mechanic", title, links, prose, bullets))
    return items


def post_lines(path):
    text = clean_text(path.read_text(encoding="utf-8"))
    start = text.find("#1")
    if start < 0:
        return []
    body = text[start:]
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Last edited") or line.startswith("Reactions:") or line.startswith("Remove formatting"):
            break
        if re.match(r"(?i)^like\b", line) or line.startswith("#2") or line == "Add bookmark":
            break
        if line in {"Report", "Share", "New", "Preview"}:
            continue
        lines.append(line)
    # Drop the #1 marker.
    if lines and lines[0] == "#1":
        lines = lines[1:]
    return lines


def split_stages(lines):
    """Return header lines and a list of (stage_title, stage_lines)."""
    stages = []
    header = []
    current_title = None
    current = []
    mode = "header"
    summary = []
    in_summary = False
    skipping_achievements = False
    for line in lines:
        if line.startswith("Achievements") or line.startswith("Complete additional challenges"):
            skipping_achievements = True
            in_summary = False
            continue
        if line == "Key Mechanics Summary":
            skipping_achievements = False
            in_summary = True
            continue
        if line.startswith("Spoiler:"):
            break
        if skipping_achievements:
            continue
        if in_summary:
            if line in {"Mechanic", "Effect"}:
                continue
            summary.append(line)
            continue
        if line.startswith("Stage ") or line == "The Echoes":
            if current_title is not None:
                stages.append((current_title, current))
            elif current:
                header.extend(current)
            current_title = line
            current = []
            mode = "stage"
            continue
        if mode == "header":
            header.append(line)
        else:
            current.append(line)
    if current_title is not None:
        stages.append((current_title, current))
    return header, stages, summary


def header_fields(header_lines):
    title = ""
    giver = ""
    requirements = ""
    for line in header_lines:
        if line.startswith("Raid Giver:") or line.startswith("Quest Giver:"):
            giver = line
        elif line.startswith("Requirements:"):
            requirements = line
        elif not title and is_label(line) and "giver" not in line.lower():
            title = line
    return title, giver, requirements


def parse_summary(summary_lines):
    pairs = []
    index = 0
    while index + 1 < len(summary_lines):
        name = summary_lines[index]
        effect = summary_lines[index + 1]
        if word_count(name) > 10 or name.endswith("."):
            break
        pairs.append((name, effect))
        index += 2
    return pairs


def collect_names(items, extra):
    names = set(extra)
    for item in items:
        if item.kind == "mechanic":
            names.update(item.links)
        walk_names(item.bullets, names)
    cleaned = set()
    for name in names:
        name = name.strip()
        if len(name) < 4:
            continue
        if name.lower() in STOP_NAMES:
            continue
        cleaned.add(name)
    return sorted(cleaned, key=len, reverse=True)


def walk_names(bullets, names):
    for bullet in bullets:
        if bullet.link_name:
            names.add(bullet.link_name)
        walk_names(bullet.children, names)


def extract_inline_names(text):
    found = []
    for regex in (CAST_RE, WITH_RE, PAREN_RE):
        for match in regex.finditer(text):
            prefix = text[max(0, match.start(1) - 12):match.start(1)].lower()
            name = match.group(1).strip(" .,:;")
            if re.search(r"(for|spawns)\s+$", prefix) and " " not in name:
                continue
            found.append(name)
    # "or Name" only counts when a cast/cause introduced the clause.
    if re.search(r"(?i)\b(casts?|causes|causing)\b", text):
        for match in OR_RE.finditer(text):
            found.append(match.group(1))
    kept = []
    for name in found:
        name = name.strip(" .,:;")
        low = name.lower()
        if not looks_like_title(name):
            continue
        if low in STOP_NAMES or low.startswith(("one ", "a ", "an ", "the ", "their ", "each ")):
            continue
        if low in {"for", "with", "uses", "via"}:
            continue
        if " " not in name and low in {"for", "doom", "slam", "power"}:
            continue
        if len(name) < 4:
            continue
        # "for" as a connector is only useful when the spell name has a space,
        # except single distinctive buff names already handled elsewhere.
        kept.append(name)
    return kept



def lines_from_text(text):
    """Return the staff post lines, dropping the forum chrome around #1."""
    text = clean_text(text)
    start = text.find("#1")
    body_text = text[start:] if start >= 0 else text
    lines = []
    for raw in body_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Last edited") or line.startswith("Reactions:") or line.startswith("Remove formatting"):
            break
        if re.match(r"(?i)^like\b", line) or line.startswith("#2") or line == "Add bookmark":
            break
        if line in {"Report", "Share", "New", "Preview"}:
            continue
        lines.append(line)
    if lines and lines[0] == "#1":
        lines = lines[1:]
    return lines


def parse_lines(lines, url=""):
    header_lines, stages, summary_lines = split_stages(lines)
    title, giver, requirements = header_fields(header_lines)
    parsed_stages = []
    all_items = []
    for stage_title, stage_lines in stages:
        items = parse_region(stage_lines)
        parsed_stages.append((stage_title, items))
        all_items.extend(items)
    summary = parse_summary(summary_lines)
    extra = []
    for name, _effect in summary:
        if name.startswith("Stage "):
            continue
        _display, links = link_targets(name)
        extra.extend(links)
    return {
        "title": title,
        "giver": giver,
        "requirements": requirements,
        "url": url,
        "stages": parsed_stages,
        "summary": summary,
        "names": collect_names(all_items, extra),
    }
