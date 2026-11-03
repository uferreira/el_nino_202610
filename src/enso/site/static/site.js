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

  /** A highlighted stretch of a loop, split at the first provisional month. */
  function loopSegments(loop, k, p, i0, i1) {
    var solid = { x: [], y: [] }, prov = { x: [], y: [] };
    if (p === null || p === undefined) p = Infinity;
    if (i0 <= Math.min(i1, p)) {
      var b = Math.min(i1, p) * k + 1;
      solid = { x: loop.x.slice(i0 * k, b), y: loop.y.slice(i0 * k, b) };
    }
    if (i1 > p) {
      var a = Math.max(i0, p) * k;
      prov = { x: loop.x.slice(a, i1 * k + 1), y: loop.y.slice(a, i1 * k + 1) };
    }
    return { solid: solid, prov: prov };
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
      time.data.forEach(function (tr, i) {
        var mt = tr.meta || {};
        if (mt.role !== 'cursor') return;
        var src = time.data[traceIndex(time, { role: mt.of, row: mt.row })];
        Plotly.restyle(time, { x: [m === null ? [] : [src.x[m]]], y: [m === null ? [] : [src.y[m]]] }, [i]);
      });
    }

    function bindOnce() {
      if (bound) return;
      bound = true;
      loop.on('plotly_hover', function (ev) { var m = hoverIndex(ev, ['hover']); if (m !== null) cursorOnTime(m); });
      loop.on('plotly_unhover', function () { cursorOnTime(null); });
      time.on('plotly_hover', function (ev) { var m = hoverIndex(ev, ['series', 'anomaly']); if (m !== null) cursorOnLoop(m); });
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
      themeListeners.push(function () { if (data) render(); });
    }

    return {
      update: function (json) {
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
        return render();
      }
    };
  };

  /* trajectory-linked: a model trajectory and its time series, linked by hover. */
  RENDERERS['trajectory-linked'] = function (panel) {
    var loop = $(panel, '[data-plot="phase"]');
    var time = $(panel, '[data-plot="time"]');
    var data = null, bound = false;

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
        if (m === null) return;
        time.data.forEach(function (tr, i) {
          var mt = tr.meta || {};
          if (mt.role !== 'cursor') return;
          var src = time.data[traceIndex(time, { role: 'series', row: mt.row })];
          Plotly.restyle(time, { x: [[src.x[m]]], y: [[src.y[m]]] }, [i]);
        });
      });
      loop.on('plotly_unhover', function () {
        time.data.forEach(function (tr, i) {
          if ((tr.meta || {}).role === 'cursor') Plotly.restyle(time, { x: [[]], y: [[]] }, [i]);
        });
      });
      time.on('plotly_hover', function (ev) {
        var m = hoverIndex(ev, ['series']);
        if (m === null) return;
        var hv = loop.data[traceIndex(loop, { role: 'hover' })];
        setXY(loop, { role: 'cursor' }, [hv.x[m]], [hv.y[m]]);
      });
      time.on('plotly_unhover', function () { setXY(loop, { role: 'cursor' }, [], []); });
      themeListeners.push(function () { if (data) render(); });
    }

    return { update: function (json) { data = json; fillFields(panel, data); return render(); } };
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

    function figures() {
      var loopFig = clone(state.frame.loop), timeFig = clone(state.frame.time);
      loopFig.data = []; timeFig.data = [];
      loopFig.layout.annotations = []; timeFig.layout.shapes = timeFig.layout.shapes || [];
      var provFrom = null;
      state.slots.forEach(function (s) {
        loopFig.data = loopFig.data.concat(slotTraces(s.data.traces.loop, s.slot));
        timeFig.data = timeFig.data.concat(slotTraces(s.data.traces.time, s.slot));
        loopFig.layout.annotations.push(s.data.label_annotation);
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
      themeListeners.push(function () { if (state) render(); });
    }

    return {
      load: function (values) {
        return slotData(values).then(function (s) {
          state = s;
          if (pending !== null) { highlight = eventHighlight(pending); pending = null; }
          return render();
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
