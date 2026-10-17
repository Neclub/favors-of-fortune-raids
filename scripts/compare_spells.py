"""Download live, test, or beta spell files and compare them to the website."""

import csv
import html
import io
import json
import lzma
import math
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAIDS = ROOT / "data" / "raids.json"
DOWNLOADS = ROOT / "Info" / "Spell Downloads"
REPORTS = ROOT / "Info" / "Spell Compare"

USER_AGENT = "Quicksilver Player/1.0.3.183"
SERVERS = {"live": "", "test": "-test", "beta": "-beta"}
SPELL_FILES = (
    "spells_us.txt",
    "spells_us_str.txt",
    "dbstr_us.txt",
    "SpellStackingGroups.txt",
)

SKILLS = {5: "Alteration", 14: "Conjuration", 24: "Evocation", 52: "Tiger Claw", 98: "Melee"}
TARGETS = {
    2: "Caster AE",
    4: "Caster PB",
    5: "Single",
    6: "Self",
    8: "Target AE",
    13: "Lifetap",
    32: "Hatelist",
    42: "Directional AE",
    44: "Frontal AE",
}
RESISTS = {
    0: "Unresistable",
    1: "Magic",
    2: "Fire",
    3: "Cold",
    4: "Poison",
    5: "Disease",
    6: "Lowest",
    7: "Average",
    8: "Physical",
    9: "Corruption",
}
# Effects whose base is another spell id, shown on the site by name rather than number.
CAST_SPAS = {85, 289, 323, 373, 387, 407, 427}
# Limit effects shown as words ("Limit Spells", "Limit Type") rather than their packed values.
LIMIT_SPAS = {385, 460}
# Effects the site names without printing the raw base.
WORD_SPAS = {
    96: "Silence",
    99: "Root",
    191: "Silence",
    376: "Fling",
}
STACK_TYPES = {
    1: "One per Player (Equal or Greater)",
    2: "Only One (Equal or Greater)",
    4: "Only One (Greater)",
    6: "Only One (Never Overwrite)",
    7: "One per Player (Always Overwrite)",
    8: "Only One (Always Overwrite)",
}
CLASSES = [
    "Warrior",
    "Cleric",
    "Paladin",
    "Ranger",
    "Shadow Knight",
    "Druid",
    "Monk",
    "Bard",
    "Rogue",
    "Shaman",
    "Necromancer",
    "Wizard",
    "Magician",
    "Enchanter",
    "Beastlord",
    "Berserker",
]
DEITIES = [
    "Agnostic",
    "Bertoxulous",
    "Brell Serilis",
    "Cazic-Thule",
    "Erollisi Marr",
    "Bristlebane",
    "Innoruuk",
    "Karana",
    "Mithaniel Marr",
    "Prexus",
    "Quellious",
    "Rallos Zek",
    "Rodcet Nife",
    "Solusek Ro",
    "The Tribunal",
    "Tunare",
    "Veeshan",
]
DATA_COLUMNS = [
    "Spell",
    "Spell ID",
    "Classes",
    "Deity",
    "Icon",
    "In Game Description",
    "Cast by You",
    "Cast by Other",
    "Land on You",
    "Land on Other",
    "Wear off",
    "Mana",
    "Endurance",
    "Endurance Upkeep",
    "Casting Time",
    "Recast Time",
    "Spell Bar Lockout",
    "Duration",
    "Duration Formula",
    "Duration Cap",
    "Skill",
    "Target",
    "Range",
    "Min Range",
    "AE Range",
    "AE Waves",
    "Max Targets",
    "Range Mod",
    "Spell Type",
    "Resist",
    "Resist Mod",
    "Min Resist",
    "Max Resist",
    "Resist Per Level",
    "Resist Cap",
    "Dispellable",
    "Focusable",
    "Interruptible",
    "Reflectable",
    "Partial Resist",
    "Spell DS",
    "Push Back",
    "Push Up",
    "Viral",
    "Hate Mod",
    "Hate Override",
    "Max Crit",
    "Stacking",
    "Spell Line",
    "Spell Group",
    "Rank",
    "Category",
    "Timer ID",
    "Max Hits",
    "Max Hits Type",
    "Restrictions",
    "Consumes",
    "Focus Items",
    "Recourse",
    "Song Window",
    "MGB",
    "NPC File",
    "Effects",
    "Notes",
]
MAX_HITS_TYPES = {
    1: "Incoming Hit Attempts",
    2: "Outgoing Hit Attempts",
    3: "Incoming Spells",
    4: "Outgoing Spells",
    5: "Outgoing Hit Successes",
    6: "Incoming Hit Successes",
    7: "Matching Spells",
    8: "Incoming Hits Or Spells",
    9: "Reflected Spells",
    10: "Defensive Proc Casts",
    11: "Offensive Proc Casts",
    13: "Incoming Hits Or Spells Or DS",
    14: "Outgoing Hits Affected By Buff",
    15: "Tradeskill Combines",
}

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
ICON_RE = re.compile(r"spellicons/(-?\d+)")
PAREN_RE = re.compile(r"\((?:v\d+|Before|After|Incremental|Scales)[^)]*\)")
RANGE_RE = re.compile(r"1%\s+to\s+")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SERVERS:
        print("Usage: compare_spells.py live|test|beta", file=sys.stderr)
        return 1
    server = sys.argv[1]
    folder = DOWNLOADS / server
    try:
        download_server(server, folder)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(exc)
        return 1
    spells = load_spells(folder / "spells_us.txt")
    strings = load_strings(folder / "spells_us_str.txt")
    text = load_dbstr(folder / "dbstr_us.txt")
    stacking = load_stacking(folder / "SpellStackingGroups.txt", text.get(40, {}))
    rows, changed, unchanged, missing = compare_site(
        spells, strings, text.get(6, {}), text.get(5, {}), text.get(27, {}), stacking
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    dest = REPORTS / f"{server}-{date.today().isoformat()}.csv"
    with dest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Spell", "Spell ID", "Field", "Website", "Downloaded"])
        writer.writerows(rows)
    data_dest = REPORTS / f"{server}-{date.today().isoformat()}-data.csv"
    data_rows = spell_data_rows(
        spells, strings, text.get(6, {}), text.get(5, {}), text.get(27, {}), stacking
    )
    with data_dest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DATA_COLUMNS)
        writer.writeheader()
        writer.writerows(data_rows)
    print(f"{server}: {changed} changed, {unchanged} unchanged, {missing} missing")
    print(f"wrote {dest}")
    print(f"wrote {data_dest}")
    return 0


