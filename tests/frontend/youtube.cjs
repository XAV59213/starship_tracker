/* Pure template smoke tests, no browser/network. Run: node tests/frontend/youtube.cjs */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const registry = new Map();
class ShadowRoot {
  constructor() { this._html = ''; this.track = null; }
  set innerHTML(html) {
    this._html = html;
    const element = () => ({handlers: {}, addEventListener(event, fn) { this.handlers[event] = fn; }});
    const items = [...html.matchAll(/<(?:a|div) class="tile ([^"]+)"[^>]*>/g)].map((match, i) => ({
      ...element(), offsetLeft: i * 300,
      dataset: match[0].includes('data-youtube') ? {youtube: 'yes'} : {key: 'mission-' + i},
    }));
    this.prev = element(); this.next = element(); this.counter = {textContent: ''};
    this.track = items.length ? {
      ...element(), scrollLeft: 0, scrollWidth: items.length * 300, clientWidth: 300,
      querySelectorAll: () => items,
      scrollTo({left}) { this.scrollLeft = left; },
    } : null;
  }
  get innerHTML() { return this._html; }
  querySelector(selector) {
    return ({'.track': this.track, '.arr.l': this.prev, '.arr.r': this.next, '.car-count': this.counter})[selector] || null;
  }
  querySelectorAll() { return []; }
}
class HTMLElement {
  attachShadow() { this.shadowRoot = new ShadowRoot(); }
}
const context = {
  HTMLElement, console, window: {}, ResizeObserver: class { observe() {} disconnect() {} },
  customElements: {get: name => registry.get(name), define: (name, element) => registry.set(name, element)},
  setInterval: () => 1, clearInterval: () => {}, URL,
};
vm.runInNewContext(fs.readFileSync('custom_components/starship_tracker/www/starship-tracker-card.js', 'utf8'), context);
const Card = registry.get('starship-tracker-card');
const card = new Card();
card.setConfig({});
const video = (title, url) => ({state: title, attributes: {title, url, published: "2026-11-08T10:00:00+00:00", thumbnail: "https://i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg"}, last_updated: title});
const states = {
  'sensor.starship_tracker_youtube_fr': video('Starship <script>alert(1)</script>', 'https://www.youtube.com/watch?v=aaaaaaaaaaa'),
  'sensor.starship_tracker_youtube_en': video('Starship EN', 'https://www.youtube.com/watch?v=bbbbbbbbbbb'),
};
card.hass = {language: 'fr', states};
assert.match(card.shadowRoot.innerHTML, /📺 Vidéos YouTube/);
assert.match(card.shadowRoot.innerHTML, /<b>FR<\/b>/);
assert.match(card.shadowRoot.innerHTML, /<b>EN<\/b>/);
assert.match(card.shadowRoot.innerHTML, /Starship &lt;script&gt;/);
assert.doesNotMatch(card.shadowRoot.innerHTML, /<script>/);
card.setConfig({show_youtube: false});
assert.doesNotMatch(card.shadowRoot.innerHTML, /📺/);
card.setConfig({});
card.hass = {language: 'en', states};
assert.match(card.shadowRoot.innerHTML, /📺 YouTube videos/);
card.hass = {language: 'en', states: {'sensor.starship_tracker_youtube_fr': video('bad', 'javascript:alert(1)')}};
assert.doesNotMatch(card.shadowRoot.innerHTML, /📺/);
card.hass = {language: 'fr', states: {}};
assert.doesNotMatch(card.shadowRoot.innerHTML, /📺/);
card.setConfig({youtube_fr: 'sensor.renamed'});
card.hass = {language: 'fr', states: {'sensor.renamed': states['sensor.starship_tracker_youtube_fr']}};
assert.match(card.shadowRoot.innerHTML, /<b>FR<\/b>/);
assert.equal(Card.getStubConfig().show_youtube, true);
assert.match(Card.getConfigForm().computeLabel({name: 'show_youtube'}), /FR\/EN/);
console.log('PASS: FR/EN links, toggle, locale, escaping, unsafe URLs, absent sensors and entity override');


