// Shared client state: catalog, downloaded models, settings, device info.
import * as api from "./api.js";

const listeners = new Set();

export const store = {
  catalog: [],
  models: [],
  settings: null,
  device: null,
  health: null,
  loading: { models: false },
  // Bumped only when catalog/models/settings/device change — NOT on health
  // polls, so views don't rebuild selects (and reset user choices) every 15s.
  dataVersion: 0,

  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  emit() {
    for (const fn of listeners) {
      try {
        fn(store);
      } catch (e) {
        console.error("store listener failed", e);
      }
    }
  },

  async refreshModels() {
    store.loading.models = true;
    store.emit();
    try {
      const [catalog, models] = await Promise.all([api.listCatalog(), api.listModels()]);
      store.catalog = catalog.models || [];
      store.models = models.models || [];
      store.dataVersion++;
    } finally {
      store.loading.models = false;
      store.emit();
    }
  },

  async refreshSettings() {
    store.settings = await api.getSettings();
    store.dataVersion++;
    store.emit();
    return store.settings;
  },

  async refreshDevice() {
    store.device = await api.device();
    store.dataVersion++;
    store.emit();
    return store.device;
  },

  async refreshHealth() {
    try {
      store.health = await api.health();
    } catch {
      store.health = null;
    }
    store.emit();
    return store.health;
  },

  downloadedIds() {
    return new Set(store.models.map((m) => m.id));
  },
  byTask(task) {
    return store.models.filter((m) => m.task === task);
  },
  catalogByTask(task) {
    return store.catalog.filter((m) => m.task === task);
  },
  findModel(id) {
    return store.models.find((m) => m.id === id) || store.catalog.find((m) => m.id === id) || null;
  },
};
