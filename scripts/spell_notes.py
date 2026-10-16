"""Load known raid spell IDs from Info note files."""

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
]

# Forum headings whose in-game spell uses a different name.
# Keyed by raid id so other "Sick" wording is left alone.
HEADING_RENAMES = {
    ("moruuk", "Sick"): "Queasy",
}

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


def rename_writeup_spells(data):
    """Replace forum headings with the in-game spell name."""
    changed = False
    for tier in data.get("tiers") or []:
        for raid in tier.get("raids") or []:
            for stage in raid.get("stages") or []:
                for block in stage.get("blocks") or []:
                    new_name = HEADING_RENAMES.get((raid.get("id"), (block.get("title") or "").strip()))
                    if not new_name:
                        continue
                    if block.get("title") != new_name:
                        block["title"] = new_name
                        changed = True
                    if block.get("spellNames") != [new_name]:
                        block["spellNames"] = [new_name]
                        changed = True
    return changed


SNOT_TEXT = "Snot will linger in the area and players getting too close will not feel so good"
SICKENING_GLOB = "Sickening Glob"


def link_sickening_glob(data):
    """Attach Sickening Glob under the lingering-snot bullet on Moruuk."""
    changed = False
    for tier in data.get("tiers") or []:
        for raid in tier.get("raids") or []:
            if raid.get("id") != "moruuk":
                continue
            for stage in raid.get("stages") or []:
                for block in stage.get("blocks") or []:
                    if (block.get("title") or "").strip() != "Sneeze":
                        continue
                    for bullet in block.get("bullets") or []:
                        if bullet.get("text") != SNOT_TEXT:
                            continue
                        children = bullet.setdefault("children", [])
                        existing = next(
                            (child for child in children if child.get("text") == SICKENING_GLOB or child.get("spell") == SICKENING_GLOB),
                            None,
                        )
                        if existing:
                            if existing.get("spell") != SICKENING_GLOB:
                                existing["spell"] = SICKENING_GLOB
                                changed = True
                            continue
                        bullet["children"] = [
                            {
                                "text": SICKENING_GLOB,
                                "spell": SICKENING_GLOB,
                                "children": children,
                            }
                        ]
                        changed = True
    return changed


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
