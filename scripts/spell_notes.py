"""Load known raid spell IDs from Info note files and reapply found spell links."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFO = ROOT / "Info"

# Note files that list site spell names and EQResource beta URLs.
NOTE_FILES = [
    INFO / "Scorn, Queen of Thorns.txt",
    INFO / "Chronicles of War.txt",
    INFO / "SirenSisters_Missingspells.txt",
    INFO / "Moruuk and Sorshkah.txt",
    INFO / "Fractured Vazaelle.txt",
    INFO / "Taurlton, the Doorman.txt",
]

# Forum headings whose in-game spell uses a different name.
# Keyed by raid id so other "Sick" wording is left alone.
HEADING_RENAMES = {
    ("moruuk", "Sick"): "Queasy",
    ("chronicles", "Spite"): "Spite of Meldrath",
}

# Exact forum lines that are typos. The saved post and the site use the corrected line.
FORUM_LINE_CORRECTIONS = {
    "chronicles": {
        "Spite": "Spite of Meldrath",
    },
}

# Manual spell links the staff post does not name correctly.
# kind: heading_rename | spell_names | bullet_spell | child_spell
SPELL_CORRECTIONS = [
    {
        "raid": "chronicles",
        "heading": "Spite of Meldrath",
        "also_heading": ("Spite",),
        "kind": "heading_rename",
        "spell": "Spite of Meldrath",
        "spell_id": "75015",
        "note": "forum typo corrected from the note file",
    },
    {
        "raid": "chronicles",
        "heading": "Spite of Meldrath",
        "also_heading": ("Spite",),
        "kind": "bullet_spell",
        "prefix": "If it fails to be removed",
        "spell": "Spite of Meldrath Effect",
        "spell_id": "75016",
        "note": "linked on the ring-damage bullet",
    },
    {
        "raid": "chronicles",
        "heading": "Tick-Tock Bomb",
        "kind": "spell_names",
        "spells": ["Tick-Tock Explosion"],
        "spell": "Tick-Tock Explosion",
        "spell_id": "75017",
        "note": "linked on the forum heading",
    },
    {
        "raid": "chronicles",
        "heading": "Self-Immolation",
        "kind": "spell_names",
        "spells": [],
        "spell": "Self-Immolation",
        "spell_id": "75009",
        "note": "IDs kept on the bullets instead of the heading",
    },
    {
        "raid": "chronicles",
        "heading": "Self-Immolation",
        "kind": "bullet_spell",
        "prefix": "PBAoE that targets",
        "spell": "Self-Immolation",
        "spell_id": "75009",
        "note": "linked on the PBAoE bullet",
    },
    {
        "raid": "chronicles",
        "heading": "Self-Immolation",
        "kind": "bullet_spell",
        "prefix": "Applies a DoT",
        "spell": "Self-Immolation Effect",
        "spell_id": "75010",
        "note": "linked on the DoT bullet",
    },
    {
        "raid": "chronicles",
        "heading": "Harvester's Gravestone",
        "kind": "bullet_spell",
        "prefix": "Spawns Stinking Miasma",
        "spell": "Stinking Miasma",
        "spell_id": "75061",
        "note": "linked on the spawn line",
    },
    {
        "raid": "vazaelle",
        "heading": "Silencing Mist",
        "kind": "child_spell",
        "prefix": "Players that move into the area will be silenced and rooted",
        "spell": "Grasping Mist",
        "spell_id": "75102",
        "note": "linked on the silencing mist root",
    },
    {
        "raid": "moruuk",
        "heading": "Queasy",
        "also_heading": ("Sick",),
        "kind": "heading_rename",
        "spell": "Queasy",
        "spell_id": "75131",
        "note": "forum Sick heading corrected to Queasy",
    },
    {
        "raid": "moruuk",
        "heading": "Sneeze",
        "kind": "child_spell",
        "prefix": "Snot will linger in the area and players getting too close will not feel so good",
        "spell": "Sickening Glob",
        "spell_id": "75136",
        "note": "linked on the lingering snot",
    },
    {
        "raid": "love",
        "heading": "Scorn - Rapid Fire Burst",
        "kind": "bullet_spell",
        "prefix": "Players caught in the AoE are charmed",
        "spell": "Coerced Loyalty",
        "spell_id": "75200",
        "note": "linked on the Stage 3 charm line",
    },
]

SPELL_URL = re.compile(
    r"https?://spells\.eqresource\.com/spells\.php\?id=(\d+)(?:&source=beta)?",
    re.I,
)
# "Spell Name:" or bare "Spell Name" (Siren sisters notes omit the colon).
HEADING = re.compile(r"^([^:]+?)(?::\s*(?:\(([^)]*)\))?)?\s*$")
SKIP_HEADINGS = {
    "remove",
    "malaise",
}


def normalize_heading(text):
    text = re.sub(r"\s+", " ", text).strip()
    key = text.casefold()
    if key in SKIP_HEADINGS:
        return None
    if key.startswith("(currently known") or key.startswith("developer placeholder"):
        return None
    if key.startswith("spite of meldrath was previously"):
        return None
    # Bare ID / dash lines are removals, not spell headings.
    if re.match(r"^\d+\b", text):
        return None
    return text


def load_spell_notes():
    """Return {spell_name: [spell_id, ...]} from Info note files."""
    found = {}
    for path in NOTE_FILES:
        if not path.is_file():
            continue
        current = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if "spells.eqresource.com" in line.casefold():
                for spell_id in SPELL_URL.findall(line):
                    if not current:
                        continue
                    ids = found.setdefault(current, [])
                    if spell_id not in ids:
                        ids.append(spell_id)
                continue
            heading = HEADING.match(line)
            if heading:
                current = normalize_heading(heading.group(1))
    return found


def correct_forum_lines(raid_id, lines):
    """Replace known mistyped forum lines before the post is compared or saved."""
    replacements = FORUM_LINE_CORRECTIONS.get(raid_id) or {}
    if not replacements:
        return lines
    return [replacements.get(line, line) for line in lines]


def renamed_spell_names(names):
    """Map forum spell names to the in-game name used in note files."""
    replacements = {old: new for (_raid, old), new in HEADING_RENAMES.items()}
    return [replacements.get(name, name) for name in names]


def ensure_writeup_links(data, spell_name):
    """Attach spellNames when a longer block title mentions the spell.

    Titles that are exactly the spell name are left alone so mechanics like
    Self-Immolation can keep IDs on their description bullets instead.
    """
    changed = False
    for tier in data.get("tiers") or []:
        for raid in tier.get("raids") or []:
            for stage in raid.get("stages") or []:
                for block in stage.get("blocks") or []:
                    title = (block.get("title") or "").strip()
                    if spell_name not in title or title == spell_name:
                        continue
                    names = block.setdefault("spellNames", [])
                    if spell_name not in names:
                        names.append(spell_name)
                        changed = True
    return changed


def _heading_matches(block, rule):
    title = (block.get("title") or "").strip()
    names = {rule["heading"], *(rule.get("also_heading") or ())}
    return title in names


def _set_spell_names(block, names):
    if block.get("spellNames") == names:
        return False
    block["spellNames"] = list(names)
    return True


def _set_bullet_spell(block, prefix, spell_name):
    changed = False
    for bullet in block.get("bullets") or []:
        if not (bullet.get("text") or "").startswith(prefix):
            continue
        if bullet.get("spell") != spell_name:
            bullet["spell"] = spell_name
            changed = True
    return changed


def _set_child_spell(block, prefix, spell_name):
    """Attach a named child under the bullet whose text matches the prefix."""
    changed = False
    for bullet in block.get("bullets") or []:
        if (bullet.get("text") or "").strip() != prefix:
            continue
        children = bullet.setdefault("children", [])
        existing = next(
            (
                child
                for child in children
                if child.get("text") == spell_name or child.get("spell") == spell_name
            ),
            None,
        )
        if existing:
            if existing.get("spell") != spell_name:
                existing["spell"] = spell_name
                changed = True
            if existing.get("text") != spell_name:
                existing["text"] = spell_name
                changed = True
            continue
        bullet["children"] = [
            {
                "text": spell_name,
                "spell": spell_name,
                "children": children,
            }
        ]
        changed = True
    return changed


def _apply_rule(block, rule):
    kind = rule["kind"]
    if kind == "heading_rename":
        changed = False
        if (block.get("title") or "").strip() != rule["spell"]:
            block["title"] = rule["spell"]
            changed = True
        changed |= _set_spell_names(block, [rule["spell"]])
        return changed
    if kind == "spell_names":
        return _set_spell_names(block, list(rule.get("spells") or []))
    if kind == "bullet_spell":
        return _set_bullet_spell(block, rule["prefix"], rule["spell"])
    if kind == "child_spell":
        return _set_child_spell(block, rule["prefix"], rule["spell"])
    return False


def apply_forum_spell_corrections(data):
    """Reattach spell links the staff post names incorrectly.

    Forum rebuilds drop these. The note files and SPELL_CORRECTIONS are the source.
    """
    notes = []
    for tier in data.get("tiers") or []:
        for raid in tier.get("raids") or []:
            raid_id = raid.get("id")
            for stage in raid.get("stages") or []:
                for block in stage.get("blocks") or []:
                    for rule in SPELL_CORRECTIONS:
                        if rule["raid"] != raid_id or not _heading_matches(block, rule):
                            continue
                        if _apply_rule(block, rule):
                            notes.append(
                                (
                                    rule["spell"],
                                    rule["spell_id"],
                                    "Writeup",
                                    "",
                                    rule["note"],
                                )
                            )
    return notes


def rename_writeup_spells(data):
    """Replace forum headings with the in-game spell name."""
    notes = apply_forum_spell_corrections(data)
    return any("corrected" in note[4] for note in notes)


def link_sickening_glob(data):
    """Attach Sickening Glob under the lingering-snot bullet on Moruuk."""
    return any(note[0] == "Sickening Glob" for note in apply_forum_spell_corrections(data))


def link_grasping_mist(data):
    """Attach Grasping Mist under the Silencing Mist root line on Vazaelle."""
    return any(note[0] == "Grasping Mist" for note in apply_forum_spell_corrections(data))
