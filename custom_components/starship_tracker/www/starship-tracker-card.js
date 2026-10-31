/* Starship Tracker card — livrée avec l'intégration starship_tracker (aucune install séparée). */
const CARD_VERSION = "1.10.0";

const KEYS = {
  live: ["binary_sensor", "starship_live", "binary_sensor.starship_tracker_starship_live"],
  next: ["sensor", "next_mission", "sensor.starship_tracker_next_starship_mission"],
  countdown: ["sensor", "countdown", "sensor.starship_tracker_starship_launch_countdown"],
  status: ["sensor", "mission_status", "sensor.starship_tracker_starship_mission_status"],
  missions: ["sensor", "missions", "sensor.starship_tracker_starship_missions"],
  news: ["sensor", "news", "sensor.starship_tracker_starship_news"],
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

class StarshipTrackerCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { show_news: true, news_count: 5, show_missions: true, missions_count: 3, ...(config || {}) };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._timer && clearInterval(this._timer);
    this._timer = setInterval(() => this._render(), 30000);
  }

  disconnectedCallback() {
    this._timer && clearInterval(this._timer);
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _entity(key) {
    if (this._config[key]) return this._config[key];
    const [domain, tkey, fallback] = KEYS[key];
    const reg = this._hass.entities || {};
    const found = Object.keys(reg).find(
      (id) => id.startsWith(domain + ".") && reg[id].platform === "starship_tracker" && reg[id].translation_key === tkey
    );
    return found || fallback;
  }

  _state(key) {
    return this._hass.states[this._entity(key)];
  }

  _countdown(cd) {
    const t = cd && Date.parse(cd.state);
    if (!t) return "—";
    let s = Math.floor((t - Date.now()) / 1000);
    if (s <= 0) return "T-0";
    const d = Math.floor(s / 86400); s %= 86400;
    const h = Math.floor(s / 3600); s %= 3600;
    const m = Math.floor(s / 60);
    return `T- ${d}j ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
  }

  _render() {
    if (!this._hass || !this.shadowRoot) return;
    const lang = (this._hass.locale?.language || this._hass.language || "en").startsWith("fr") ? "fr" : "en";
    const L = lang === "fr"
      ? { provider: "Fournisseur", vehicle: "Véhicule", pad: "Rampe de lancement", location: "Emplacement", date: "Date cible",
          countdown: "Compte à rebours", tags: "Tags", live: "EN DIRECT", nolive: "Pas de live en cours", watch: "Regarder",
          news: "Actualités Starship", nonews: "Aucune actualité", details: "Détails", none: "Aucune mission annoncée",
          upcoming: "Prochaines missions Starship", past: "Derniers vols Starship", video: "▶ Vidéo", nomission: "Aucune" }
      : { provider: "Provider", vehicle: "Vehicle", pad: "Launch Pad", location: "Location", date: "Target Date",
          countdown: "Countdown", tags: "Tags", live: "LIVE", nolive: "No live stream", watch: "Watch",
          news: "Starship news", nonews: "No news", details: "Details", none: "No mission announced",
          upcoming: "Upcoming Starship missions", past: "Latest Starship flights", video: "▶ Video", nomission: "None" };

    const next = this._state("next");
    const a = next?.attributes || {};
    const hasMission = next && !["unknown", "unavailable", ""].includes(next.state);
    const live = this._state("live");
    const isLive = live?.state === "on";
    const status = this._state("status");
    const cd = this._state("countdown");
    const url = safeUrl(a.url) || safeUrl(live?.attributes?.url) || "https://www.spacex.com/vehicles/starship";
    let date = a.launch_date || "TBD";
    if (cd && Date.parse(cd.state)) {
      date = new Date(cd.state).toLocaleString(lang, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    }
    const tags = [a.mission_type, status?.state && !["unknown", "unavailable"].includes(status.state) ? status.state : a.mission_status]
      .filter(Boolean).map(esc).join(" | ");
    const row = (k, v) => `<div class="row"><span class="k">${esc(k)}:</span> ${v}</div>`;

    const news = (this._state("news")?.attributes?.news || []).slice(0, this._config.news_count);
    const newsHtml = news.length
      ? news.map((n) => {
          const link = safeUrl(n.link);
          const title = esc(n.title);
          return `<li>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${title}</a>` : title}</li>`;
        }).join("")
      : `<li class="muted">${L.nonews}</li>`;

    const ma = this._state("missions")?.attributes || {};
    const n = this._config.missions_count;
    const mList = (list) => (list || []).length
      ? list.slice(0, n).map((m) => {
          const v = safeUrl(m.video_url) || safeUrl(m.url);
          const d = m.launch_date ? new Date(m.launch_date + "T00:00:00").toLocaleDateString(lang, { day: "2-digit", month: "short", year: "numeric" }) : "TBD";
          return `<li>${m.is_live ? "🔴 " : ""}<b>${esc(m.mission)}</b> — ${esc(d)}${m.launch_site ? ` · ${esc(m.launch_site)}` : ""}${v ? ` · <a href="${esc(v)}" target="_blank" rel="noopener">${L.video}</a>` : ""}</li>`;
        }).join("")
      : `<li class="muted">${L.nomission}</li>`;
    const missionsHtml = this._config.show_missions && this._state("missions")
      ? `<h3>${L.upcoming}</h3><ul>${mList(ma.upcoming)}</ul><h3>${L.past}</h3><ul>${mList(ma.past)}</ul>` : "";
    const vurl = safeUrl(a.video_url) || url;

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .title { font-size: 1.35em; font-weight: 700; margin-bottom: 6px; }
        .row { line-height: 1.5; }
        .k { color: var(--secondary-text-color); }
        .live { margin: 12px 0 4px; padding: 8px 10px; border-radius: 8px; background: var(--secondary-background-color); }
        .live.on { background: #d32f2f; color: #fff; font-weight: 700; }
        .live a { color: inherit; }
        h3 { margin: 16px 0 6px; font-size: 1.05em; }
        ul { margin: 0; padding-left: 18px; }
        li { margin: 4px 0; }
        a { color: var(--primary-color); text-decoration: none; }
        .muted { color: var(--secondary-text-color); list-style: none; margin-left: -18px; }
        .cd { font-weight: 700; }
      </style>
      <ha-card>
        <div class="title">${hasMission ? esc(next.state) : "TBD"} (SpaceX)</div>
        ${row(L.provider, "SpaceX")}
        ${row(L.vehicle, esc(a.vehicle || "Starship"))}
        ${row(L.pad, esc(a.launch_site || "Starbase"))}
        ${row(L.location, "Starbase, Texas, United States")}
        ${row(L.date, esc(hasMission ? date : "TBD"))}
        ${hasMission ? row(L.countdown, `<span class="cd">${esc(this._countdown(cd))}</span>`) : ""}
        ${row(L.tags, hasMission ? (tags || "—") + " |" : esc(L.none))}
        ${hasMission ? `<div class="row"><a href="${esc(url)}" target="_blank" rel="noopener">${L.details} →</a> · <a href="${esc(vurl)}" target="_blank" rel="noopener">${L.video}</a></div>` : ""}
        <div class="live ${isLive ? "on" : ""}">
          ${isLive ? `🔴 ${L.live} — <a href="${esc(url)}" target="_blank" rel="noopener">${L.watch}</a>`
                   : `⚪ ${L.nolive} — <a href="https://www.spacex.com/vehicles/starship" target="_blank" rel="noopener">spacex.com</a>`}
        </div>
        ${missionsHtml}
        ${this._config.show_news ? `<h3>${L.news}</h3><ul>${newsHtml}</ul>` : ""}
      </ha-card>`;
  }
}

if (!customElements.get("starship-tracker-card")) {
  customElements.define("starship-tracker-card", StarshipTrackerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "starship-tracker-card",
    name: "Starship Tracker",
    description: "Missions Starship (passées / à venir), vidéos, live et actualités / Starship missions (past / upcoming), videos, live and news",
    preview: true,
  });
  console.info(`%c STARSHIP-TRACKER-CARD %c ${CARD_VERSION} `, "background:#000;color:#fff", "background:#f60;color:#000");
}
