// lock family — the tab sets (quick start, hub) and the Copy buttons. No dependencies.
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

  // Copy buttons on the install boxes: copy the commands only (no prompt,
  // no comment). Without JS the <pre> stays plain, selectable text.
  function commands(pre) {
    var code = pre.cloneNode(true);
    Array.prototype.forEach.call(code.querySelectorAll(".c, .prompt"), function (n) { n.remove(); });
    return code.textContent.split("\n").map(function (l) { return l.replace(/\s+$/, ""); })
      .filter(function (l) { return l !== ""; }).join("\n") + "\n";
  }
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-copy]"), function (box) {
    var pre = box.querySelector("pre");
    var bar = box.querySelector(".install-bar");
    if (!pre || !bar) return;
    var actions = document.createElement("span");
    actions.className = "install-actions";
    var status = document.createElement("span");
    status.className = "copy-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy the install commands");
    var timer;
    function done(ok) {
      status.textContent = ok ? "Copied" : "Select and copy";
      clearTimeout(timer);
      timer = setTimeout(function () { status.textContent = ""; }, 2500);
    }
    btn.addEventListener("click", function () {
      var text = commands(pre);
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); });
      } else {
        done(fallbackCopy(text));
      }
    });
    actions.appendChild(status);
    actions.appendChild(btn);
    bar.appendChild(actions);
  });
})();
