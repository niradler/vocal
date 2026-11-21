// Vocal console — hash router, shell wiring, health polling.
import { el, clear, iconSvg, badge } from "./ui.js";
import { store } from "./store.js";
import { detectApiBase, setApiBase, getApiBase, isHosted, openConnectionModal } from "./connection.js";

const ROUTES = [
  { path: "/dashboard", title: "Dashboard", icon: "dashboard", section: "Overview", load: () => import("./views/dashboard.js") },
  { path: "/tts", title: "TTS Studio", icon: "speaker", section: "Playgrounds", load: () => import("./views/tts.js") },
  { path: "/stt", title: "Transcribe", icon: "file", section: "Playgrounds", load: () => import("./views/stt.js") },
  { path: "/live", title: "Live Dictation", icon: "activity", section: "Playgrounds", load: () => import("./views/live.js") },
  { path: "/agent", title: "Voice Agent", icon: "bot", section: "Playgrounds", load: () => import("./views/agent.js") },
  { path: "/clone", title: "Voice Clone", icon: "copy", section: "Playgrounds", load: () => import("./views/clone.js") },
  { path: "/models", title: "Models", icon: "box", section: "Manage", load: () => import("./views/models.js") },
  { path: "/settings", title: "Settings", icon: "settings", section: "Manage", load: () => import("./views/settings.js") },
];

const nav = document.getElementById("nav");
const viewArea = document.getElementById("view");
const viewTitle = document.getElementById("view-title");
const sidebar = document.getElementById("sidebar");
const backdrop = document.getElementById("sidebar-backdrop");
const hamburger = document.getElementById("hamburger");

let currentDestroy = null;
let navSeq = 0;

/* ---------- navigation ---------- */
function buildNav() {
  let lastSection = null;
  for (const route of ROUTES) {
    if (route.section !== lastSection) {
      nav.append(el("p", { class: "nav-section", text: route.section }));
      lastSection = route.section;
    }
    nav.append(
      el("a", {
        href: `#${route.path}`,
        class: "nav-item",
        dataset: { route: route.path },
        onclick: () => closeSidebar(),
      }, el("span", { html: iconSvg(route.icon, 17) }), route.title)
    );
  }
}

function markActive(path) {
  for (const item of nav.querySelectorAll(".nav-item")) {
    item.classList.toggle("active", item.dataset.route === path);
  }
}

function openSidebar() {
  sidebar.classList.add("open");
  backdrop.classList.remove("hidden");
}
function closeSidebar() {
  sidebar.classList.remove("open");
  backdrop.classList.add("hidden");
}
hamburger.addEventListener("click", openSidebar);
backdrop.addEventListener("click", closeSidebar);

/* ---------- router ---------- */
function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/dashboard";
  const [path, query = ""] = raw.split("?");
  return { path: path.startsWith("/") ? path : `/${path}`, params: new URLSearchParams(query) };
}

async function navigate() {
  const seq = ++navSeq;
  const { path, params } = parseHash();
  const route = ROUTES.find((r) => r.path === path) || ROUTES[0];
  markActive(route.path);
  viewTitle.textContent = route.title;
  document.title = `${route.title} · Vocal Console`;

  if (currentDestroy) {
    try {
      currentDestroy();
    } catch (e) {
      console.error("view cleanup failed", e);
    }
    currentDestroy = null;
  }
  clear(viewArea);

  try {
    const mod = await route.load();
    // Guard against races: a newer navigation superseded this one while the
    // module loaded (e.g. boot hash-set + hashchange firing together).
    if (seq !== navSeq) return;
    currentDestroy = mod.render(viewArea, params) || null;
  } catch (e) {
    if (seq !== navSeq) return;
    console.error(e);
    viewArea.append(
      el("div", { class: "panel" },
        el("p", { class: "text-sm font-semibold text-[#ff5c5c]", text: "Failed to load view" }),
        el("p", { class: "mt-2 text-xs text-lightgrey", text: String(e && e.message ? e.message : e) })
      )
    );
  }
}

window.addEventListener("hashchange", navigate);

/* ---------- health polling ---------- */
const topbarHealth = document.getElementById("topbar-health");
const sidebarDot = document.getElementById("sidebar-dot");
const sidebarStatus = document.getElementById("sidebar-status");
const sidebarVersion = document.getElementById("sidebar-version");

function drawHealth() {
  const h = store.health;
  clear(topbarHealth);
  if (h) {
    topbarHealth.className = "badge badge-green hidden sm:inline-flex";
    topbarHealth.append(el("span", { class: "dot dot-live" }), `online · v${h.api_version}`);
    sidebarDot.className = "dot dot-live";
    sidebarStatus.textContent = "server online";
    sidebarVersion.textContent = `API v${h.api_version}`;
  } else {
    topbarHealth.className = "badge badge-red hidden sm:inline-flex";
    topbarHealth.append(el("span", { class: "dot dot-off" }), "offline");
    sidebarDot.className = "dot dot-off";
    sidebarStatus.textContent = "server offline";
    sidebarVersion.textContent = isHosted() ? "start it: vocal serve" : "check the API process";
  }
}

/* ---------- server connection (local vs hosted console) ---------- */
const serverBtn = document.getElementById("server-btn");
const serverBtnLabel = document.getElementById("server-btn-label");
const docsLink = document.getElementById("docs-link");
const homeLink = document.getElementById("home-link");

function drawServerButton() {
  const base = getApiBase();
  serverBtnLabel.textContent = base ? base.replace(/^https?:\/\//, "") : "this server";
  serverBtn.title = `Vocal server: ${base || location.origin}`;
  // Docs live on the API server; the landing page is next to this file when hosted.
  docsLink.href = `${base}/docs`;
  homeLink.href = isHosted() ? "index.html" : "/";
}
serverBtn.addEventListener("click", openConnectionModal);

/* ---------- boot ---------- */
async function boot() {
  // Resolve which Vocal server to talk to before any request fires.
  setApiBase(await detectApiBase());
  drawServerButton();

  buildNav();
  if (!location.hash) location.hash = "#/dashboard";
  navigate();
  store.refreshModels().catch(() => {});
  store.refreshSettings().catch(() => {});
  store.refreshDevice().catch(() => {});

  store.subscribe(drawHealth);
  const health = await store.refreshHealth();
  setInterval(() => store.refreshHealth(), 15000);
  // Hosted console with no reachable server: show the connection dialog once
  // so the user can point it at their Vocal instance (or start one).
  if (isHosted() && !health) openConnectionModal();
}
boot();
