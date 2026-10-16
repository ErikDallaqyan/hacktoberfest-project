const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const state = {
  meta: null,
  file: null,
  menu: null,
  targets: new Set(["en", "ru"]),
  translations: {},
  stats: [],
  active: null,
};

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `Request failed (${r.status})`);
  return body;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- setup ----------
async function loadMeta() {
  state.meta = await api("/api/meta");
  const { languages, models, vision_model, glossaries, ocr_languages } = state.meta;
  if (!ocr_languages.length) $("#reader").value = "vision";

  $("#sourceLang").innerHTML = Object.entries(languages)
    .map(([k, v]) => `<option value="${k}" ${k === "hy" ? "selected" : ""}>${v}</option>`).join("");

  $("#targetLangs").innerHTML = Object.entries(languages)
    .map(([k, v]) => `<button type="button" class="chip ${state.targets.has(k) ? "on" : ""}" data-lang="${k}">${v.split(" ")[0]}</button>`).join("");

  const opts = models.length ? models : [vision_model];
  $("#model").innerHTML = opts.map(m => `<option ${m === vision_model ? "selected" : ""}>${esc(m)}</option>`).join("");
  if (!models.length) {
    $("#privacy").textContent = "● Ollama not reachable — start it with `ollama serve`";
    $("#privacy").style.color = "var(--accent)";
  }
  renderGlossaries(glossaries);
}

function renderGlossaries(list, selected) {
  $("#glossary").innerHTML = list
    .map(g => `<option value="${g.id}" ${g.id === selected ? "selected" : ""}>${esc(g.name)} (${g.entries})</option>`).join("");
}

$("#targetLangs").addEventListener("click", e => {
  const b = e.target.closest(".chip");
  if (!b) return;
  const k = b.dataset.lang;
  state.targets.has(k) ? state.targets.delete(k) : state.targets.add(k);
  b.classList.toggle("on");
});

$("#newGlossary").addEventListener("click", async () => {
  const name = prompt("Restaurant name (we'll start from the Armenian classics glossary):");
  if (!name) return;
  try {
    const { id } = await api("/api/glossaries", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, copy_from: $("#glossary").value }),
    });
    renderGlossaries(await api("/api/glossaries"), id);
  } catch (err) { alert(err.message); }
});

// ---------- input ----------
$$(".tab").forEach(t => t.addEventListener("click", () => {
  $$(".tab").forEach(x => x.classList.toggle("active", x === t));
  $$(".tabpane").forEach(p => p.hidden = p.dataset.pane !== t.dataset.tab);
}));

function setFile(file) {
  state.file = file;
  const img = $("#preview");
  img.src = URL.createObjectURL(file);
  img.hidden = false;
  $("#dropHint").hidden = true;
}

$("#file").addEventListener("change", e => e.target.files[0] && setFile(e.target.files[0]));
const drop = $("#drop");
drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", e => {
  e.preventDefault(); drop.classList.remove("over");
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});
$("#useSample").addEventListener("click", async () => {
  const blob = await (await fetch("/api/sample")).blob();
  setFile(new File([blob], "sample_menu_hy.png", { type: "image/png" }));
  $("#sourceLang").value = "hy";
});

function ticker(el, label) {
  const t0 = Date.now();
  el.classList.remove("err");
  const id = setInterval(() => el.textContent = `${label}… ${Math.round((Date.now() - t0) / 1000)}s`, 500);
  return () => clearInterval(id);
}

$("#extractBtn").addEventListener("click", async () => {
  const usingText = !$('[data-pane="text"]').hidden;
  const fd = new FormData();
  fd.append("source_lang", $("#sourceLang").value);
  fd.append("model", $("#model").value);
  fd.append("reader", $("#reader").value);
  fd.append("glossary_id", $("#glossary").value);
  if (usingText) fd.append("text", $("#menuText").value);
  else if (state.file) fd.append("file", state.file);

  const btn = $("#extractBtn"), st = $("#extractStatus");
  btn.disabled = true;
  const stop = ticker(st, "Reading the menu on your machine");
  try {
    const res = await api("/api/extract", { method: "POST", body: fd });
    state.menu = res.menu;
    state.stats = [{ step: "read", ...res.stats }];
    const fixes = res.menu.sections.flatMap(s => s.items).filter(i => i.ocr_name).length;
    st.textContent = `Read ${countDishes(res.menu)} dishes in ${res.stats.seconds}s` +
      (res.stats.ocr_seconds !== undefined ? ` (OCR ${res.stats.ocr_seconds}s)` : "") +
      (fixes ? ` · ${fixes} name${fixes > 1 ? "s" : ""} auto-corrected from your glossary (highlighted)` : "");
    renderSource();
    $("#review").hidden = false;
    $("#review").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    st.textContent = err.message; st.classList.add("err");
  } finally { stop(); btn.disabled = false; }
});

const countDishes = m => m.sections.reduce((n, s) => n + s.items.length, 0);

