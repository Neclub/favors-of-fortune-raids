const navList = document.getElementById("navList");
const writeup = document.getElementById("writeup");

let data = null;
let selectedId = "";

function spellNames() {
  return Object.keys(data.spells).sort((a, b) => b.length - a.length);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function spellPage(id) {
  return `https://spells.eqresource.com/spells.php?id=${id}&source=beta`;
}

function appendSpell(parent, name) {
  const matches = data.spells[name];
  if (!matches || !matches.length) {
    parent.append(name);
    return;
  }
  const wrap = el("span", "spell");
  const seen = new Set();
  matches.forEach((match) => {
    if (seen.has(match.icon)) return;
    seen.add(match.icon);
    const img = document.createElement("img");
    img.src = match.icon;
    img.alt = "";
    img.width = 22;
    img.height = 22;
    wrap.append(img);
  });
  const link = document.createElement("a");
  link.href = matches.length === 1 ? matches[0].url : matches[0].url;
  link.textContent = name;
  if (matches.length > 1) {
    link.href = `https://spells.eqresource.com/spellsearch.php?name=${encodeURIComponent(name)}&class=&level=1&range=greater&expac=&source=beta&searchname=true&strict=true`;
  }
  wrap.append(link);
  const ids = el("span", "spell-ids");
  ids.append(" (");
  matches.forEach((match, index) => {
    if (index) ids.append(", ");
    const idLink = document.createElement("a");
    idLink.href = match.url || spellPage(match.id);
    idLink.textContent = match.id;
    ids.append(idLink);
  });
  ids.append(")");
  wrap.append(ids);
  parent.append(wrap);
}

function appendLinkedText(parent, text) {
  if (data.spells[text]) {
    appendSpell(parent, text);
    return;
  }
  const names = spellNames().filter((name) => name.includes(" ") || name.length > 8);
  let cursor = 0;
  const spans = [];
  const used = new Array(text.length).fill(false);
  names.forEach((name) => {
    let from = 0;
    while (from < text.length) {
      const index = text.indexOf(name, from);
      if (index < 0) break;
      const end = index + name.length;
      const beforeOk = index === 0 || !/[A-Za-z0-9'’]/.test(text[index - 1]);
      const afterOk = end === text.length || !/[A-Za-z0-9'’]/.test(text[end]);
      if (beforeOk && afterOk && !used.slice(index, end).some(Boolean)) {
        for (let i = index; i < end; i += 1) used[i] = true;
        spans.push([index, end, name]);
      }
      from = index + 1;
    }
  });
  spans.sort((a, b) => a[0] - b[0]);
  spans.forEach(([start, end, name]) => {
    if (start > cursor) parent.append(text.slice(cursor, start));
    appendSpell(parent, name);
    cursor = end;
  });
  if (cursor < text.length) parent.append(text.slice(cursor));
}

function appendCopies(parent, name) {
  const matches = data.spells[name] || [];
  if (matches.length < 2) return;
  const list = el("ul", "spell-copies");
  matches.forEach((match) => {
    const item = document.createElement("li");
    const img = document.createElement("img");
    img.src = match.icon;
    img.alt = "";
    img.width = 22;
    img.height = 22;
    item.append(img, " ");
    const link = document.createElement("a");
    link.href = match.url;
    link.textContent = match.id;
    item.append(link);
    if (match.effect) item.append(` — ${match.effect}`);
    list.append(item);
  });
  parent.append(list);
}

function renderBullets(bullets) {
  const list = el("ul", "effects");
  bullets.forEach((bullet) => {
    const item = document.createElement("li");
    appendLinkedText(item, bullet.text);
    if (bullet.spell) appendCopies(item, bullet.spell);
    if (bullet.children && bullet.children.length) {
      item.append(renderBullets(bullet.children));
    }
    list.append(item);
  });
  return list;
}

function renderRaid(raid) {
  writeup.replaceChildren();
  const title = el("h1", "", raid.title);
  writeup.append(title);
  if (raid.giver) writeup.append(el("p", "meta", raid.giver));
  if (raid.requirements) writeup.append(el("p", "meta", raid.requirements));
  const forum = document.createElement("a");
  forum.className = "forum-link";
  forum.href = raid.forum;
  forum.textContent = "Open the forum writeup";
  writeup.append(forum);

  raid.stages.forEach((stage) => {
    writeup.append(el("h2", "stage", stage.title));
    stage.blocks.forEach((block) => {
      const section = el("section", `block ${block.kind}`);
      const heading = el("h3");
      appendLinkedText(heading, block.title);
      section.append(heading);
      (block.spellNames || []).forEach((name) => appendCopies(section, name));
      (block.prose || []).forEach((paragraph) => {
        const p = el("p", "prose");
        appendLinkedText(p, paragraph);
        section.append(p);
      });
      if (block.bullets && block.bullets.length) {
        section.append(renderBullets(block.bullets));
      }
      writeup.append(section);
    });
  });

  if (raid.summary && raid.summary.length) {
    writeup.append(el("h2", "summary-title", "Key mechanics"));
    const list = el("ul", "effects");
    raid.summary.forEach((row) => {
      const item = document.createElement("li");
      appendLinkedText(item, row.name);
      item.append(" — ");
      appendLinkedText(item, row.effect);
      (data.spells[row.name] ? [row.name] : []).forEach((name) => appendCopies(item, name));
      list.append(item);
    });
    writeup.append(list);
  }
}

function selectRaid(id, updateHash) {
  const raid = data.tiers.flatMap((tier) => tier.raids).find((item) => item.id === id);
  if (!raid) return;
  selectedId = id;
  if (updateHash) history.replaceState(null, "", `#${id}`);
  navList.querySelectorAll(".nav-btn").forEach((button) => {
    const active = button.dataset.raid === id;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  });
  const group = navList.querySelector(`.nav-btn[data-raid="${id}"]`)?.closest(".nav-group");
  if (group) {
    group.classList.remove("collapsed");
    const toggle = group.querySelector(".nav-group-toggle");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
  }
  renderRaid(raid);
  document.getElementById("content").scrollTop = 0;
  window.scrollTo(0, 0);
}

function renderNav() {
  navList.replaceChildren();
  data.tiers.forEach((tier, tierIndex) => {
    const group = el("div", "nav-group");
    if (tierIndex !== 0) group.classList.add("collapsed");
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "nav-group-toggle";
    toggle.setAttribute("aria-expanded", tierIndex === 0 ? "true" : "false");
    const label = el("span", "", tier.label);
    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("viewBox", "0 0 12 12");
    chevron.setAttribute("class", "nav-chevron");
    chevron.innerHTML = '<path d="M2 4l4 4 4-4" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>';
    toggle.append(label, chevron);
    toggle.addEventListener("click", () => {
      const collapsed = group.classList.toggle("collapsed");
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    });
    const items = el("div", "nav-group-items");
    tier.raids.forEach((raid) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "nav-btn";
      button.dataset.raid = raid.id;
      button.textContent = raid.short;
      button.addEventListener("click", () => selectRaid(raid.id, true));
      items.append(button);
    });
    group.append(toggle, items);
    navList.append(group);
  });
}

async function start() {
  const response = await fetch("data/raids.json");
  data = await response.json();
  renderNav();
  const fromHash = location.hash.replace("#", "");
  const known = data.tiers.flatMap((tier) => tier.raids).some((raid) => raid.id === fromHash);
  selectRaid(known ? fromHash : data.tiers[0].raids[0].id, false);
}

start().catch(() => {
  writeup.textContent = "The raid writeups could not be loaded.";
});