// Four separate carousels: SpaceX, UFOTINIK, StarBase FR, NASASpaceflight.
const missions = Array.from({length: 21}, (_, i) => ({mission: `Flight ${i}`, link: `mission-${i}`, mission_status: 'final'}));
const allStates = {...states, 'sensor.starship_tracker_starship_missions': {state: '21', attributes: {past: missions}}};
const html = () => card.shadowRoot.innerHTML;
const cars = () => [...html().matchAll(/data-car="([^"]+)"/g)].map(m => m[1]);
const count = (id) => { const part = html().split(`data-car="${id}"`)[1] || ''; return (part.split('data-car=')[0].match(/class="tile /g) || []).length; };
card.setConfig({});
card.hass = {language: 'fr-FR', states: allStates};
assert.deepEqual(cars(), ['spacex', 'youtube_fr', 'youtube_en']);
card.setConfig({youtube_carousel_lang: 'auto'});
card.hass = {language: 'fr-FR', states: allStates};
assert.deepEqual(cars(), ['spacex', 'youtube_fr', 'youtube_en']);
card.setConfig({youtube_carousel_lang: 'fr'});
card.hass = {language: 'fr-FR', states: allStates};
assert.deepEqual(cars(), ['spacex', 'youtube_fr', 'youtube_en']);
assert.equal(count('spacex'), 21);
assert.equal(count('youtube_fr'), 1);
assert.doesNotMatch(html().split('data-car="youtube_fr"')[0], /data-youtube/);
assert.match(html(), /<a class="tile youtube"[^>]*href="https:\/\/www.youtube.com\/watch\?v=aaaaaaaaaaa"/);
card.setConfig({youtube_carousel_lang: 'auto'});
card.hass = {language: 'en-US', states: allStates};
assert.deepEqual(cars(), ['spacex', 'youtube_en']);
const starbase = video('Projet hebdomadaire', 'https://www.youtube.com/watch?v=ccccccccccc');
starbase.attributes.videos = [1, 2, 3].map(n => ({title: `SB ${n}`, url: `https://www.youtube.com/watch?v=cccccccccc${n}`, published: '2026-11-0' + n + 'T00:00:00+00:00'}));
card.setConfig({youtube_carousel_lang: 'both'});
card.hass = {language: 'fr', states: {...allStates, 'sensor.starship_tracker_youtube_fr_starbase': starbase}};
assert.deepEqual(cars(), ['spacex', 'youtube_fr', 'youtube_fr_starbase', 'youtube_en']);
assert.equal(count('youtube_fr_starbase'), 3);
card.setConfig({youtube_count_youtube_fr_starbase: 2});
card.hass = {language: 'fr', states: {...allStates, 'sensor.starship_tracker_youtube_fr_starbase': starbase}};
assert.equal(count('youtube_fr_starbase'), 2);
card.setConfig({youtube_carousel_lang: 'both', show_carousel_spacex: false, show_carousel_youtube_en: false});
assert.deepEqual(cars(), ['youtube_fr', 'youtube_fr_starbase']);
card.setConfig({carousel_count: 10});
assert.equal(count('spacex'), 21);
card.setConfig({show_carousel: false});
assert.deepEqual(cars(), []);
console.log('PASS: four separate carousels, language filter, per-carousel toggles and limit');

// UFOTINIK and StarBase FR: upcoming / live / ended badges. NASASpaceflight keeps the language badge.
const clip = (id, title, extra = {}) => ({
  title, url: `https://www.youtube.com/watch?v=${id}`, published: '2026-11-01T10:00:00+00:00',
  thumbnail: 'https://i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg', ...extra,
});
const withClips = (title, id, clips) => {
  const state = video(title, `https://www.youtube.com/watch?v=${id}`);
  state.attributes.videos = clips;
  return state;
};
const frLive = withClips('Starship base', 'aaaaaaaaaaa', [
  clip('aaaaaaaaaaa', 'Starship base'),
  clip('bbbbbbbbbbb', 'Live Starship', {live_status: 'live', published: '2026-11-08T18:00:00+00:00'}),
  clip('ccccccccccc', 'Upcoming Starship', {live_status: 'upcoming', scheduled: '2026-11-15T20:00:00+00:00', published: '2026-11-15T20:00:00+00:00'}),
  clip('ddddddddddd', 'Past stream', {live_status: 'ended', published: '2026-10-01T10:00:00+00:00'}),
]);
const enLive = withClips('EN premiere', 'eeeeeeeeeee', [
  clip('eeeeeeeeeee', 'EN premiere', {live_status: 'upcoming', scheduled: '2026-11-15T20:00:00+00:00', published: '2026-11-15T20:00:00+00:00'}),
]);
const slice = (id) => (html().split(`data-car="${id}"`)[1] || '').split('data-car=')[0];
card.setConfig({youtube_carousel_lang: 'both', show_carousel_spacex: false});
card.hass = {language: 'fr', states: {
  'sensor.starship_tracker_youtube_fr': frLive,
  'sensor.starship_tracker_youtube_en': enLive,
}};
const frCar = slice('youtube_fr');
assert.match(frCar, /badge soon">À venir</);
assert.match(frCar, /badge live">En direct</);
assert.match(frCar, /badge done">Terminé</);
const soon = frCar.match(/<a class="tile youtube"[\s\S]*?Upcoming Starship[\s\S]*?<\/a>/);
assert.ok(soon);
assert.match(soon[0], /\d{1,2}:\d{2}|\d{1,2}\s*h\s*\d{2}/);
assert.match(slice('youtube_en'), /badge soon">À venir</);
card.setConfig({youtube_carousel_lang: 'both', show_carousel_spacex: false, youtube_live_badges_en: false});
card.hass = {language: 'fr', states: {'sensor.starship_tracker_youtube_en': enLive}};
assert.match(slice('youtube_en'), /badge youtube">EN</);
assert.doesNotMatch(slice('youtube_en'), /À venir|Upcoming|En direct|Terminé/);
card.setConfig({youtube_carousel_lang: 'both', show_carousel_spacex: false});
card.hass = {language: 'en', states: {'sensor.starship_tracker_youtube_fr': frLive}};
assert.match(slice('youtube_fr'), /badge soon">Upcoming</);
assert.match(slice('youtube_fr'), /badge live">Live</);
assert.match(slice('youtube_fr'), /badge done">Ended</);
const starbaseLive = withClips('SB', 'fffffffffff', [clip('fffffffffff', 'SB live', {live_status: 'live'})]);
card.setConfig({youtube_carousel_lang: 'fr', show_carousel_spacex: false});
card.hass = {language: 'fr', states: {'sensor.starship_tracker_youtube_fr_starbase': starbaseLive}};
assert.match(slice('youtube_fr_starbase'), /badge live">En direct</);
card.hass = {language: 'fr', states: {'sensor.starship_tracker_youtube_fr': video('Plain', 'https://www.youtube.com/watch?v=aaaaaaaaaaa')}};
assert.match(slice('youtube_fr'), /badge youtube">FR</);
assert.doesNotMatch(slice('youtube_fr'), /À venir|En direct|Terminé/);
console.log('PASS: UFOTINIK and StarBase FR live badges, datetime, EN labels, NASASpaceflight unchanged');
