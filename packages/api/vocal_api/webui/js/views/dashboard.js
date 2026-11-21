// Dashboard — server status, hardware, library overview, quick actions.
import { el, clear, iconSvg, badge, skeletonBlock, fmtBytes } from "../ui.js";
import { store } from "../store.js";

const QUICK = [
  { route: "#/tts", icon: "speaker", title: "TTS Studio", desc: "Synthesize speech with any installed voice model" },
  { route: "#/stt", icon: "file", title: "Transcribe", desc: "Upload or record audio, get text or subtitles" },
  { route: "#/live", icon: "activity", title: "Live Dictation", desc: "Streaming microphone transcription over WebSocket" },
  { route: "#/agent", icon: "bot", title: "Voice Agent", desc: "Full realtime loop: mic → STT → LLM → TTS" },
  { route: "#/clone", icon: "copy", title: "Voice Clone", desc: "Speak any text in a reference voice" },
  { route: "#/models", icon: "box", title: "Model Catalog", desc: "Browse, pull and manage 45 voice models" },
];

export function render(container) {
  const root = el("div", {});
  container.append(root);

  const statsRow = el("div", { class: "grid gap-4 sm:grid-cols-2 xl:grid-cols-4" });
  const quickGrid = el("div", { class: "grid gap-4 sm:grid-cols-2 xl:grid-cols-3" });
  const hwPanel = el("div", { class: "panel" });
  const libPanel = el("div", { class: "panel" });

  root.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Dashboard" }),
      el("p", { text: "Your self-hosted speech stack at a glance. Everything runs on this machine." })
    ),
    statsRow,
    el("h3", { class: "panel-title mt-8", html: iconSvg("zap", 15) + "<span>Quick actions</span>" }),
    quickGrid,
    el("div", { class: "mt-8 grid gap-4 lg:grid-cols-2" }, hwPanel, libPanel)
  );

  for (const q of QUICK) {
    quickGrid.append(
      el("a", { href: q.route, class: "card card-hover card-accent flex cursor-pointer items-start gap-4 p-5 transition-all" },
        el("span", { class: "flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-[#3a3a3a] bg-coal text-accent", html: iconSvg(q.icon, 18) }),
        el("span", {},
          el("span", { class: "block text-sm font-bold text-white", text: q.title }),
          el("span", { class: "mt-1 block text-xs leading-relaxed text-lightgrey", text: q.desc })
        )
      )
    );
  }

  function drawStats() {
    clear(statsRow);
    const h = store.health;
    const stt = store.byTask("stt").length;
    const tts = store.byTask("tts").length;
    const gpu = store.device && store.device.cuda_available ? store.device.gpu_devices[0] : null;

    const cards = [
      {
        label: "Server", icon: "server",
        value: h ? "Online" : "Offline",
        sub: h ? `v${h.api_version} · /health ok` : "no response from API",
        color: h ? "var(--circuit-green)" : "var(--danger)",
      },
      {
        label: "Installed models", icon: "box",
        value: String(store.models.length),
        sub: `${stt} STT · ${tts} TTS · ${store.catalog.length} in catalog`,
        color: "var(--accent-green)",
      },
      {
        label: "Compute", icon: "cpu",
        value: gpu ? "CUDA" : "CPU",
        sub: gpu ? gpu.name : `${store.device ? store.device.cpu_count : "?"} threads available`,
        color: gpu ? "var(--circuit-green)" : "var(--electric-blue)",
      },
      {
        label: "VRAM", icon: "layers",
        value: gpu ? `${gpu.vram_gb.toFixed(1)} GB` : "—",
        sub: gpu ? `compute capability ${gpu.compute_capability}` : "no GPU detected",
        color: "var(--electric-blue)",
      },
    ];
    for (const c of cards) {
      statsRow.append(
        el("div", { class: "panel card-accent" },
          el("div", { class: "flex items-center justify-between" },
            el("span", { class: "label mb-0", text: c.label }),
            el("span", { class: "text-[#8a8a8a]", html: iconSvg(c.icon, 16) })
          ),
          el("p", { class: "stat-value mt-2", style: { color: c.color }, text: c.value }),
          el("p", { class: "mt-1 truncate text-xs text-[#8a8a8a]", text: c.sub, title: c.sub })
        )
      );
    }
  }

  function drawHardware() {
    clear(hwPanel);
    hwPanel.append(el("div", { class: "panel-title", html: iconSvg("cpu", 15) + "<span>Hardware</span>" }));
    const d = store.device;
    if (!d) {
      hwPanel.append(skeletonBlock("5rem"));
      return;
    }
    const dl = el("dl", { class: "kv" });
    const rows = [
      ["Platform", d.platform],
      ["Processor", d.processor || "unknown"],
      ["CPU threads", String(d.cpu_count ?? "—")],
      ["CUDA", d.cuda_available ? `available (${d.cuda_version})` : "not available"],
    ];
    for (const g of d.gpu_devices || []) {
      rows.push([`GPU ${g.index}`, `${g.name} · ${g.vram_gb.toFixed(1)} GB · sm_${g.compute_capability.replace(".", "")}`]);
    }
    for (const [k, v] of rows) dl.append(el("dt", { text: k }), el("dd", { text: v }));
    hwPanel.append(dl);
  }

  function drawLibrary() {
    clear(libPanel);
    libPanel.append(el("div", { class: "panel-title", html: iconSvg("box", 15) + "<span>Installed library</span>" }));
    if (store.loading.models && !store.models.length) {
      libPanel.append(skeletonBlock("5rem"));
      return;
    }
    if (!store.models.length) {
      libPanel.append(
        el("p", { class: "text-sm text-lightgrey", text: "No models downloaded yet." }),
        el("a", { href: "#/models", class: "btn btn-primary btn-sm mt-4", text: "Browse catalog" })
      );
      return;
    }
    const list = el("div", { class: "flex flex-col gap-2" });
    for (const m of store.models.slice(0, 6)) {
      list.append(
        el("div", { class: "flex items-center justify-between gap-3 rounded-lg border border-[#3a3a3a] bg-coal px-3 py-2" },
          el("div", { class: "min-w-0" },
            el("p", { class: "truncate text-xs font-semibold text-white", text: m.name }),
            el("p", { class: "truncate text-[10px] text-[#8a8a8a]", text: m.id })
          ),
          el("div", { class: "flex flex-none items-center gap-2" },
            badge(m.task, m.task === "stt" ? "blue" : "accent"),
            el("span", { class: "text-[10px] text-[#8a8a8a]", text: m.size_readable || fmtBytes(m.size) })
          )
        )
      );
    }
    libPanel.append(list);
    if (store.models.length > 6) {
      libPanel.append(el("a", { href: "#/models", class: "mt-3 inline-block cursor-pointer text-xs text-accent transition-all hover:underline", text: `View all ${store.models.length} models →` }));
    }
  }

  function drawAll() {
    drawStats();
    drawHardware();
    drawLibrary();
  }

  drawAll();
  const unsub = store.subscribe(drawAll);
  store.refreshHealth();
  store.refreshDevice().catch(() => {});
  if (!store.catalog.length) store.refreshModels().catch(() => {});

  return () => unsub();
}
