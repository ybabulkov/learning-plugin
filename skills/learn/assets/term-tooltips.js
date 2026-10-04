/* Term tooltips for learning explainer pages.
   Inline this whole file in an explainer page, after the
   <script type="application/json" id="learn-terms"> block that `terms.py plan` produced.
   Containers marked data-learn="code" get every tracked term; data-learn="prose" gets only
   terms whose "prose" flag is true (so keywords that are also English words stay plain).
   Only terms in the plan get tooltips; excluded and retired terms are never in it.
   Text inside .cm (comments), .str (strings) or [data-learn-skip] is never marked.
   Containers are re-scanned when their content changes, so pages that swap code
   panels per step need no extra calls. window.LearnTerms.scan(el) is there if needed. */
(function () {
  "use strict";
  var dataEl = document.getElementById("learn-terms");
  if (!dataEl) return;
  var data;
  try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var terms = data.terms || {};
  var max = data.max_showings || 3;
  var SKIP_CLASSES = ["cm", "str", "learn-t"];

  var rules = [];
  Object.keys(terms).forEach(function (id) {
    (terms[id].match || []).forEach(function (src) {
      try { rules.push({ id: id, prose: !!terms[id].prose, re: new RegExp(src, "g") }); } catch (e) {}
    });
  });

  var style = document.createElement("style");
  style.textContent =
    ".learn-t{text-decoration:underline dotted;text-decoration-thickness:1.5px;text-underline-offset:3px;" +
    "text-decoration-color:color-mix(in srgb,currentColor 60%,transparent);cursor:help;border-radius:3px}" +
    ".learn-t:hover,.learn-t:focus-visible,.learn-t.learn-on{background:rgba(255,210,122,.24);outline:none}" +
    ".learn-tip{position:fixed;z-index:2147483000;max-width:min(340px,calc(100vw - 16px));background:#111827;" +
    "color:#F3F4F6;border:1px solid #374151;border-radius:10px;padding:10px 12px;" +
    "font:13px/1.5 var(--f-body,system-ui,sans-serif);box-shadow:0 10px 30px rgba(0,0,0,.35);pointer-events:none;text-align:left}" +
    ".learn-tip .learn-h{display:flex;gap:10px;align-items:baseline;justify-content:space-between;margin-bottom:4px}" +
    ".learn-tip .learn-n{font:600 13.5px var(--f-mono,ui-monospace,monospace);color:#fff}" +
    ".learn-tip .learn-k{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:#FCD34D;white-space:nowrap}" +
    ".learn-tip .learn-d{margin:0}" +
    ".learn-tip .learn-f{margin-top:6px;font-size:11.5px;color:#9CA3AF}" +
    "@media (prefers-reduced-motion:no-preference){.learn-tip{transition:opacity .12s}}";
  document.head.appendChild(style);

  var tip = document.createElement("div");
  tip.className = "learn-tip";
  tip.id = "learn-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);

  function ordinal(n) { return n === 1 ? "1st" : n === 2 ? "2nd" : n === 3 ? "3rd" : n + "th"; }

  function skipped(node, root) {
    for (var el = node.parentElement; el; el = el.parentElement) {
      if (el.matches("script,style,textarea,[data-learn-skip]")) return true;
      for (var i = 0; i < SKIP_CLASSES.length; i++) if (el.classList.contains(SKIP_CLASSES[i])) return true;
      if (el === root) return false;
    }
    return false;
  }

  function firstMatch(text, proseOnly) {
    var best = null;
    for (var i = 0; i < rules.length; i++) {
      var r = rules[i];
      if (proseOnly && !r.prose) continue;
      r.re.lastIndex = 0;
      var m = r.re.exec(text);
      if (!m || !m[0]) continue;
      // Earliest match wins; at the same spot the longer one does ("data class" over "class").
      if (!best || m.index < best.index || (m.index === best.index && m[0].length > best.len)) {
        best = { index: m.index, len: m[0].length, id: r.id };
      }
    }
    return best;
  }

  function scan(root) {
    var proseOnly = root.getAttribute("data-learn") === "prose";
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (node) {
      if (!node.nodeValue.trim() || skipped(node, root)) return;
      var m;
      while (node && (m = firstMatch(node.nodeValue, proseOnly))) {
        var hit = node.splitText(m.index);
        var rest = hit.splitText(m.len);
        var span = document.createElement("span");
        span.className = "learn-t";
        span.setAttribute("data-t", m.id);
        span.tabIndex = 0;
        span.setAttribute("aria-describedby", "learn-tip");
        hit.parentNode.replaceChild(span, hit);
        span.appendChild(hit);
        node = rest;
      }
    });
  }

  var current = null, pinned = false;
  function show(span) {
    var t = terms[span.getAttribute("data-t")];
    if (!t) return;
    if (current && current !== span) current.classList.remove("learn-on");
    current = span;
    span.classList.add("learn-on");
    tip.textContent = "";
    var head = document.createElement("div"); head.className = "learn-h";
    var name = document.createElement("span"); name.className = "learn-n"; name.textContent = t.term;
    var kind = document.createElement("span"); kind.className = "learn-k"; kind.textContent = t.kind;
    head.appendChild(name); head.appendChild(kind);
    var def = document.createElement("p"); def.className = "learn-d"; def.textContent = t.short;
    var foot = document.createElement("div"); foot.className = "learn-f";
    foot.textContent = t.nth >= max
      ? "Last time this gets a tooltip. From now on it shows up in your quizzes."
      : "Explained for the " + ordinal(t.nth) + " of " + max + " times.";
    tip.appendChild(head); tip.appendChild(def); tip.appendChild(foot);
    tip.hidden = false;
    var r = span.getBoundingClientRect();
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.min(Math.max(8, r.left), window.innerWidth - w - 8);
    var top = r.bottom + 8;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 8);
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }
  function hide() {
    tip.hidden = true;
    pinned = false;
    if (current) current.classList.remove("learn-on");
    current = null;
  }

  document.addEventListener("mouseover", function (e) {
    var s = e.target.closest && e.target.closest(".learn-t");
    if (s && !pinned) show(s);
  });
  document.addEventListener("mouseout", function (e) {
    var s = e.target.closest && e.target.closest(".learn-t");
    if (s && !pinned && !(e.relatedTarget && s.contains(e.relatedTarget))) hide();
  });
  document.addEventListener("focusin", function (e) {
    var s = e.target.closest && e.target.closest(".learn-t");
    if (s) show(s);
  });
  document.addEventListener("focusout", function (e) {
    if (e.target.closest && e.target.closest(".learn-t")) hide();
  });
  document.addEventListener("click", function (e) {
    var s = e.target.closest && e.target.closest(".learn-t");
    if (s) {
      if (pinned && current === s) { hide(); return; }
      show(s); pinned = true;
    } else if (pinned) hide();
  }, true);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", function () { if (!pinned) hide(); }, true);

  var containers = Array.prototype.slice.call(document.querySelectorAll("[data-learn]"));
  var observer = new MutationObserver(function (records) {
    var roots = [];
    records.forEach(function (rec) {
      containers.forEach(function (c) { if (c.contains(rec.target) && roots.indexOf(c) < 0) roots.push(c); });
    });
    if (!roots.length) return;
    observer.disconnect();
    roots.forEach(scan);
    observeAll();
  });
  function observeAll() {
    containers.forEach(function (c) { observer.observe(c, { childList: true, subtree: true, characterData: true }); });
  }
  containers.forEach(scan);
  observeAll();
  window.LearnTerms = { scan: scan, terms: terms };
})();
