"""Drop non-raid spell IDs from the site data and the Word writeup."""

import json
import sys
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_site_data import load_exclusions

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RAIDS = ROOT / "data" / "raids.json"
DOC = ROOT / "Info" / "FoF_Raid_Mechanics.docx"


def element_text(element):
    return "".join(node.text or "" for node in element.iter(W + "t"))


def delete_element(element):
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def remove_ids_from_paragraph(paragraph, remove_ids):
    element = paragraph._p
    for child in list(element):
        if child.tag != W + "hyperlink":
            continue
        if element_text(child).strip() not in remove_ids:
            continue
        previous = child.getprevious()
        following = child.getnext()
        if following is not None and following.tag == W + "r" and element_text(following).strip() == ",":
            delete_element(following)
        elif previous is not None and previous.tag == W + "r" and element_text(previous).strip() == ",":
            delete_element(previous)
        delete_element(child)
    for child in list(element):
        if child.tag != W + "r" or element_text(child).strip() != "(":
            continue
        closing = child.getnext()
        if closing is not None and closing.tag == W + "r" and element_text(closing).strip() == ")":
            delete_element(child)
            delete_element(closing)


def update_document(remove_ids):
    document = Document(DOC)
    removed_paragraphs = 0
    for paragraph in list(document.paragraphs):
        text = paragraph.text.strip()
        first = text.split()[0] if text else ""
        if first in remove_ids:
            delete_element(paragraph._p)
            removed_paragraphs += 1
            continue
        remove_ids_from_paragraph(paragraph, remove_ids)
    document.save(DOC)
    return removed_paragraphs


def update_raids(remove_ids, skip_names):
    data = json.loads(RAIDS.read_text(encoding="utf-8"))
    for name in list(data["spells"]):
        if name in skip_names:
            del data["spells"][name]
            continue
        kept = [match for match in data["spells"][name] if match["id"] not in remove_ids]
        if kept:
            data["spells"][name] = kept
        else:
            del data["spells"][name]
    RAIDS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def main():
    remove_ids, skip_names = load_exclusions()
    data = json.loads(RAIDS.read_text(encoding="utf-8"))
    for name in skip_names:
        for match in data["spells"].get(name) or []:
            remove_ids.add(match["id"])
    if "Sneeze" in skip_names:
        remove_ids.add("39118")
    removed_paragraphs = update_document(remove_ids)
    update_raids(remove_ids, skip_names)
    print(f"removed ids={len(remove_ids)} names={sorted(skip_names)} doc paragraphs={removed_paragraphs}")


if __name__ == "__main__":
    main()
