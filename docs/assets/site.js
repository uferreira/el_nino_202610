/* site.js: draws what Python wrote. No science happens here.
 *
 * Every <section class="panel" data-kind data-src> is loaded the same way:
 * the values of its <select data-control> elements (and of the page-level
 * ones in .page-controls) fill the data path, the JSON is fetched, and
 * RENDERERS[kind] draws it. Control values are kept in the URL. Colours come
 * from data/theme.json by trace role (trace.meta.role) or Compare slot
 * (trace.meta.slot), so light/dark switching needs no rebuild.
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var main = document.querySelector('main');
  var THEME_KEY = 'enso.theme';
  var THEMES = null;
  var themeListeners = [];
  var narrow = window.matchMedia('(max-width: 760px)');

  // ---- Small helpers -------------------------------------------------------

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function $(scope, sel) { return scope.querySelector(sel); }
  function $$(scope, sel) { return Array.prototype.slice.call(scope.querySelectorAll(sel)); }
  function find(list, fn) { for (var i = 0; i < list.length; i++) if (fn(list[i])) return list[i]; return null; }

  var jsonCache = {};
  function fetchJSON(path) {
    if (!jsonCache[path]) {
      jsonCache[path] = fetch(path).then(function (r) {
        if (!r.ok) throw new Error(r.status + ' ' + path);
        return r.json();
      }).catch(function (e) { delete jsonCache[path]; throw e; });
    }
    return jsonCache[path];
  }

  function getField(obj, path) {
    return path.split('.').reduce(function (o, k) { return o == null ? o : o[k]; }, obj);
  }

  /** Fill [data-field] text; hide [data-optional] blocks whose value is null. */
  function fillFields(scope, data) {
    $$(scope, '[data-field]').forEach(function (el) {
      var v = getField(data, el.dataset.field);
      if (v !== undefined && v !== null && typeof v !== 'object') el.textContent = v;
    });
    $$(scope, '[data-optional]').forEach(function (el) {
      var v = getField(data, el.dataset.optional);
      if (v !== undefined) el.hidden = v === null;
    });
  }

  // ---- Theme ---------------------------------------------------------------

  function themeName() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function onThemeChange() {
    var name = themeName();
    var btn = $(document, '[data-theme-toggle]');
    if (btn) btn.setAttribute('aria-label', name === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    themeListeners.forEach(function (fn) { fn(name); });
  }

  function initTheme() {
    var btn = $(document, '[data-theme-toggle]');
    if (btn) btn.addEventListener('click', function () {
      var next = themeName() === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* storage blocked: still switches */ }
      onThemeChange();
    });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (!root.dataset.theme) onThemeChange();
    });
  }

  function rgba(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + (n >> 16) + ', ' + ((n >> 8) & 255) + ', ' + (n & 255) + ', ' + a + ')';
  }

  /** Give a figure the theme's template and colour each trace by role or slot. */
  function paint(fig, name) {
    var t = THEMES[name];
    fig = clone(fig);
    fig.layout.template = t.template;
    fig.data.forEach(function (tr) {
      var m = tr.meta || {};
      var r = t.roles[m.role];
      if (!r) return;
      var slot = m.slot && t.slots[m.slot];
      var lineColor = slot || r.line, markerColor = slot || r.marker;
      if (m.role === 'cursor') markerColor = r.marker;          // hollow ring
      var ring = r.ring && (m.role === 'cursor' && slot ? slot : r.ring);
      // A translucent line as an rgba colour, not trace opacity: it looks the
      // same (one path is one stroke) and the browser does not composite a
      // layer per trace on every animation frame.
      if (r.line && tr.mode === 'lines' && tr.opacity !== undefined && tr.opacity < 1 && /^#[0-9a-f]{6}$/i.test(lineColor)) {
        lineColor = rgba(lineColor, tr.opacity);
        delete tr.opacity;
      }
      if (r.line) tr.line = Object.assign({}, tr.line, { color: lineColor });
      if (r.marker || ring) {
        tr.marker = Object.assign({}, tr.marker);
        if (r.marker) tr.marker.color = markerColor;
        if (ring) tr.marker.line = Object.assign({}, tr.marker.line, { color: ring });
      }
    });
    (fig.layout.shapes || []).forEach(function (s) {
      if (s.type === 'line') s.line = Object.assign({}, s.line, { color: t.zero });
      if (s.name === 'provisional') s.fillcolor = t.provisional;
      if (s.name === 'band') s.fillcolor = t.band;
    });
    var meta = fig.layout.meta || {};
    if (narrow.matches && meta.narrow_top !== undefined) {
      fig.layout.margin = Object.assign({}, fig.layout.margin, { t: meta.narrow_top });
    }
    return fig;
  }

  // ---- Plotting --------------------------------------------------------------

  /* Plotly re-measures only on window resize; a plot whose box changes for
   * another reason (a legend row appearing) is resized here. */
  var resizer = new ResizeObserver(function (entries) {
    entries.forEach(function (e) { if (e.target.data) Plotly.Plots.resize(e.target); });
  });

  function draw(div, fig, filename) {
    resizer.observe(div);
    var config = {
      responsive: true,
      displaylogo: false,
      displayModeBar: narrow.matches ? false : 'hover',
      modeBarButtons: [['toImage']],
      toImageButtonOptions: { format: 'png', scale: 2, filename: filename }
    };
    div._ensoConfig = config;      // reused when playing redraws the plot
    return Plotly.react(div, fig.data, fig.layout, config);
  }

  /** Index of the first trace matching every key of `meta`. */
  function traceIndex(div, meta) {
    for (var i = 0; i < div.data.length; i++) {
      var m = div.data[i].meta || {}, ok = true;
      for (var k in meta) if (m[k] !== meta[k]) { ok = false; break; }
      if (ok) return i;
    }
    return -1;
  }

  function setXY(div, meta, x, y) {
    var i = traceIndex(div, meta);
    if (i >= 0) Plotly.restyle(div, { x: [x], y: [y] }, [i]);
  }

  /** Loop points a..b (inclusive), split at loop point `split` (the first
   * provisional one; Infinity for none) into a solid and a dashed part. */
  function segments(loop, a, b, split) {
    var solid = { x: [], y: [] }, prov = { x: [], y: [] };
    if (a <= Math.min(b, split)) {
      var e = Math.min(b, split) + 1;
      solid = { x: loop.x.slice(a, e), y: loop.y.slice(a, e) };
    }
    if (b > split) {
      var s = Math.max(a, split);
      prov = { x: loop.x.slice(s, b + 1), y: loop.y.slice(s, b + 1) };
    }
    return { solid: solid, prov: prov };
  }

  /** A highlighted stretch of a loop (months i0..i1), split at the first provisional month p. */
  function loopSegments(loop, k, p, i0, i1) {
    return segments(loop, i0 * k, i1 * k, (p === null || p === undefined) ? Infinity : p * k);
  }

  /** Per-period paths (each starting where the last one ended) joined into one loop. */
  function joinPaths(traces) {
    var x = [], y = [];
    traces.forEach(function (t, j) {
      x = x.concat(j ? t.x.slice(1) : t.x);
      y = y.concat(j ? t.y.slice(1) : t.y);
    });
    return { x: x, y: y };
  }

  /** Month indices covered by a dragged range: dates ("YYYY-MM...") or numbers. */
  function rangeToIndices(periods, range) {
    var numeric = typeof periods[0] === 'number';
    var a = numeric ? +range[0] : String(range[0]).slice(0, 7);
    var b = numeric ? +range[1] : String(range[1]).slice(0, 7);
    var i0 = -1, i1 = -1;
    periods.forEach(function (p, i) {
      if (p >= a && i0 < 0) i0 = i;
      if (p <= b) i1 = i;
    });
    return (i0 >= 0 && i1 >= i0) ? { i0: i0, i1: i1 } : null;
  }

  function hoverIndex(ev, roles) {
    var p = find(ev.points, function (q) { return roles.indexOf((q.data.meta || {}).role) >= 0; });
    return p ? p.pointIndex : null;
  }

  // ---- URL state and controls -----------------------------------------------

  function urlParams() { return new URLSearchParams(location.search); }

  function setParam(name, value) {
    var q = urlParams();
    if (value === null || value === undefined) q.delete(name); else q.set(name, value);
    var s = q.toString();
    history.replaceState(null, '', s ? '?' + s : location.pathname);
  }

  function initSelect(sel, onChange) {
    var v = urlParams().get(sel.name);
    if (v && find(sel.options, function (o) { return o.value === v; })) sel.value = v;
    sel.addEventListener('change', function () {
      setParam(sel.name, sel.value);
      onChange();
    });
  }

  /** Play buttons step their select through its options. */
  function initPlay(btn) {
    var sel = $(btn.closest('.field'), 'select');
    var timer = null;
    function stop() {
      clearInterval(timer); timer = null;
      btn.setAttribute('aria-pressed', 'false');
    }
    btn.addEventListener('click', function () {
      if (timer) return stop();
      btn.setAttribute('aria-pressed', 'true');
      timer = setInterval(function () {
        sel.selectedIndex = (sel.selectedIndex + 1) % sel.options.length;
        sel.dispatchEvent(new Event('change'));
      }, 700);
    });
    sel.addEventListener('pointerdown', stop);
    sel.addEventListener('keydown', stop);
  }

  function controlValues(panel) {
    var values = {};
    $$(document, '.page-controls select[data-control]').concat($$(panel, 'select[data-control]'))
      .forEach(function (sel) { values[sel.name] = sel.value; });
    return values;
  }

  function fillTemplate(src, values) {
    return src.replace(/\{(\w+)\}/g, function (_, k) { return values[k]; });
  }

  // ---- Event highlight shared by the linked views ----------------------------

  function initialEvent() {
    var q = urlParams();
    if (q.has('ev')) return q.get('ev') || null;
    return main.dataset.defaultEvent || null;
  }

  function syncEventButtons(buttons, label) {
    buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(!!label && label === b.dataset.event)); });
  }

  // ---- Player: animation through precomputed arrays ----------------------------

  /* The panel's [data-player] bar drives it; the renderer supplies hooks:
   *   ready()      data loaded?
   *   range()      {a, b}: first and last loop point to play (inclusive)
   *   unit()       loop points per speed unit (a month, a forcing cycle)
   *   label(i)     text for loop point i
   *   enter()      hide the static end state (called again when the range changes)
   *   frame(i, a)  draw loop point i, playing from a
   *   leave()      back to the static view
   * States: idle (static view), playing, paused. The bar's data-state shows it. */
  function Player(panel, hooks) {
    var el = $(panel, '[data-player]');
    if (!el) return null;
    var toggle = $(el, '[data-player-toggle]'), reset = $(el, '[data-player-reset]');
    var scrub = $(el, '[data-player-scrub]'), label = $(el, '[data-player-label]');
    var speed = $(el, '[data-player-speed]'), stamp = $(panel, '[data-player-stamp]');
    var state = 'idle', pos = 0, shown = -1, r = { a: 0, b: 0 }, raf = null, last = null;

    function setState(s) {
      state = s;
      el.dataset.state = s;
      toggle.setAttribute('aria-pressed', String(s === 'playing'));
      toggle.setAttribute('aria-label', s === 'playing' ? 'Pause' : 'Play through time');
      reset.disabled = s === 'idle';
      if (s !== 'playing' && raf !== null) { cancelAnimationFrame(raf); raf = null; }
    }

    function setRange() {
      r = hooks.range();
      scrub.min = r.a; scrub.max = r.b;
    }

    function show(i) {
      shown = Math.max(r.a, Math.min(r.b, Math.floor(i)));
      hooks.frame(shown, r.a);
      scrub.value = shown;
      var t = hooks.label(shown);
      label.textContent = t;
      if (stamp) { stamp.textContent = t; stamp.hidden = false; }
    }

    function tick(now) {
      raf = null;
      if (state !== 'playing') return;
      if (last !== null) {      // capped: a tab in the background must not jump ahead
        pos += Math.min(now - last, 100) / 1000 * (+speed.value) * hooks.unit();
      }
      last = now;
      if (pos >= r.b) { pos = r.b; show(pos); setState('paused'); return; }
      if (Math.floor(pos) !== shown) show(pos);
      raf = requestAnimationFrame(tick);
    }

    function play() {
      if (!hooks.ready()) return;
      if (state === 'idle') { setRange(); hooks.enter(); pos = r.a; }
      else if (pos >= r.b) pos = r.a;
      setState('playing');
      last = null;
      show(pos);
      raf = requestAnimationFrame(tick);
    }

    function stop() {
      if (state === 'idle') return;
      setState('idle');
      hooks.leave();
      label.textContent = '';
      if (stamp) stamp.hidden = true;
    }

    /* After a redraw, a new dataset or a new range: keep going from `at`
     * (a loop point of the new data) or, if it is outside the range, the start.
     * Idle, it only sets the slider's range, so the slider works before Play. */
    function sync(at) {
      if (!hooks.ready()) return;
      if (state === 'idle') { setRange(); scrub.value = r.a; return; }
      setRange();
      if (at !== undefined && at !== null) pos = at;
      if (pos < r.a || pos > r.b) pos = r.a;
      hooks.enter();
      show(pos);
      last = null;
    }

    toggle.addEventListener('click', function () { if (state === 'playing') setState('paused'); else play(); });
    reset.addEventListener('click', stop);
    scrub.addEventListener('input', function () {
      if (!hooks.ready()) return;
      if (state === 'idle') { setRange(); hooks.enter(); setState('paused'); }
      pos = +scrub.value;
      last = null;
      show(pos);
    });
    setState('idle');

    return {
      active: function () { return state !== 'idle'; },
      position: function () { return Math.floor(pos); },
      sync: sync
    };
  }

  /* The play layer of one loop (the traces with meta.play, made in Python):
   * the path from a to i, the tail behind the dot, the tail's monthly points
   * and the dot. `extra` narrows the trace lookup (Compare: the slot). With
   * `into` set, the path goes into those traces instead (a highlight). */
  function playFrame(div, loop, i, a, opts, extra) {
    var split = opts.split === null || opts.split === undefined ? Infinity : opts.split;
    var m = function (o) { return Object.assign({}, o, extra || {}); };
    var idx = [], xs = [], ys = [];
    function put(meta, x, y) {
      var j = traceIndex(div, m(meta));
      if (j >= 0) { idx.push(j); xs.push(x); ys.push(y); }
    }
    var empty = i < a;
    var path = empty ? segments(loop, 0, -1, split) : segments(loop, a, i, split);
    var t0 = Math.max(a, i - opts.tail);
    var tail = empty ? path : segments(loop, t0, i, split);
    var into = opts.into || { role: 'trace', play: true };
    var other = opts.into ? { role: 'trace', play: true } : null;
    put(Object.assign({ provisional: false }, into), path.solid.x, path.solid.y);
    put(Object.assign({ provisional: true }, into), path.prov.x, path.prov.y);
    if (other) {
      put(Object.assign({ provisional: false }, other), [], []);
      put(Object.assign({ provisional: true }, other), [], []);
    }
    put({ role: 'recent', provisional: false, play: true }, tail.solid.x, tail.solid.y);
    put({ role: 'recent', provisional: true, play: true }, tail.prov.x, tail.prov.y);
    var dx = [], dy = [];
    if (!empty && opts.step) {
      for (var q = Math.ceil(t0 / opts.step) * opts.step; q <= i; q += opts.step) { dx.push(loop.x[q]); dy.push(loop.y[q]); }
    }
    put({ role: 'recent', dots: true, play: true }, dx, dy);
    put({ role: 'now', play: true }, empty ? [] : [loop.x[i]], empty ? [] : [loop.y[i]]);
    return { idx: idx, x: xs, y: ys };
  }

  /* Apply one or more playFrame results in one call. Plotly.animate with
   * redraw off redraws only the traces it is given (restyle would redraw
   * every trace of the plot, several times slower on a long record). */
  var STEP = { transition: { duration: 0 }, frame: { duration: 0, redraw: false }, mode: 'immediate' };
  function applyFrames(div, frames) {
    var idx = [], data = [];
    frames.forEach(function (f) {
      f.idx.forEach(function (j, n) { idx.push(j); data.push({ x: f.x[n], y: f.y[n] }); });
    });
    if (idx.length) Plotly.animate(div, { data: data, traces: idx }, STEP);
  }

  /* While playing, the loop is redrawn once without what playing does not
   * show: traces for which hide(meta) is true, annotations for which
   * hideNote(annotation) is true, and the per-year context paths joined into
   * one path per record. Each frame costs in proportion to the number of
   * traces (Plotly re-checks them all), so this keeps playing smooth.
   * Leaving play draws the full figure again. */
  function drawPlaying(div, fig, hide, hideNote) {
    var data = [], joined = {};
    fig.data.forEach(function (t) {
      var m = t.meta || {};
      if (!m.play && hide(m)) return;
      if (m.role === 'history' && !m.provisional && !m.play) {
        var j = joined[m.slot || ''];
        if (j) { j.x = j.x.concat(t.x.slice(1)); j.y = j.y.concat(t.y.slice(1)); return; }
        t = joined[m.slot || ''] = Object.assign({}, t, { x: t.x.slice(), y: t.y.slice() });
      }
      data.push(t);
    });
    var layout = Object.assign({}, fig.layout, {
      annotations: (fig.layout.annotations || []).filter(function (an) { return !hideNote(an); })
    });
    return Plotly.react(div, data, layout, div._ensoConfig);
  }

  // ---- Renderers ---------------------------------------------------------------

  var RENDERERS = {};

  /* phase-linked: the loop (T, dT/dt) and its time series, linked by hover,
   * by dragging a range on the time series, and by event buttons. */
  RENDERERS['phase-linked'] = function (panel) {
    var loop = $(panel, '[data-plot="phase"]');
    var time = $(panel, '[data-plot="time"]');
    var keyItem = $(panel, '.key__highlight');
    var buttons = $$(panel, '[data-event]');
    var data = null, highlight = null, bound = false;
    var pending = initialEvent();

    /* Play: the whole record, or only the highlighted period. Without a
     * highlight the path builds up from nothing; with one, the rest of the
     * record stays as faint context and the highlight itself builds up. */
    var player = Player(panel, {
      ready: function () { return !!data; },
      range: function () {
        var k = data.play.step;
        return highlight ? { a: highlight.i0 * k, b: highlight.i1 * k } : { a: 0, b: data.loop.x.length - 1 };
      },
      unit: function () { return data.play.unit; },
      label: function (i) {
        var m = Math.floor(i / data.play.step);
        return data.period_labels[m] + (m >= data.provisional_from ? ' (provisional)' : '');
      },
      enter: function () {
        drawPlaying(loop, paint(data.figures.phase, themeName()), function (m) {
          return m.role === 'recent' || m.role === 'now' || m.role === 'hover' || (m.role === 'history' && !highlight);
        }, function (an) { return an.name === 'now'; });
      },
      frame: function (i, a) {
        applyFrames(loop, [playFrame(loop, data.loop, i, a, {
          split: data.provisional_from * data.play.step, tail: data.play.tail, step: data.play.step,
          into: highlight ? { role: 'highlight' } : null
        })]);
        cursorOnTime(Math.floor(i / data.play.step));
      },
      leave: function () { render(); }
    });
    function playing() { return player && player.active(); }

    function render() {
      var name = themeName(), stem = 'enso-' + data.dataset.key;
      return Promise.all([
        draw(loop, paint(data.figures.phase, name), stem + '-phase'),
        draw(time, paint(data.figures.time, name), stem + '-time')
      ]).then(function () { bindOnce(); applyHighlight(); });
    }

    function eventHighlight(label) {
      var ev = label && find(data.events, function (e) { return e.label === label; });
      return ev ? { i0: ev.i0, i1: ev.i1, event: ev.label, range: ev.range } : null;
    }

    function setHighlight(h) {
      highlight = h;
      setParam('ev', h && h.event ? h.event : (h ? null : ''));
      applyHighlight();
      if (player) player.sync();
    }

    function applyHighlight() {
      var h = highlight;
      var seg = h ? loopSegments(data.loop, data.ndots, data.provisional_from, h.i0, h.i1)
                  : { solid: { x: [], y: [] }, prov: { x: [], y: [] } };
      setXY(loop, { role: 'highlight', provisional: false }, seg.solid.x, seg.solid.y);
      setXY(loop, { role: 'highlight', provisional: true }, seg.prov.x, seg.prov.y);

      time.data.forEach(function (tr, i) {
        var m = tr.meta || {};
        if (m.role !== 'highlight') return;
        var src = time.data[traceIndex(time, { role: m.of, row: m.row })];
        Plotly.restyle(time, {
          x: [h ? src.x.slice(h.i0, h.i1 + 1) : []],
          y: [h ? src.y.slice(h.i0, h.i1 + 1) : []]
        }, [i]);
      });

      var shapes = (time.layout.shapes || []).filter(function (s) { return s.name !== 'band'; });
      if (h) shapes.push({
        name: 'band', type: 'rect', layer: 'below', xref: 'x', yref: 'paper',
        x0: data.periods[h.i0], x1: data.periods[h.i1], y0: 0, y1: 1,
        fillcolor: THEMES[themeName()].band, line: { width: 0 }
      });
      Plotly.relayout(time, { shapes: shapes });

      syncEventButtons(buttons, h && h.event);
      if (keyItem) {
        keyItem.hidden = !h;
        if (h) fillFields(keyItem, { highlight: {
          range: h.range || (data.period_labels[h.i0] + ' to ' + data.period_labels[h.i1])
        } });
      }
    }

    function cursorOnLoop(m) {
      var hv = loop.data[traceIndex(loop, { role: 'hover' })];
      setXY(loop, { role: 'cursor' }, m === null ? [] : [hv.x[m]], m === null ? [] : [hv.y[m]]);
    }

    function cursorOnTime(m) {
      var f = { idx: [], x: [], y: [] };
      time.data.forEach(function (tr, i) {
        var mt = tr.meta || {};
        if (mt.role !== 'cursor') return;
        var src = time.data[traceIndex(time, { role: mt.of, row: mt.row })];
        f.idx.push(i); f.x.push(m === null ? [] : [src.x[m]]); f.y.push(m === null ? [] : [src.y[m]]);
      });
      applyFrames(time, [f]);
    }

    function bindOnce() {
      if (bound) return;
      bound = true;
      // While playing, the time cursor follows the dot, not the mouse.
      loop.on('plotly_hover', function (ev) { var m = hoverIndex(ev, ['hover']); if (m !== null && !playing()) cursorOnTime(m); });
      loop.on('plotly_unhover', function () { if (!playing()) cursorOnTime(null); });
      time.on('plotly_hover', function (ev) { var m = hoverIndex(ev, ['series', 'anomaly']); if (m !== null && !playing()) cursorOnLoop(m); });
      time.on('plotly_unhover', function () { cursorOnLoop(null); });

      time.on('plotly_selected', function (ev) {
        if (!ev || !ev.range) return;
        var h = rangeToIndices(data.periods, ev.range.x);
        Plotly.relayout(time, { selections: [] });
        Plotly.restyle(time, { selectedpoints: [null] });
        if (h) setHighlight(h);
      });
      time.on('plotly_deselect', function () { setHighlight(null); });

      buttons.forEach(function (b) {
        b.addEventListener('click', function () {
          var same = highlight && highlight.event === b.dataset.event;
          setHighlight(same ? null : eventHighlight(b.dataset.event));
        });
      });
      var clear = $(panel, '[data-action="clear"]');
      if (clear) clear.addEventListener('click', function () { setHighlight(null); });
      themeListeners.push(function () { if (data) render().then(function () { if (player) player.sync(); }); });
    }

    return {
      update: function (json) {
        // Playing on: carry on from the same month in the new dataset.
        var keep = null;
        if (playing()) {
          var k0 = data.play.step, at = player.position();
          keep = { period: data.periods[Math.floor(at / k0)], frac: at % k0 };
        }
        data = json;
        if (pending !== null) {           // first load: event from the URL or the page default
          highlight = eventHighlight(pending);
          pending = null;
        } else if (highlight) {            // keep an event highlight across datasets
          highlight = highlight.event ? eventHighlight(highlight.event) : null;
        }
        buttons.forEach(function (b) {
          b.disabled = !data.events.some(function (e) { return e.label === b.dataset.event; });
        });
        fillFields(panel, data);
        var state = $(panel, '.now__state');
        if (state && data.now) state.dataset.rising = String(data.now.rising);
        return render().then(function () {
          var m = keep ? data.periods.indexOf(keep.period) : -1;
          if (player) player.sync(m >= 0 ? m * data.play.step + keep.frac : null);
        });
      }
    };
  };

  /* trajectory-linked: a model trajectory and its time series, linked by
   * hover, and played through time like the observed loops. */
  RENDERERS['trajectory-linked'] = function (panel) {
    var loop = $(panel, '[data-plot="phase"]');
    var time = $(panel, '[data-plot="time"]');
    var data = null, path = null, names = null, bound = false;

    function timeCursor(m) {
      var f = { idx: [], x: [], y: [] };
      time.data.forEach(function (tr, i) {
        var mt = tr.meta || {};
        if (mt.role !== 'cursor') return;
        var src = time.data[traceIndex(time, { role: 'series', row: mt.row })];
        f.idx.push(i); f.x.push(m === null ? [] : [src.x[m]]); f.y.push(m === null ? [] : [src.y[m]]);
      });
      applyFrames(time, [f]);
    }

    var player = Player(panel, {
      ready: function () { return !!path; },
      range: function () { return { a: 0, b: path.x.length - 1 }; },
      unit: function () { return data.play.unit; },
      label: function (i) { return names[Math.floor(i / data.play.step)]; },
      enter: function () {
        drawPlaying(loop, paint(data.figures.phase, themeName()), function (m) {
          return m.role === 'history' || m.role === 'hover';
        }, function () { return false; });
      },
      frame: function (i, a) {
        applyFrames(loop, [playFrame(loop, path, i, a, { tail: data.play.tail })]);
        timeCursor(Math.floor(i / data.play.step));
      },
      leave: function () { render(); }
    });
    function playing() { return player && player.active(); }

    function render() {
      var name = themeName(), stem = 'duffing-' + data.key;
      return Promise.all([
        draw(loop, paint(data.figures.phase, name), stem + '-trajectory'),
        draw(time, paint(data.figures.time, name), stem + '-time')
      ]).then(bindOnce);
    }

    function bindOnce() {
      if (bound) return;
      bound = true;
      loop.on('plotly_hover', function (ev) {
        var m = hoverIndex(ev, ['hover']);
        if (m !== null && !playing()) timeCursor(m);
      });
      loop.on('plotly_unhover', function () { if (!playing()) timeCursor(null); });
      time.on('plotly_hover', function (ev) {
        var m = hoverIndex(ev, ['series']);
        if (m === null) return;
        var hv = loop.data[traceIndex(loop, { role: 'hover' })];
        setXY(loop, { role: 'cursor' }, [hv.x[m]], [hv.y[m]]);
      });
      time.on('plotly_unhover', function () { setXY(loop, { role: 'cursor' }, [], []); });
      themeListeners.push(function () { if (data) render().then(function () { if (player) player.sync(); }); });
    }

    return {
      update: function (json) {
        // Playing on: carry on from the same point of the new run (or its end).
        var at = playing() ? player.position() : null;
        data = json;
        // The trajectory as one path: Python's per-cycle paths, joined.
        path = joinPaths(data.figures.phase.data.filter(function (t) { return (t.meta || {}).role === 'history'; }));
        names = find(data.figures.phase.data, function (t) { return (t.meta || {}).role === 'hover'; }).customdata;
        fillFields(panel, data);
        return render().then(function () {
          if (player) player.sync(at === null ? null : Math.min(at, path.x.length - 1));
        });
      }
    };
  };

  /* figure: one Python figure, plus text fields. */
  RENDERERS.figure = function (panel) {
    var div = $(panel, '[data-plot]');
    var data = null, bound = false;
    function render() { return draw(div, paint(data.figure, themeName()), data.filename || 'enso'); }
    return {
      update: function (json) {
        data = json;
        fillFields(panel, data);
        if (!bound) { bound = true; themeListeners.push(function () { if (data) render(); }); }
        return render();
      }
    };
  };

  /* Compare: one file per dataset, combined here into the slot overlays.
   * Only placement and colour happen in the browser: every number, trace and
   * label comes from Python. */
  var SLOTS = ['a', 'b', 'c'];

  function slotData(values) {
    return Promise.all([fetchJSON('data/compare/frame.json')].concat(SLOTS.map(function (s) {
      var key = values[s];
      return key && key !== 'none' ? fetchJSON('data/compare/' + key + '.json') : Promise.resolve(null);
    }))).then(function (all) {
      var frame = all[0], slots = [];
      all.slice(1).forEach(function (d, i) { if (d) slots.push({ slot: SLOTS[i].toUpperCase(), data: d }); });
      return { frame: frame, slots: slots };
    });
  }

  function slotTraces(traces, slot) {
    return clone(traces).map(function (t) { t.meta = Object.assign({}, t.meta, { slot: slot }); return t; });
  }

  function fillSlotKey(panel, slots) {
    var t = THEMES[themeName()];
    $$(panel, '[data-slot-key]').forEach(function (li) {
      var s = find(slots, function (x) { return x.slot === li.dataset.slotKey; });
      li.hidden = !s;
      if (!s) return;
      $(li, '.swatch').style.borderTopColor = t.slots[s.slot];
      $(li, '[data-slot-label]').textContent = s.data.label;
    });
  }

  /** Smallest box holding every chosen record's extent (each made in Python). */
  function unionExtent(slots) {
    if (!slots.length) return null;
    var out = {};
    ['x', 'y', 'ta'].forEach(function (k) {
      var ext = slots.map(function (s) { return s.data.extent[k]; }).filter(Boolean);
      if (!ext.length) return;
      out[k] = [Math.min.apply(null, ext.map(function (e) { return e[0]; })),
                Math.max.apply(null, ext.map(function (e) { return e[1]; }))];
    });
    return out;
  }

  RENDERERS['compare-linked'] = function (panel) {
    var loop = $(panel, '[data-plot="phase"]');
    var time = $(panel, '[data-plot="time"]');
    var buttons = $$(panel, '[data-event]');
    var keyItem = $(panel, '.key__highlight');
    var state = null, highlight = null, bound = false;
    var pending = initialEvent();

    /* One player for every chosen record, on the calendar in frame.json: at
     * calendar point i each record shows its own loop point for that month.
     * The model has no calendar: it stays drawn whole and does not move. */
    function onCalendar(slot) {
      var s = find(state.slots, function (x) { return x.slot === slot; });
      return !!(s && s.data.calendar);
    }
    var player = Player(panel, {
      ready: function () { return !!state; },
      range: function () {
        var f = state.frame, k = f.play.step;
        var idx = highlight ? rangeToIndices(f.calendar, [highlight.from, highlight.to]) : null;
        return idx ? { a: idx.i0 * k, b: idx.i1 * k } : { a: 0, b: (f.calendar.length - 1) * k };
      },
      unit: function () { return state.frame.play.unit; },
      label: function (i) { return state.frame.calendar_labels[Math.floor(i / state.frame.play.step)]; },
      enter: function () {
        drawPlaying(loop, paint(figures().loop, themeName()), function (m) {
          return m.role === 'hover' ||
            (onCalendar(m.slot) && (m.role === 'recent' || m.role === 'now' || (m.role === 'history' && !highlight)));
        }, function (an) { return onCalendar(an.name); });
      },
      frame: function (i, a) {
        var f = state.frame, k = f.play.step, frames = [];
        var cur = { idx: [], x: [], y: [] };
        state.slots.forEach(function (s) {
          var d = s.data;
          if (!d.calendar) return;
          var off = f.calendar.indexOf(d.periods[0]) * k;      // this record's first month on the calendar
          var j = Math.min(i - off, d.loop.x.length - 1), from = Math.max(0, a - off);
          frames.push(playFrame(loop, d.loop, j, from, {
            split: d.provisional_from * k, tail: f.play.tail, step: k,
            into: highlight ? { role: 'highlight' } : null
          }, { slot: s.slot }));
          var m = j >= from ? Math.floor(j / k) : -1;
          var src = time.data[traceIndex(time, { role: 'series', slot: s.slot })];
          var c = traceIndex(time, { role: 'cursor', slot: s.slot });
          if (c >= 0) { cur.idx.push(c); cur.x.push(m >= 0 ? [src.x[m]] : []); cur.y.push(m >= 0 ? [src.y[m]] : []); }
        });
        applyFrames(loop, frames);
        applyFrames(time, [cur]);
      },
      leave: function () { render(); }
    });
    function playing() { return player && player.active(); }

    function figures() {
      var loopFig = clone(state.frame.loop), timeFig = clone(state.frame.time);
      loopFig.data = []; timeFig.data = [];
      loopFig.layout.annotations = []; timeFig.layout.shapes = timeFig.layout.shapes || [];
      var provFrom = null;
      state.slots.forEach(function (s) {
        loopFig.data = loopFig.data.concat(slotTraces(s.data.traces.loop, s.slot));
        timeFig.data = timeFig.data.concat(slotTraces(s.data.traces.time, s.slot));
        loopFig.layout.annotations.push(Object.assign({}, s.data.label_annotation, { name: s.slot }));
        if (s.data.provisional_start && (!provFrom || s.data.provisional_start < provFrom)) provFrom = s.data.provisional_start;
      });
      var ext = unionExtent(state.slots);
      if (ext) {
        loopFig.layout.xaxis.range = ext.x; loopFig.layout.yaxis.range = ext.y;
        if (ext.ta) timeFig.layout.yaxis.range = ext.ta;
      }
      if (provFrom) timeFig.layout.shapes.push({
        type: 'rect', name: 'provisional', xref: 'x', yref: 'paper', layer: 'below',
        x0: provFrom, x1: state.frame.time_end, y0: 0, y1: 1, line: { width: 0 }
      });
      return { loop: loopFig, time: timeFig };
    }

    function render() {
      var f = figures(), name = themeName();
      fillSlotKey(panel, state.slots);
      return Promise.all([
        draw(loop, paint(f.loop, name), 'enso-compare-loops'),
        draw(time, paint(f.time, name), 'enso-compare-time')
      ]).then(function () { bindOnce(); applyHighlight(); });
    }

    /* A highlight is a pair of dates; each slot maps it to its own months. */
    function applyHighlight() {
      var h = highlight;
      state.slots.forEach(function (s) {
        var d = s.data, idx = h && d.calendar ? rangeToIndices(d.periods, [h.from, h.to]) : null;
        var seg = idx ? loopSegments(d.loop, d.ndots, d.provisional_from, idx.i0, idx.i1)
                      : { solid: { x: [], y: [] }, prov: { x: [], y: [] } };
        setXY(loop, { role: 'highlight', provisional: false, slot: s.slot }, seg.solid.x, seg.solid.y);
        setXY(loop, { role: 'highlight', provisional: true, slot: s.slot }, seg.prov.x, seg.prov.y);
        if (!d.calendar) return;            // the model is not on the time strip
        var src = time.data[traceIndex(time, { role: 'series', slot: s.slot })];
        setXY(time, { role: 'highlight', slot: s.slot },
              idx ? src.x.slice(idx.i0, idx.i1 + 1) : [], idx ? src.y.slice(idx.i0, idx.i1 + 1) : []);
      });
      var shapes = (time.layout.shapes || []).filter(function (s) { return s.name !== 'band'; });
      if (h) shapes.push({ name: 'band', type: 'rect', layer: 'below', xref: 'x', yref: 'paper',
        x0: h.from, x1: h.to, y0: 0, y1: 1, fillcolor: THEMES[themeName()].band, line: { width: 0 } });
      Plotly.relayout(time, { shapes: shapes });
      syncEventButtons(buttons, h && h.event);
      if (keyItem) {
        keyItem.hidden = !h;
        if (h) fillFields(keyItem, { highlight: { range: h.range } });
      }
    }

    function eventHighlight(label) {
      var ev = label && find(state.frame.events, function (e) { return e.label === label; });
      return ev ? { from: ev.start, to: ev.end, event: ev.label, range: ev.range } : null;
    }

    function setHighlight(h) {
      highlight = h;
      setParam('ev', h && h.event ? h.event : (h ? null : ''));
      applyHighlight();
      if (player) player.sync();
    }

    function cursorAt(period) {
      state.slots.forEach(function (s) {
        var m = period && s.data.calendar ? s.data.periods.indexOf(period) : -1;
        var hv = s.data.month;
        setXY(loop, { role: 'cursor', slot: s.slot }, m >= 0 ? [hv.x[m]] : [], m >= 0 ? [hv.y[m]] : []);
      });
    }

    function bindOnce() {
      if (bound) return;
      bound = true;
      time.on('plotly_hover', function (ev) {
        if (!ev.event) return;   // hover sent from the loop: leave the loop alone
        cursorAt(String(ev.points[0].x).slice(0, 7));
      });
      time.on('plotly_unhover', function () { cursorAt(null); });
      loop.on('plotly_hover', function (ev) {
        var p = find(ev.points, function (q) { return (q.data.meta || {}).role === 'hover'; });
        var s = p && find(state.slots, function (x) { return x.slot === p.data.meta.slot; });
        if (s && s.data.calendar) Plotly.Fx.hover(time, { xval: p.customdata[1] }, ['xy']);
      });
      loop.on('plotly_unhover', function () { Plotly.Fx.unhover(time); });
      time.on('plotly_selected', function (ev) {
        if (!ev || !ev.range) return;
        var a = String(ev.range.x[0]).slice(0, 7), b = String(ev.range.x[1]).slice(0, 7);
        Plotly.relayout(time, { selections: [] });
        Plotly.restyle(time, { selectedpoints: [null] });
        setHighlight({ from: a, to: b, event: null, range: a + ' to ' + b });
      });
      time.on('plotly_deselect', function () { setHighlight(null); });
      buttons.forEach(function (b) {
        b.addEventListener('click', function () {
          var same = highlight && highlight.event === b.dataset.event;
          setHighlight(same ? null : eventHighlight(b.dataset.event));
        });
      });
      var clear = $(panel, '[data-action="clear"]');
      if (clear) clear.addEventListener('click', function () { setHighlight(null); });
      themeListeners.push(function () { if (state) render().then(function () { if (player) player.sync(); }); });
    }

    return {
      load: function (values) {
        var at = playing() ? player.position() : null;     // same calendar: carry on
        return slotData(values).then(function (s) {
          state = s;
          if (pending !== null) { highlight = eventHighlight(pending); pending = null; }
          return render().then(function () { if (player) player.sync(at); });
        });
      }
    };
  };

  RENDERERS['compare-section'] = function (panel) {
    var div = $(panel, '[data-plot="section"]');
    var state = null, month = 0, bound = false;
    function render() {
      var fig = clone(state.frame.section);
      fig.data = [];
      state.slots.forEach(function (s) { fig.data = fig.data.concat(slotTraces(s.data.traces.section[month], s.slot)); });
      var ext = unionExtent(state.slots);    // same box as the loops, steady while playing
      if (ext) { fig.layout.xaxis.range = ext.x; fig.layout.yaxis.range = ext.y; }
      fillSlotKey(panel, state.slots);
      return draw(div, paint(fig, themeName()), 'enso-compare-section');
    }
    return {
      load: function (values) {
        month = +values.month;
        return slotData(values).then(function (s) {
          state = s;
          if (!bound) { bound = true; themeListeners.push(function () { if (state) render(); }); }
          return render();
        });
      }
    };
  };

  // ---- Panels: controls, URL state, loading -------------------------------------

  function initPanel(panel) {
    var make = RENDERERS[panel.dataset.kind];
    if (!make) return Promise.resolve();
    var renderer = make(panel);

    function load() {
      var values = controlValues(panel);
      panel.setAttribute('aria-busy', 'true');
      var job = renderer.load ? renderer.load(values)
        : fetchJSON(fillTemplate(panel.dataset.src, values)).then(renderer.update);
      return Promise.resolve(job).then(function () {
        $(panel, '[data-error]').hidden = true;
      }).catch(function (err) {
        $(panel, '[data-error]').hidden = false;
        console.error(err);
      }).then(function () {
        panel.setAttribute('aria-busy', 'false');
      });
    }
    $$(panel, 'select[data-control]').forEach(function (sel) { initSelect(sel, load); });
    panel._load = load;
    return load();
  }

  function initPage() {
    var panels = $$(document, '.panel[data-kind]');
    $$(document, '.page-controls select[data-control]').forEach(function (sel) {
      initSelect(sel, function () { panels.forEach(function (p) { if (p._load) p._load(); }); });
    });
    $$(document, '[data-play]').forEach(initPlay);
    return Promise.all(panels.map(initPanel));
  }

  initTheme();
  fetchJSON('data/theme.json').then(function (t) {
    THEMES = t;
    onThemeChange();
    return initPage();
  }).then(function () {
    root.dataset.ready = 'true';   // tests and screenshots wait for this
  });
})();