def download_server(server, folder):
    suffix = SERVERS[server]
    manifest_url = (
        "http://manifest.patch.daybreakgames.com/patch/sha/manifest/eq/"
        f"eq-en{suffix}/live/eq-en{suffix}.sha.soe"
    )
    print(f"Manifest {manifest_url}")
    try:
        manifest = fetch(manifest_url)
    except urllib.error.HTTPError as exc:
        print(f"Could not download the {server} manifest: {manifest_url}")
        raise exc
    try:
        manifest = decompress_lzma(manifest)
    except lzma.LZMAError:
        pass
    folder.mkdir(parents=True, exist_ok=True)
    for name in SPELL_FILES:
        info = find_manifest_file(manifest, name)
        if info is None:
            raise FileNotFoundError(f"{name} is not in the {server} manifest: {manifest_url}")
        url = "http://eq.patch.daybreakgames.com/patch/sha/eq/eq.sha.zs/" + info["path"]
        print(f"Downloading {name}")
        blob = fetch(url)
        (folder / name).write_bytes(decompress_lzma(blob))
        print(f"  saved {folder / name}")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def decompress_lzma(blob):
    return lzma.decompress(blob, format=lzma.FORMAT_ALONE)


def find_manifest_file(manifest, name):
    """Read one LaunchPad file record the way eqspellparser's Patcher does."""
    text = manifest.decode("latin-1")
    pos = text.find(name)
    if pos < 2:
        return None
    stream = io.BytesIO(manifest)
    stream.seek(pos - 2)
    info = {"name": "", "path": ""}
    while True:
        kind = stream.read(1)
        if not kind:
            break
        kind = kind[0]
        if kind == 1:
            info["name"] = read_string(stream)
        elif kind == 2:
            read_int(stream)
        elif kind == 3:
            read_int(stream)
        elif kind == 4:
            read_int(stream)
        elif kind == 8:
            read_int(stream)
        elif kind == 10:
            stream.seek(read_size(stream), io.SEEK_CUR)
        elif kind == 18:
            length = stream.read(1)[0]
            digest = stream.read(length)
            info["path"] = hash_path(digest)
        else:
            break
    if info["name"] != name or not info["path"]:
        return None
    return info


def read_string(stream):
    length = stream.read(1)[0]
    return stream.read(length).decode("utf-8", errors="replace").rstrip("\0")


def read_int(stream):
    length = stream.read(1)[0]
    raw = stream.read(length)
    value = 0
    for byte in raw:
        value = (value << 8) + byte
    return value


