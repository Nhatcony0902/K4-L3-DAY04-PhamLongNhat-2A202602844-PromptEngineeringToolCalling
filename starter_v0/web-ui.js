// Shared rendering for the chat page and the compare page.
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const pretty = (v) => JSON.stringify(v, null, 2);

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.status);
  return data;
}

function showKeyWarning(info) {
  $("keywarn").hidden = info.api_key_present;
  $("keywarn").textContent = `Thiếu ${info.api_key_env} trong starter_v0/.env — mọi lượt sẽ báo provider_error.`;
}

function toolCard(round, event) {
  const result = event.result || {};
  const errorCode = result.error || event.error;
  const card = el("details", "tool" + (errorCode ? " has-error" : "") + (result.dry_run ? " dry-run" : ""));
  const summary = el("summary", null, `round ${round} · ${event.tool}(${Object.keys(event.args || {}).join(", ")})`);
  if (errorCode) summary.append(" ", el("span", "err", `error: ${errorCode}`));
  else if (result.status) summary.append(" → " + result.status);
  card.append(summary, el("div", "label", "input"), el("pre", null, pretty(event.args || {})),
              el("div", "label", errorCode ? "error" : "result"), el("pre", null, pretty(result)));
  if (errorCode) card.open = true;
  return card;
}

function renderTurn(turn, box) {
  box.replaceChildren();
  const badges = el("div", "badges");
  const calls = (turn.rounds || []).reduce((n, r) => n + (r.tool_calls || []).length, 0);
  badges.append(el("span", "badge st-" + turn.status, turn.status), el("span", "badge", turn.artifact_version || ""),
                el("span", "badge", `${calls} tool call(s)`));
  box.append(badges);
  if (!calls && turn.status === "answered") box.append(el("div", "note", "Không gọi tool."));
  (turn.rounds || []).forEach((r) => (r.tool_results || []).forEach((ev) => box.append(toolCard(r.round, ev))));
  if (turn.error) box.append(el("div", "error", turn.error));
  if (turn.assistant_text) box.append(el("div", "reply", turn.assistant_text));
}

function bindComposer(onSend) {
  $("form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("msg").value.trim();
    if (!text || $("send").disabled) return;
    $("msg").value = "";
    onSend(text);
  });
  $("msg").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("form").requestSubmit(); }
  });
}
