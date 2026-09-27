/**
 * CBS250 Switch Card
 * Front-panel view and port table for the CBS250 Monitor integration.
 *
 *   type: custom:cbs250-switch-card
 *   device_id: <optional, only needed with more than one switch>
 *   uplink: gi17          # optional, shows uplink throughput in the summary
 *   sfp_ports: 2          # optional, number of SFP cages on the right
 *   port_order: odd_top   # optional: odd_top (1,3,5,7 over 2,4,6,8) or sequential
 *   title: Rack switch    # optional, defaults to the switch name
 */

const PLATFORM = "cbs250";

const JACK = { w: 52, h: 42, tab: 22, tabD: 8, gap: 8 };
const BLOCK_W = JACK.w * 4 + JACK.gap * 3;
const ROW_TOP = 38;
const ROW_BOTTOM = ROW_TOP + JACK.h + 8;
const PANEL_H = 170;
const LEFT_ZONE = 190;
const BLOCK_GAP = 40;
const SFP = { w: 70, h: 38, gap: 16 };

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const numState = (hass, eid) => {
  const st = eid && hass.states[eid];
  if (!st) return null;
  const v = parseFloat(st.state);
  return Number.isFinite(v) ? v : null;
};

const strState = (hass, eid) => {
  const st = eid && hass.states[eid];
  return st && st.state !== "unavailable" && st.state !== "unknown" ? st.state : null;
};

const fmtRate = (v) => {
  if (v == null) return "–";
  if (v >= 1000) return `${(v / 1000).toFixed(2)} Gb/s`;
  if (v >= 100) return `${v.toFixed(0)} Mb/s`;
  if (v >= 1) return `${v.toFixed(1)} Mb/s`;
  return `${Math.round(v * 1000)} kb/s`;
};

const fmtSpeed = (v) => {
  if (!v) return null;
  return v >= 1000 ? `${v / 1000} Gb/s` : `${v} Mb/s`;
};

const fmtW = (v) => (v == null ? "–" : `${v.toFixed(1)} W`);

const POE_TEXT = {
  delivering_power: "Delivering power",
  searching: "Not powering",
  disabled: "PoE off",
  fault: "Fault",
  other_fault: "Fault",
  test: "Testing",
};

/** Log-scaled share of the link, so light traffic is still visible. */
const rateFraction = (mbps, linkMbps) => {
  if (!mbps || !linkMbps) return 0;
  const f = Math.log10(1 + mbps * 1000) / Math.log10(1 + linkMbps * 1000);
  return Math.max(0.02, Math.min(1, f));
};

