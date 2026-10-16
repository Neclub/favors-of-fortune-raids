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
