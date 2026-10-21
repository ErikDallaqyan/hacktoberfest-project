const $ = (s) => document.querySelector(s);
const list = $("#list");
const tpl = $("#row");
const seen = new Set();
let lastSignature = "";

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Request failed (${r.status})`);
  return data;
}

function fmtSeconds(s) {
  s = Math.round(s);
  return s < 90 ? `${s}s` : `${Math.round(s / 60)} min`;
}

function renderStatus(st) {
  const pill = $("#pill");
  pill.className = "pill";
  if (!st.ollama_up) {
    pill.classList.add("bad");
    pill.textContent = "Ollama isn't running. Start it and I'll pick up where I left off.";
  } else if (!st.model_ready) {
    pill.classList.add("bad");
    pill.textContent = `Model missing: run "ollama pull ${st.model}"`;
  } else if (st.paused) {
    pill.textContent = "Paused";
  } else if (st.current) {
    pill.classList.add("busy");
    pill.textContent = `Reading ${st.current}${st.queued > 1 ? ` (+${st.queued - 1} waiting)` : ""}`;
  } else {
    pill.classList.add("ok");
    pill.textContent = `Watching · ${st.model}`;
  }
  $("#pause").textContent = st.paused ? "Resume" : "Pause";
  $("#pause").dataset.paused = st.paused ? "1" : "";
  $("#folders").checked = st.sort_into_folders;
  $("#watching").textContent = st.watching.length ? `Watching ${st.watching.join(" and ")}` : "No folders to watch";

  const t = st.totals;
  const named = t.named || 0;
  $("#s-named").textContent = named;
  const kept = named - (t.edited || 0);
  $("#s-kept").textContent = named ? `${Math.round((100 * kept) / named)}%` : "–";
  $("#s-time").textContent = fmtSeconds(t.model_seconds || 0);

  const backlog = st.backlog - st.queued;
  $("#backlog").hidden = backlog <= 0;
  $("#b-count").textContent = backlog;
  $("#b-where").textContent = st.watching.join(" and ");
}

function chip(text, cls = "") {
  const s = document.createElement("span");
  s.className = `chip ${cls}`;
  s.textContent = text;
  return s;
}

function renderRow(r, firstLoad) {
  const li = tpl.content.firstElementChild.cloneNode(true);
  li.dataset.id = r.id;
  li.classList.add(r.status);
  if (!seen.has(r.id) && !firstLoad) li.classList.add("fresh");
  seen.add(r.id);

  const img = li.querySelector(".thumb");
  if (r.status !== "error") img.src = `/api/renames/${r.id}/thumb?v=${encodeURIComponent(r.new_name || "")}${r.status}`;
  img.onerror = () => (img.style.visibility = "hidden");

  li.querySelector(".old").textContent = r.old_name;
  const nw = li.querySelector(".new");
  if (r.status === "error") nw.textContent = `Couldn't name this one: ${r.error}`;
  else nw.textContent = (r.subfolder ? `${r.subfolder}/` : "") + r.new_name;

  li.querySelector(".what").textContent =
    r.status === "undone" ? `Undone. It's back to its old name, and Sloth Sort will leave it alone.` : r.what;

  const meta = li.querySelector(".meta");
  if (r.category) meta.append(chip(r.category));
  if (r.secrets) meta.append(chip("shows a password or key", "warn"));
  if (r.status === "edited") meta.append(chip("you renamed it", "plain"));
  if (r.seconds) meta.append(chip(`${r.seconds}s`, "plain"));
  meta.append(chip(r.folder, "plain"));

  const canAct = r.status === "renamed" || r.status === "edited";
  li.querySelector(".actions").hidden = !canAct;

  li.querySelector(".undo").onclick = async () => {
    try { await api(`/api/renames/${r.id}/undo`, { method: "POST" }); refresh(true); }
    catch (e) { alert(e.message); }
  };

  const form = li.querySelector(".edit");
  const input = form.querySelector("input");
  li.querySelector(".rename").onclick = () => {
    form.hidden = false;
    input.value = r.new_name.replace(/\.[^.]+$/, "");
    input.focus();
    input.select();
  };
  form.querySelector(".cancel").onclick = () => (form.hidden = true);
  form.onsubmit = async (e) => {
    e.preventDefault();
    try { await api(`/api/renames/${r.id}/rename`, { method: "POST", body: { name: input.value } }); refresh(true); }
    catch (err) { alert(err.message); }
  };
  return li;
}

async function refresh(force = false) {
  let st;
  try {
    st = await api("/api/status");
  } catch {
    $("#pill").className = "pill bad";
    $("#pill").textContent = "Sloth Sort isn't running. Start it with: python -m slothsort";
    return;
  }
  renderStatus(st);

  // Only redraw the list when something changed, so an open rename box isn't wiped mid-typing.
  const sig = JSON.stringify([st.totals, st.current]);
  if (!force && sig === lastSignature) return;
  if (!force && list.querySelector(".edit:not([hidden])")) return;
  lastSignature = sig;

  const rows = await api("/api/renames");
  const firstLoad = seen.size === 0;
  list.replaceChildren(...rows.filter((r) => r.status !== "preview").map((r) => renderRow(r, firstLoad)));
  $("#empty").hidden = rows.length > 0;
}

$("#pause").onclick = async () => {
  await api("/api/pause", { method: "POST", body: { on: !$("#pause").dataset.paused } });
  refresh(true);
};
$("#folders").onchange = async (e) => {
  await api("/api/folders", { method: "POST", body: { on: e.target.checked } });
};
$("#b-go").onclick = async () => {
  $("#b-go").disabled = true;
  try { await api("/api/backlog", { method: "POST" }); } finally { $("#b-go").disabled = false; refresh(true); }
};

refresh(true);
setInterval(refresh, 2000);
