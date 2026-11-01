/*
 * pp-lab calculator page. Talks to api/calc next to this page.
 * Texts: add a language by copying the "en" block in TEXT and adding an <option> in index.html.
 */
(function () {
  'use strict';

  var TEXT = {
    en: {
      title: 'pp calculator', map: 'Map (ID or link)', map_placeholder: 'e.g. 129891 or https://osu.ppy.sh/b/129891',
      mode: 'Mode', mode_auto: "Map's", mods: 'Mods', by_acc: 'Accuracy', by_hits: 'Hit counts',
      acc: 'Accuracy (%)', miss: 'Misses', combo: 'Combo', combo_full: 'empty = full combo',
      note: 'Maps are downloaded from osu! the first time they are calculated.',
      empty: 'Enter a map ID or link.', not_found: 'This map was not found.',
      too_many: 'Too many requests, try again in a minute.', busy: 'The calculator is busy, try again in a moment.',
      error: 'Could not calculate pp. Try again in a moment.', mapped_by: 'mapped by {creator}',
      converted: 'convert', max_combo: 'max combo {combo}x', acc_result: 'Accuracy: {acc}%',
      table_acc: 'Full combo, {mods}', table_mods: 'SS with mods', base: 'main',
      footer: 'pp calculated with rosu-pp and akatsuki-pp.', theme_toggle: 'Light / dark'
    },
    pl: {
      title: 'kalkulator pp', map: 'Mapa (ID albo link)', map_placeholder: 'np. 129891 albo https://osu.ppy.sh/b/129891',
      mode: 'Tryb', mode_auto: 'Mapy', mods: 'Mody', by_acc: 'Celność', by_hits: 'Trafienia',
      acc: 'Celność (%)', miss: 'Missy', combo: 'Combo', combo_full: 'puste = pełne combo',
      note: 'Mapy są pobierane z osu! przy pierwszym liczeniu.',
      empty: 'Wpisz ID albo link mapy.', not_found: 'Nie znaleziono takiej mapy.',
      too_many: 'Za dużo zapytań, spróbuj za minutę.', busy: 'Kalkulator jest zajęty, spróbuj za chwilę.',
      error: 'Nie udało się policzyć pp. Spróbuj za chwilę.', mapped_by: 'mapa: {creator}',
      converted: 'konwersja', max_combo: 'max combo {combo}x', acc_result: 'Celność: {acc}%',
      table_acc: 'Pełne combo, {mods}', table_mods: 'SS z modami', base: 'główny',
      footer: 'pp liczone przez rosu-pp i akatsuki-pp.', theme_toggle: 'Jasny / ciemny'
    }
  };
  var MOD_ORDER = ['NF', 'EZ', 'HD', 'HR', 'DT', 'NC', 'HT', 'FL', 'SO'];
  var EXCLUSIVE = { EZ: ['HR'], HR: ['EZ'], DT: ['HT', 'NC'], NC: ['HT', 'DT'], HT: ['DT', 'NC'], NF: ['SO'], SO: ['NF'] };
  var MODES = ['osu!', 'osu!taiko', 'osu!catch', 'osu!mania'];

  var root = document.getElementById('pl-root');
  var $ = function (id) { return document.getElementById(id); };
  var state = { mode: '', mods: [], kind: 'acc', names: {}, last: null };
  var timer = null, seq = 0;

  function store(key, value) { try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch (e) { return null; } }
  var lang = (new URLSearchParams(location.search).get('lang')) || store('pl.lang') || ((navigator.language || 'en').slice(0, 2));
  if (!TEXT[lang]) lang = 'en';
  function t(key) { return (TEXT[lang] && TEXT[lang][key]) || TEXT.en[key] || key; }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(n) { return Number(n).toLocaleString(lang, { maximumFractionDigits: 2 }); }

  function applyTexts() {
    document.documentElement.lang = lang;
    $('pl-lang').value = lang;
    document.querySelectorAll('[data-i18n]').forEach(function (el) { el.textContent = t(el.getAttribute('data-i18n')); });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) { el.placeholder = t(el.getAttribute('data-i18n-placeholder')); });
    document.querySelectorAll('[data-i18n-title]').forEach(function (el) { el.title = t(el.getAttribute('data-i18n-title')); });
    if (state.last) render(state.last);
  }

  // theme: saved choice, else the system setting
  var theme = store('pl.theme') || (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', theme);
  $('pl-theme').addEventListener('click', function () {
    theme = theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    store('pl.theme', theme);
  });
  $('pl-lang').addEventListener('change', function () { lang = this.value; store('pl.lang', lang); applyTexts(); });

  fetch('api/calc/variants').then(function (r) { return r.json(); }).then(function (d) {
    (d.variants || []).forEach(function (v) { state.names[v.id] = v.name || {}; });
    if (state.last) render(state.last);
  }).catch(function () {});
  function variantName(id) { var n = state.names[id]; return (n && (n[lang] || n.en)) || id; }

  // settings from the address, so results can be shared as links
  var qs = new URLSearchParams(location.search);
  $('pl-map').value = qs.get('map') || '';
  if (qs.get('mods')) state.mods = (qs.get('mods').toUpperCase().match(/[A-Z]{2}/g) || []).filter(function (m) { return MOD_ORDER.indexOf(m) >= 0; });
  if (/^[0-3]$/.test(qs.get('mode') || '')) state.mode = qs.get('mode');
  if (qs.get('acc')) $('pl-acc').value = qs.get('acc');
  if (qs.get('n100') || qs.get('n50')) {
    state.kind = 'hits';
    $('pl-n100').value = qs.get('n100') || 0;
    $('pl-n50').value = qs.get('n50') || 0;
    $('pl-miss').value = qs.get('miss') || 0;
  } else if (qs.get('miss')) {
    $('pl-miss-a').value = qs.get('miss');
  }
  if (qs.get('combo')) $('pl-combo').value = qs.get('combo');

  function syncButtons() {
    document.querySelectorAll('#pl-mods [data-mod]').forEach(function (b) { b.classList.toggle('active', state.mods.indexOf(b.dataset.mod) >= 0); });
    document.querySelectorAll('#pl-modes [data-mode]').forEach(function (b) { b.classList.toggle('active', b.dataset.mode === state.mode); });
    document.querySelectorAll('#pl-kind [data-kind]').forEach(function (b) { b.classList.toggle('active', b.dataset.kind === state.kind); });
    $('pl-acc-box').hidden = state.kind !== 'acc';
    $('pl-hits-box').hidden = state.kind !== 'hits';
  }

  $('pl-mods').addEventListener('click', function (e) {
    var b = e.target.closest('[data-mod]');
    if (!b) return;
    var m = b.dataset.mod, i = state.mods.indexOf(m);
    if (i >= 0) state.mods.splice(i, 1);
    else {
      state.mods = state.mods.filter(function (x) { return (EXCLUSIVE[m] || []).indexOf(x) < 0; });
      state.mods.push(m);
    }
    syncButtons(); schedule(0);
  });
  $('pl-modes').addEventListener('click', function (e) {
    var b = e.target.closest('[data-mode]');
    if (b) { state.mode = b.dataset.mode; syncButtons(); schedule(0); }
  });
  $('pl-kind').addEventListener('click', function (e) {
    var b = e.target.closest('[data-kind]');
    if (b) { state.kind = b.dataset.kind; syncButtons(); schedule(0); }
  });
  ['pl-map', 'pl-acc', 'pl-miss-a', 'pl-n100', 'pl-n50', 'pl-miss', 'pl-combo'].forEach(function (id) {
    $(id).addEventListener('input', function () { schedule(350); });
  });

  function params() {
    var p = new URLSearchParams();
    p.set('map', $('pl-map').value.trim());
    var mods = MOD_ORDER.filter(function (m) { return state.mods.indexOf(m) >= 0; }).join('');
    if (mods) p.set('mods', mods);
    if (state.mode !== '') p.set('mode', state.mode);
    if (state.kind === 'acc') {
      p.set('acc', $('pl-acc').value || '100');
      if (+$('pl-miss-a').value > 0) p.set('miss', $('pl-miss-a').value);
    } else {
      p.set('n100', $('pl-n100').value || '0');
      p.set('n50', $('pl-n50').value || '0');
      p.set('miss', $('pl-miss').value || '0');
    }
    if (+$('pl-combo').value > 0) p.set('combo', $('pl-combo').value);
    return p;
  }
  function schedule(delay) { clearTimeout(timer); timer = setTimeout(run, delay); }
  function showEmpty(text) { $('pl-result').hidden = true; $('pl-empty').hidden = false; $('pl-empty-text').textContent = text; }

  function run() {
    var p = params();
    var base = location.pathname;
    if (!/\d/.test(p.get('map'))) { showEmpty(t('empty')); history.replaceState(null, '', base); return; }
    history.replaceState(null, '', base + '?' + p.toString());
    var my = ++seq;
    fetch('api/calc?' + p.toString())
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, status: r.status, d: d }; }); })
      .then(function (res) {
        if (my !== seq) return;
        if (!res.ok) {
          var msg = { 404: t('not_found'), 429: t('too_many'), 503: t('busy') }[res.status] ||
            (typeof (res.d && res.d.detail) === 'string' ? res.d.detail : t('error'));
          showEmpty(msg);
          return;
        }
        state.last = res.d;
        render(res.d);
      })
      .catch(function () { if (my === seq) showEmpty(t('error')); });
  }

  function render(d) {
    $('pl-empty').hidden = true;
    $('pl-result').hidden = false;
    var m = d.map;
    var cover = root.getAttribute('data-cover') || '';
    $('pl-cover').hidden = !cover || !m.set_id;
    if (cover && m.set_id) $('pl-cover').style.backgroundImage = 'url("' + cover.replace('{set_id}', String(parseInt(m.set_id, 10))) + '")';
    $('pl-artist').textContent = m.artist;
    $('pl-title').textContent = m.title + ' [' + m.version + ']';
    $('pl-title').href = 'https://osu.ppy.sh/b/' + parseInt(m.id, 10);
    var meta = [
      t('mapped_by').replace('{creator}', m.creator),
      MODES[d.play.mode] + (d.play.mode !== m.mode ? ' (' + t('converted') + ')' : ''),
      Number(m.stars).toFixed(2) + '★ ' + d.play.mods,
      t('max_combo').replace('{combo}', m.max_combo)
    ];
    $('pl-meta').textContent = meta.join(' · ');
    $('pl-acc-note').textContent = state.kind === 'hits' && d.play.acc != null ? t('acc_result').replace('{acc}', Number(d.play.acc).toFixed(2)) : '';

    var html = '';
    d.variants.forEach(function (v) {
      var r = d.results[v], isBase = v === d.base, parts = [];
      ['aim', 'speed', 'acc', 'fl', 'reading'].forEach(function (k) { if (r.parts[k] > 0) parts.push(k + ' ' + fmt(r.parts[k])); });
      html += '<div class="pl-card pl-variant' + (isBase ? ' base' : '') + '">' +
        '<div class="pl-muted">' + esc(variantName(v)) + (isBase ? '<span class="pl-badge">' + esc(t('base')) + '</span>' : '') + '</div>' +
        '<div class="pl-pp">' + (r.error ? '-' : esc(fmt(r.pp)) + '<small>pp</small>') + '</div>' +
        '<div class="pl-muted">' + esc(r.error ? r.error : Number(r.stars).toFixed(2) + '★' + (parts.length ? ' · ' + parts.join(', ') : '')) + '</div></div>';
    });
    $('pl-variants').innerHTML = html;

    $('pl-acc-head').textContent = t('table_acc').replace('{mods}', d.play.mods);
    var head = '<thead><tr><th></th>' + d.variants.map(function (v) { return '<th>' + esc(variantName(v)) + '</th>'; }).join('') + '</tr></thead>';
    $('pl-acc-table').innerHTML = head + '<tbody>' + d.results[d.base].acc_table.map(function (row, i) {
      return '<tr><td>' + (row.acc === 100 ? 'SS' : esc(row.acc) + '%') + '</td>' +
        d.variants.map(function (v) { return '<td>' + esc(fmt(d.results[v].acc_table[i].pp)) + '</td>'; }).join('') + '</tr>';
    }).join('') + '</tbody>';
    $('pl-mod-table').innerHTML = head + '<tbody>' + d.results[d.base].mod_table.map(function (row, i) {
      return '<tr><td>' + esc(row.mods) + ' <span class="pl-muted">' + esc(Number(row.stars).toFixed(2)) + '★</span></td>' +
        d.variants.map(function (v) { return '<td>' + esc(fmt(d.results[v].mod_table[i].pp)) + '</td>'; }).join('') + '</tr>';
    }).join('') + '</tbody>';
  }

  applyTexts();
  syncButtons();
  if ($('pl-map').value) run();
})();
