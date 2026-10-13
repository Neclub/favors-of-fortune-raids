const navList = document.getElementById("navList");
const writeup = document.getElementById("writeup");

let data = null;
let selectedId = "";

let cachedSpellNames = null;
let spellIndex = [];

function spellNames() {
  if (!cachedSpellNames) {
    cachedSpellNames = Object.keys(data.spells).sort((a, b) => b.length - a.length);
  }
  return cachedSpellNames;
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

function openInNewTab(link) {
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

const card = document.getElementById("spell-card");
const spellPanel = document.getElementById("spell-panel");

function showEmptyCard() {
  card.replaceChildren(el("p", "spell-panel-empty", "Hover a spell in the writeup to see its details."));
}

function detailText(value) {
  return value
    .replace(/\s*function degreesToRadians[\s\S]*$/, "")
    .replace(/&deg;/g, "°")
    .replace(/&amp;/g, "&");
}

function fillCard(matches, name) {
  card.replaceChildren();
  matches.forEach((match) => {
    const block = el("article", "spell-card-spell");
    const head = el("div", "spell-card-head");
    const img = document.createElement("img");
    img.src = match.icon;
    img.alt = "";
    const title = el("div");
    const nameLink = openInNewTab(document.createElement("a"));
    nameLink.className = "spell-card-name";
    nameLink.href = match.url || spellPage(match.id);
    nameLink.textContent = name;
    const idLink = openInNewTab(document.createElement("a"));
    idLink.className = "spell-card-id";
    idLink.href = match.url || spellPage(match.id);
    idLink.textContent = `Beta ${match.id}`;
    title.append(nameLink, idLink);
    head.append(img, title);
    block.append(head);
    const slots = match.slots && match.slots.length ? match.slots : (match.effect ? [match.effect] : []);
    if (slots.length) {
      const list = el("ul", "spell-card-slots");
      slots.forEach((text) => list.append(el("li", "", text)));
      block.append(list);
    }
    if (match.details && match.details.length) {
      const details = el("dl", "spell-card-details");
      match.details.forEach((row) => {
        details.append(el("dt", "", row.label));
        details.append(el("dd", "", detailText(row.value)));
      });
      block.append(details);
    }
    card.append(block);
  });
  spellPanel.scrollTop = 0;
}

function showCard(event, matches, name) {
  document.querySelectorAll(".is-open").forEach((node) => node.classList.remove("is-open"));
  const spell = event.currentTarget.closest(".spell");
  (spell || event.currentTarget).classList.add("is-open");
  fillCard(matches, name);
}

function bindSpellHover(node, matches, name) {
  node.addEventListener("mouseenter", (event) => showCard(event, matches, name));
  node.addEventListener("focusin", (event) => showCard(event, matches, name));
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
  const link = openInNewTab(document.createElement("a"));
  link.href = matches.length === 1 ? matches[0].url : matches[0].url;
  link.textContent = name;
  if (matches.length > 1) {
    link.href = `https://spells.eqresource.com/spellsearch.php?name=${encodeURIComponent(name)}&class=&level=1&range=greater&expac=&source=beta&searchname=true&strict=true`;
  }
  wrap.dataset.spell = name;
  wrap.append(link);
  const ids = el("span", "spell-ids");
  ids.append(" (");
  matches.forEach((match, index) => {
    if (index) ids.append(", ");
    const idLink = openInNewTab(document.createElement("a"));
    idLink.href = match.url || spellPage(match.id);
    idLink.textContent = match.id;
    ids.append(idLink);
    bindSpellHover(idLink, [match], name);
  });
  ids.append(")");
  wrap.append(ids);
  parent.append(wrap);
  wrap.addEventListener("mouseenter", (event) => showCard(event, matches, name));
  bindSpellHover(link, matches, name);
  if (matches.length === 1 && matches[0].effect) {
    parent.append(el("span", "spell-effect", ` — ${matches[0].effect}`));
  }
}

function spellSpans(text) {
  if (data.spells[text]) return [[0, text.length, text]];
  const names = spellNames().filter((name) => name.includes(" ") || name.length > 8);
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
  return spans;
}

function appendLinkedText(parent, text) {
  const spans = spellSpans(text);
  let cursor = 0;
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
    const link = openInNewTab(document.createElement("a"));
    link.href = match.url;
    link.textContent = match.id;
    item.append(link);
    bindSpellHover(link, [match], name);
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
  const forum = openInNewTab(document.createElement("a"));
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
      const singleEffect = data.spells[row.name] && data.spells[row.name].length === 1 && data.spells[row.name][0].effect;
      item.append(singleEffect ? ". " : " — ");
      appendLinkedText(item, row.effect);
      (data.spells[row.name] ? [row.name] : []).forEach((name) => appendCopies(item, name));
      list.append(item);
    });
    writeup.append(list);
  }
}

