/* site.js: draws what Python wrote. No science happens here.
 *
 * Every <section class="panel" data-kind data-src> is loaded the same way:
 * its <select data-control> values (also kept in the URL) fill the data path,
 * the JSON is fetched, and RENDERERS[kind] draws it. Colours come from
 * data/theme.json by trace role (trace.meta.role), so light/dark switching
 * needs no rebuild.
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var THEME_KEY = 'enso.theme';
  var THEMES = null;
  var themeListeners = [];

  // ---- Theme -------------------------------------------------------------

  function themeName() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function onThemeChange() {
    var name = themeName();
    var btn = document.querySelector('[data-theme-toggle]');
    if (btn) btn.setAttribute('aria-label', name === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    themeListeners.forEach(function (fn) { fn(name); });
  }

  function initTheme() {
    var btn = document.querySelector('[data-theme-toggle]');
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

  /** Give a figure the theme's template and colour each trace by its role. */
  function paint(fig, name) {
    var t = THEMES[name];
    fig = JSON.parse(JSON.stringify(fig));
    fig.layout.template = t.template;
    fig.data.forEach(function (tr) {
      var r = tr.meta && t.roles[tr.meta.role];
      if (!r) return;
      if (r.line) tr.line = Object.assign({}, tr.line, { color: r.line });
      if (r.marker || r.ring) {
        tr.marker = Object.assign({}, tr.marker);
        if (r.marker) tr.marker.color = r.marker;
        if (r.ring) tr.marker.line = Object.assign({}, tr.marker.line, { color: r.ring });
      }
    });
    (fig.layout.shapes || []).forEach(function (s) {
      if (s.type === 'line') s.line = Object.assign({}, s.line, { color: t.zero });
    });
    return fig;
  }

  var PLOT_CONFIG = {
    responsive: true,
    displaylogo: false,
    modeBarButtons: [['toImage']],
    toImageButtonOptions: { format: 'png', scale: 2 }
  };

  /* Plotly re-measures only on window resize; a plot whose box changes for
   * another reason (a legend row appearing) is resized here. */
  var resizer = new ResizeObserver(function (entries) {
    entries.forEach(function (e) { if (e.target.data) Plotly.Plots.resize(e.target); });
  });

  function draw(div, fig, filename) {
    resizer.observe(div);
    var config = Object.assign({}, PLOT_CONFIG, {
      toImageButtonOptions: Object.assign({}, PLOT_CONFIG.toImageButtonOptions, { filename: filename })
    });
    return Plotly.react(div, fig.data, fig.layout, config);
  }

  /** Index of the trace with this role (and row, for multi-row figures). */
  function traceIndex(div, role, row) {
    for (var i = 0; i < div.data.length; i++) {
      var m = div.data[i].meta || {};
      if (m.role === role && (row === undefined || m.row === row)) return i;
    }
    return -1;
  }

  function getField(obj, path) {
    return path.split('.').reduce(function (o, k) { return o == null ? o : o[k]; }, obj);
  }

  function fillFields(scope, data) {
    scope.querySelectorAll('[data-field]').forEach(function (el) {
      var v = getField(data, el.dataset.field);
      if (v !== undefined && v !== null && typeof v !== 'object') el.textContent = v;
    });
  }

  // ---- Renderers ---------------------------------------------------------

  var RENDERERS = {};

  /* phase-linked: the loop (T, dT/dt) and its two time series, linked by
   * hover, by dragging a range on the time series, and by event buttons. */
  RENDERERS['phase-linked'] = function (panel) {
    var loop = panel.querySelector('[data-plot="phase"]');
    var time = panel.querySelector('[data-plot="time"]');
    var keyItem = panel.querySelector('.key__highlight');
    var buttons = panel.querySelectorAll('[data-event]');
    var data = null;
    var highlight = null;   // {i0, i1, event}
    var bound = false;

    function render() {
      var name = themeName();
      var stem = 'enso-' + data.dataset.key;
      return Promise.all([
        draw(loop, paint(data.figures.phase, name), stem + '-phase'),
        draw(time, paint(data.figures.time, name), stem + '-time')
      ]).then(function () {
        bindOnce();
        applyHighlight();
      });
    }

    function setHighlight(h) {
      highlight = h;
      applyHighlight();
    }

    function applyHighlight() {
      var h = highlight, k = data.ndots;
      var hist = loop.data[traceIndex(loop, 'history')];
      var hx = [], hy = [];
      if (h) {
        hx = hist.x.slice(h.i0 * k, h.i1 * k + 1);
        hy = hist.y.slice(h.i0 * k, h.i1 * k + 1);
      }
      Plotly.restyle(loop, { x: [hx], y: [hy] }, [traceIndex(loop, 'highlight')]);

      ['T', 'V'].forEach(function (row) {
        var s = time.data[traceIndex(time, 'series', row)];
        var x = h ? s.x.slice(h.i0, h.i1 + 1) : [];
        var y = h ? s.y.slice(h.i0, h.i1 + 1) : [];
        Plotly.restyle(time, { x: [x], y: [y] }, [traceIndex(time, 'highlight', row)]);
      });

      var shapes = (time.layout.shapes || []).filter(function (s) { return s.name !== 'band'; });
      if (h) shapes.push({
        name: 'band', type: 'rect', layer: 'below', xref: 'x', yref: 'paper',
        x0: data.periods[h.i0], x1: data.periods[h.i1], y0: 0, y1: 1,
        fillcolor: THEMES[themeName()].band, line: { width: 0 }
      });
      Plotly.relayout(time, { shapes: shapes });

      buttons.forEach(function (b) {
        b.setAttribute('aria-pressed', String(!!h && h.event === b.dataset.event));
      });
      keyItem.hidden = !h;
      if (h) fillFields(keyItem, { highlight: {
        range: data.period_labels[h.i0] + ' to ' + data.period_labels[h.i1]
      } });
    }

    /** Month indices covered by a dragged range of dates. */
    function rangeToMonths(range) {
      var a = String(range[0]).slice(0, 7), b = String(range[1]).slice(0, 7);
      var i0 = -1, i1 = -1;
      data.periods.forEach(function (p, i) {
        if (p >= a && i0 < 0) i0 = i;
        if (p <= b) i1 = i;
      });
      return (i0 >= 0 && i1 >= i0) ? { i0: i0, i1: i1, event: null } : null;
    }

    function cursorOnLoop(m) {
      var hv = loop.data[traceIndex(loop, 'hover')];
      var x = m === null ? [] : [hv.x[m]], y = m === null ? [] : [hv.y[m]];
      Plotly.restyle(loop, { x: [x], y: [y] }, [traceIndex(loop, 'cursor')]);
    }

    function cursorOnTime(m) {
      ['T', 'V'].forEach(function (row) {
        var s = time.data[traceIndex(time, 'series', row)];
        var x = m === null ? [] : [s.x[m]], y = m === null ? [] : [s.y[m]];
        Plotly.restyle(time, { x: [x], y: [y] }, [traceIndex(time, 'cursor', row)]);
      });
    }

    function bindOnce() {
      if (bound) return;
      bound = true;

      // Hover one view, mark the same month in the other.
      loop.on('plotly_hover', function (ev) {
        var p = ev.points.filter(function (q) { return (q.data.meta || {}).role === 'hover'; })[0];
        if (p) cursorOnTime(p.pointIndex);
      });
      loop.on('plotly_unhover', function () { cursorOnTime(null); });
      time.on('plotly_hover', function (ev) {
        var p = ev.points.filter(function (q) { return (q.data.meta || {}).role === 'series'; })[0];
        if (p) cursorOnLoop(p.pointIndex);
      });
      time.on('plotly_unhover', function () { cursorOnLoop(null); });

      // Drag a range on the time series: highlight it on the loop.
      time.on('plotly_selected', function (ev) {
        if (!ev || !ev.range) return;
        var h = rangeToMonths(ev.range.x);
        Plotly.relayout(time, { selections: [] });
        Plotly.restyle(time, { selectedpoints: [null] });
        if (h) setHighlight(h);
      });
      time.on('plotly_deselect', function () { setHighlight(null); });

      buttons.forEach(function (b) {
        b.addEventListener('click', function () {
          var ev = data.events.filter(function (e) { return e.label === b.dataset.event; })[0];
          if (!ev) return;
          var same = highlight && highlight.event === ev.label;
          setHighlight(same ? null : { i0: ev.i0, i1: ev.i1, event: ev.label });
        });
      });
      panel.querySelector('[data-action="clear"]').addEventListener('click', function () {
        setHighlight(null);
      });
      themeListeners.push(function () { if (data) render(); });
    }

    return {
      update: function (json) {
        data = json;
        // Keep an event highlight across datasets when the event exists there.
        if (highlight) {
          var ev = highlight.event && data.events.filter(function (e) { return e.label === highlight.event; })[0];
          highlight = ev ? { i0: ev.i0, i1: ev.i1, event: ev.label } : null;
        }
        buttons.forEach(function (b) {
          b.disabled = !data.events.some(function (e) { return e.label === b.dataset.event; });
        });
        fillFields(panel, data);
        var state = panel.querySelector('.now__state');
        if (state) state.dataset.rising = String(data.now.rising);
        return render();
      }
    };
  };

  // ---- Panels: controls, URL state, loading -------------------------------

  function initPanel(panel) {
    var make = RENDERERS[panel.dataset.kind];
    if (!make) return;
    var renderer = make(panel);
    var controls = panel.querySelectorAll('select[data-control]');
    var params = new URLSearchParams(location.search);
    var cache = {};

    controls.forEach(function (sel) {
      var v = params.get(sel.name);
      if (v && sel.querySelector('option[value="' + CSS.escape(v) + '"]')) sel.value = v;
      sel.addEventListener('change', function () {
        var q = new URLSearchParams(location.search);
        q.set(sel.name, sel.value);
        history.replaceState(null, '', '?' + q.toString());
        load();
      });
    });

    function load() {
      var src = panel.dataset.src;
      controls.forEach(function (sel) { src = src.replace('{' + sel.name + '}', sel.value); });
      panel.setAttribute('aria-busy', 'true');
      var req = cache[src] || (cache[src] = fetch(src).then(function (r) {
        if (!r.ok) throw new Error(r.status + ' ' + src);
        return r.json();
      }));
      return req.then(function (json) {
        return renderer.update(json);
      }).then(function () {
        panel.querySelector('[data-error]').hidden = true;
      }).catch(function (err) {
        delete cache[src];
        panel.querySelector('[data-error]').hidden = false;
        console.error(err);
      }).then(function () {
        panel.setAttribute('aria-busy', 'false');
      });
    }
    return load();
  }

  initTheme();
  fetch('data/theme.json').then(function (r) { return r.json(); }).then(function (t) {
    THEMES = t;
    onThemeChange();
    return Promise.all(Array.prototype.map.call(document.querySelectorAll('.panel[data-kind]'), initPanel));
  }).then(function () {
    root.dataset.ready = 'true';   // tests and screenshots wait for this
  });
})();
