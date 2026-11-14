/* lockfamily.dev/docs (#34): theme, sidebar drawer, copy buttons, the
   table of contents' current section, and search. No dependency, no
   third-party request; every page works without it. */
(function () {
  'use strict';
  var root = document.documentElement;

  /* ---------------------------------------------------- theme */
  var themes = ['system', 'light', 'dark'];
  var themeButton = document.querySelector('.theme-button');
  function currentTheme() { return root.dataset.theme || 'system'; }
  function showTheme() {
    if (!themeButton) return;
    var t = currentTheme();
    themeButton.textContent = t;
    themeButton.setAttribute('aria-label', 'Colour theme: ' + t + '. Change it');
  }
  if (themeButton) {
    showTheme();
    themeButton.addEventListener('click', function () {
      var next = themes[(themes.indexOf(currentTheme()) + 1) % themes.length];
      if (next === 'system') delete root.dataset.theme; else root.dataset.theme = next;
      try {
        if (next === 'system') localStorage.removeItem('lf-theme'); else localStorage.setItem('lf-theme', next);
      } catch (e) { /* private mode: the choice lasts for this page */ }
      showTheme();
    });
  }

  /* ---------------------------------------------------- sidebar drawer */
  var menu = document.querySelector('.menu-button');
  var sidebar = document.getElementById('sidebar');
  function closeMenu() {
    if (!sidebar.classList.contains('open')) return;
    sidebar.classList.remove('open');
    menu.setAttribute('aria-expanded', 'false');
    menu.focus();
  }
  if (menu && sidebar) {
    menu.addEventListener('click', function () {
      var open = !sidebar.classList.contains('open');
      sidebar.classList.toggle('open', open);
      menu.setAttribute('aria-expanded', String(open));
      if (open) {
        var cur = sidebar.querySelector('[aria-current="page"]') || sidebar.querySelector('a');
        if (cur) cur.focus();
      }
    });
    document.addEventListener('click', function (e) {
      if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !menu.contains(e.target)) closeMenu();
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
  }
  var current = sidebar && sidebar.querySelector('[aria-current="page"]');
  if (current && current.scrollIntoView && window.matchMedia('(min-width: 900px)').matches) {
    current.scrollIntoView({ block: 'nearest' });
  }

  /* ---------------------------------------------------- copy buttons */
  var status = document.createElement('p');
  status.className = 'visually-hidden';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  document.body.appendChild(status);

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      // A clipboard that never answers (a permission prompt left open)
      // falls back to selecting the text.
      return Promise.race([navigator.clipboard.writeText(text), new Promise(function (_, reject) {
        setTimeout(function () { reject(new Error('clipboard timeout')); }, 1000);
      })]);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      if (ok) resolve(); else reject(new Error('copy failed'));
    });
  }
  document.querySelectorAll('.doc pre').forEach(function (pre) {
    var wrap = document.createElement('div');
    wrap.className = 'code';
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    pre.setAttribute('tabindex', '0');
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'copy'; b.textContent = 'Copy';
    b.setAttribute('aria-label', 'Copy this code');
    b.addEventListener('click', function () {
      var text = pre.innerText.replace(/\n$/, '');
      copyText(text).then(function () {
        b.textContent = 'Copied'; status.textContent = 'Copied to the clipboard';
      }, function () {
        var r = document.createRange(); r.selectNodeContents(pre);
        var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
        b.textContent = 'Ctrl+C'; status.textContent = 'Selected: press Ctrl+C to copy';
      });
      setTimeout(function () { b.textContent = 'Copy'; }, 2000);
    });
    wrap.appendChild(b);
  });

  /* ---------------------------------------------------- on this page */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var heads = tocLinks.map(function (a) { return document.getElementById(decodeURIComponent(a.hash.slice(1))); });
    var visible = new Set();
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) visible.add(e.target); else visible.delete(e.target); });
      var active = null;
      for (var i = 0; i < heads.length; i++) { if (visible.has(heads[i])) { active = i; break; } }
      if (active === null) return;
      tocLinks.forEach(function (a, j) { a.classList.toggle('active', j === active); });
    }, { rootMargin: '-110px 0px -60% 0px' });
    heads.forEach(function (h) { if (h) io.observe(h); });
  }

  /* ---------------------------------------------------- search */
  var dialog = document.querySelector('dialog.search');
  var openButton = document.querySelector('.search-button');
  if (!dialog || !openButton || typeof dialog.showModal !== 'function') {
    if (openButton) openButton.hidden = true;
    return;
  }
  var input = dialog.querySelector('input');
  var list = dialog.querySelector('.search-results');
  var said = dialog.querySelector('.search-status');
  var index = null, loading = null, selected = -1;

  function load() {
    if (!loading) {
      loading = fetch('/docs/_assets/search.json').then(function (r) { return r.json(); }).then(function (data) {
        index = data.map(function (e) {
          return { e: e, t: e.t.toLowerCase(), h: e.h.toLowerCase(), x: e.x.toLowerCase() };
        });
      });
    }
    return loading;
  }
  function words(q) { return q.toLowerCase().split(/\s+/).filter(Boolean); }
  function score(it, ws, phrase) {
    var s = 0;
    for (var i = 0; i < ws.length; i++) {
      var w = ws[i], hit = 0;
      if (it.t.indexOf(w) >= 0) hit += it.h ? 4 : 10;
      if (it.h.indexOf(w) >= 0) hit += 8;
      if (it.x.indexOf(w) >= 0) hit += 1 + Math.min(3, it.x.split(w).length - 2);
      if (!hit) return 0;
      s += hit;
    }
    if (ws.length > 1) {
      if (it.t.indexOf(phrase) >= 0) s += it.h ? 8 : 20;
      if (it.h.indexOf(phrase) >= 0) s += 12;
      if (it.x.indexOf(phrase) >= 0) s += 3;
    }
    if (it.t === phrase || it.h === phrase) s += 20;
    if (!it.h && it.t.indexOf(ws[0]) === 0) s += 6;
    return s;
  }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function excerpt(text, ws) {
    var low = text.toLowerCase(), at = -1;
    for (var i = 0; i < ws.length && at < 0; i++) at = low.indexOf(ws[i]);
    var start = Math.max(0, at - 40), out = (start ? '…' : '') + text.slice(start, start + 160);
    var re = new RegExp('(' + ws.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')', 'i');
    // split() with a capturing group: odd pieces are the matches.
    return out.split(re).map(function (p, i) { return i % 2 ? '<mark>' + esc(p) + '</mark>' : esc(p); }).join('');
  }
  function select(i) {
    var items = list.querySelectorAll('a');
    if (!items.length) return;
    selected = (i + items.length) % items.length;
    items.forEach(function (a, j) { a.setAttribute('aria-selected', String(j === selected)); });
    items[selected].scrollIntoView({ block: 'nearest' });
  }
  function run() {
    var q = input.value.trim(), ws = words(q);
    list.innerHTML = ''; selected = -1;
    if (!ws.length) { said.textContent = ''; return; }
    if (!index) { said.textContent = 'Loading the index…'; load().then(run); return; }
    var hits = [];
    var phrase = ws.join(' ');
    for (var i = 0; i < index.length; i++) {
      var s = score(index[i], ws, phrase);
      if (s) hits.push([s, index[i].e]);
    }
    hits.sort(function (a, b) { return b[0] - a[0]; });
    // At most two sections of one page.
    var per = {};
    hits = hits.filter(function (h) {
      var p = h[1].u.split('#')[0];
      per[p] = (per[p] || 0) + 1;
      return per[p] <= 2;
    }).slice(0, 12);
    said.textContent = hits.length ? hits.length + (hits.length === 12 ? '+' : '') + ' results' : 'No result for "' + q + '"';
    hits.forEach(function (h) {
      var e = h[1], li = document.createElement('li');
      li.innerHTML = '<a href="' + esc(e.u) + '"><span class="where">' + esc(e.b) + ' · ' + esc(e.t) + '</span>' +
        '<span class="what">' + esc(e.h || e.t) + '</span><span class="excerpt">' + excerpt(e.x, ws) + '</span></a>';
      list.appendChild(li);
    });
  }
  function open() {
    load();
    dialog.showModal();
    input.select();
  }
  openButton.addEventListener('click', open);
  input.addEventListener('input', run);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); select(selected + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); select(selected - 1); }
    else if (e.key === 'Enter') {
      var items = list.querySelectorAll('a');
      var a = items[selected >= 0 ? selected : 0];
      if (a) { e.preventDefault(); location.href = a.href; dialog.close(); }
    }
  });
  list.addEventListener('click', function (e) { if (e.target.closest('a')) dialog.close(); });
  dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
  document.addEventListener('keydown', function (e) {
    var tag = (e.target.tagName || '').toLowerCase();
    var typing = tag === 'input' || tag === 'textarea' || e.target.isContentEditable;
    if (dialog.open) return;
    if ((e.key === '/' && !typing) || (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey))) {
      e.preventDefault();
      open();
    }
  });
})();
