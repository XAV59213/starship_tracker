/* Starship Tracker card — livrée avec l'intégration starship_tracker (aucune install séparée). */
const CARD_VERSION = "1.24.1";

const KEYS = {
  live: ["binary_sensor", "starship_live", "binary_sensor.starship_tracker_starship_live"],
  next: ["sensor", "next_mission", "sensor.starship_tracker_next_starship_mission"],
  countdown: ["sensor", "countdown", "sensor.starship_tracker_starship_launch_countdown"],
  status: ["sensor", "mission_status", "sensor.starship_tracker_starship_mission_status"],
  missions: ["sensor", "missions", "sensor.starship_tracker_starship_missions"],
  news: ["sensor", "news", "sensor.starship_tracker_starship_news"],
  youtube_fr: ["sensor", "youtube_fr", "sensor.starship_tracker_youtube_fr"],
  youtube_en: ["sensor", "youtube_en", "sensor.starship_tracker_youtube_en"],
  youtube_fr_starbase: ["sensor", "youtube_fr_starbase", "sensor.starship_tracker_youtube_fr_starbase"],
  total_launches: ["sensor", "total_launches", "sensor.starship_tracker_spacex_completed_missions"],
  total_landings: ["sensor", "total_landings", "sensor.starship_tracker_spacex_total_landings"],
  total_reflights: ["sensor", "total_reflights", "sensor.starship_tracker_spacex_total_reflights"],
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

const imgUrl = (im) => {
  if (!im || typeof im !== "object") return null;
  const f = im.formats || {};
  let u = (f.large && f.large.url) || (f.medium && f.medium.url) || im.url;
  if (typeof u !== "string") return null;
  if (u.startsWith("/")) u = "https://content.spacex.com" + u;
  return safeUrl(u);
};
const plain = (h) => String(h || "").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, " ").trim();
const webcast = (c) => {
  const vid = String((c && c.videoId) || "").split(/[&?#]/)[0];
  const k = String((c && c.streamingVideoType) || "").toLowerCase();
  if (!/^[A-Za-z0-9_-]+$/.test(vid)) return null;
  if (k.includes("youtube")) return { type: "youtube", url: `https://www.youtube.com/watch?v=${vid}`, embed: `https://www.youtube-nocookie.com/embed/${vid}` };
  if (k === "x-live-studio") return { type: "x", url: `https://x.com/i/broadcasts/${vid}` };
  if (["x.com", "x", "twitter"].includes(k)) return { type: "x", url: `https://x.com/SpaceX/status/${vid}` };
  return null;
};
const timeline = (t) => ((t && t.timelineEntries) || []).slice(0, 30)
  .map((e) => [plain(e.time).slice(0, 16), plain(e.description).slice(0, 160)]).filter((e) => e[1]);
// Équivalent JS de mission_date.extract_mission_details (pages des vols passés).
const parseMission = (p) => {
  if (!p || typeof p !== "object") return {};
  const desc = (p.paragraphs || []).map((x) => plain(x && x.content)).filter(Boolean).join("\n\n");
  const vids = (p.webcasts || []).map(webcast).filter(Boolean).slice(0, 3);
  const file = p.videoDesktop && safeUrl(p.videoDesktop.url);
  if (file) vids.unshift({ type: "file", url: file });
  return {
    mission_image: imgUrl(p.imageDesktop) || imgUrl(p.imageMobile),
    mission_description: desc.length > 1500 ? desc.slice(0, 1499) + "…" : desc,
    mission_videos: vids,
    mission_infographic: imgUrl(p.infographicDesktop),
    mission_infographic_mobile: imgUrl(p.infographicMobile),
    mission_countdown: timeline(p.preLaunchTimeline),
    mission_timeline: timeline(p.postLaunchTimeline),
  };
};

// Traduction FR déterministe (miroir de translate.py : titres, statuts, chronologie).
const TIMELINE_FR = {"spacex flight director conducts poll and verifies go for propellant load": "Le directeur de vol SpaceX fait le tour des équipes et confirme le GO pour le remplissage des ergols", "max q (moment of peak aerodynamic stress on the rocket)": "Max Q (moment de contrainte aérodynamique maximale sur la fusée)", "super heavy meco (most engines cut off)": "MECO du Super Heavy (arrêt de la plupart des moteurs)", "hot-staging (starship raptor ignition and stage separation)": "Hot-staging (allumage des Raptor de Starship et séparation des étages)", "super heavy boostback burn startup": "Début de l'allumage de retour (boostback) du Super Heavy", "super heavy boostback burn shutdown": "Fin de l'allumage de retour (boostback) du Super Heavy", "super heavy is expected to be over the gulf of america": "Super Heavy devrait être au-dessus du golfe du Mexique", "super heavy landing burn startup": "Début de l'allumage d'atterrissage du Super Heavy", "super heavy landing burn shutdown": "Fin de l'allumage d'atterrissage du Super Heavy", "super heavy landing burn startup and catch": "Allumage d'atterrissage et capture du Super Heavy", "super heavy catch": "Capture du Super Heavy", "booster lox (liquid oxygen) load underway": "Remplissage du LOX (oxygène liquide) du booster en cours", "booster fuel (liquid methane) load underway": "Remplissage du carburant (méthane liquide) du booster en cours", "starship fuel (liquid methane) load underway": "Remplissage du carburant (méthane liquide) de Starship en cours", "starship lox (liquid oxygen) load underway": "Remplissage du LOX (oxygène liquide) de Starship en cours", "raptor begins engine chill on booster": "Début de la mise en froid des moteurs Raptor du booster", "raptor begins engine chill on starship": "Début de la mise en froid des moteurs Raptor de Starship", "starship engine chill": "Mise en froid des moteurs de Starship", "booster engine chill": "Mise en froid des moteurs du booster", "spacex flight director verifies go for launch": "Le directeur de vol SpaceX confirme le GO pour le lancement", "excess propellant offload": "Délestage des ergols en excès", "flight computers command booster and ship propellant pressurization": "Les ordinateurs de vol commandent la pressurisation des ergols du booster et du vaisseau", "booster and ship propellant pressurization": "Pressurisation des ergols du booster et du vaisseau", "propellant load complete": "Remplissage des ergols terminé", "propellant load": "Remplissage des ergols", "starship secos (second engine cutoff)": "SECO de Starship (arrêt des moteurs du second étage)", "starship seco (second engine cutoff)": "SECO de Starship (arrêt des moteurs du second étage)", "starship seco": "SECO de Starship", "starship meco": "MECO de Starship", "starship entry": "Rentrée atmosphérique de Starship", "starship atmospheric entry": "Rentrée atmosphérique de Starship", "starship flip, landing burn, and landing": "Basculement, allumage d'atterrissage et atterrissage de Starship", "starship flip, landing burn, and catch": "Basculement, allumage d'atterrissage et capture de Starship", "starship landing flip": "Basculement d'atterrissage de Starship", "starship landing burn": "Allumage d'atterrissage de Starship", "starship splashdown": "Amerrissage de Starship", "starship catch": "Capture de Starship", "raptor in-space relight": "Rallumage d'un Raptor dans l'espace", "in-space raptor relight": "Rallumage d'un Raptor dans l'espace", "starlink simulator deployment begins": "Début du déploiement des simulateurs Starlink", "starlink simulator deployment complete": "Fin du déploiement des simulateurs Starlink", "payload deploy": "Déploiement de la charge utile", "hot-staging": "Hot-staging (séparation à chaud)", "stage separation": "Séparation des étages", "liftoff": "Décollage", "lift off": "Décollage", "max q": "Max Q (pression dynamique maximale)", "landing": "Atterrissage", "splashdown": "Amerrissage", "catch": "Capture"};
const ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh",
  "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth"];
const STATUS_FR = { final: "Terminé", upcoming: "À venir", live: "En direct", active: "En cours", past: "Terminé" };
const trTitle = (t) => {
  const s = String(t || "").trim();
  let m = s.match(/^Starship'?s?\s+(\w+)\s+Flight\s+Test$/i);
  if (m && ORD.includes(m[1].toLowerCase())) { const n = ORD.indexOf(m[1].toLowerCase()) + 1; return `${n === 1 ? "1er" : n + "e"} vol d'essai Starship`; }
  if ((m = s.match(/^Starship\s+Flight\s+(\d+)$/i))) return `Vol Starship ${m[1]}`;
  if (/^Starship\s+Flight\s+Test$/i.test(s)) return "Vol d'essai Starship";
  if ((m = s.match(/^Starship\s+High\s+Altitude\s+Test\s*-\s*(\S+)$/i))) return `Test haute altitude Starship - ${m[1]}`;
  if ((m = s.match(/^Starship\s+Test\s*-\s*(\S+)$/i))) return `Test Starship - ${m[1]}`;
  return t;
};
const trStatus = (v) => (v && STATUS_FR[String(v).toLowerCase()]) || v;
const trEntry = (d) => TIMELINE_FR[String(d || "").trim().toLowerCase().replace(/\s+/g, " ").replace(/\.$/, "")] || d;

const DEFAULTS = {
  show_details: true, show_details_button: true, show_countdown: true, show_live: true, show_videos: true,
  show_missions: true, missions_count: 3, show_upcoming: true, show_last: true,
  show_youtube: true, youtube_carousel_lang: "both", show_carousel_spacex: true, show_carousel_youtube_fr: true, show_carousel_youtube_fr_starbase: true, show_carousel_youtube_en: true, youtube_live_badges_en: true, youtube_count_youtube_fr: 0, youtube_count_youtube_fr_starbase: 0, youtube_count_youtube_en: 0, show_news: true, news_count: 5, show_stats: true, show_carousel: true, carousel_count: 25,
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
  show_youtube: "Vidéos YouTube FR/EN / YouTube videos FR/EN",
  youtube_live_badges_en: "Badges live NASASpaceflight / NASASpaceflight live badges",
  youtube_carousel_lang: "Langue YouTube du carrousel / Carousel YouTube language",
  youtube_fr: "YouTube français / French YouTube",
  youtube_en: "YouTube anglais / English YouTube",
  youtube_fr_starbase: "YouTube StarBase FR (optionnel) / StarBase FR YouTube (optional)",
  show_news: "Actualités / News",
  news_count: "Nb actualités / News count",
  show_stats: "Compteurs SpaceX / SpaceX counters",
  show_carousel: "Carrousel d'images / Image carousel",
  show_carousel_spacex: "Carrousel SpaceX / SpaceX carousel",
  show_carousel_youtube_fr: "Carrousel UFOTINIK (FR) / UFOTINIK carousel",
  show_carousel_youtube_fr_starbase: "Carrousel StarBase FR / StarBase FR carousel",
  show_carousel_youtube_en: "Carrousel NASASpaceflight (EN) / NASASpaceflight carousel",
  carousel_count: "Nb vignettes / Max tiles",
  youtube_count_youtube_fr: "Nb vidéos UFOTINIK (0 = toutes) / UFOTINIK videos (0 = all)",
  youtube_count_youtube_fr_starbase: "Nb vidéos StarBase FR (0 = toutes) / StarBase FR videos (0 = all)",
  youtube_count_youtube_en: "Nb vidéos NASASpaceflight (0 = toutes) / NASASpaceflight videos (0 = all)",
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
            b("show_details"), b("show_details_button"), b("show_countdown"), b("show_live"), b("show_videos"), b("show_youtube"),
          ] },
        ] },
        { type: "expandable", name: "", title: "Compteurs SpaceX / SpaceX counters", flatten: true, schema: [b("show_stats")] },
        { type: "expandable", name: "", title: "Carrousel / Carousel", flatten: true, schema: [
          { type: "grid", name: "", flatten: true, schema: [b("show_carousel"), num("carousel_count", 50)] },
          { type: "grid", name: "", flatten: true, schema: [b("show_carousel_spacex"), b("show_carousel_youtube_fr"), b("show_carousel_youtube_fr_starbase"), b("show_carousel_youtube_en"), b("youtube_live_badges_en")] },
          { type: "grid", name: "", flatten: true, schema: ["youtube_count_youtube_fr", "youtube_count_youtube_fr_starbase", "youtube_count_youtube_en"].map((name) => ({ name, selector: { number: { min: 0, max: 50, mode: "box" } } })) },
          { name: "youtube_carousel_lang", selector: { select: { options: [
            { value: "auto", label: "Auto (langue HA / HA language)" },
            { value: "fr", label: "Français / French" },
            { value: "en", label: "Anglais / English" },
            { value: "both", label: "Les deux / Both" },
          ] } } },
        ] },
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
          ent("youtube_fr", "sensor"), ent("youtube_en", "sensor"), ent("youtube_fr_starbase", "sensor"),
          ent("total_launches", "sensor"), ent("total_landings", "sensor"), ent("total_reflights", "sensor"),
        ] },
      ],
      computeLabel: (s) => LABELS[s.name] || s.name,
    };
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._userCount = Boolean(config && config.carousel_count != null);
    if (!["auto", "fr", "en", "both"].includes(this._config.youtube_carousel_lang)) this._config.youtube_carousel_lang = "auto";
    this._config.news_count = Math.max(1, Number(this._config.news_count) || DEFAULTS.news_count);
    this._config.carousel_count = Math.max(1, Number(this._config.carousel_count) || DEFAULTS.carousel_count);
    ["youtube_fr", "youtube_fr_starbase", "youtube_en"].forEach((key) => {
      const name = "youtube_count_" + key;
      this._config[name] = Math.max(0, Math.floor(Number(this._config[name]) || 0));
    });
    this._config.missions_count = Math.max(1, Number(this._config.missions_count) || DEFAULTS.missions_count);
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._sig = null;
    this._details = this._details || {};
    this._secs = this._secs || new Set();
    this._startTimer();
    if (this._hass) this._render();
  }

  // Le compte à rebours est mis à jour en place (pas de reconstruction du DOM).
  _startTimer() {
    this._timer && clearInterval(this._timer);
    this._timer = setInterval(() => this._tick(), 30000);
  }

  _tick() {
    const el = this.shadowRoot && this.shadowRoot.querySelector(".cd");
    if (el && this._launchMs) el.textContent = this._countdown(this._launchMs);
  }

  // Page mission chargée à la demande (content.spacex.com autorise CORS), cache mémoire 6 h.
  _loadDetails(link) {
    this._details = this._details || {};
    this._fetching = this._fetching || {};
    const ts = this._fetching[link];
    if (this._details[link] || (ts && Date.now() - ts < 6 * 3600 * 1000)) return;
    this._fetching[link] = Date.now();
    fetch(`https://content.spacex.com/api/spacex-website/missions/${encodeURIComponent(link)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => { this._details[link] = parseMission(p); this._render(); })
      .catch(() => { this._details[link] = {}; this._render(); });
  }

  connectedCallback() {
    if (this._config) this._startTimer();
  }

  disconnectedCallback() {
    this._timer && clearInterval(this._timer);
    this._timer = null;
    (this._carouselResizes || []).forEach((r) => r.disconnect()); this._carouselResizes = [];
  }

  // HA appelle « set hass » à chaque changement d'état de toute la maison :
  // on ne redessine que si les entités Starship (ou la langue) ont changé.
  _signature(hass) {
    const parts = [hass.locale?.language || hass.language || ""];
    for (const key of Object.keys(KEYS)) {
      const st = hass.states[this._entity(key)];
      parts.push(st ? [st.state, st.last_updated, st.last_changed] : null);
    }
    return JSON.stringify(parts);
  }

  set hass(hass) {
    this._hass = hass;
    const sig = this._signature(hass);
    if (sig === this._sig) return;
    this._sig = sig;
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
    const lang = (this._config.lang || this._hass.locale?.language || this._hass.language || "en").startsWith("fr") ? "fr" : "en";
    const L = lang === "fr"
      ? { provider: "Fournisseur", vehicle: "Véhicule", pad: "Rampe de lancement", location: "Emplacement", date: "Date cible",
          window: "Fenêtre de lancement", dateSource: "Source de la date", sourceFeed: "Flux", sourcePage: "Page mission",
          countdown: "Compte à rebours", tags: "Tags", live: "EN DIRECT", nolive: "Pas de live en cours", watch: "Regarder",
          news: "Actualités Starship", nonews: "Aucune actualité", details: "Détails", hide: "Masquer les détails", status: "Statut", page: "Page mission spacex.com", webcast: "Webcast", links: "Liens", nodesc: "Pas de description disponible", bSoon: "À VENIR", watchVideo: "Voir la vidéo", plan: "Plan de vol", cdTitle: "COMPTE À REBOURS", tlTitle: "CHRONOLOGIE DU VOL", approx: "Horaires approximatifs", loading: "Chargement des détails…", bLive: "DIRECT", bDone: "TERMINÉ", none: "Aucune mission annoncée",
          upcoming: "Prochaines missions Starship", past: "Derniers vols Starship", video: "▶ Vidéo", nomission: "Aucune",
          s1: "Missions terminées", s2: "Atterrissages totaux", s3: "Réutilisations totales",
          ytSoon: "À venir", ytLive: "En direct", ytDone: "Terminé" }
      : { provider: "Provider", vehicle: "Vehicle", pad: "Launch Pad", location: "Location", date: "Target Date",
          window: "Launch window", dateSource: "Date source", sourceFeed: "Feed", sourcePage: "Mission page",
          countdown: "Countdown", tags: "Tags", live: "LIVE", nolive: "No live stream", watch: "Watch",
          news: "Starship news", nonews: "No news", details: "Details", hide: "Hide details", status: "Status", page: "spacex.com mission page", webcast: "Webcast", links: "Links", nodesc: "No description available", bSoon: "UPCOMING", watchVideo: "Watch video", plan: "Flight plan", cdTitle: "COUNTDOWN", tlTitle: "FLIGHT TIMELINE", approx: "All times approximate", loading: "Loading details…", bLive: "LIVE", bDone: "COMPLETED", none: "No mission announced",
          upcoming: "Upcoming Starship missions", past: "Latest Starship flights", video: "▶ Video", nomission: "None",
          s1: "Completed missions", s2: "Total landings", s3: "Total reflights",
          ytSoon: "Upcoming", ytLive: "Live", ytDone: "Ended" };

    const C = this._config;
    const fr = lang === "fr" && !this._orig;
    const T = (t) => (fr ? trTitle(t) : t);
    const S = (v) => (fr ? trStatus(v) : v);
    const next = this._state("next");
    const a = next?.attributes || {};
    const hasMission = next && !["unknown", "unavailable", ""].includes(next.state);
    const live = this._state("live");
    const isLive = live?.state === "on";
    const status = this._state("status");
    const cd = this._state("countdown");
    const url = safeUrl(a.url) || safeUrl(live?.attributes?.url) || "https://www.spacex.com/vehicles/starship";
    const launchMs = this._instant(cd, a);
    this._launchMs = launchMs;
    let date = a.launch_date || "TBD";
    if (launchMs) {
      date = new Date(launchMs).toLocaleString(lang, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    }
    const windowMin = Number(a.launch_window_minutes);
    const windowText = Number.isInteger(windowMin) && windowMin > 0 ? `${windowMin} min` : "";
    const sourceNames = { feed: L.sourceFeed, mission_page: L.sourcePage };
    const sourceLabel = sourceNames[a.date_source] || "";
    const tags = [a.mission_type, status?.state && !["unknown", "unavailable"].includes(status.state) ? status.state : a.mission_status]
      .filter(Boolean).map((v) => esc(S(v))).join(" | ");
    const row = (k, v) => `<div class="row"><span class="k">${esc(k)}:</span> ${v}</div>`;

    const youtubeChannels = [["fr", "youtube_fr", "FR", "UFOTINIK"], ["fr", "youtube_fr_starbase", "FR · StarBase FR", "StarBase FR"], ["en", "youtube_en", "EN", "NASASpaceflight"]];
    const youtubeVideos = youtubeChannels.map(([language, key, label]) => {
      const state = this._state(key);
      const link = safeUrl(state?.attributes?.url);
      if (!state || ["unknown", "unavailable"].includes(state.state) || !link) return null;
      return { language, label, url: link, title: state.attributes.title || state.state,
        thumbnail: safeUrl(state.attributes.thumbnail), published: state.attributes.published };
    }).filter(Boolean);
    const youtubeLinks = youtubeVideos.map((v) => `<li><b>${esc(v.label)}</b> · <a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a></li>`).join("");
    const youtubeHtml = C.show_youtube && youtubeLinks
      ? `<h3>📺 ${lang === "fr" ? "Vidéos YouTube" : "YouTube videos"}</h3><ul>${youtubeLinks}</ul>` : "";

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
          return `<li>${m.is_live ? "🔴 " : ""}<b>${esc(T(m.mission))}</b> — ${esc(d)}${m.launch_site ? ` · ${esc(m.launch_site)}` : ""}${v && C.show_videos ? ` · <a href="${esc(v)}" target="_blank" rel="noopener">${L.video}</a>` : ""}</li>`;
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

    const statusText0 = status?.state && !["unknown", "unavailable"].includes(status.state) ? status.state : (a.mission_status || "—");
    const statusText = fr ? (a.mission_status_fr || trStatus(statusText0)) : statusText0;
    const murl = safeUrl(a.mission_url) || url;
    const img = safeUrl(a.mission_image);
    const desc = String((fr && a.mission_description_fr) || a.mission_description || "").split(/\n{2,}/).filter((p) => p.trim())
      .map((p) => `<p>${esc(p)}</p>`).join("") || `<p class="muted0">${L.nodesc}</p>`;
    const casts = [...(a.webcast_links || []), ...(a.mission_links || []), vurl].map(safeUrl).filter(Boolean)
      .filter((u, i, arr) => arr.indexOf(u) === i).slice(0, 8);
    const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } };
    const fullDate = launchMs
      ? new Date(launchMs).toLocaleString(lang, { weekday: "long", day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" })
      : "TBD";
    const showBtn = hasMission && C.show_details_button;
    const fmtDate = (m) => {
      const ms = this._instant(null, m);
      if (ms) return new Date(ms).toLocaleString(lang, { weekday: "long", day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
      return m.launch_date ? new Date(m.launch_date + "T00:00:00").toLocaleDateString(lang, { day: "2-digit", month: "long", year: "numeric" }) : "TBD";
    };
    const allM = [...(ma.upcoming || []), ...(ma.past || [])];
    const sel = this._sel ? allM.find((m) => (m.link || m.mission) === this._sel) : null;
    const isNextSel = !sel || (a.link && sel.link === a.link);
    if (sel && !isNextSel && sel.link) this._loadDetails(sel.link);
    const embedOk = (u) => /^https:\/\/(www\.youtube-nocookie\.com|www\.youtube\.com)\/embed\//.test(u || "");
    const videoHtml = (vids) => (vids || []).slice(0, 3).map((v) => {
      const u = safeUrl(v.url);
      if (!u) return "";
      if (v.type === "youtube" && embedOk(v.embed)) {
        return `<div class="vid"><iframe src="${esc(v.embed)}" title="video" loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`;
      }
      if (v.type === "file") return `<div class="vid"><video src="${esc(u)}" controls preload="none" playsinline></video></div>`;
      return `<a class="play" href="${esc(u)}" target="_blank" rel="noopener">▶ ${esc(L.watchVideo)} (${esc(host(u))})</a>`;
    }).join("");
    const tl = (key, title, list) => (list || []).length ? `<details class="tl" data-sec="${key}" ${this._secs.has(key) ? "open" : ""}>
        <summary>${esc(title)}</summary>
        <div class="tlh"><span>HR/MIN/SEC</span><span>EVENT</span></div>
        ${list.map(([t, d]) => `<div class="tlr"><span class="tlt">${esc(t)}</span><span>${esc(d)}</span></div>`).join("")}
        <div class="tld">${esc(L.approx)}</div>
      </details>` : "";
    const panelOf = (m, isNext) => {
      const D = isNext ? a : (this._details[m.link] || {});
      const loading = !isNext && m.link && !this._details[m.link];
      const pimg = safeUrl(D.mission_image) || safeUrl(m.image);
      const wm = Number(m.launch_window_minutes);
      const st = isNext ? statusText : (S(m.mission_status) || "—");
      const tlFr = (list, frList) => (fr ? ((frList && frList.length ? frList : (list || []).map(([t, d]) => [t, trEntry(d)]))) : list);
      const dtext = isNext ? desc : String(D.mission_description || "").split(/\n{2,}/).filter((p) => p.trim()).map((p) => `<p>${esc(p)}</p>`).join("");
      const plinks = [...(isNext ? casts : []), ...(D.webcast_links || []), m.video_url, m.url].map(safeUrl).filter(Boolean)
        .filter((u, i, arr) => arr.indexOf(u) === i).slice(0, 8);
      const page = safeUrl(isNext ? murl : m.url) || url;
      const info = safeUrl(D.mission_infographic);
      const infoM = safeUrl(D.mission_infographic_mobile);
      return `<div class="panel">
        ${pimg ? `<img class="mimg" src="${esc(pimg)}" alt="${esc(m.mission)}" decoding="async" width="1000" height="563">` : ""}
        <div class="ptitle">${esc(T(m.mission))}${lang === "fr" ? ` <button class="orig" type="button">${this._orig ? "Texte traduit" : "Texte original"}</button>` : ""}</div>
        ${row(L.date, esc(isNext ? fullDate : fmtDate(m)))}
        ${Number.isInteger(wm) && wm > 0 ? row(L.window, esc(wm + " min")) : ""}
        ${row(L.pad, esc(m.launch_site || "Starbase"))}
        ${row(L.status, esc(st))}
        ${C.show_videos ? videoHtml(D.mission_videos) : ""}
        ${loading ? `<div class="muted0">${esc(L.loading)}</div>` : ""}
        ${dtext ? `<div class="desc">${dtext}</div>` : (isNext ? "" : "")}
        ${info ? `<div class="sech">${esc(L.plan)}</div><a href="${esc(info)}" target="_blank" rel="noopener"><picture>${infoM ? `<source media="(max-width: 600px)" srcset="${esc(infoM)}">` : ""}<img class="info" src="${esc(info)}" alt="${esc(L.plan)}" decoding="async" width="1000" height="522"></picture></a>` : ""}
        ${tl("cd", L.cdTitle, tlFr(D.mission_countdown, isNext && D.mission_countdown_fr))}
        ${tl("tl", L.tlTitle, tlFr(D.mission_timeline, isNext && D.mission_timeline_fr))}
        ${C.show_videos && plinks.length ? `<div class="row"><span class="k">${L.links}:</span> ${plinks.map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(host(u))}</a>`).join(" · ")}</div>` : ""}
        <div class="row"><a href="${esc(page)}" target="_blank" rel="noopener">${L.page} →</a></div>
      </div>`;
    };
    const panel = this._open && (sel || showBtn)
      ? panelOf(sel || { ...a, mission: next.state }, isNextSel) : "";
    const badge = (m) => m.is_live ? ["live", L.bLive] : m.mission_status === "final" ? ["done", L.bDone] : ["soon", L.bSoon];
    const youtubeLanguage = C.youtube_carousel_lang === "auto" ? lang : C.youtube_carousel_lang;
    const ytBadge = (status, language, enabled) => {
      if (enabled && status === "live") return ["live", L.ytLive];
      if (enabled && status === "upcoming") return ["soon", L.ytSoon];
      if (enabled && status === "ended") return ["done", L.ytDone];
      return ["youtube", String(language || "").toUpperCase()];
    };
    const ytWhen = (m, upcoming) => {
      const raw = upcoming && m.scheduled ? m.scheduled : m.published;
      const parsed = Date.parse(raw);
      if (!Number.isFinite(parsed)) return "—";
      const date = new Date(parsed);
      return upcoming
        ? (m.scheduled_approx ? "≈ " : "") + date.toLocaleString(lang, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
        : date.toLocaleDateString(lang, { day: "2-digit", month: "short", year: "numeric" });
    };
    // Badges de direct seulement pour UFOTINIK et StarBase FR. NASASpaceflight garde la langue.
    const ytTile = (m, withLive) => {
      const status = withLive && typeof m.live_status === "string" ? m.live_status : "";
      const [cls, lbl] = ytBadge(status, m.language, withLive);
      const d = ytWhen(m, status === "upcoming");
      return `<a class="tile youtube" data-youtube="${m.language}" href="${esc(m.url)}" target="_blank" rel="noopener" aria-label="${esc(m.title)} (${m.language.toUpperCase()})">
        <div class="timg">${m.thumbnail ? `<img src="${esc(m.thumbnail)}" alt="" decoding="async" width="1000" height="563" draggable="false">` : ""}<span class="badge ${cls}">${esc(lbl)}</span></div>
        <div class="tt">▶ ${esc(m.title)}</div><div class="ts">${esc(d)} · YouTube</div><div class="bar ${cls}"></div>
      </a>`;
    };
    const spacexTile = (m) => {
      const [cls, lbl] = badge(m);
      const im = safeUrl(m.image);
      const d = m.launch_date ? new Date(m.launch_date + "T00:00:00").toLocaleDateString(lang, { day: "2-digit", month: "short", year: "numeric" }) : "TBD";
      return `<div class="tile ${cls}" data-key="${esc(m.link || m.mission)}" role="button" tabindex="0">
        <div class="timg">${im ? `<img src="${esc(im)}" alt="" decoding="async" width="1000" height="563" draggable="false">` : ""}<span class="badge ${cls}">${esc(lbl)}</span></div>
        <div class="tt">${esc(T(m.mission))}</div>
        <div class="ts">${esc(d)}${m.launch_site ? " · " + esc(m.launch_site) : ""}</div>
        <div class="bar ${cls}"></div>
      </div>`;
    };
    const carBlock = (id, title, html) => `<div class="carwrap" data-car="${id}"><h3>${title}</h3><div class="car">
        <button class="arr l" type="button" aria-label="prev">‹</button>
        <div class="track">${html}</div>
        <button class="arr r" type="button" aria-label="next">›</button>
        <div class="car-count" role="status" aria-live="polite"></div>
      </div></div>`;
    const carousels = [];
    const spacexCarHtml = C.show_carousel && C.show_carousel_spacex !== false && allM.length ? (carBlock("spacex", "🚀 SpaceX Starship", allM.map(spacexTile).join(""))) : "";
    if (C.show_carousel && C.show_youtube) youtubeChannels.forEach(([language, key, , name]) => {
      // NASASpaceflight (lives Starship) is always shown, whatever the language filter.
      if (C["show_carousel_" + key] === false || !(key === "youtube_en" || youtubeLanguage === "both" || language === youtubeLanguage)) return;
      const st = this._state(key);
      if (!st || ["unknown", "unavailable"].includes(st.state)) return;
      const withLive = key === "youtube_fr" || key === "youtube_fr_starbase" || (key === "youtube_en" && C.youtube_live_badges_en !== false);
      const list = Array.isArray(st.attributes?.videos) && st.attributes.videos.length ? st.attributes.videos : [st.attributes || {}];
      const vids = list.filter((v) => v && typeof v === "object").map((v) => ({
        language, url: safeUrl(v.url), title: v.title || st.state, thumbnail: safeUrl(v.thumbnail),
        published: v.published, scheduled: v.scheduled, scheduled_approx: v.scheduled_approx === true, live_status: v.live_status,
      })).filter((v) => v.url);
      // Per channel count (0 = all). Legacy carousel_count applies only when set explicitly.
      const perChannel = C["youtube_count_" + key];
      const max = perChannel > 0 ? perChannel : (this._userCount ? C.carousel_count : vids.length);
      vids.splice(max);
      if (vids.length) carousels.push(carBlock(key, `📺 ${name} (${language.toUpperCase()})`, vids.map((v) => ytTile(v, withLive)).join("")));
    });
    const carouselHtml = carousels.join("");

    const keepScrolls = {};
    (this.shadowRoot.querySelectorAll(".carwrap") || []).forEach((w) => {
      const t = w.querySelector(".track"); if (t) keepScrolls[w.dataset.car] = t.scrollLeft;
    });
    (this._carouselResizes || []).forEach((r) => r.disconnect()); this._carouselResizes = [];
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
        .mimg { width: 100%; aspect-ratio: 16 / 9; height: auto; object-fit: cover; border-radius: 6px; display: block; margin-bottom: 8px; background: #111; }
        .orig { margin-left: 8px; font-size: .7em; padding: 2px 8px; border-radius: 10px; border: 1px solid var(--divider-color, #888); background: transparent; color: var(--secondary-text-color); cursor: pointer; vertical-align: middle; }
        .ptitle { font-weight: 700; font-size: 1.1em; margin-bottom: 4px; }
        .desc p { margin: 6px 0; line-height: 1.4; }
        .muted0 { color: var(--secondary-text-color); }
        .car { position: relative; margin: 12px 0 4px; }
        .track { position: relative; display: flex; gap: 12px; overflow-x: auto; scroll-snap-type: x mandatory; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; scrollbar-width: none; padding-bottom: 2px; }
        .track::-webkit-scrollbar { display: none; }
        .tile { flex: 0 0 auto; width: calc(50% - 6px); min-width: 200px; max-width: 340px; box-sizing: border-box; scroll-snap-align: start; cursor: pointer; border-radius: 14px; overflow: hidden; background: var(--secondary-background-color); position: relative; }
        .timg { aspect-ratio: 16 / 9; width: 100%; background: #1a1a1a; position: relative; border-radius: 14px 14px 0 0; overflow: hidden; }
        .timg img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
        .badge { z-index: 1; }
        @media (max-width: 600px) { .tile { width: 82%; min-width: 0; } }
        .vid { position: relative; aspect-ratio: 16 / 9; margin: 8px 0; border-radius: 8px; overflow: hidden; background: #000; }
        .vid iframe, .vid video { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
        .play { display: inline-block; margin: 8px 0; padding: 8px 14px; border-radius: 18px; background: #000; color: #fff; font-weight: 600; }
        .sech { margin: 12px 0 6px; font-weight: 700; letter-spacing: .08em; font-size: .85em; }
        .info { width: 100%; height: auto; aspect-ratio: 1000 / 522; object-fit: contain; display: block; border-radius: 6px; background: #000; }
        .tl { margin: 10px 0; font-family: "D-DIN", "Roboto Mono", ui-monospace, monospace; font-size: .85em; }
        .tl summary { cursor: pointer; font-weight: 700; letter-spacing: .12em; padding: 6px 0; }
        .tlh, .tlr { display: grid; grid-template-columns: 84px 1fr; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--divider-color, #444); }
        .tlh { color: var(--secondary-text-color); font-size: .8em; letter-spacing: .1em; }
        .tlt { font-variant-numeric: tabular-nums; }
        .tld { color: var(--secondary-text-color); font-size: .75em; padding-top: 6px; text-transform: uppercase; }
        .badge { position: absolute; top: 8px; right: 8px; padding: 3px 8px; border-radius: 10px; font-size: 0.7em; font-weight: 700; color: #fff; letter-spacing: .04em; }
        a.tile.youtube { color: inherit; text-decoration: none; }
        .badge.youtube, .bar.youtube { background: #c62828; }
        .badge.soon, .bar.soon { background: #1e88e5; }
        .badge.live, .bar.live { background: #d32f2f; }
        .badge.done, .bar.done { background: #757575; }
        .tt { font-weight: 700; padding: 8px 10px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .ts { font-size: 0.8em; color: var(--secondary-text-color); padding: 2px 10px 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .bar { height: 4px; width: 100%; }
        .arr { position: absolute; top: calc(50% - 34px); width: 34px; height: 34px; border-radius: 50%; border: none; cursor: pointer; z-index: 2; background: rgba(0,0,0,.6); color: #fff; font-size: 1.4em; line-height: 1; }
        .arr:disabled { visibility: hidden; pointer-events: none; }
        .car-count { text-align: center; font-size: .8em; color: var(--secondary-text-color); padding-top: 4px; font-variant-numeric: tabular-nums; }
        .arr.l { left: 4px; } .arr.r { right: 4px; }
        .sl { font-size: 0.8em; color: var(--secondary-text-color); text-transform: uppercase; }
      </style>
      <ha-card>
        <div class="title">${C.title ? esc(C.title) : `${hasMission ? esc(T(next.state)) : "TBD"} (SpaceX)`}</div>
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
        ${spacexCarHtml}
        ${showBtn ? `<button class="dbtn" type="button">${this._open ? L.hide : "ℹ️ " + L.details}</button>` : ""}
        ${panel}
        ${carouselHtml}
        ${C.show_live ? `<div class="live ${isLive ? "on" : ""}">
          ${isLive ? `🔴 ${L.live} — <a href="${esc(url)}" target="_blank" rel="noopener">${L.watch}</a>`
                   : `⚪ ${L.nolive} — <a href="https://www.spacex.com/vehicles/starship" target="_blank" rel="noopener">spacex.com</a>`}
        </div>` : ""}
        ${statsHtml}
        ${missionsHtml}
        ${youtubeHtml}
        ${C.show_news ? `<h3>${L.news}</h3><ul>${newsHtml}</ul>` : ""}
      </ha-card>`;
    const ob = this.shadowRoot.querySelector(".orig");
    if (ob) ob.addEventListener("click", (ev) => { ev.stopPropagation(); this._orig = !this._orig; this._render(); });
    const btn = this.shadowRoot.querySelector(".dbtn");
    if (btn) btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (this._open && this._sel) { this._sel = null; } else { this._open = !this._open; this._sel = null; }
      this._render();
    });
    this.shadowRoot.querySelectorAll("details.tl").forEach((d) => d.addEventListener("toggle", () => {
      if (d.open) this._secs.add(d.dataset.sec); else this._secs.delete(d.dataset.sec);
    }));
    this.shadowRoot.querySelectorAll(".carwrap").forEach((wrap) => {
      const track = wrap.querySelector(".track");
      if (!track) return;
      const keepScroll = keepScrolls[wrap.dataset.car] || 0;
      const items = [...track.querySelectorAll(".tile")];
      const prev = wrap.querySelector(".arr.l");
      const next = wrap.querySelector(".arr.r");
      const counter = wrap.querySelector(".car-count");
      const maxScroll = () => Math.max(0, track.scrollWidth - track.clientWidth);
      // offsetLeft is relative to .track, not to the card/arrow container.
      const target = (i) => Math.min(maxScroll(), items[i].offsetLeft);
      const current = () => {
        if (maxScroll() > 1 && track.scrollLeft >= maxScroll() - 1) return items.length - 1;
        return items.reduce((best, _, i) =>
          Math.abs(target(i) - track.scrollLeft) < Math.abs(target(best) - track.scrollLeft) ? i : best, 0);
      };
      const update = () => {
        prev.disabled = track.scrollLeft <= 1;
        next.disabled = track.scrollLeft >= maxScroll() - 1;
        counter.textContent = `${current() + 1} / ${items.length}`;
      };
      // Restore synchronously after layout; a delayed RAF could overwrite a new swipe.
      track.scrollLeft = Math.min(keepScroll, maxScroll());
      const step = (dir) => {
        const positions = items.map((_, i) => target(i));
        const left = track.scrollLeft;
        const destination = dir > 0
          ? positions.find((x) => x > left + 1) ?? maxScroll()
          : positions.filter((x) => x < left - 1).pop() ?? 0;
        // Exact, non-animated targets avoid interrupted smooth scrolls + iOS snap.
        track.scrollTo({ left: destination, behavior: "instant" });
        update();
      };
      prev.addEventListener("click", (ev) => { ev.stopPropagation(); step(-1); });
      next.addEventListener("click", (ev) => { ev.stopPropagation(); step(1); });
      track.addEventListener("scroll", update, { passive: true });
      const ro = new ResizeObserver(update);
      ro.observe(track);
      this._carouselResizes.push(ro);
      update();
      track.querySelectorAll(".tile").forEach((t) => {
        // Native anchors open YouTube (including keyboard Enter), not mission details.
        if (t.dataset.youtube) return;
        const open = (ev) => {
          ev.stopPropagation();
          const key = t.dataset.key;
          if (this._open && this._sel === key) { this._open = false; this._sel = null; } else { this._open = true; this._sel = key; }
          this._render();
        };
        t.addEventListener("click", open);
        t.addEventListener("keydown", (ev) => { if (ev.key === "Enter") open(ev); });
      });
    });
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