class Cbs250SwitchCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._selected = null;
    this._sig = null;
    this._index = null;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("keydown", (ev) => {
      if ((ev.key === "Enter" || ev.key === " ") && ev.target.closest?.("[data-port]") && ev.target.tagName !== "BUTTON") {
        ev.preventDefault();
        this._onClick(ev);
      }
      if (ev.key === "Escape" && this._selected != null) {
        this._selected = null;
        this._render(true);
      }
    });
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { sfp_ports: 2, port_order: "odd_top", ...(config || {}) };
    this._sig = null;
    if (this._hass) this._render(true);
  }

  set hass(hass) {
    this._hass = hass;
    this._render(false);
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  // ---------------------------------------------------------------- model

  _buildIndex(hass) {
    if (this._index && this._index.ents === hass.entities && this._index.devs === hass.devices) {
      return this._index;
    }
    const byDevice = new Map();
    let firstSwitch = null;
    for (const ent of Object.values(hass.entities || {})) {
      if (ent.platform !== PLATFORM || !ent.device_id || !ent.translation_key) continue;
      if (!byDevice.has(ent.device_id)) byDevice.set(ent.device_id, {});
      byDevice.get(ent.device_id)[ent.translation_key] = ent.entity_id;
      if (ent.translation_key === "total_poe_power" && !firstSwitch) firstSwitch = ent.device_id;
    }
    this._index = { ents: hass.entities, devs: hass.devices, byDevice, firstSwitch };
    return this._index;
  }

  _model() {
    const hass = this._hass;
    const idx = this._buildIndex(hass);
    const switchId = this._config.device_id || idx.firstSwitch;
    const sw = switchId && hass.devices?.[switchId];
    if (!sw) return null;

    const swEnts = idx.byDevice.get(switchId) || {};
    const ports = new Map();
    for (const dev of Object.values(hass.devices)) {
      if (dev.via_device_id !== switchId) continue;
      let label = (dev.model || "").replace(/^Port\s+/, "");
      if (!label) {
        const ident = (dev.identifiers || []).find((i) => i[0] === PLATFORM);
        const m = ident && String(ident[1]).match(/_port_(\d+)$/);
        label = m ? `gi${m[1]}` : "";
      }
      const m = label.match(/(\d+)\D*$/);
      if (!m) continue;
      const n = parseInt(m[1], 10);
      const e = idx.byDevice.get(dev.id) || {};
      const name = dev.name_by_user || dev.name || label;
      const status = strState(hass, e.link_status);
      ports.set(n, {
        n,
        label,
        name,
        labelled: name !== label,
        up: status === "up",
        speed: numState(hass, e.link_speed),
        rx: numState(hass, e.rx_throughput),
        tx: numState(hass, e.tx_throughput),
        poe: numState(hass, e.poe_power),
        poeStatus: strState(hass, e.poe_status),
        cable: numState(hass, e.cable_length),
        ents: e,
      });
    }

    const portsUpState = swEnts.ports_up && hass.states[swEnts.ports_up];
    const maxSeen = Math.max(0, ...ports.keys());
    const total = parseInt(portsUpState?.attributes?.total_ports, 10) || Math.max(maxSeen, 18);

    return {
      title: this._config.title || sw.name_by_user || sw.name || "Switch",
      dark: !!hass.themes?.darkMode,
      total,
      ports,
      portsUp: numState(hass, swEnts.ports_up),
      poeTotal: numState(hass, swEnts.total_poe_power),
      poeBudget: numState(hass, swEnts.poe_budget),
      poeTotalEid: swEnts.total_poe_power,
      portsUpEid: swEnts.ports_up,
    };
  }

  // ---------------------------------------------------------------- events

  _onClick(ev) {
    const t = ev.target.closest?.("[data-eid],[data-port],[data-close]");
    if (!t) return;
    if (t.dataset.close != null) {
      this._selected = null;
    } else if (t.dataset.eid) {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", { detail: { entityId: t.dataset.eid }, bubbles: true, composed: true })
      );
      return;
    } else if (t.dataset.port) {
      const n = parseInt(t.dataset.port, 10);
      this._selected = this._selected === n ? null : n;
    }
    this._render(true);
  }

  // ---------------------------------------------------------------- render

  _render(force) {
    if (!this._hass || !this._config) return;
    const model = this._model();
    const sig = JSON.stringify([model && [...model.ports.values()].map((p) => [p.n, p.name, p.up, p.speed, p.rx, p.tx, p.poe, p.poeStatus, p.cable]),
      model?.portsUp, model?.poeTotal, model?.poeBudget, model?.dark, model?.title, this._selected]);
    if (!force && sig === this._sig) return;
    this._sig = sig;

    // Keep keyboard focus across refreshes.
    const active = this.shadowRoot.activeElement;
    const focusKey = active ? `${active.dataset?.focus || ""}` : "";

    if (!model) {
      this.shadowRoot.innerHTML = `${STYLE}<ha-card><div class="empty">
        <p>No CBS250 switch found.</p>
        <p class="sub">Add the CBS250 Monitor integration, or set <code>device_id</code> in the card configuration if you have more than one switch.</p>
      </div></ha-card>`;
      return;
    }
    if (this._selected != null && !model.ports.has(this._selected)) this._selected = null;

    this.shadowRoot.innerHTML = `${STYLE}
      <ha-card class="${model.dark ? "dark" : ""}">
        <div class="head">
          <h2>${esc(model.title)}</h2>
          ${this._summary(model)}
        </div>
        <div class="panel-wrap">${this._faceplate(model)}</div>
        ${this._detail(model)}
        ${this._table(model)}
      </ha-card>`;

    if (focusKey) this.shadowRoot.querySelector(`[data-focus="${focusKey}"]`)?.focus();
  }

  _summary(m) {
    const up = m.portsUp ?? [...m.ports.values()].filter((p) => p.up).length;
    const parts = [
      `<button class="stat" data-eid="${esc(m.portsUpEid || "")}" data-focus="s-ports">
         <span class="big">${up}</span><span class="of">of ${m.total} ports connected</span>
       </button>`,
    ];
    if (m.poeTotal != null) {
      const pct = m.poeBudget ? Math.min(100, (m.poeTotal / m.poeBudget) * 100) : 0;
      parts.push(`<button class="stat poe" data-eid="${esc(m.poeTotalEid || "")}" data-focus="s-poe">
         <span class="big">${m.poeTotal.toFixed(1)} W</span>
         <span class="of">PoE${m.poeBudget ? ` of ${m.poeBudget.toFixed(0)} W` : ""}</span>
         ${m.poeBudget ? `<span class="meter" role="img" aria-label="${pct.toFixed(0)}% of PoE budget"><i style="width:${pct}%"></i></span>` : ""}
       </button>`);
    }
    const upl = this._config.uplink && [...m.ports.values()].find((p) => p.label === this._config.uplink);
    if (upl) {
      parts.push(`<div class="stat">
         <span class="rates"><span data-eid="${esc(upl.ents.rx_throughput || "")}" class="rate"><span class="arrow" aria-label="Download">↓</span>${fmtRate(upl.rx)}</span>
         <span data-eid="${esc(upl.ents.tx_throughput || "")}" class="rate"><span class="arrow" aria-label="Upload">↑</span>${fmtRate(upl.tx)}</span></span>
         <span class="of">Uplink on ${esc(upl.label)}</span>
       </div>`);
    }
    return `<div class="stats">${parts.join("")}</div>`;
  }

  _layout(m) {
    const sfp = Math.max(0, Math.min(this._config.sfp_ports ?? 2, m.total));
    const copper = m.total - sfp;
    const blocks = Math.ceil(copper / 8);
    const blocksEnd = LEFT_ZONE + blocks * BLOCK_W + Math.max(0, blocks - 1) * BLOCK_GAP;
    const sfpStart = blocksEnd + BLOCK_GAP;
    const width = (sfp ? sfpStart + sfp * SFP.w + (sfp - 1) * SFP.gap : blocksEnd) + 30;
    const slots = [];
    for (let i = 0; i < copper; i++) {
      const n = i + 1;
      const block = Math.floor(i / 8);
      const k = i % 8;
      let col, row;
      if (this._config.port_order === "sequential") {
        row = k < 4 ? 0 : 1;
        col = k % 4;
      } else {
        row = k % 2;
        col = Math.floor(k / 2);
      }
      const x = LEFT_ZONE + block * (BLOCK_W + BLOCK_GAP) + col * (JACK.w + JACK.gap);
      slots.push({ n, kind: "rj45", x, y: row ? ROW_BOTTOM : ROW_TOP, flip: row === 1 });
    }
    for (let j = 0; j < sfp; j++) {
      slots.push({ n: copper + j + 1, kind: "sfp", x: sfpStart + j * (SFP.w + SFP.gap), y: 66 });
    }
    return { slots, width };
  }

  _faceplate(m) {
    const { slots, width } = this._layout(m);
    const jackPath = (x, y, flip, grow = 0) => {
      x -= grow; y -= grow;
      const w = JACK.w + grow * 2, h = JACK.h + grow * 2;
      const tab = JACK.tab + grow * 2, tabD = JACK.tabD;
      const tx = x + (w - tab) / 2;
      return flip
        ? `M${x},${y} H${x + w} V${y + h - tabD} H${tx + tab} V${y + h} H${tx} V${y + h - tabD} H${x} Z`
        : `M${x},${y + tabD} H${tx} V${y} H${tx + tab} V${y + tabD} H${x + w} V${y + h} H${x} Z`;
    };
    const bolt = (cx, cy) =>
      `<path class="bolt" transform="translate(${cx - 7},${cy - 8})" d="M8.5 0 L1 9.5 H6.5 L5 16 L13 6 H7.5 Z"/>`;

    const parts = [];
    // Left zone: echoes the real switch without the brand mark.
    parts.push(`<text class="model" x="28" y="44">CBS250</text>
      <circle class="deco" cx="44" cy="112" r="6"/>
      <rect class="deco" x="70" y="106" width="22" height="12" rx="2"/>
      <rect class="deco-port" x="110" y="84" width="54" height="50" rx="3"/>
      <rect class="deco" x="116" y="66" width="42" height="12" rx="2"/>`);

    for (const s of slots) {
      const p = m.ports.get(s.n);
      const sel = this._selected === s.n;
      const cls = !p ? "idle" : p.up ? (p.speed && p.speed < 1000 ? "up slow" : "up") : "known";
      const title = p
        ? `${p.name}${p.labelled ? `, ${p.label}` : ""}, ${p.up ? `connected at ${fmtSpeed(p.speed) || "unknown speed"}` : "disconnected"}${p.poe ? `, ${fmtW(p.poe)}` : ""}`
        : `Port ${s.n}, not in use`;
      const attrs = p
        ? `data-port="${s.n}" data-focus="j-${s.n}" tabindex="0" role="button" aria-pressed="${sel}"`
        : "";
      if (s.kind === "rj45") {
        const { w, h } = JACK;
        const contactsY = s.flip ? s.y + 5 : s.y + h - 9;
        const contacts = Array.from({ length: 8 }, (_, i) =>
          `<rect class="pin" x="${s.x + 10 + i * 4.3}" y="${contactsY}" width="2" height="4"/>`).join("");
        const labelY = s.flip ? s.y + h + 17 : s.y - 8;
        parts.push(`<g class="jack ${cls}${sel ? " sel" : ""}" ${attrs}>
          <title>${esc(title)}</title>
          <path class="body" d="${jackPath(s.x, s.y, s.flip)}"/>
          ${contacts}
          ${p && p.poeStatus === "delivering_power" ? bolt(s.x + w / 2, s.y + h / 2 + (s.flip ? -2 : 3)) : ""}
          ${sel ? `<path class="ring" d="${jackPath(s.x, s.y, s.flip, 4)}"/>` : ""}
          <text class="num" x="${s.x + w / 2}" y="${labelY}">${s.n}</text>
        </g>`);
      } else {
        parts.push(`<g class="jack sfp ${cls}${sel ? " sel" : ""}" ${attrs}>
          <title>${esc(title)}</title>
          <rect class="body" x="${s.x}" y="${s.y}" width="${SFP.w}" height="${SFP.h}" rx="3"/>
          <rect class="cage" x="${s.x + 8}" y="${s.y + 10}" width="${SFP.w - 16}" height="${SFP.h - 20}" rx="2"/>
          ${sel ? `<rect class="ring" x="${s.x - 4}" y="${s.y - 4}" width="${SFP.w + 8}" height="${SFP.h + 8}" rx="6"/>` : ""}
          <text class="num" x="${s.x + SFP.w / 2}" y="${s.y + SFP.h + 20}">${s.n}</text>
        </g>`);
      }
    }
    return `<svg class="panel" viewBox="0 0 ${width} ${PANEL_H}" role="group" aria-label="Switch front panel">
      <rect class="plate" x="1" y="1" width="${width - 2}" height="${PANEL_H - 2}" rx="8"/>
      ${parts.join("")}
    </svg>`;
  }

  _detail(m) {
    if (this._selected == null) return "";
    const p = m.ports.get(this._selected);
    if (!p) return "";
    const sub = p.up ? `connected at ${fmtSpeed(p.speed) || "unknown speed"}` : "disconnected";
    const metric = (label, value, eid, note) =>
      eid
        ? `<button class="metric" data-eid="${esc(eid)}" data-focus="m-${esc(label)}">
             <span class="ml">${label}</span><span class="mv">${value}</span>${note ? `<span class="mn">${esc(note)}</span>` : ""}
           </button>`
        : "";
    return `<section class="detail" aria-label="${esc(p.name)} details">
      <div class="dh">
        <div>
          <h3>${esc(p.name)}</h3>
          <p>${p.labelled ? `${esc(p.label)}, ` : ""}${sub}</p>
        </div>
        <button class="x" data-close aria-label="Close port details" data-focus="close">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6 L18 18 M18 6 L6 18"/></svg>
        </button>
      </div>
      <div class="metrics">
        ${metric("Download", fmtRate(p.rx), p.ents.rx_throughput)}
        ${metric("Upload", fmtRate(p.tx), p.ents.tx_throughput)}
        ${metric("PoE power", fmtW(p.poe), p.ents.poe_power, POE_TEXT[p.poeStatus] || "")}
        ${metric("Cable length", p.cable != null ? `${p.cable} m` : "–", p.ents.cable_length)}
      </div>
    </section>`;
  }

  _table(m) {
    const ports = [...m.ports.values()].sort((a, b) => a.n - b.n);
    if (!ports.length) {
      return `<p class="none">Ports appear here once something is connected, or when you give a port a description on the switch.</p>`;
    }
    const rows = ports
      .map((p) => {
        const sel = this._selected === p.n;
        const speed = fmtSpeed(p.speed);
        const sub = p.up ? (p.labelled ? `${p.label}, ${speed || ""}` : speed || "") : p.labelled ? `${p.label}, disconnected` : "Disconnected";
        const swatch = !p.up ? "known" : p.speed && p.speed < 1000 ? "up slow" : "up";
        const bar = (f) => `<span class="bar"><i style="width:${(f * 100).toFixed(1)}%"></i></span>`;
        return `<button class="row${p.up ? "" : " down"}${sel ? " sel" : ""}" data-port="${p.n}" data-focus="r-${p.n}" aria-pressed="${sel}">
          <span class="sw ${swatch}" aria-hidden="true"></span>
          <span class="who"><span class="nm">${esc(p.name)}</span><span class="sub">${esc(sub)}</span></span>
          <span class="met rx"><span class="v">${p.up ? fmtRate(p.rx) : "–"}</span>${bar(p.up ? rateFraction(p.rx, p.speed) : 0)}</span>
          <span class="met tx"><span class="v">${p.up ? fmtRate(p.tx) : "–"}</span>${bar(p.up ? rateFraction(p.tx, p.speed) : 0)}</span>
          <span class="met poe"><span class="v">${p.ents.poe_power ? (p.poe ? fmtW(p.poe) : "–") : ""}</span>${p.ents.poe_power ? bar(p.poe ? Math.min(1, p.poe / 30) : 0) : ""}</span>
        </button>`;
      })
      .join("");
    return `<div class="table" role="list">
      <div class="th" aria-hidden="true"><span></span><span>Port</span><span>Download</span><span>Upload</span><span>PoE</span></div>
      ${rows}
    </div>`;
  }
}

