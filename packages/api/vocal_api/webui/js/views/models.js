// Models — catalog browser, pull with live progress, delete, details.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, badge, toast, confirmModal, modal, fmtBytes, emptyState, debounce } from "../ui.js";

const activePulls = new Map(); // modelId -> {progress, message, status}

function capabilityChips(m) {
  const chips = [];
  if (m.supports_streaming) chips.push(["streaming", "accent"]);
  if (m.supports_live_streaming) chips.push(["live stream", "accent"]);
  if (m.supports_voice_list) chips.push(["voices", "blue"]);
  if (m.supports_voice_clone) chips.push(["clone", "blue"]);
  if (m.supports_voice_design) chips.push(["voice design", "blue"]);
  if (m.requires_gpu) chips.push(["GPU required", "amber"]);
  return chips;
}

function statusBadge(m, installed) {
  if (activePulls.has(m.id)) return badge("downloading", "amber");
  if (installed) return badge("installed", "green");
  if (m.runtime === "external") return badge("external engine", "amber");
  if (m.maintenance_status === "retired") return badge("retired", "red");
  if (m.maintenance_status === "deprecated") return badge("deprecated", "amber");
  return badge("not downloaded", "");
}

function detailModal(m, installed) {
  const dl = el("dl", { class: "kv" });
  const rows = [
    ["Model ID", m.id],
    ["Backend", m.backend],
    ["Task", m.task.toUpperCase()],
    ["Provider", m.provider],
    ["Size", m.size_readable || fmtBytes(m.size)],
    ["Parameters", m.parameters || "unknown"],
    ["License", m.license || "unknown"],
    ["Commercial use", m.commercial_use == null ? "unknown" : m.commercial_use ? "permitted" : "not permitted"],
    ["Runtime", m.runtime === "external" ? `external — ${m.runtime_note || "see docs"}` : "in-process"],
    ["Maintenance", m.maintenance_status || "active"],
    ["VRAM", m.recommended_vram || "—"],
    ["Languages", (m.languages || []).join(", ") || "—"],
    ["Output formats", m.task === "tts" ? (m.output_formats || []).join(", ") || "all (mp3, opus, aac, flac, wav, pcm)" : "n/a (STT)"],
    ["Author", m.author || "—"],
    ["HF downloads", m.downloads != null ? m.downloads.toLocaleString() : "—"],
    ["Source", m.source_url || "—"],
  ];
  if (m.local_path) rows.push(["Local path", m.local_path]);
  if (m.downloaded_at) rows.push(["Downloaded", m.downloaded_at]);
  for (const [k, v] of rows) dl.append(el("dt", { text: k }), el("dd", { text: String(v) }));

  const caps = capabilityChips(m);
  modal({
    title: m.name,
    wide: true,
    body: el("div", {},
      m.description ? el("p", { class: "mb-4 text-sm leading-relaxed text-lightgrey", text: m.description }) : null,
      caps.length ? el("div", { class: "chip-row mb-4" }, caps.map(([t, k]) => badge(t, k))) : null,
      m.runtime === "external"
        ? el("p", { class: "mb-4 rounded-lg border border-[rgba(255,194,75,0.35)] bg-[rgba(255,194,75,0.08)] p-3 text-xs text-[#ffc24b]", text: `This model needs an external engine: ${m.runtime_note || "not specified"}. Vocal lists it for reference but cannot run it in-process.` })
        : null,
      dl,
      m.source_url ? el("a", { href: String(m.source_url), target: "_blank", rel: "noopener", class: "btn btn-ghost btn-sm mt-5", text: "View on Hugging Face" }) : null
    ),
    actions: installed
      ? [{ label: "Close", kind: "btn-ghost", onclick: (close) => close() }]
      : [
          { label: "Close", kind: "btn-ghost", onclick: (close) => close() },
          { label: "Pull model", kind: "btn-primary", onclick: (close) => { close(); startPull(m.id); } },
        ],
  });
}

async function startPull(id) {
  if (activePulls.has(id)) return;
  activePulls.set(id, { progress: 0, message: "Starting download…", status: "downloading" });
  updateCard(id);
  try {
    await api.pullModel(id, (p) => {
      activePulls.set(id, p);
      updateCard(id);
    });
    toast(`${id} downloaded`, "ok");
  } catch (e) {
    toast(`Pull failed: ${e.message}`, "error", 7000);
  } finally {
    activePulls.delete(id);
    await store.refreshModels().catch(() => {});
  }
}

