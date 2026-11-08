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


// Carousel: auto matches HA locale, overrides are explicit, native links don't open details.
const missions = Array.from({length: 21}, (_, i) => ({mission: `Flight ${i}`, link: `mission-${i}`, mission_status: 'final'}));
const allStates = {...states, 'sensor.starship_tracker_starship_missions': {state: '21', attributes: {past: missions}}};
const tiles = () => card.shadowRoot.track.querySelectorAll('.tile');
const youtubeCount = () => tiles().filter(t => t.dataset.youtube).length;
card.setConfig({});
card.hass = {language: 'fr-FR', states: allStates};
assert.match(card.shadowRoot.innerHTML, /data-youtube="fr"/);
assert.doesNotMatch(card.shadowRoot.innerHTML, /data-youtube="en"/);
assert.equal(tiles().length, 22);
assert.equal(youtubeCount(), 1);
assert.equal(card.shadowRoot.counter.textContent, '1 / 22');
assert.equal(tiles()[0].handlers.click, undefined);
assert.equal(typeof tiles()[1].handlers.click, 'function');
assert.match(card.shadowRoot.innerHTML, /<a class="tile youtube"[^>]*href="https:\/\/www.youtube.com\/watch\?v=aaaaaaaaaaa"/);
assert.match(card.shadowRoot.innerHTML, /hqdefault.jpg/);
for (let i = 0; i < 21; i++) card.shadowRoot.next.handlers.click({stopPropagation() {}});
assert.equal(card.shadowRoot.counter.textContent, '22 / 22');
assert.equal(card.shadowRoot.next.disabled, true);
card.hass = {language: 'en-US', states: allStates};
assert.match(card.shadowRoot.innerHTML, /data-youtube="en"/);
assert.doesNotMatch(card.shadowRoot.innerHTML, /data-youtube="fr"/);
card.setConfig({youtube_carousel_lang: 'both'});
assert.equal(youtubeCount(), 2);
assert.equal(tiles().length, 23);
card.setConfig({youtube_carousel_lang: 'fr'});
assert.match(card.shadowRoot.innerHTML, /data-youtube="fr"/);
assert.doesNotMatch(card.shadowRoot.innerHTML, /data-youtube="en"/);
card.setConfig({youtube_carousel_lang: 'en'});
assert.match(card.shadowRoot.innerHTML, /data-youtube="en"/);
card.setConfig({lang: 'fr', youtube_carousel_lang: 'auto'});
assert.match(card.shadowRoot.innerHTML, /data-youtube="fr"/);
card.setConfig({show_youtube: false});
assert.equal(youtubeCount(), 0);
assert.equal(tiles().length, 21);
card.setConfig({youtube_carousel_lang: 'both', carousel_count: 10});
assert.equal(tiles().length, 10);
assert.equal(youtubeCount(), 2);
card.setConfig({show_carousel: false});
assert.equal(card.shadowRoot.track, null);
console.log('PASS: carousel auto/fr/en/both, native video links, thumbnails, total limit, navigation counter and hidden toggle');


// Optional StarBase FR is another French source, without replacing UFOTINIK.
const starbase = video('Projet hebdomadaire', 'https://www.youtube.com/watch?v=ccccccccccc');
card.setConfig({});
card.hass = {language: 'fr', states: {...allStates, 'sensor.starship_tracker_youtube_fr_starbase': starbase}};
assert.equal(youtubeCount(), 2);
assert.equal(tiles().length, 23);
assert.match(card.shadowRoot.innerHTML, /FR · StarBase FR/);
card.hass = {language: 'en', states: {...allStates, 'sensor.starship_tracker_youtube_fr_starbase': starbase}};
assert.equal(youtubeCount(), 1);
assert.doesNotMatch(card.shadowRoot.innerHTML, /data-youtube="fr"/);
card.setConfig({youtube_carousel_lang: 'both'});
assert.equal(youtubeCount(), 3);
assert.equal(tiles().length, 24);
console.log('PASS: optional StarBase FR source, FR auto selection and three-channel both mode');