function selectRaid(id, updateHash, keepCard) {
  const raid = data.tiers.flatMap((tier) => tier.raids).find((item) => item.id === id);
  if (!raid) return;
  const raidChanged = id !== selectedId;
  selectedId = id;
  if (updateHash && raidChanged) history.pushState({ raid: id }, "", `#${id}`);
  navList.querySelectorAll(".nav-btn").forEach((button) => {
    const active = button.dataset.raid === id;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  });
  const active = navList.querySelector(`.nav-btn[data-raid="${id}"]`);
  const group = active?.closest(".nav-group");
  if (group) {
    group.classList.remove("collapsed");
    const toggle = group.querySelector(".nav-group-toggle");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
  }
  if (active) {
    const sidebar = document.getElementById("sidebar");
    const button = active.getBoundingClientRect();
    const frame = sidebar.getBoundingClientRect();
    if (button.bottom > frame.bottom) sidebar.scrollTop += button.bottom - frame.bottom + 8;
    else if (button.top < frame.top) sidebar.scrollTop -= frame.top - button.top + 8;
  }
  renderRaid(raid);
  if (!keepCard) showEmptyCard();
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

function raidTexts(raid) {
  const texts = [];
  function walkBullets(bullets) {
    (bullets || []).forEach((bullet) => {
      if (bullet.text) texts.push(bullet.text);
      walkBullets(bullet.children);
    });
  }
  (raid.stages || []).forEach((stage) => {
    if (stage.title) texts.push(stage.title);
    (stage.blocks || []).forEach((block) => {
      if (block.title) texts.push(block.title);
      (block.spellNames || []).forEach((name) => texts.push(name));
      (block.prose || []).forEach((paragraph) => texts.push(paragraph));
      walkBullets(block.bullets);
    });
  });
  (raid.summary || []).forEach((row) => {
    if (row.name) texts.push(row.name);
    if (row.effect) texts.push(row.effect);
  });
  return texts;
}

function buildSpellIndex() {
  const locations = new Map();
  data.tiers.forEach((tier) => {
    tier.raids.forEach((raid) => {
      const names = new Set();
      raidTexts(raid).forEach((text) => {
        spellSpans(text).forEach((span) => names.add(span[2]));
      });
      names.forEach((name) => {
        if (!locations.has(name)) locations.set(name, []);
        locations.get(name).push({ id: raid.id, short: raid.short, tier: tier.label });
      });
    });
  });
  spellIndex = [...locations.entries()]
    .map(([name, raids]) => ({ name, raids, matches: data.spells[name] || [] }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function matchingIds(entry, query) {
  const q = query.trim();
  const ids = entry.matches.map((match) => String(match.id));
  if (/^\d+$/.test(q)) {
    const matched = ids.filter((id) => id.startsWith(q));
    if (matched.length) return matched;
  }
  return ids;
}

function searchSpells(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const numeric = /^\d+$/.test(q);
  const hits = spellIndex.filter((entry) => {
    if (entry.name.toLowerCase().includes(q)) return true;
    if (!numeric) return false;
    return entry.matches.some((match) => String(match.id).startsWith(q));
  });
  hits.sort((a, b) => {
    const rank = (entry) => {
      const name = entry.name.toLowerCase();
      const ids = entry.matches.map((match) => String(match.id));
      if (numeric && ids.some((id) => id === q)) return 0;
      if (name === q) return 1;
      if (numeric && ids.some((id) => id.startsWith(q))) return 2;
      if (name.startsWith(q)) return 3;
      return 4;
    };
    return rank(a) - rank(b) || a.name.localeCompare(b.name);
  });
  return hits;
}

function highlightQuery(text, query) {
  const q = query.trim();
  const fragment = document.createDocumentFragment();
  if (!q || /^\d+$/.test(q)) {
    fragment.append(text);
    return fragment;
  }
  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  let cursor = 0;
  let index = lower.indexOf(needle, cursor);
  while (index >= 0) {
    if (index > cursor) fragment.append(text.slice(cursor, index));
    fragment.append(el("mark", "search-mark", text.slice(index, index + needle.length)));
    cursor = index + needle.length;
    index = lower.indexOf(needle, cursor);
  }
  if (cursor < text.length) fragment.append(text.slice(cursor));
  return fragment;
}

function openSpell(raidId, name, ids) {
  selectRaid(raidId, true, true);
  const nodes = [...writeup.querySelectorAll(".spell")].filter((node) => node.dataset.spell === name);
  const matches = data.spells[name] || [];
  const shown = ids.length ? matches.filter((match) => ids.includes(String(match.id))) : matches;
  if (nodes.length) {
    document.querySelectorAll(".is-open").forEach((node) => node.classList.remove("is-open"));
    nodes[0].classList.add("is-open");
    nodes[0].scrollIntoView({ block: "center", inline: "nearest" });
  }
  if (shown.length) fillCard(shown, name);
  else if (matches.length) fillCard(matches, name);
}

const searchInput = document.getElementById("spell-search");
const searchResults = document.getElementById("spell-search-results");
const SEARCH_LIMIT = 25;
const expandedSpellIds = new Set();
let lastSearchQuery = "";

function orderedIds(entry, query) {
  const ids = matchingIds(entry, query);
  const q = query.trim();
  if (/^\d+$/.test(q)) {
    ids.sort((a, b) => Number(b === q) - Number(a === q) || a.localeCompare(b, undefined, { numeric: true }));
  }
  return ids;
}

function renderSearch(query) {
  const q = query.trim();
  if (q !== lastSearchQuery) {
    expandedSpellIds.clear();
    lastSearchQuery = q;
  }
  searchResults.replaceChildren();
  searchInput.setAttribute("aria-expanded", q ? "true" : "false");
  if (!q || !spellIndex.length) return;

  const hits = searchSpells(q);
  const status = el("p", "search-status");
  if (!hits.length) {
    status.textContent = "No spells match.";
    searchResults.append(status);
    return;
  }
  const shown = hits.slice(0, SEARCH_LIMIT);
  status.textContent = hits.length > shown.length
    ? `Showing ${shown.length} of ${hits.length} spells. Keep typing to narrow the list.`
    : `${hits.length} spell${hits.length === 1 ? "" : "s"}`;
  const list = el("div", "search-results");
  shown.forEach((entry) => {
    const ids = orderedIds(entry, q);
    const expanded = expandedSpellIds.has(entry.name);
    const visibleIds = expanded ? ids : ids.slice(0, 1);
    const hit = el("article", "search-hit");
    const spell = el("div", "search-hit-spell");
    const icon = entry.matches.find((match) => visibleIds.includes(String(match.id)) && match.icon) || entry.matches[0];
    if (icon && icon.icon) {
      const img = document.createElement("img");
      img.src = icon.icon;
      img.alt = "";
      spell.append(img);
    }
    const title = el("div");
    const name = el("div", "search-hit-name");
    name.append(highlightQuery(entry.name, q));
    title.append(name, el("div", "search-hit-ids", visibleIds.join(", ")));
    if (ids.length > 1) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "search-id-more";
      more.dataset.expand = entry.name;
      more.setAttribute("aria-expanded", expanded ? "true" : "false");
      more.textContent = expanded
        ? "Show one ID"
        : ids.length === 2
          ? "Show the other ID"
          : `Show all ${ids.length} IDs`;
      more.addEventListener("click", () => {
        if (expandedSpellIds.has(entry.name)) expandedSpellIds.delete(entry.name);
        else expandedSpellIds.add(entry.name);
        renderSearch(searchInput.value);
        [...searchResults.querySelectorAll(".search-id-more")].find((button) => button.dataset.expand === entry.name)?.focus();
      });
      title.append(more);
    }
    spell.append(title);
    hit.append(spell);
    const raids = el("div", "search-hit-raids");
    entry.raids.forEach((raid) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-raid";
      button.textContent = `${raid.tier} · ${raid.short}`;
      button.setAttribute("aria-label", `Show ${entry.name} in ${raid.short}`);
      button.addEventListener("click", () => openSpell(raid.id, entry.name, visibleIds));
      raids.append(button);
    });
    hit.append(raids);
    list.append(hit);
  });
  searchResults.append(status, list);
}

function searchRaidButtons() {
  return [...searchResults.querySelectorAll(".search-raid")];
}

function bindSearch() {
  searchInput.addEventListener("input", () => renderSearch(searchInput.value));
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      searchInput.value = "";
      renderSearch("");
      return;
    }
    if (event.key === "ArrowDown") {
      const first = searchRaidButtons()[0];
      if (!first) return;
      event.preventDefault();
      first.focus();
      return;
    }
    if (event.key === "Enter") {
      const first = searchRaidButtons()[0];
      if (!first) return;
      event.preventDefault();
      first.click();
    }
  });
  searchResults.addEventListener("keydown", (event) => {
    const buttons = searchRaidButtons();
    if (!buttons.length) return;
    const index = buttons.indexOf(document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const next = index < 0 ? buttons[0] : buttons[Math.min(index + 1, buttons.length - 1)];
      next.focus();
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (index <= 0) searchInput.focus();
      else buttons[index - 1].focus();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      searchInput.value = "";
      renderSearch("");
      searchInput.focus();
    }
  });
}

function raidIdFromLocation() {
  const fromHash = decodeURIComponent(location.hash.replace(/^#/, ""));
  const known = data.tiers.flatMap((tier) => tier.raids).some((raid) => raid.id === fromHash);
  return known ? fromHash : data.tiers[0].raids[0].id;
}

function onHistoryNavigation() {
  const id = raidIdFromLocation();
  if (id === selectedId) return;
  selectRaid(id, false);
}

async function start() {
  const response = await fetch("data/raids.json");
  data = await response.json();
  cachedSpellNames = null;
  renderNav();
  buildSpellIndex();
  bindSearch();
  window.addEventListener("popstate", onHistoryNavigation);
  window.addEventListener("hashchange", onHistoryNavigation);
  if (searchInput.value.trim()) renderSearch(searchInput.value);
  selectRaid(raidIdFromLocation(), false);
}

start().catch(() => {
  writeup.textContent = "The raid writeups could not be loaded.";
});
