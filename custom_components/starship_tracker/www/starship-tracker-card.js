/* Starship Tracker card — livrée avec l'intégration starship_tracker (aucune install séparée). */
const CARD_VERSION = "1.13.0";

const KEYS = {
  live: ["binary_sensor", "starship_live", "binary_sensor.starship_tracker_starship_live"],
  next: ["sensor", "next_mission", "sensor.starship_tracker_next_starship_mission"],
  countdown: ["sensor", "countdown", "sensor.starship_tracker_starship_launch_countdown"],
  status: ["sensor", "mission_status", "sensor.starship_tracker_starship_mission_status"],
  missions: ["sensor", "missions", "sensor.starship_tracker_starship_missions"],
  news: ["sensor", "news", "sensor.starship_tracker_starship_news"],
  total_launches: ["sensor", "total_launches", "sensor.starship_tracker_spacex_completed_missions"],
  total_landings: ["sensor", "total_landings", "sensor.starship_tracker_spacex_total_landings"],
  total_reflights: ["sensor", "total_reflights", "sensor.starship_tracker_spacex_total_reflights"],
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

const DEFAULTS = {
  show_details: true, show_details_button: true, show_countdown: true, show_live: true, show_videos: true,
  show_missions: true, missions_count: 3, show_upcoming: true, show_last: true,
  show_news: true, news_count: 5, show_stats: true,
};

const LABELS = {
  title: "Titre (vide = mission) / Title",
  show_details: "Détails mission / Mission details",
  show_details_button: "Bouton Détails (photo + infos) / Details button (photo + info)",
  show_countdown: "Compte à rebours / Countdown",
  show_live: "Bandeau live / Live banner",
  show_videos: "Liens vidéo / Video links",
  show_missions: "Suivi des missions / Missions tracking",
  missions_count: "Nb missions / Missions count",
  show_upcoming: "Prochaines missions / Upcoming",
  show_last: "Derniers vols / Latest flights",
  show_news: "Actualités / News",
  news_count: "Nb actualités / News count",
  show_stats: "Compteurs SpaceX / SpaceX counters",
  total_launches: "Missions terminées / Completed missions",
  total_landings: "Atterrissages / Landings", total_reflights: "Réutilisations / Reflights",
  next: "Prochaine mission", countdown: "Countdown", status: "Statut mission",
  missions: "Missions", news: "News", live: "Live",
};

class StarshipTrackerCard extends HTMLElement {
  static getStubConfig() {
    return { ...DEFAULTS };
  }

  // Éditeur visuel natif HA (2024.11+) : « Modifier la carte » affiche ce formulaire.
  static getConfigForm() {
    const b = (name) => ({ name, selector: { boolean: {} } });
    const num = (name, max) => ({ name, selector: { number: { min: 1, max, mode: "box" } } });
    const ent = (name, domain) => ({ name, selector: { entity: { domain, integration: "starship_tracker" } } });
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { type: "expandable", name: "", title: "Affichage / Display", flatten: true, schema: [
          { type: "grid", name: "", flatten: true, schema: [
            b("show_details"), b("show_details_button"), b("show_countdown"), b("show_live"), b("show_videos"),
          ] },
        ] },
        { type: "expandable", name: "", title: "Compteurs SpaceX / SpaceX counters", flatten: true, schema: [b("show_stats")] },
        { type: "expandable", name: "", title: "Missions", flatten: true, schema: [
          { type: "grid", name: "", flatten: true, schema: [
            b("show_missions"), num("missions_count", 20), b("show_upcoming"), b("show_last"),
          ] },
        ] },
        { type: "expandable", name: "", title: "Actualités / News", flatten: true, schema: [
          { type: "grid", name: "", flatten: true, schema: [b("show_news"), num("news_count", 20)] },
        ] },
        { type: "expandable", name: "", title: "Entités (optionnel) / Entities (optional)", flatten: true, schema: [
          ent("next", "sensor"), ent("countdown", "sensor"), ent("status", "sensor"),
          ent("missions", "sensor"), ent("news", "sensor"), ent("live", "binary_sensor"),
          ent("total_launches", "sensor"), ent("total_landings", "sensor"), ent("total_reflights", "sensor"),
        ] },
      ],
      computeLabel: (s) => LABELS[s.name] || s.name,
    };
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._config.news_count = Math.max(1, Number(this._config.news_count) || DEFAULTS.news_count);
    this._config.missions_count = Math.max(1, Number(this._config.missions_count) || DEFAULTS.missions_count);
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

  // Compte à rebours : état timestamp du sensor, sinon launch_date + launch_time (UTC).
  _instant(cd, attrs) {
    const stateMs = cd && Date.parse(cd.state);
    if (stateMs) return stateMs;
    const date = attrs && attrs.launch_date;
    if (!date) return NaN;
    if (String(date).includes("T")) return Date.parse(date);
    const time = attrs.launch_time;
    if (!time) return NaN;
    const stamp = `${String(date).slice(0, 10)}T${time}`;
    return Date.parse(/[zZ]|[+-]\d{2}:\d{2}$/.test(stamp) ? stamp : `${stamp}Z`);
  }

  _countdown(ms) {
    if (!ms) return "—";
    let s = Math.floor((ms - Date.now()) / 1000);
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
          window: "Fenêtre de lancement", dateSource: "Source de la date", sourceFeed: "Flux", sourcePage: "Page mission",
          countdown: "Compte à rebours", tags: "Tags", live: "EN DIRECT", nolive: "Pas de live en cours", watch: "Regarder",
          news: "Actualités Starship", nonews: "Aucune actualité", details: "Détails", hide: "Masquer les détails", status: "Statut", page: "Page mission spacex.com", webcast: "Webcast", links: "Liens", nodesc: "Pas de description disponible", none: "Aucune mission annoncée",
          upcoming: "Prochaines missions Starship", past: "Derniers vols Starship", video: "▶ Vidéo", nomission: "Aucune",
          s1: "Missions terminées", s2: "Atterrissages totaux", s3: "Réutilisations totales" }
      : { provider: "Provider", vehicle: "Vehicle", pad: "Launch Pad", location: "Location", date: "Target Date",
          window: "Launch window", dateSource: "Date source", sourceFeed: "Feed", sourcePage: "Mission page",
          countdown: "Countdown", tags: "Tags", live: "LIVE", nolive: "No live stream", watch: "Watch",
          news: "Starship news", nonews: "No news", details: "Details", hide: "Hide details", status: "Status", page: "spacex.com mission page", webcast: "Webcast", links: "Links", nodesc: "No description available", none: "No mission announced",
          upcoming: "Upcoming Starship missions", past: "Latest Starship flights", video: "▶ Video", nomission: "None",
          s1: "Completed missions", s2: "Total landings", s3: "Total reflights" };

    const C = this._config;
    const next = this._state("next");
    const a = next?.attributes || {};
    const hasMission = next && !["unknown", "unavailable", ""].includes(next.state);
    const live = this._state("live");
    const isLive = live?.state === "on";
    const status = this._state("status");
    const cd = this._state("countdown");
    const url = safeUrl(a.url) || safeUrl(live?.attributes?.url) || "https://www.spacex.com/vehicles/starship";
    const launchMs = this._instant(cd, a);
    let date = a.launch_date || "TBD";
    if (launchMs) {
      date = new Date(launchMs).toLocaleString(lang, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    }
    const windowMin = Number(a.launch_window_minutes);
    const windowText = Number.isInteger(windowMin) && windowMin > 0 ? `${windowMin} min` : "";
    const sourceNames = { feed: L.sourceFeed, mission_page: L.sourcePage };
    const sourceLabel = sourceNames[a.date_source] || "";
    const tags = [a.mission_type, status?.state && !["unknown", "unavailable"].includes(status.state) ? status.state : a.mission_status]
      .filter(Boolean).map(esc).join(" | ");
    const row = (k, v) => `<div class="row"><span class="k">${esc(k)}:</span> ${v}</div>`;

    const news = (this._state("news")?.attributes?.news || []).slice(0, C.news_count);
    const newsHtml = news.length
      ? news.map((n) => {
          const link = safeUrl(n.link);
          const title = esc(n.title);
          return `<li>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${title}</a>` : title}</li>`;
        }).join("")
      : `<li class="muted">${L.nonews}</li>`;

    const ma = this._state("missions")?.attributes || {};
    const n = C.missions_count;
    const mList = (list) => (list || []).length
      ? list.slice(0, n).map((m) => {
          const v = safeUrl(m.video_url) || safeUrl(m.url);
          const d = m.launch_date ? new Date(m.launch_date + "T00:00:00").toLocaleDateString(lang, { day: "2-digit", month: "short", year: "numeric" }) : "TBD";
          return `<li>${m.is_live ? "🔴 " : ""}<b>${esc(m.mission)}</b> — ${esc(d)}${m.launch_site ? ` · ${esc(m.launch_site)}` : ""}${v && C.show_videos ? ` · <a href="${esc(v)}" target="_blank" rel="noopener">${L.video}</a>` : ""}</li>`;
        }).join("")
      : `<li class="muted">${L.nomission}</li>`;
    const missionsHtml = C.show_missions && this._state("missions")
      ? (C.show_upcoming ? `<h3>${L.upcoming}</h3><ul>${mList(ma.upcoming)}</ul>` : "")
        + (C.show_last ? `<h3>${L.past}</h3><ul>${mList(ma.past)}</ul>` : "") : "";
    const vurl = safeUrl(a.video_url) || url;
    const statVal = (k) => {
      const st = this._state(k);
      const v = Number(st?.state);
      return st && Number.isFinite(v) ? v.toLocaleString(lang) : "—";
    };
    const statsHtml = C.show_stats && this._state("total_launches")
      ? `<a class="stats" href="https://www.spacex.com/launches" target="_blank" rel="noopener">
          ${[["total_launches", L.s1], ["total_landings", L.s2], ["total_reflights", L.s3]]
            .map(([k, l]) => `<div class="stat"><div class="sv">${esc(statVal(k))}</div><div class="sl">${esc(l)}</div></div>`).join("")}
        </a>` : "";

    const statusText = status?.state && !["unknown", "unavailable"].includes(status.state) ? status.state : (a.mission_status || "—");
    const murl = safeUrl(a.mission_url) || url;
    const img = safeUrl(a.mission_image);
    const desc = String(a.mission_description || "").split(/\n{2,}/).filter((p) => p.trim())
      .map((p) => `<p>${esc(p)}</p>`).join("") || `<p class="muted0">${L.nodesc}</p>`;
    const casts = [...(a.webcast_links || []), ...(a.mission_links || []), vurl].map(safeUrl).filter(Boolean)
      .filter((u, i, arr) => arr.indexOf(u) === i).slice(0, 8);
    const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } };
    const fullDate = launchMs
      ? new Date(launchMs).toLocaleString(lang, { weekday: "long", day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" })
      : "TBD";
    const showBtn = hasMission && C.show_details_button;
    const panel = showBtn && this._open ? `<div class="panel">
        ${img ? `<img class="mimg" src="${esc(img)}" alt="${esc(next.state)}" loading="lazy">` : ""}
        <div class="ptitle">${esc(next.state)}</div>
        ${row(L.date, esc(fullDate))}
        ${windowText ? row(L.window, esc(windowText)) : ""}
        ${row(L.pad, esc(a.launch_site || "Starbase"))}
        ${row(L.status, esc(statusText))}
        <div class="desc">${desc}</div>
        ${C.show_videos && casts.length ? `<div class="row"><span class="k">${L.links}:</span> ${casts.map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(host(u))}</a>`).join(" · ")}</div>` : ""}
        <div class="row"><a href="${esc(murl)}" target="_blank" rel="noopener">${L.page} →</a></div>
      </div>` : "";

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
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0 4px; color: inherit; }
        .stat { text-align: center; padding: 8px 4px; border-radius: 8px; background: var(--secondary-background-color); }
        .sv { font-size: 1.6em; font-weight: 700; }
        .dbtn { margin-top: 8px; padding: 6px 14px; border: none; border-radius: 16px; cursor: pointer; background: var(--primary-color); color: var(--text-primary-color, #fff); font-weight: 600; }
        .panel { margin-top: 10px; padding: 10px; border-radius: 8px; background: var(--secondary-background-color); }
        .mimg { width: 100%; border-radius: 6px; display: block; margin-bottom: 8px; }
        .ptitle { font-weight: 700; font-size: 1.1em; margin-bottom: 4px; }
        .desc p { margin: 6px 0; line-height: 1.4; }
        .muted0 { color: var(--secondary-text-color); }
        .sl { font-size: 0.8em; color: var(--secondary-text-color); text-transform: uppercase; }
      </style>
      <ha-card>
        <div class="title">${C.title ? esc(C.title) : `${hasMission ? esc(next.state) : "TBD"} (SpaceX)`}</div>
        ${C.show_details ? `
        ${row(L.provider, "SpaceX")}
        ${row(L.vehicle, esc(a.vehicle || "Starship"))}
        ${row(L.pad, esc(a.launch_site || "Starbase"))}
        ${row(L.location, "Starbase, Texas, United States")}
        ${row(L.date, esc(hasMission ? date : "TBD"))}
        ${hasMission && windowText ? row(L.window, esc(windowText)) : ""}
        ${hasMission && sourceLabel ? row(L.dateSource, esc(sourceLabel)) : ""}` : ""}
        ${hasMission && C.show_countdown ? row(L.countdown, `<span class="cd">${esc(this._countdown(launchMs))}</span>`) : ""}
        ${C.show_details ? row(L.tags, hasMission ? (tags || "—") + " |" : esc(L.none)) : ""}
        ${hasMission && C.show_details ? `<div class="row"><a href="${esc(url)}" target="_blank" rel="noopener">${L.details} →</a>${C.show_videos ? ` · <a href="${esc(vurl)}" target="_blank" rel="noopener">${L.video}</a>` : ""}</div>` : ""}
        ${showBtn ? `<button class="dbtn" type="button">${this._open ? L.hide : "ℹ️ " + L.details}</button>` : ""}
        ${panel}
        ${C.show_live ? `<div class="live ${isLive ? "on" : ""}">
          ${isLive ? `🔴 ${L.live} — <a href="${esc(url)}" target="_blank" rel="noopener">${L.watch}</a>`
                   : `⚪ ${L.nolive} — <a href="https://www.spacex.com/vehicles/starship" target="_blank" rel="noopener">spacex.com</a>`}
        </div>` : ""}
        ${statsHtml}
        ${missionsHtml}
        ${C.show_news ? `<h3>${L.news}</h3><ul>${newsHtml}</ul>` : ""}
      </ha-card>`;
    const btn = this.shadowRoot.querySelector(".dbtn");
    if (btn) btn.addEventListener("click", (ev) => { ev.stopPropagation(); this._open = !this._open; this._render(); });
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