function updateCard(id) {
  const card = document.querySelector(`[data-model-card="${CSS.escape(id)}"]`);
  if (card) decorateCard(card, store.findModel(id));
}

function decorateCard(card, m) {
  if (!m) return;
  const installed = store.downloadedIds().has(m.id);
  const statusArea = card.querySelector("[data-status-area]");
  const badgeArea = card.querySelector("[data-badge-area]");
  clear(badgeArea).append(statusBadge(m, installed));
  clear(statusArea);

  const pull = activePulls.get(m.id);
  if (pull) {
    const pct = Math.round((pull.progress || 0) * 100);
    statusArea.append(
      el("div", { class: "w-full" },
        el("div", { class: "mb-1 flex justify-between text-[10px] text-[#8a8a8a]" },
          el("span", { class: "truncate", text: pull.message || "downloading…" }),
          el("span", { text: `${pct}%` })
        ),
        el("div", { class: "progress" }, el("div", { class: "progress-bar", style: { width: `${pct}%` } }))
      )
    );
    return;
  }

  if (installed) {
    statusArea.append(
      el("div", { class: "flex w-full gap-2" },
        el("a", {
          href: m.task === "stt" ? `#/stt?model=${encodeURIComponent(m.id)}` : `#/tts?model=${encodeURIComponent(m.id)}`,
          class: "btn btn-primary btn-sm flex-1",
          text: m.task === "stt" ? "Transcribe" : "Synthesize",
        }),
        el("button", {
          class: "btn btn-danger btn-sm",
          title: "Delete model",
          html: iconSvg("trash", 14),
          onclick: () =>
            confirmModal({
              title: "Delete model",
              message: `Remove ${m.id} from local storage? You can pull it again later.`,
              confirmLabel: "Delete",
              danger: true,
              onConfirm: async () => {
                try {
                  await api.deleteModel(m.id);
                  toast(`${m.id} deleted`, "info");
                  await store.refreshModels();
                } catch (e) {
                  toast(`Delete failed: ${e.message}`, "error");
                }
              },
            }),
        })
      )
    );
  } else {
    statusArea.append(
      el("button", {
        class: "btn btn-ghost btn-sm w-full",
        disabled: m.runtime === "external",
        title: m.runtime === "external" ? "Requires an external engine — cannot run in Vocal" : "Download model",
        onclick: () => startPull(m.id),
      }, el("span", { html: iconSvg("download", 14) }), m.runtime === "external" ? "External engine" : `Pull · ${m.size_readable || fmtBytes(m.size)}`)
    );
  }
}

