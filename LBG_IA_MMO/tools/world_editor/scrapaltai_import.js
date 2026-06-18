/**
 * Import coords IG → layout Scrapaltai (v2)
 * Formats : message dump chat, session key=value, export JSON scrapaltai
 */
(function (global) {
  "use strict";

  function parseDumpLine(text) {
    const out = {};
    const re = /(\w+)=([^\s]+)/g;
    let m;
    while ((m = re.exec(text)) !== null) {
      const k = m[1].toLowerCase();
      let v = m[2];
      if (k === "x" || k === "y" || k === "z" || k === "heading") {
        out[k] = parseFloat(v);
      } else if (k === "cell") {
        out.cell = v === "nil" || v === "null" ? 0 : parseInt(v, 10);
      } else {
        out[k] = v;
      }
    }
    if (out.x == null && out.y == null) return null;
    return out;
  }

  function parseDumpText(text) {
    const lines = (text || "").split(/\r?\n/);
    for (const line of lines) {
      if (/dump\s+/i.test(line) || /\bx=/.test(line)) {
        const d = parseDumpLine(line);
        if (d && d.x != null) return d;
      }
    }
    const trimmed = (text || "").trim();
    if (trimmed.startsWith("{")) {
      try {
        const j = JSON.parse(trimmed);
        if (j.x != null) return j;
        if (j.last_dump) return j.last_dump;
        if (j.world) return { ...j.world, zone: j.zone_id || j.zone };
      } catch (_) { /* ignore */ }
    }
    return parseDumpLine(trimmed);
  }

  function parseSessionText(text) {
    const sess = { last_dump: null, poi: {}, active: false, actor: "" };
    for (const line of (text || "").split(/\r?\n/)) {
      const eq = line.indexOf("=");
      if (eq < 0) continue;
      const k = line.slice(0, eq).trim();
      const v = line.slice(eq + 1).trim();
      if (k === "active") sess.active = v === "1" || v === "true";
      else if (k === "actor") sess.actor = v;
      else if (k === "last_x") {
        sess.last_dump = sess.last_dump || {};
        sess.last_dump.x = parseFloat(v);
      } else if (k === "last_y") {
        sess.last_dump = sess.last_dump || {};
        sess.last_dump.y = parseFloat(v);
      } else if (k === "last_z") {
        sess.last_dump = sess.last_dump || {};
        sess.last_dump.z = parseFloat(v);
      } else if (k === "last_cell") {
        sess.last_dump = sess.last_dump || {};
        sess.last_dump.cell = parseInt(v, 10);
      } else if (k === "last_heading") {
        sess.last_dump = sess.last_dump || {};
        sess.last_dump.heading = parseFloat(v);
      } else if (k.startsWith("wpoi.")) {
        const poiId = k.slice(5);
        const parts = v.split(",");
        if (parts.length >= 5) {
          sess.poi[poiId] = {
            template: parts[0],
            x: parseFloat(parts[1]),
            y: parseFloat(parts[2]),
            z: parseFloat(parts[3]),
            heading: parseFloat(parts[4]),
          };
        }
      }
    }
    if (sess.last_dump && sess.last_dump.x != null) {
      sess.last_dump.zone = "tatooine";
    }
    return sess;
  }

  function parseExportJson(text) {
    const j = JSON.parse(text);
    const pois = j.pois || [];
    const anchor = j.anchor || null;
    return { anchor, pois, meta: j };
  }

  function worldToOffset(wx, wy, anchor) {
    return {
      ox: Math.round(wx - anchor.x),
      oy: Math.round(wy - anchor.y),
    };
  }

  function applyDumpToAnchor(layout, dump) {
    layout.anchor.x = Math.round(dump.x);
    layout.anchor.y = Math.round(dump.y);
    if (dump.z != null) layout.anchor.z = dump.z;
    return layout;
  }

  function applySessionPoisToLayout(layout, sess, options) {
    const snap = options && options.snapGrid;
    const g = layout.grid_spacing_m || 100;
    const bm = {};
    layout.buildings.forEach(b => { bm[b.poi_id] = b; });

    for (const [poiId, p] of Object.entries(sess.poi || {})) {
      let { ox, oy } = worldToOffset(p.x, p.y, layout.anchor);
      if (snap) {
        ox = Math.round(ox / g) * g;
        oy = Math.round(oy / g) * g;
      }
      if (bm[poiId]) {
        bm[poiId].ox = ox;
        bm[poiId].oy = oy;
      } else {
        layout.buildings.push({ poi_id: poiId, ox, oy });
        bm[poiId] = layout.buildings[layout.buildings.length - 1];
      }
    }
    return layout;
  }

  function applyExportPoisToLayout(layout, exportData, options) {
    const snap = options && options.snapGrid;
    const g = layout.grid_spacing_m || 100;
    if (exportData.anchor) {
      applyDumpToAnchor(layout, exportData.anchor);
    }
    const sess = { poi: {} };
    for (const p of exportData.pois) {
      const w = p.world || p;
      sess.poi[p.poi_id] = {
        x: w.x,
        y: w.y,
        z: w.z,
        heading: w.heading,
        template: p.structure_template,
      };
    }
    return applySessionPoisToLayout(layout, sess, { snapGrid: snap });
  }

  global.ScrapaltaiImport = {
    parseDumpText,
    parseSessionText,
    parseExportJson,
    worldToOffset,
    applyDumpToAnchor,
    applySessionPoisToLayout,
    applyExportPoisToLayout,
  };
})(typeof window !== "undefined" ? window : globalThis);