// ---------- review ----------
function renderSource() {
  $("#sourceMenu").innerHTML = state.menu.sections.map((s, si) => `
    <div class="src-section">
      <input data-s="${si}" data-f="name" value="${esc(s.name)}" aria-label="Section name">
      ${s.items.map((it, ii) => `
        <div class="src-item">
          <input data-s="${si}" data-i="${ii}" data-f="name" value="${esc(it.name)}" aria-label="Dish name"
            ${it.ocr_name ? `class="fixed" title="Auto-corrected from “${esc(it.ocr_name)}” using your glossary"` : ""}>
          <input class="d" data-s="${si}" data-i="${ii}" data-f="description" value="${esc(it.description)}" placeholder="(no description)" aria-label="Description">
          <input data-s="${si}" data-i="${ii}" data-f="price" value="${esc(it.price)}" aria-label="Price">
        </div>`).join("")}
    </div>`).join("");
}

$("#sourceMenu").addEventListener("input", e => {
  const { s, i, f } = e.target.dataset;
  if (s === undefined) return;
  const target = i === undefined ? state.menu.sections[s] : state.menu.sections[s].items[i];
  target[f] = e.target.value;
});

$("#translateBtn").addEventListener("click", async () => {
  const langs = [...state.targets].filter(l => l !== $("#sourceLang").value);
  if (!langs.length) { $("#translateStatus").textContent = "Pick at least one target language."; return; }
  const btn = $("#translateBtn"), st = $("#translateStatus");
  btn.disabled = true;
  state.translations = {};
  state.stats = state.stats.filter(s => s.step === "read");
  $("#results").hidden = false;
  try {
    for (const lang of langs) {
      const stop = ticker(st, `Translating into ${state.meta.languages[lang]}`);
      try {
        const res = await api("/api/translate", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            menu: state.menu, source_lang: $("#sourceLang").value, target_lang: lang,
            glossary_id: $("#glossary").value, model: $("#model").value,
          }),
        });
        state.translations[lang] = res.translation;
        state.stats.push({ step: lang, ...res.stats });
        if (!state.active || !state.translations[state.active]) state.active = lang;
        renderResults();
      } finally { stop(); }
    }
    st.textContent = "Done.";
    $("#results").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    st.textContent = err.message; st.classList.add("err");
  } finally { btn.disabled = false; }
});

// ---------- results ----------
function renderResults() {
  const langs = Object.keys(state.translations);
  $("#langTabs").innerHTML = langs.map(l =>
    `<button class="chip ${l === state.active ? "on" : ""}" data-lang="${l}">${state.meta.languages[l]}</button>`).join("");

  const t = state.translations[state.active];
  const cur = t.currency ? ` ${esc(t.currency)}` : "";
  const sheet = $("#sheet");
  sheet.innerHTML = `
    <div class="sheet-title"><h3>${esc(t.title)}</h3><div>${esc(t.source_title)}</div></div>
    ${t.sections.map((s, si) => `
      <div class="sheet-section">
        <h4>${esc(s.name)}<small>${esc(s.source_name)}</small></h4>
        <div class="dishes" data-s="${si}"></div>
      </div>`).join("")}`;

  t.sections.forEach((s, si) => {
    const holder = $(`.dishes[data-s="${si}"]`, sheet);
    s.items.forEach(it => {
      const node = $("#dishTpl").content.firstElementChild.cloneNode(true);
      $(".dish-name", node).textContent = it.name;
      $(".dish-src", node).textContent = it.source_name;
      $(".dish-price", node).textContent = it.price ? `${it.price}${cur}` : "";
      $(".dish-desc", node).textContent = it.description;
      $(".tags", node).innerHTML = it.dietary.map(d => `<span class="tag">${esc(d)}</span>`).join(" ");
      $(".gloss", node).textContent = it.glossary_hits.length ? `✓ house glossary: ${it.glossary_hits.join(", ")}` : "";
      if (it.needs_review) $(".tags", node).insertAdjacentHTML("afterbegin", '<span class="tag warn">⚠ not translated, please correct</span>');
      wireEdit(node, it);
      holder.appendChild(node);
    });
  });

  const tokens = state.stats.reduce((a, s) => a + (s.prompt_tokens || 0) + (s.output_tokens || 0), 0);
  $("#stats").textContent =
    `${state.stats.map(s => `${s.step}: ${s.seconds}s`).join(" · ")} · ${tokens.toLocaleString()} tokens on ${state.stats[0]?.model} · API cost $0.00`;
}

$("#langTabs").addEventListener("click", e => {
  const b = e.target.closest(".chip");
  if (!b) return;
  state.active = b.dataset.lang;
  renderResults();
});

function wireEdit(node, it) {
  const form = $(".dish-edit", node);
  $(".edit", node).addEventListener("click", () => {
    form.name.value = it.name;
    form.description.value = it.description;
    form.hidden = false;
    form.name.focus();
  });
  $(".cancel", node).addEventListener("click", () => form.hidden = true);
  form.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api(`/api/glossaries/${encodeURIComponent($("#glossary").value)}/corrections`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_name: it.source_name, lang: state.active,
          name: form.name.value, description: form.description.value,
        }),
      });
      it.name = form.name.value;
      it.description = form.description.value;
      $(".dish-name", node).textContent = it.name;
      $(".dish-desc", node).textContent = it.description;
      form.hidden = true;
      node.classList.add("saved");
      const list = await api("/api/glossaries");
      renderGlossaries(list, $("#glossary").value);
    } catch (err) { alert(err.message); }
  });
}

$("#printBtn").addEventListener("click", () => window.print());
$("#jsonBtn").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify({ source: state.menu, translations: state.translations }, null, 2)], { type: "application/json" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "menu-translations.json" });
  a.click();
});

loadMeta().catch(err => { $("#privacy").textContent = err.message; });
