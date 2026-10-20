// lock family — the flow demo and the quick-start tabs. No dependencies.
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Examples taken from each project's README and approval screens.
  var EXAMPLES = {
    sql: {
      ask: "locksql run PLAN_ID\nSELECT id, email FROM customers\nWHERE country = 'BE' LIMIT 20",
      approve: "class READ · est. 410 rows examined\nPII columns touched: customers.email\n╰─ Approve? [y/N] ",
      yes: "y",
      answer: "id | email\n 1 | <redacted:r1.1.2>\n 2 | <redacted:r1.2.2>",
      source: "Database",
      sourceSub: "MariaDB · MySQL · PostgreSQL · SQLite",
      icon: "🗄️"
    },
    mq: {
      ask: "READ stream order-events\nfrom timestamp 2026-10-19T10:40:00Z max 20",
      approve: "no offset stored · no message removed\nPII: masked (body redact-unknown)\n╰─ Type the profile name \"prod\" to approve: ",
      yes: "prod",
      answer: "{\"order_id\": 4127,\n \"email\": \"<redacted:r1.1>\",\n \"status\": \"failed\"}",
      source: "RabbitMQ",
      sourceSub: "management API · streams · AMQP 0-9-1",
      icon: "📨"
    },
    file: {
      ask: "lockfile plan --key invoices/2026/10/abc123.pdf\n  --plugin format.is-pdf --run",
      approve: "format.is-pdf: 1 = a PDF, 0 = not a PDF\nanswers revealed: 1\n╰─ Approve? [y/N] ",
      yes: "y",
      answer: "{\"plugin\": \"format.is-pdf\",\n \"result\": 1}",
      source: "File",
      sourceSub: "S3 · SFTP · local directory, sandboxed plugin",
      icon: "📄"
    }
  };
  var ORDER = ["sql", "mq", "file"];

  var flow = document.querySelector("[data-flow]");
  if (flow) {
    var stage = flow.querySelector(".flow-stage");
    var tabs = Array.prototype.slice.call(flow.querySelectorAll("[data-product]"));
    var pauseBtn = flow.querySelector("[data-pause]");
    var field = function (n) { return flow.querySelector("[data-field=" + n + "]"); };
    var w1 = flow.querySelector(".w1");
    var w2 = flow.querySelector(".w2");
    var current = "sql";
    var timers = [];
    var paused = false;
    var visible = true;

    function clearTimers() { timers.forEach(clearTimeout); timers = []; }
    function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
    function fire(wire, dir) {
      wire.classList.remove("out", "back");
      void wire.offsetWidth; // restart the animation
      wire.classList.add(dir);
    }

    function show(name) {
      var ex = EXAMPLES[name];
      current = name;
      stage.setAttribute("data-product", name);
      tabs.forEach(function (t) { t.setAttribute("aria-pressed", String(t.getAttribute("data-product") === name)); });
      field("ask").innerHTML = esc(ex.ask);
      field("approve").innerHTML = esc(ex.approve) + "<b>" + esc(ex.yes) + "</b>";
      field("answer").innerHTML = esc(ex.answer);
      field("source").textContent = ex.source;
      field("source-sub").textContent = ex.sourceSub;
      var icon = flow.querySelector(".node-source .node-icon");
      if (icon) icon.textContent = ex.icon;
    }

    function animated() { return !reduce.matches && !paused && visible; }

    // One cycle: ask → approve → answer, then the next product.
    function play(name) {
      clearTimers();
      show(name);
      if (!animated()) { stage.setAttribute("data-step", "3"); return; }
      stage.setAttribute("data-step", "0");
      later(function () { stage.setAttribute("data-step", "1"); }, 300);
      later(function () { fire(w1, "out"); }, 900);
      later(function () { stage.setAttribute("data-step", "2"); }, 1500);
      later(function () { fire(w2, "out"); }, 2700);
      later(function () { fire(w2, "back"); }, 3300);
      later(function () { fire(w1, "back"); }, 3900);
      later(function () { stage.setAttribute("data-step", "3"); }, 4400);
      later(function () { play(ORDER[(ORDER.indexOf(name) + 1) % ORDER.length]); }, 8000);
    }

    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        paused = true;
        pauseBtn.textContent = "Play";
        play(t.getAttribute("data-product"));
      });
    });

    pauseBtn.addEventListener("click", function () {
      paused = !paused;
      pauseBtn.textContent = paused ? "Play" : "Pause";
      play(current);
    });

    function syncMotion() {
      pauseBtn.hidden = reduce.matches;
      play(current);
    }
    if (reduce.addEventListener) reduce.addEventListener("change", syncMotion);

    // Run only while on screen.
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        var v = entries[0].isIntersecting;
        if (v === visible) return;
        visible = v;
        play(current);
      }).observe(stage);
    }
    syncMotion();
  }

  // Quick-start tabs (without JS, every panel shows).
  var qs = document.querySelector("[data-tabs]");
  if (qs) {
    var qtabs = Array.prototype.slice.call(qs.querySelectorAll("[role=tab]"));
    var panels = qtabs.map(function (t) { return document.getElementById(t.getAttribute("aria-controls")); });
    function select(i, focus) {
      qtabs.forEach(function (t, j) {
        var on = i === j;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        panels[j].hidden = !on;
        panels[j].classList.toggle("enter", on);
      });
      if (focus) qtabs[i].focus();
    }
    qtabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(i, false); });
      t.addEventListener("keydown", function (e) {
        var n = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: qtabs.length - 1 }[e.key];
        if (n === undefined) return;
        e.preventDefault();
        select((n + qtabs.length) % qtabs.length, true);
      });
    });
    select(0, false);
  }
})();
