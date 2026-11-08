/* Per-field keys prevent an unchanged/stale tab from overwriting other work. */
(() => {
  'use strict';
  function create(storage, key, ids) {
    const state = {};
    const dirty = new Map();
    let available = true;
    let legacy = {};
    try {
      const parsed = JSON.parse(storage.getItem(key) || '{}');
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) legacy = parsed;
    } catch { available = false; }
    const valid = (field, value) => field === 'notes' ? typeof value === 'string' : typeof value === 'boolean';
    const fallback = field => field === 'notes' ? '' : false;
    const fieldKey = (id, field) => key + ':' + id + ':' + field;
    for (const id of ids) {
      state[id] = {};
      for (const field of ['notes', 'done']) {
        let value = legacy[id] && legacy[id][field];
        try {
          const raw = storage.getItem(fieldKey(id, field));
          if (raw !== null) value = JSON.parse(raw);
        } catch { available = false; }
        state[id][field] = valid(field, value) ? value : fallback(field);
      }
    }
    return {
      state,
      get available() { return available; },
      update(id, field, value) {
        if (!Object.hasOwn(state, id) || !['notes', 'done'].includes(field) || !valid(field, value)) {
          throw new TypeError('Unknown practice field');
        }
        state[id][field] = value;
        dirty.set(fieldKey(id, field), { id, field });
      },
      save() {
        if (!dirty.size) return available;
        try {
          for (const [name, { id, field }] of dirty) {
            storage.setItem(name, JSON.stringify(state[id][field]));
            dirty.delete(name);
          }
          available = true;
        } catch { available = false; }
        return available;
      },
      receive(name, raw) {
        if (name === null) {
          for (const id of ids) for (const field of ['notes', 'done']) {
            if (!dirty.has(fieldKey(id, field))) state[id][field] = fallback(field);
          }
          return;
        }
        if (!name.startsWith(key + ':') || dirty.has(name)) return;
        const suffix = name.slice(key.length + 1).split(':');
        const [id, field] = suffix;
        if (suffix.length !== 2 || !Object.hasOwn(state, id) || !['notes', 'done'].includes(field)) return;
        try {
          const value = raw === null ? fallback(field) : JSON.parse(raw);
          if (valid(field, value)) state[id][field] = value;
        } catch { /* An invalid value from another tab must not break local input. */ }
      },
    };
  }
  globalThis.MLPracticeStore = { create };
})();
