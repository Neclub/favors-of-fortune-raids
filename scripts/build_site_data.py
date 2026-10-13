"""Write the raid writeups used by the GitHub Pages site."""

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BUILDER = Path(r"C:\Users\120ch\AppData\Local\Temp\fof-posts\build_raid_doc.py")

SHORT = {
    "siren": "Siren Sisters",
    "dipuc": "Dipuc, General of Scorn",
    "love": "Scorn, Queen of Thorns",
    "moruuk": "Moruuk and Sorshkah",
    "taurlton": "Taurlton, the Doorman",
    "vazaelle": "Fractured Vazaelle",
    "chronicles": "Chronicles of War",
    "eriak": "Eriak Zek",
    "xev": "Xev Tests Fate",
}


def load_builder():
    spec = importlib.util.spec_from_file_location("build_raid_doc", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_lookup()
    return module


def icon_url(icon_src):
    return "https://spells.eqresource.com/" + quote(icon_src, safe="/")


def spell_page(spell_id):
    return f"https://spells.eqresource.com/spells.php?id={spell_id}&source=beta"


def slot_pages():
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_spreadsheet import load_pages

    return load_pages()


def matches_for(module, name, pages):
    info = module.LOOKUP.get(name) or {}
    spells = []
    for match in info.get("matches") or []:
        page = pages.get(str(match["id"])) or {}
        spells.append(
            {
                "id": match["id"],
                "icon": icon_url(match["icon"]),
                "effect": match.get("effect") or "",
                "slots": page.get("slots") or [],
                "url": spell_page(match["id"]),
            }
        )
    return spells


def bullet_dict(module, bullet):
    return {
        "text": bullet.text,
        "spell": bullet.link_name or "",
        "children": [bullet_dict(module, child) for child in bullet.children],
    }


def item_dict(module, item):
    return {
        "kind": item.kind,
        "title": item.title,
        "spellNames": list(item.links),
        "prose": list(item.prose),
        "bullets": [bullet_dict(module, bullet) for bullet in item.bullets],
    }


def main():
    module = load_builder()
    pages = slot_pages()
    spells = {}
    for name, info in module.LOOKUP.items():
        found = matches_for(module, name, pages)
        if found:
            spells[name] = found

    tiers = []
    for tier_number in (1, 2, 3):
        raids = []
        for spec in module.RAIDS:
            if spec["tier"] != tier_number:
                continue
            raid = module.parse_raid(spec)
            raids.append(
                {
                    "id": spec["key"],
                    "title": raid["title"],
                    "short": SHORT[spec["key"]],
                    "forum": raid["url"],
                    "giver": raid["giver"],
                    "requirements": raid["requirements"],
                    "stages": [
                        {"title": stage_title, "blocks": [item_dict(module, item) for item in items]}
                        for stage_title, items in raid["stages"]
                    ],
                    "summary": [
                        {"name": name, "effect": effect}
                        for name, effect in raid["summary"]
                        if not name.startswith("Stage ")
                    ],
                }
            )
        tiers.append({"id": f"t{tier_number}", "label": f"Tier {tier_number}", "raids": raids})

    payload = {"title": "Favors of Fortune Raids", "spells": spells, "tiers": tiers}
    dest = ROOT / "data" / "raids.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {dest} tiers={len(tiers)} spells={len(spells)}")


if __name__ == "__main__":
    main()
