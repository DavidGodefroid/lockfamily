// lock family — the tab sets (quick start, hub). No dependencies.
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  // Tab sets: the quick start, the hub (without JS, every panel shows).
  Array.prototype.forEach.call(document.querySelectorAll("[data-tabs]"), function (qs) {
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
  });
})();
