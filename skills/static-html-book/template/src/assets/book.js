/* 段階的拡張: JS が無くても全ページは通常リンクで読める。ここでは体験の上乗せだけを行う。 */
(function () {
  "use strict";
  var doc = document;
  var cache = {};
  var navSeq = 0;
  var shownPath = location.pathname;
  var observer = null;

  function isChapterUrl(url) {
    return /\/chapters\/[^\/]+\.html$/.test(url.pathname);
  }

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

  /* 目次のハイライト */
  function initScrollSpy() {
    if (observer) observer.disconnect();
    if (!("IntersectionObserver" in window)) return;
    var links = doc.querySelectorAll("#page-toc .toc a");
    if (!links.length) return;
    var map = {};
    links.forEach(function (a) { map[decodeURIComponent(a.hash.slice(1))] = a; });
    var headings = doc.querySelectorAll(".chapter-body h2[id], .chapter-body h3[id]");
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

  /* サイドバーの現在位置 */
  function markCurrent(url) {
    doc.querySelectorAll(".chapter-list a").forEach(function (a) {
      if (a.href.split("#")[0] === url.split("#")[0]) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }

  function fetchPage(url) {
    if (!cache[url]) {
      cache[url] = fetch(url, { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      });
      cache[url].catch(function () { delete cache[url]; });
    }
    return cache[url];
  }

  /* fetch + history API による章移動（http(s) 配信時のみ） */
  function navigate(href, push) {
    var url = new URL(href, location.href);
    var seq = ++navSeq;
    var main = doc.getElementById("main");
    main.classList.add("is-loading");
    return fetchPage(url.href.split("#")[0]).then(function (html) {
      if (seq !== navSeq) return;
      var next = new DOMParser().parseFromString(html, "text/html");
      var newMain = next.getElementById("main");
      var newToc = next.getElementById("page-toc");
      if (!newMain || !newToc) throw new Error("layout");
      main.replaceWith(newMain);
      doc.getElementById("page-toc").replaceWith(newToc);
      doc.title = next.title;
      shownPath = url.pathname;
      doc.body.setAttribute("data-chapter", next.body.getAttribute("data-chapter") || "");
      var label = next.getElementById("topbar-chapter");
      var cur = doc.getElementById("topbar-chapter");
      if (label && cur) cur.textContent = label.textContent;
      if (push) history.pushState({ pjax: true }, "", url.href);
      markCurrent(url.href);
      var toggle = doc.getElementById("nav-toggle");
      if (toggle) toggle.checked = false;
      var target = url.hash ? doc.getElementById(decodeURIComponent(url.hash.slice(1))) : null;
      if (target) target.scrollIntoView();
      else window.scrollTo(0, 0);
      newMain.focus({ preventScroll: true });
      initCopy(newMain);
      initScrollSpy();
    }).catch(function () {
      if (seq === navSeq) location.href = url.href;
    });
  }

  function initPjax() {
    if (location.protocol === "file:" || !window.fetch || !window.DOMParser || !history.pushState) return;
    if (!doc.body.classList.contains("page-chapter")) return;
    history.replaceState({ pjax: true }, "", location.href);
    doc.addEventListener("click", function (e) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var a = e.target.closest && e.target.closest("a[href]");
      if (!a || a.target || a.hasAttribute("download")) return;
      var url = new URL(a.href, location.href);
      if (url.origin !== location.origin || !isChapterUrl(url)) return;
      if (url.pathname === location.pathname) return;
      e.preventDefault();
      navigate(url.href, true);
    });
    doc.addEventListener("mouseover", function (e) {
      var a = e.target.closest && e.target.closest(".chapter-list a, .pager a");
      if (!a) return;
      var url = new URL(a.href, location.href);
      if (url.origin === location.origin && isChapterUrl(url)) fetchPage(url.href.split("#")[0]);
    });
    window.addEventListener("popstate", function () {
      if (location.pathname !== shownPath) navigate(location.href, false);
      else {
        navSeq++;
        doc.getElementById("main").classList.remove("is-loading");
      }
    });
  }

  /* ← → キーで章移動 */
  function initKeys() {
    doc.addEventListener("keydown", function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      var t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      var rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : null;
      if (!rel) return;
      var link = doc.querySelector('.pager a[rel="' + rel + '"]');
      if (link) { e.preventDefault(); link.click(); }
    });
  }

  function init() {
    initCopy(doc);
    if (!doc.body.classList.contains("page-chapter")) return;
    initScrollSpy();
    initProgress();
    initPjax();
    initKeys();
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})();