const STYLE = `<style>
  :host { display: block; }
  ha-card {
    --plate: #e3e6e9; --plate-edge: #c7ccd1; --plate-ink: #6c747c;
    --jack: #3a3f45; --jack-known: #50575f; --pin: #8b939b;
    --link: #2aa864; --link-slow: #df9a2f; --bolt: #ffd23f;
    --muted: var(--secondary-text-color);
    --rule: var(--divider-color, rgba(127,127,127,.2));
    display: block;
    container-type: inline-size;
    padding: 16px 16px 8px;
    overflow: hidden;
  }
  ha-card.dark {
    --plate: #3b4046; --plate-edge: #4d535a; --plate-ink: #a3abb3;
    --jack: #1e2226; --jack-known: #2c3137; --pin: #5b636b;
  }
  button { font: inherit; color: inherit; background: none; border: 0; padding: 0; text-align: inherit; cursor: pointer; }
  :focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; border-radius: 6px; }

  .head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 24px; margin-bottom: 14px; }
  h2 { margin: 0; font-size: 1.25rem; font-weight: 500; line-height: 1.2; }
  .stats { display: flex; flex-wrap: wrap; gap: 6px 28px; }
  .stat { display: grid; grid-template-columns: auto; gap: 1px; min-width: 0; }
  .stat .big { font-size: 1.15rem; font-weight: 500; font-variant-numeric: tabular-nums; line-height: 1.2; }
  .stat .of { font-size: .8rem; color: var(--muted); }
  .stat.poe { min-width: 120px; }
  .meter { display: block; height: 3px; border-radius: 2px; background: var(--rule); margin-top: 4px; overflow: hidden; }
  .meter i { display: block; height: 100%; background: var(--bolt); filter: saturate(.85); }
  .rates { display: flex; gap: 12px; font-size: 1.15rem; font-weight: 500; font-variant-numeric: tabular-nums; }
  .rate { cursor: pointer; }
  .arrow { color: var(--muted); margin-right: 3px; font-weight: 400; }

  .panel-wrap { margin: 0 -2px; }
  .panel { display: block; width: 100%; height: auto; }
  .plate { fill: var(--plate); stroke: var(--plate-edge); }
  .model { fill: var(--plate-ink); font-size: 15px; font-weight: 600; letter-spacing: .02em; }
  .deco { fill: none; stroke: var(--plate-ink); stroke-width: 1.5; opacity: .55; }
  .deco-port { fill: var(--jack); opacity: .45; }
  .num { fill: var(--plate-ink); font-size: 12px; text-anchor: middle; font-variant-numeric: tabular-nums; }
  .jack .body { fill: var(--jack); transition: fill .25s; }
  .jack.known .body { fill: var(--jack-known); }
  .jack.up .body { fill: var(--link); }
  .jack.up.slow .body { fill: var(--link-slow); }
  .jack .pin { fill: var(--pin); }
  .jack.up .pin { fill: rgba(0,0,0,.28); }
  .jack.sfp .cage { fill: rgba(0,0,0,.35); }
  .jack.idle { opacity: .42; }
  .jack[data-port] { cursor: pointer; }
  .jack[data-port]:hover .body { filter: brightness(1.12); }
  .jack:focus { outline: none; }
  .jack:focus-visible .body { stroke: var(--primary-color); stroke-width: 3; }
  .ring { fill: none; stroke: var(--primary-color); stroke-width: 2.5; }
  .bolt { fill: var(--bolt); stroke: rgba(0,0,0,.45); stroke-width: .8; }

  .detail { margin: 14px 0 4px; padding: 14px 14px 12px; border-radius: 10px;
    background: color-mix(in srgb, var(--primary-color) 7%, transparent);
    border: 1px solid color-mix(in srgb, var(--primary-color) 25%, transparent); }
  .dh { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .dh h3 { margin: 0; font-size: 1.05rem; font-weight: 500; }
  .dh p { margin: 2px 0 0; font-size: .85rem; color: var(--muted); }
  .x { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 50%; margin: -6px -6px 0 0; }
  .x:hover { background: var(--rule); }
  .x svg { width: 18px; height: 18px; stroke: var(--muted); stroke-width: 2; stroke-linecap: round; }
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px 16px; margin-top: 12px; }
  .metric { display: grid; align-content: start; gap: 1px; padding: 6px 8px; margin: -6px -8px; border-radius: 8px; }
  .metric:hover { background: var(--rule); }
  .ml { font-size: .78rem; color: var(--muted); }
  .mv { font-size: 1.1rem; font-weight: 500; font-variant-numeric: tabular-nums; }
  .mn { font-size: .75rem; color: var(--muted); }

  .table { margin-top: 12px; }
  .th, .row { display: grid; grid-template-columns: 10px minmax(0, 1.6fr) repeat(3, minmax(0, 1fr)); gap: 12px; align-items: center; }
  .th { font-size: .75rem; color: var(--muted); padding: 0 8px 6px; border-bottom: 1px solid var(--rule); }
  .row { width: 100%; box-sizing: border-box; padding: 9px 8px; border-bottom: 1px solid var(--rule); border-radius: 0; }
  .row:last-child { border-bottom: 0; }
  .row:hover { background: color-mix(in srgb, var(--primary-text-color) 4%, transparent); }
  .row.sel { background: color-mix(in srgb, var(--primary-color) 9%, transparent); }
  .row.down .nm, .row.down .v { color: var(--muted); }
  .sw { width: 10px; height: 10px; border-radius: 3px; background: var(--jack-known); box-shadow: inset 0 0 0 1px var(--pin); }
  .sw.up { box-shadow: none; }
  .sw.up { background: var(--link); }
  .sw.up.slow { background: var(--link-slow); }
  .who { display: grid; min-width: 0; }
  .nm { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { font-size: .78rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .met { display: grid; gap: 4px; min-width: 0; }
  .v { font-variant-numeric: tabular-nums; font-size: .9rem; white-space: nowrap; }
  .bar { display: block; height: 3px; border-radius: 2px; background: var(--rule); overflow: hidden; }
  .bar i { display: block; height: 100%; background: var(--link); opacity: .8; }
  .met.poe .bar i { background: var(--bolt); }

  .none, .empty { color: var(--muted); font-size: .9rem; margin: 14px 4px 10px; }
  .empty { padding: 8px 4px; }
  .empty p { margin: 0 0 6px; color: var(--primary-text-color); }
  .empty .sub { color: var(--muted); white-space: normal; }

  @container (max-width: 520px) {
    .th { display: none; }
    .row { grid-template-columns: 10px minmax(0, 1fr) auto 64px; grid-template-rows: auto auto; row-gap: 2px; column-gap: 12px; }
    .row .sw { grid-row: 1 / span 2; }
    .row .who { grid-column: 2; grid-row: 1 / span 2; }
    .row .met { justify-items: end; }
    .row .met .bar { display: none; }
    .row .met.rx { grid-column: 3; grid-row: 1; }
    .row .met.tx { grid-column: 3; grid-row: 2; }
    .row .met.poe { grid-column: 4; grid-row: 1 / span 2; }
    .row .met.rx .v::before { content: "↓ "; color: var(--muted); }
    .row .met.tx .v::before { content: "↑ "; color: var(--muted); }
    .row .v { font-size: .85rem; }
  }
  @media (prefers-reduced-motion: reduce) { .jack .body { transition: none; } }
</style>`;

customElements.define("cbs250-switch-card", Cbs250SwitchCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "cbs250-switch-card",
  name: "CBS250 switch",
  description: "Front panel and port table for a CBS250 switch.",
  preview: false,
});
