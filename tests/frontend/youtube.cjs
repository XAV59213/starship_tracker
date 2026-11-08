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
assert.deepEqual(cars(), ['spacex', 'youtube_fr']);
assert.equal(count('spacex'), 21);
assert.equal(count('youtube_fr'), 1);
assert.doesNotMatch(html().split('data-car="youtube_fr"')[0], /data-youtube/);
assert.match(html(), /<a class="tile youtube"[^>]*href="https:\/\/www.youtube.com\/watch\?v=aaaaaaaaaaa"/);
card.hass = {language: 'en-US', states: allStates};
assert.deepEqual(cars(), ['spacex', 'youtube_en']);
const starbase = video('Projet hebdomadaire', 'https://www.youtube.com/watch?v=ccccccccccc');
starbase.attributes.videos = [1, 2, 3].map(n => ({title: `SB ${n}`, url: `https://www.youtube.com/watch?v=cccccccccc${n}`, published: '2026-11-0' + n + 'T00:00:00+00:00'}));
card.setConfig({youtube_carousel_lang: 'both'});
card.hass = {language: 'fr', states: {...allStates, 'sensor.starship_tracker_youtube_fr_starbase': starbase}};
assert.deepEqual(cars(), ['spacex', 'youtube_fr', 'youtube_fr_starbase', 'youtube_en']);
assert.equal(count('youtube_fr_starbase'), 3);
card.setConfig({youtube_carousel_lang: 'both', show_carousel_spacex: false, show_carousel_youtube_en: false});
assert.deepEqual(cars(), ['youtube_fr', 'youtube_fr_starbase']);
card.setConfig({carousel_count: 10});
assert.equal(count('spacex'), 21);
card.setConfig({show_carousel: false});
assert.deepEqual(cars(), []);
console.log('PASS: four separate carousels, language filter, per-carousel toggles and limit');