def read_size(stream):
    size = stream.read(1)[0]
    if size == 255:
        size = 0
        for _ in range(4):
            size = (size << 8) + stream.read(1)[0]
    elif size >= 128:
        size = ((size & 0x7F) << 8) + stream.read(1)[0]
    return size


def hash_path(digest):
    text = digest.hex()
    text = text[:5] + "/" + text[5:]
    return text[:2] + "/" + text[2:]


def load_spells(path):
    spells = {}
    with path.open(encoding="cp1252", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            cols = line.rstrip("\r\n").split("^")
            if len(cols) < 160 or not cols[0].isdigit():
                continue
            spells[int(cols[0])] = parse_spell(cols)
    return spells


def parse_spell(cols):
    return {
        "id": int(cols[0]),
        "name": cols[1],
        "range": number(cols[4]),
        "ae_range": number(cols[5]),
        "push_back": number(cols[6]),
        "push_up": number(cols[7]),
        "cast_ms": number(cols[8]),
        "duration_formula": number(cols[11]),
        "duration_cap": number(cols[12]),
        "rest_ms": number(cols[9]),
        "recast_ms": number(cols[10]),
        "mana": number(cols[14]),
        "beneficial": number(cols[28]) != 0,
        "resist": number(cols[29]),
        "target": number(cols[30]),
        "skill": number(cols[32]),
        "icon": number(cols[75]),
        "resist_mod": number(cols[78]),
        "interruptable": not flag(cols[77]),
        "description_id": number(cols[85]),
        "category_id": number(cols[86]),
        "subcategory_id": number(cols[87]),
        "endurance": number(cols[96]),
        "timer_id": number(cols[97]),
        "hate_override": number(cols[99]),
        "max_hits_type": number(cols[101]),
        "max_hits": number(cols[102]),
        "no_dispell": flag(cols[111]),
        "viral_min": number(cols[116]),
        "viral_max": number(cols[117]),
        "viral_range": number(cols[126]),
        "max_targets": number(cols[142]),
        "spell_line_id": number(cols[164]) if len(cols) > 164 else 0,
        "npc": cols[3],
        "ae_duration": number(cols[13]),
        "reagents": [
            (number(cols[15 + index]), number(cols[19 + index]))
            for index in range(4)
            if number(cols[15 + index]) > 0
        ],
        "focus_items": [number(cols[23 + index]) for index in range(4) if number(cols[23 + index]) > 0],
        "zone": number(cols[33]),
        "levels": [number(cols[36 + index]) for index in range(16)],
        "cancel_on_sit": flag(cols[56]),
        "deities": [flag(cols[57 + index]) for index in range(17)],
        "recourse_id": number(cols[81]),
        "partial_resist": flag(cols[82]),
        "song_window": flag(cols[84]),
        "feedbackable": flag(cols[90]),
        "reflectable": flag(cols[91]),
        "hate_mod": number(cols[92]),
        "resist_per_level": number(cols[93]),
        "resist_cap": number(cols[94]),
        "endurance_upkeep": number(cols[100]),
        "mgb": flag(cols[110]),
        "sneaking": flag(cols[121]),
        "duration_frozen": flag(cols[125]),
        "no_sanctification": flag(cols[134]),
        "target_restrict": number(cols[136]),
        "cast_out_of_combat": not flag(cols[138]),
        "crit_override": number(cols[141]),
        "caster_restrict": number(cols[144]),
        "persist_after_death": flag(cols[148]),
        "range_close_dist": number(cols[151]),
        "range_close_mult": decimal(cols[152]),
        "range_far_dist": number(cols[153]),
        "range_far_mult": decimal(cols[154]),
        "min_range": number(cols[155]),
        "cast_in_fast_regen": flag(cols[158]),
        "group_id": number(cols[132]),
        "rank": number(cols[133]),
        "min_resist": number(cols[114]),
        "max_resist": number(cols[115]),
        "cone_start": number(cols[119]),
        "cone_end": number(cols[120]),
        "not_focusable": flag(cols[122]),
        "blockable": not flag(cols[130]),
        "no_remove": flag(cols[156]),
        "beta_only": flag(cols[159]),
        "effects": parse_effects(cols[-1]),
    }


def parse_effects(blob):
    effects = []
    if "|" not in blob:
        return effects
    for part in blob.split("$"):
        bits = part.split("|")
        if len(bits) < 6:
            continue
        effects.append(
            {
                "slot": number(bits[0]),
                "spa": number(bits[1]),
                "base": number(bits[2]),
                "limit": number(bits[3]),
                "formula": number(bits[4]),
                "max": number(bits[5]),
            }
        )
    return effects


def load_strings(path):
    strings = {}
    if not path.exists():
        return strings
    with path.open(encoding="cp1252", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            cols = line.rstrip("\r\n").split("^")
            if not cols[0].isdigit():
                continue
            strings[int(cols[0])] = {
                "cast_self": cols[1] if len(cols) > 1 else "",
                "cast_other": cols[2] if len(cols) > 2 else "",
                "land_self": cols[3] if len(cols) > 3 else "",
                "land_other": cols[4] if len(cols) > 4 else "",
                "wear_off": cols[5] if len(cols) > 5 else "",
            }
    return strings


def load_dbstr(path):
    tables = {}
    if not path.exists():
        return tables
    with path.open(encoding="cp1252", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            cols = line.rstrip("\r\n").split("^")
            if len(cols) < 3 or not cols[0].isdigit() or not cols[1].isdigit():
                continue
            tables.setdefault(int(cols[1]), {})[int(cols[0])] = cols[2]
    return tables


def load_stacking(path, names):
    groups = {}
    if not path.exists():
        return groups
    with path.open(encoding="cp1252", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            cols = line.rstrip("\r\n").split("^")
            if len(cols) < 4 or not cols[0].isdigit():
                continue
            group_name = names.get(int(cols[1]), f"Group {cols[1]}")
            kind = STACK_TYPES.get(int(cols[3]), f"Type {cols[3]}")
            groups.setdefault(int(cols[0]), []).append(f"{group_name} {cols[2]} - {kind}")
    return groups


def compare_site(spells, strings, descriptions, categories, lines, stacking, raids_path=RAIDS):
    data = json.loads(raids_path.read_text(encoding="utf-8"))
    names = {spell_id: spell["name"] for spell_id, spell in spells.items()}
    rows = []
    changed = unchanged = missing = 0
    for site_name, entries in data["spells"].items():
        for entry in entries:
            spell_id = int(entry["id"])
            downloaded = spells.get(spell_id)
            if downloaded is None:
                missing += 1
                rows.append([site_name, entry["id"], "Spell", site_name, "(missing)"])
                continue
            diffs = field_diffs(
                site_name,
                entry,
                downloaded,
                strings.get(spell_id, {}),
                descriptions,
                names,
                categories,
                lines,
                stacking.get(spell_id, []),
            )
            if diffs:
                changed += 1
                for field, website, downloaded_value in diffs:
                    rows.append([site_name, entry["id"], field, website, downloaded_value])
            else:
                unchanged += 1
    return rows, changed, unchanged, missing


def field_diffs(site_name, entry, spell, messages, descriptions, names, categories, lines, stacking):
    website = details_map(entry.get("details") or [])
    downloaded = {
        "Name": spell["name"],
        "Icon": str(spell["icon"]),
        "Cast by You": messages.get("cast_self", ""),
        "Cast by Other": format_land_other(messages.get("cast_other", "")),
        "Mana": str(spell["mana"]),
        "Endurance": str(spell["endurance"]),
        "Casting Time": format_cast(spell["cast_ms"]),
        "Recast Time": format_cast(spell["recast_ms"]),
        "Duration": format_duration(spell["duration_formula"], spell["duration_cap"]),
        "Skill": SKILLS.get(spell["skill"], str(spell["skill"])),
        "Target": format_target(spell),
        "Range": format_number(spell["range"]),
        "AE Range": format_number(spell["ae_range"]),
        "Max Targets": str(spell["max_targets"]),
        "Spell Type": format_spell_type(spell),
        "Push Back": format_number(spell["push_back"]),
        "Push Up": format_number(spell["push_up"]),
        "Dispellable": "No" if spell["no_dispell"] else "Yes",
        "Focusable": "No" if spell["not_focusable"] else "Yes",
        "Interruptible": "Yes" if spell["interruptable"] else "No",
        "Viral": format_viral(spell),
        "Hate Override": str(spell["hate_override"]),
        "Spell Bar Lockout": format_cast(spell["rest_ms"]),
        "Stacking": " | ".join(stacking),
        "Spell Line": lines.get(spell["spell_line_id"], ""),
        "Timer ID": str(spell["timer_id"]),
        "Category": format_category(spell, categories),
        "Max Hits": str(spell["max_hits"]),
        "Max Hits Type": MAX_HITS_TYPES.get(spell["max_hits_type"], ""),
        "Land on You": messages.get("land_self", ""),
        "Land on Other": format_land_other(messages.get("land_other", "")),
        "Wear off": messages.get("wear_off", ""),
    }
    description_id = spell["description_id"] or spell["id"]
    if descriptions is not None:
        downloaded["In Game Description"] = descriptions.get(description_id, "")
    restrictions = []
    if spell["beta_only"]:
        restrictions.append("Beta Only")
    if spell["no_remove"]:
        restrictions.append("Cannot Remove")
    downloaded["Restriction"] = restrictions

    diffs = []
    if site_name.casefold() != spell["name"].casefold():
        diffs.append(("Name", site_name, spell["name"]))
    icon = icon_number(entry.get("icon", ""))
    if icon is not None and icon != spell["icon"]:
        diffs.append(("Icon", str(icon), str(spell["icon"])))

    for label, website_value in website.items():
        if label == "Restriction":
            continue
        if label == "In Game Description" and descriptions is None:
            continue
        if label not in downloaded:
            continue
        if values_differ(label, website_value, downloaded[label]):
            diffs.append((label, flatten(website_value), flatten(downloaded[label])))

    site_restrictions = website.get("Restriction") or []
    if site_restrictions or restrictions:
        if sorted(site_restrictions) != sorted(restrictions):
            diffs.append(("Restriction", " | ".join(site_restrictions), " | ".join(restrictions)))

    description = downloaded.get("In Game Description", "")
    slot_diff = slot_change(entry.get("slots") or [], spell["effects"], names, description)
    if slot_diff:
        diffs.append(("Slots", slot_diff[0], slot_diff[1]))
    return diffs


def details_map(details):
    grouped = {}
    for row in details:
        grouped.setdefault(row["label"], []).append(row["value"])
    flattened = {}
    for label, values in grouped.items():
        flattened[label] = values if label == "Restriction" else values[0]
    return flattened


def values_differ(label, website, downloaded):
    if label == "Target":
        return normalize_text(clean_target(website)) != normalize_text(downloaded)
    if label in {"Land on Other", "Cast by Other"}:
        return land_other_differs(website, downloaded)
    if label in {"In Game Description", "Land on You", "Wear off", "Name"}:
        return normalize_text(website) != normalize_text(downloaded)
    return normalize_text(str(website)) != normalize_text(str(downloaded))


def slot_change(slots, effects, names, description=""):
    site_text = "\n".join(slots)
    searchable = PAREN_RE.sub("", site_text)
    searchable = RANGE_RE.sub("", searchable)
    site_numbers = [float(item) if "." in item else int(item) for item in NUMBER_RE.findall(searchable)]
    site_numbers = [item for item in site_numbers if item != 0]
    consumed = []
    unexplained = []
    for effect in effects:
        if not effect_visible(effect):
            continue
        if effect["spa"] in CAST_SPAS and cast_effect_shown(effect, slots, names):
            continue
        if effect["spa"] in LIMIT_SPAS and "Limit" in site_text:
            continue
        word = WORD_SPAS.get(effect["spa"])
        if word and word in site_text:
            continue
        if effect["spa"] == 71 and "Summon Pet" in site_text:
            continue
        if effect["spa"] == 1 and abs(effect["base"]) >= 500 and consume_class_ac(site_numbers, effect["base"], consumed):
            continue
        if consume_effect(site_numbers, effect, consumed) or explained_by_prior(effect, consumed):
            continue
        unexplained.append(effect)
    leftovers = [
        item
        for item in site_numbers
        if item is not None and not any(abs(float(item) - float(seen)) < 0.001 for seen in consumed)
    ]
    if not unexplained and not leftovers:
        if direction_conflict(slots, description):
            return " | ".join(slots), "wording disagrees with the in-game description"
        return None
    website = " | ".join(slots)
    downloaded = " | ".join(format_effect(effect) for effect in effects if effect_visible(effect))
    return website, downloaded


def direction_conflict(slots, description):
    """True when every slot line says Increase or Decrease and the description says the other.

    Effect signs are not a reliable guide: a damage shield is stored as a negative
    base and still displayed as Increase. The in-game description is the wording
    the slot line is supposed to follow.
    """
    desc = normalize_text(description).casefold()
    desc_increase = bool(re.search(r"\bincreas", desc))
    desc_decrease = bool(re.search(r"\bdecreas", desc))
    if desc_increase == desc_decrease:
        return False
    slot_text = "\n".join(slots)
    slot_increase = bool(re.search(r"\bIncrease\b", slot_text))
    slot_decrease = bool(re.search(r"\bDecrease\b", slot_text))
    if desc_increase and slot_decrease and not slot_increase:
        return True
    if desc_decrease and slot_increase and not slot_decrease:
        return True
    return False


def cast_effect_shown(effect, slots, names):
    site_text = "\n".join(slots)
    name = names.get(abs(effect["base"]), "")
    if name and name in site_text:
        return True
    for line in slots:
        if re.match(r"Cast (?:on|if)|Add Defensive Proc|Summon Pet", line):
            if not line.split(":", 1)[-1].strip():
                return True
    return False


def consume_class_ac(site_numbers, base, consumed):
    low, high = class_ac_range(base)
    if not has_number(site_numbers, low) or not has_number(site_numbers, high):
        return False
    consume(site_numbers, low, consumed)
    consume(site_numbers, high, consumed)
    return True


def consume_effect(site_numbers, effect, consumed):
    matched = False
    for magnitude in effect_magnitudes(effect):
        if consume_magnitude(site_numbers, magnitude, consumed):
            matched = True
    if effect["formula"] >= 4000:
        rate = effect["formula"] - 4000
        if consume(site_numbers, rate, consumed):
            matched = True
        consume(site_numbers, rate - 1, consumed)
    return matched


def explained_by_prior(effect, consumed):
    for magnitude in effect_magnitudes(effect):
        for candidate in (magnitude, magnitude / 1000, magnitude / 100, magnitude / 10):
            if any(abs(float(candidate) - float(seen)) < 0.001 for seen in consumed):
                return True
    return False


def class_ac_range(base):
    magnitude = abs(base)
    low = int(math.floor(magnitude * 53 / 800 + 0.5))
    high = int(math.floor(magnitude * 7 / 80 + 0.5))
    return low, high


def effect_magnitudes(effect):
    magnitudes = []
    for raw in (effect["base"], effect["limit"], effect["max"]):
        if raw in (-1, 0):
            continue
        magnitude = abs(raw)
        if magnitude not in magnitudes:
            magnitudes.append(magnitude)
    if effect["spa"] == 11 and effect["base"]:
        shifted = abs(effect["base"] - 100)
        if shifted and shifted not in magnitudes:
            magnitudes.append(shifted)
    return magnitudes


def consume_magnitude(site_numbers, magnitude, consumed):
    if consume(site_numbers, magnitude, consumed):
        return True
    if consume(site_numbers, magnitude / 1000, consumed):
        return True
    if consume(site_numbers, magnitude / 100, consumed):
        return True
    if consume(site_numbers, magnitude / 10, consumed):
        return True
    return False


def has_number(site_numbers, expected):
    return any(
        value is not None and abs(float(value) - float(expected)) < 0.001 for value in site_numbers
    )


def consume(site_numbers, expected, consumed):
    for index, value in enumerate(site_numbers):
        if value is None:
            continue
        if abs(float(value) - float(expected)) < 0.001:
            site_numbers[index] = None
            consumed.append(expected)
            return True
    return False


def effect_visible(effect):
    return not (effect["base"] == 0 and effect["limit"] == 0 and effect["max"] == 0)


def format_effect(effect):
    parts = [str(effect["spa"]), str(effect["base"])]
    if effect["limit"] or effect["max"]:
        parts.append(str(effect["limit"]))
    if effect["max"]:
        parts.append(str(effect["max"]))
    return " ".join(parts)


def format_category(spell, categories):
    primary = categories.get(spell["category_id"], "")
    secondary = categories.get(spell["subcategory_id"], "")
    if primary and secondary:
        return f"{primary} -> {secondary}"
    return primary or secondary


def format_viral(spell):
    if spell["viral_range"] <= 0:
        return ""
    return f"Range: {spell['viral_range']}, Recast: {spell['viral_min']}s to {spell['viral_max']}s"


def format_cast(milliseconds):
    if milliseconds <= 0:
        return "Instant"
    if milliseconds % 1000 == 0:
        return f"{milliseconds // 1000}s"
    seconds = f"{milliseconds / 1000:.2f}".rstrip("0").rstrip(".")
    return f"{seconds}s"


def format_duration(formula, cap):
    ticks = duration_ticks(formula, cap)
    if ticks <= 0:
        return "Instant"
    if ticks < 10:
        return "1 tick" if ticks == 1 else f"{ticks} ticks"
    seconds = ticks * 6
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds == 60:
        return "60s"
    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"{minutes}m"
    return f"{minutes}m {remainder}s"


def duration_ticks(formula, cap):
    if formula == 0:
        return 0
    if cap > 0:
        return cap
    if formula == 50:
        return 72000
    if formula == 5:
        return 2
    return 0


def format_target(spell):
    name = TARGETS.get(spell["target"], str(spell["target"]))
    if spell["target"] != 42:
        return name
    return f"Directional AE - {format_number(spell['cone_start'])}° to {format_number(spell['cone_end'])}°"


def land_other_differs(website, downloaded):
    site = normalize_text(website)
    raw = normalize_text(downloaded)
    if site == raw:
        return False
    compact_site = site.replace(" ", "")
    compact_raw = raw.lstrip(" '").replace(" ", "")
    return not compact_raw or compact_raw not in compact_site


def format_spell_type(spell):
    if spell["beneficial"]:
        return "Beneficial: Blockable"
    text = "Detrimental - Resist: " + RESISTS.get(spell["resist"], str(spell["resist"]))
    if spell["resist_mod"]:
        text += f" {spell['resist_mod']}"
    if spell["min_resist"]:
        text += f" Min: {format_percent(spell['min_resist'])}"
    if spell["max_resist"]:
        text += f" Max: {format_percent(spell['max_resist'])}"
    return text


def format_percent(value):
    if value % 2:
        return f"{value / 2:.1f}%"
    return f"{value // 2}%"


def format_land_other(message):
    if message.startswith((" ", "'")):
        return "Target" + message
    return message


def format_number(value):
    if value == int(value):
        return str(int(value))
    return str(value)


def icon_number(url):
    match = ICON_RE.search(url or "")
    if not match:
        return None
    return int(match.group(1))


def clean_target(value):
    value = html.unescape(value or "")
    return value.split(" function ")[0].strip()


def normalize_text(value):
    text = html.unescape(value or "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"(?<=\w)\?(?=\w)", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def flatten(value):
    if isinstance(value, list):
        return " | ".join(value)
    return str(value).replace("\r", " ").replace("\n", " ")


def number(value):
    if value is None or value == "":
        return 0
    return int(float(value))


def decimal(value):
    if value is None or value == "":
        return 0.0
    return float(value)


def flag(value):
    return value not in ("", "0")


def yes_no(enabled):
    return "Yes" if enabled else "No"


def spell_data_rows(spells, strings, descriptions, categories, lines, stacking, raids_path=RAIDS):
    data = json.loads(raids_path.read_text(encoding="utf-8"))
    rows = []
    for site_name, entries in data["spells"].items():
        for entry in entries:
            spell_id = int(entry["id"])
            spell = spells.get(spell_id)
            if spell is None:
                row = {column: "" for column in DATA_COLUMNS}
                row["Spell"] = site_name
                row["Spell ID"] = entry["id"]
                row["Notes"] = "Missing on this server"
                rows.append(row)
                continue
            messages = strings.get(spell_id, {})
            description_id = spell["description_id"] or spell["id"]
            target = format_target(spell)
            if spell["target_restrict"]:
                target += f" (Restrict {spell['target_restrict']})"
            notes = ""
            if site_name.casefold() != spell["name"].casefold():
                notes = f"Website name: {site_name}"
            rows.append(
                {
                    "Spell": spell["name"],
                    "Spell ID": entry["id"],
                    "Classes": format_classes(spell["levels"]),
                    "Deity": format_deities(spell["deities"]),
                    "Icon": str(spell["icon"]),
                    "In Game Description": descriptions.get(description_id, "") if descriptions is not None else "",
                    "Cast by You": messages.get("cast_self", ""),
                    "Cast by Other": format_land_other(messages.get("cast_other", "")),
                    "Land on You": messages.get("land_self", ""),
                    "Land on Other": format_land_other(messages.get("land_other", "")),
                    "Wear off": messages.get("wear_off", ""),
                    "Mana": str(spell["mana"]),
                    "Endurance": str(spell["endurance"]),
                    "Endurance Upkeep": str(spell["endurance_upkeep"]),
                    "Casting Time": format_cast(spell["cast_ms"]),
                    "Recast Time": format_cast(spell["recast_ms"]),
                    "Spell Bar Lockout": format_cast(spell["rest_ms"]),
                    "Duration": format_duration(spell["duration_formula"], spell["duration_cap"]),
                    "Duration Formula": str(spell["duration_formula"]),
                    "Duration Cap": str(spell["duration_cap"]),
                    "Skill": SKILLS.get(spell["skill"], str(spell["skill"])),
                    "Target": target,
                    "Range": format_number(spell["range"]),
                    "Min Range": format_number(spell["min_range"]),
                    "AE Range": format_number(spell["ae_range"]),
                    "AE Waves": format_ae_waves(spell),
                    "Max Targets": str(spell["max_targets"]),
                    "Range Mod": format_range_mod(spell),
                    "Spell Type": format_spell_type(spell),
                    "Resist": RESISTS.get(spell["resist"], str(spell["resist"])),
                    "Resist Mod": str(spell["resist_mod"]),
                    "Min Resist": resist_percent(spell["min_resist"]),
                    "Max Resist": resist_percent(spell["max_resist"]),
                    "Resist Per Level": str(spell["resist_per_level"]),
                    "Resist Cap": str(spell["resist_cap"]),
                    "Dispellable": yes_no(not spell["no_dispell"]),
                    "Focusable": yes_no(not spell["not_focusable"]),
                    "Interruptible": yes_no(spell["interruptable"]),
                    "Reflectable": yes_no(spell["reflectable"]),
                    "Partial Resist": yes_no(spell["partial_resist"]),
                    "Spell DS": yes_no(spell["feedbackable"]),
                    "Push Back": format_number(spell["push_back"]),
                    "Push Up": format_number(spell["push_up"]),
                    "Viral": format_viral(spell),
                    "Hate Mod": str(spell["hate_mod"]),
                    "Hate Override": str(spell["hate_override"]),
                    "Max Crit": str(spell["crit_override"]),
                    "Stacking": " | ".join(stacking.get(spell_id, [])),
                    "Spell Line": lines.get(spell["spell_line_id"], ""),
                    "Spell Group": str(spell["group_id"]) if spell["group_id"] else "",
                    "Rank": str(spell["rank"]) if spell["rank"] else "",
                    "Category": format_category(spell, categories),
                    "Timer ID": str(spell["timer_id"]),
                    "Max Hits": str(spell["max_hits"]),
                    "Max Hits Type": MAX_HITS_TYPES.get(spell["max_hits_type"], ""),
                    "Restrictions": format_restrictions(spell),
                    "Consumes": " | ".join(f"{item_id} x {count}" for item_id, count in spell["reagents"]),
                    "Focus Items": " | ".join(str(item_id) for item_id in spell["focus_items"]),
                    "Recourse": str(spell["recourse_id"]) if spell["recourse_id"] else "",
                    "Song Window": yes_no(spell["song_window"]),
                    "MGB": yes_no(spell["mgb"]),
                    "NPC File": spell["npc"],
                    "Effects": format_effect_list(spell["effects"]),
                    "Notes": notes,
                }
            )
    return rows


def format_classes(levels):
    return ", ".join(
        f"{name} {level}" for name, level in zip(CLASSES, levels) if 0 < level < 255
    )


def format_deities(flags):
    return ", ".join(name for name, enabled in zip(DEITIES, flags) if enabled)


def format_restrictions(spell):
    items = []
    if spell["beta_only"]:
        items.append("Beta Only")
    if spell["no_remove"]:
        items.append("Cannot Remove")
    if spell["cast_out_of_combat"]:
        items.append("Out of Combat")
    if spell["cast_in_fast_regen"]:
        items.append("In Fast Regen")
    if spell["sneaking"]:
        items.append("Sneaking")
    if spell["cancel_on_sit"]:
        items.append("Cancel on Sit")
    if spell["persist_after_death"]:
        items.append("Persist After Death")
    if spell["no_sanctification"]:
        items.append("No Sanctification")
    if spell["duration_frozen"]:
        items.append("Duration Frozen")
    if spell["zone"]:
        items.append(f"Zone {spell['zone']}")
    if spell["caster_restrict"] > 100:
        items.append(f"Caster Restrict {spell['caster_restrict']}")
    return " | ".join(items)


def format_ae_waves(spell):
    if spell["ae_duration"] < 2500:
        return ""
    return str(spell["ae_duration"] // 2500)


def format_range_mod(spell):
    if not spell["range_far_dist"]:
        return ""
    close = format_multiplier(spell["range_close_mult"])
    far = format_multiplier(spell["range_far_mult"])
    return f"{close} at {spell['range_close_dist']} to {far} at {spell['range_far_dist']}"


def format_multiplier(value):
    percent = value * 100
    if percent == int(percent):
        return f"{int(percent)}%"
    return f"{percent:g}%"


def resist_percent(value):
    if not value:
        return ""
    return format_percent(value)


def format_effect_list(effects):
    lines = []
    for effect in effects:
        if effect["spa"] == 254:
            break
        if not effect_visible(effect):
            continue
        lines.append(
            f"Slot {effect['slot']}: SPA {effect['spa']}, Base {effect['base']}, "
            f"Limit {effect['limit']}, Formula {effect['formula']}, Max {effect['max']}"
        )
    return " | ".join(lines)


if __name__ == "__main__":
    sys.exit(main())
