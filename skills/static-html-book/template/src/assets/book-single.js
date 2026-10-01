/* 1ファイル本（single）用。fetch は使わず location.hash で章を切り替えるので file:// でも動く。 */
(function () {
  "use strict";
  var doc = document;
  var observer = null;

  /* コードのコピー */
  function initCopy(root) {
    if (!navigator.clipboard) return;
    root.querySelectorAll(".code-block").forEach(function (block) {
      if (block.querySelector(".copy-btn")) return;
      var btn = doc.createElement("button");
      btn.type = "button";
      btn.className = "copy-btn";
      btn.textContent = "コピー";
      btn.addEventListener("click", function () {
        var code = block.querySelector("pre");
        navigator.clipboard.writeText(code ? code.innerText : "").then(function () {
          btn.textContent = "コピーしました";
          btn.classList.add("is-done");
          setTimeout(function () { btn.textContent = "コピー"; btn.classList.remove("is-done"); }, 1600);
        });
      });
      block.appendChild(btn);
    });
  }

  /* 表示中の章の目次ハイライト */
  function initScrollSpy(section) {
    if (observer) observer.disconnect();
    if (!("IntersectionObserver" in window) || !section) return;
    var card = doc.querySelector('.toc-card[data-chapter-toc="' + section.id + '"]');
    if (!card) return;
    var links = card.querySelectorAll(".toc a");
    if (!links.length) return;
    var map = {};
    links.forEach(function (a) { map[decodeURIComponent(a.hash.slice(1))] = a; });
    var headings = section.querySelectorAll(".chapter-body h2[id], .chapter-body h3[id]");
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.remove("is-active"); });
        var a = map[e.target.id];
        if (a) a.classList.add("is-active");
      });
    }, { rootMargin: "-64px 0px -70% 0px" });
    headings.forEach(function (h) { observer.observe(h); });
  }

  /* 読書進捗バー */
  function initProgress() {
    var bar = doc.querySelector(".topbar");
    if (!bar) return;
    var p = doc.createElement("span");
    p.className = "progress";
    p.setAttribute("aria-hidden", "true");
    bar.appendChild(p);
    function update() {
      var max = doc.documentElement.scrollHeight - window.innerHeight;
      p.style.width = (max > 0 ? Math.min(100, (window.scrollY / max) * 100) : 0) + "%";
    }
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  /* 章・表紙セクションの切り替え */
  function showSection(section) {
    doc.querySelectorAll(".single-chapter.is-current").forEach(function (s) {
      s.classList.remove("is-current");
    });
    var isChapter = section && section.classList.contains("single-chapter");
    if (isChapter) section.classList.add("is-current");
    var isCover = !section || section.classList.contains("single-cover");
    doc.body.classList.toggle("is-cover", isCover);
    if (section && section.dataset.title) doc.title = section.dataset.title;
    var label = doc.getElementById("topbar-chapter");
    if (label) label.textContent = (section && section.dataset.label) || "";
    doc.querySelectorAll(".chapter-list a").forEach(function (a) {
      if (isChapter && a.getAttribute("href") === "#" + section.id) {
        a.setAttribute("aria-current", "page");
      } else {
        a.removeAttribute("aria-current");
      }
    });
    doc.querySelectorAll(".toc-card").forEach(function (c) {
      c.classList.toggle("is-current", isChapter && c.dataset.chapterToc === section.id);
    });
    var toggle = doc.getElementById("nav-toggle");
    if (toggle) toggle.checked = false;
    initScrollSpy(isChapter ? section : null);
  }

  function route(isNav) {
    var id = decodeURIComponent(location.hash.slice(1));
    var el = id ? doc.getElementById(id) : null;
    var section = el ? el.closest(".single-cover, .single-chapter") : null;
    if (el && !section) return; /* #main など章でも表紙でもない要素は表示を変えない */
    if (!section) section = doc.querySelector(".single-cover");
    showSection(section);
    if (el && el !== section) el.scrollIntoView();
    else window.scrollTo(0, 0);
    if (isNav && section.classList.contains("single-chapter")) {
      var main = doc.getElementById("main");
      if (main) main.focus({ preventScroll: true });
    }
  }

  /* ← → キーで章移動（表紙のときは何もしない） */
  function initKeys() {
    doc.addEventListener("keydown", function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      var t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      var rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : null;
      if (!rel) return;
      var cur = doc.querySelector(".single-chapter.is-current");
      if (!cur) return;
      var link = cur.querySelector('.pager a[rel="' + rel + '"]');
      if (link) { e.preventDefault(); link.click(); }
    });
  }

  function init() {
    initCopy(doc);
    initProgress();
    initKeys();
    window.addEventListener("hashchange", function () { route(true); });
    route(false);
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})();