export function render(container, params = {}) {
  const state = {
    search: "",
    task: params.get("task") || "all",
    status: "all",
  };

  const grid = el("div", { class: "model-grid" });
  const countLabel = el("span", { class: "text-xs text-[#8a8a8a]" });

  const searchInput = el("input", {
    class: "input",
    type: "search",
    placeholder: "Search models, backends, tags…",
    "aria-label": "Search models",
    oninput: debounce((e) => { state.search = e.target.value.toLowerCase(); drawGrid(); }, 200),
  });
  const taskSelect = el("select", { class: "select", "aria-label": "Filter by task", onchange: (e) => { state.task = e.target.value; drawGrid(); } },
    el("option", { value: "all", text: "All tasks" }),
    el("option", { value: "stt", text: "STT — speech to text" }),
    el("option", { value: "tts", text: "TTS — text to speech" })
  );
  taskSelect.value = state.task;
  const statusSelect = el("select", { class: "select", "aria-label": "Filter by status", onchange: (e) => { state.status = e.target.value; drawGrid(); } },
    el("option", { value: "all", text: "All statuses" }),
    el("option", { value: "installed", text: "Installed" }),
    el("option", { value: "missing", text: "Not downloaded" }),
    el("option", { value: "clone", text: "Clone-capable" })
  );

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Models" }),
      el("p", { text: "The curated catalog — pull weights, inspect licenses and capabilities, then test models in the playgrounds." })
    ),
    el("div", { class: "mb-5 grid gap-3 md:grid-cols-[1fr_auto_auto_auto]" },
      searchInput,
      taskSelect,
      statusSelect,
      el("button", { class: "btn btn-ghost", onclick: () => store.refreshModels().then(() => toast("Catalog refreshed", "info", 1800)).catch((e) => toast(e.message, "error")) },
        el("span", { html: iconSvg("refresh", 14) }), "Refresh")
    ),
    el("div", { class: "mb-3 flex items-center justify-between" }, countLabel),
    grid
  );

  function allModels() {
    // Catalog entries plus any installed model the curated catalog doesn't
    // list (e.g. pulled via CLI) — otherwise those installs are invisible.
    const byId = new Map(store.catalog.map((m) => [m.id, m]));
    for (const m of store.models) {
      if (!byId.has(m.id)) byId.set(m.id, m);
    }
    return [...byId.values()];
  }

  function filtered() {
    const installed = store.downloadedIds();
    return allModels().filter((m) => {
      if (state.task !== "all" && m.task !== state.task) return false;
      if (state.status === "installed" && !installed.has(m.id)) return false;
      if (state.status === "missing" && installed.has(m.id)) return false;
      if (state.status === "clone" && !m.supports_voice_clone) return false;
      if (state.search) {
        const hay = `${m.id} ${m.name} ${m.backend} ${m.description || ""} ${(m.tags || []).join(" ")} ${(m.languages || []).join(" ")}`.toLowerCase();
        if (!hay.includes(state.search)) return false;
      }
      return true;
    });
  }

  function drawGrid() {
    clear(grid);
    const items = filtered();
    countLabel.textContent = `${items.length} of ${allModels().length} models · ${store.models.length} installed`;
    if (store.loading.models && !store.catalog.length) {
      for (let i = 0; i < 6; i++) {
        grid.append(el("div", { class: "card p-5" }, el("div", { class: "skeleton mb-3", style: { height: "1.2rem", width: "60%" } }), el("div", { class: "skeleton mb-2", style: { height: "0.8rem" } }), el("div", { class: "skeleton", style: { height: "2.5rem" } })));
      }
      return;
    }
    if (!items.length) {
      grid.append(el("div", { class: "card", style: { gridColumn: "1 / -1" } }, emptyState("search", "No models match", "Try a different search or filter.")));
      return;
    }
    const installed = store.downloadedIds();
    for (const m of items) {
      const card = el("div", { class: "card card-hover model-card", dataset: { modelCard: m.id } },
        el("div", { class: "flex items-start justify-between gap-2" },
          el("div", { class: "min-w-0" },
            el("p", { class: "truncate text-sm font-bold text-white", text: m.name, title: m.name }),
            el("p", { class: "model-id", text: m.id })
          ),
          el("div", { class: "flex flex-none flex-col items-end gap-1.5" },
            el("div", { dataset: { badgeArea: "" } }),
            badge(m.task, m.task === "stt" ? "blue" : "accent")
          )
        ),
        el("p", { class: "model-desc", text: m.description || "No description provided." }),
        el("div", { class: "flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[#8a8a8a]" },
          el("span", { text: m.backend }),
          el("span", { text: "·" }),
          el("span", { text: m.size_readable || fmtBytes(m.size) }),
          el("span", { text: "·" }),
          el("span", { text: m.parameters || "?" }),
          m.license ? el("span", { class: "text-lightgrey", text: `· ${m.license}${m.commercial_use === false ? " (non-commercial)" : ""}` }) : null
        ),
        el("div", { class: "chip-row" }, capabilityChips(m).map(([t, k]) => badge(t, k))),
        el("div", { class: "mt-auto flex items-center gap-2 pt-1", dataset: { statusArea: "" } }),
        el("button", { class: "cursor-pointer self-start text-[10px] uppercase tracking-widest text-[#8a8a8a] transition-all hover:text-accent", onclick: () => detailModal(m, installed.has(m.id)), text: "Details →" })
      );
      decorateCard(card, m);
      grid.append(card);
    }
  }

  drawGrid();
  let lastSig = `${store.dataVersion}:${store.loading.models}`;
  const unsub = store.subscribe(() => {
    const sig = `${store.dataVersion}:${store.loading.models}`;
    if (sig === lastSig) return;
    lastSig = sig;
    drawGrid();
  });
  if (!store.catalog.length) store.refreshModels().catch((e) => toast(`Failed to load catalog: ${e.message}`, "error"));

  return () => unsub();
}
