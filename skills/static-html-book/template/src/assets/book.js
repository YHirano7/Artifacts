/*
 * 段階的拡張。HTML だけで「表紙＋全章を縦に並べた1ページ」として読める。
 * JavaScript が動くときだけ、location.hash（#ch-<slug>・#top・#見出しID）で
 * 章を1つずつ切り替えて表示する。fetch は使わないので file:// でも動く。
 * 途中で例外が起きたら js クラスを外し、縦に並べた表示に戻す。
 */
(function () {
  "use strict";
  var doc = document;
  var root = doc.documentElement;
  var body = doc.body;
  if (!root.classList.contains("js")) return;

  var observer = null;
  var current = null;      // 表示中の .cover / .chapter
  var freshNav = false;    // リンクのクリックによる遷移か（戻る／進むではないか）
  var restoreY = null;     // 戻る／進むで復元するスクロール位置
  var saveTimer = 0;

  function $(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }

  /* ---------- スクロール位置の保存（戻る／進むで元の位置に戻すため） ---------- */
  function saveScroll() {
    clearTimeout(saveTimer);
    try {
      var st = history.state && typeof history.state === "object" ? history.state : {};
      var next = {};
      for (var k in st) if (Object.prototype.hasOwnProperty.call(st, k)) next[k] = st[k];
      next.bookY = window.scrollY;
      history.replaceState(next, "");
    } catch (e) { /* 保存できなくても表示には影響しない */ }
  }
  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveScroll, 200);
  }

  /* ---------- コードのコピー ---------- */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var ta = doc.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = doc.execCommand("copy"); } catch (e) { ok = false; }
      body.removeChild(ta);
      if (ok) resolve(); else reject(new Error("copy failed"));
    });
  }
  function initCopy() {
    $$(".code-block").forEach(function (block) {
      var btn = doc.createElement("button");
      btn.type = "button";
      btn.className = "copy-btn";
      btn.textContent = "コピー";
      btn.addEventListener("click", function () {
        var code = $("pre", block);
        copyText(code ? code.innerText : "").then(function () {
          btn.textContent = "コピーしました";
          btn.classList.add("is-done");
        }, function () {
          btn.textContent = "コピーできません";
        }).then(function () {
          setTimeout(function () { btn.textContent = "コピー"; btn.classList.remove("is-done"); }, 1600);
        });
      });
      block.appendChild(btn);
    });
  }

  /* ---------- 目次の現在位置 ---------- */
  function initScrollSpy(section) {
    if (observer) { observer.disconnect(); observer = null; }
    if (!("IntersectionObserver" in window) || !section) return;
    var card = $('.toc-card[data-chapter-toc="' + section.id + '"]');
    if (!card) return;
    var links = $$(".toc a", card);
    if (!links.length) return;
    var map = {};
    links.forEach(function (a) { map[decodeURIComponent(a.hash.slice(1))] = a; });
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var a = map[e.target.id];
        if (!a) return;
        links.forEach(function (l) { l.classList.remove("is-active"); });
        a.classList.add("is-active");
      });
    }, { rootMargin: "-64px 0px -70% 0px" });
    $$(".chapter-body h2[id], .chapter-body h3[id]", section).forEach(function (h) { observer.observe(h); });
  }

  /* ---------- 読書進捗バー ---------- */
  var progress = null;
  function updateProgress() {
    if (!progress) return;
    var max = root.scrollHeight - window.innerHeight;
    progress.style.width = (max > 0 ? Math.min(100, (window.scrollY / max) * 100) : 0) + "%";
  }
  function initProgress() {
    var bar = $(".topbar");
    if (!bar) return;
    progress = doc.createElement("span");
    progress.className = "progress";
    progress.setAttribute("aria-hidden", "true");
    bar.appendChild(progress);
    window.addEventListener("resize", updateProgress);
  }

  /* ---------- モバイルのチャプター一覧（ドロワー） ---------- */
  var menuBtn = null;
  function setDrawer(open, returnFocus) {
    body.classList.toggle("nav-open", open);
    if (menuBtn) menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      var link = $('.chapter-list a[aria-current="page"]') || $(".chapter-list a");
      if (link) link.focus({ preventScroll: true });
    } else if (returnFocus && menuBtn) {
      menuBtn.focus({ preventScroll: true });
    }
  }
  function initDrawer() {
    menuBtn = $(".menu-btn");
    if (menuBtn) {
      menuBtn.setAttribute("role", "button");
      menuBtn.setAttribute("aria-expanded", "false");
      menuBtn.addEventListener("click", function (e) {
        e.preventDefault();
        setDrawer(!body.classList.contains("nav-open"), false);
      });
    }
    var scrim = $("#scrim");
    if (scrim) scrim.addEventListener("click", function () { setDrawer(false, true); });
  }

  /* ---------- 表紙・章の切り替え ---------- */
  function showSection(section) {
    if (section === current) return;
    current = section;
    var isChapter = section.classList.contains("chapter");
    $$(".chapter.is-current, .toc-card.is-current").forEach(function (el) { el.classList.remove("is-current"); });
    body.classList.toggle("is-cover", !isChapter);
    if (isChapter) {
      section.classList.add("is-current");
      var card = $('.toc-card[data-chapter-toc="' + section.id + '"]');
      if (card) card.classList.add("is-current");
    }
    if (section.getAttribute("data-title")) doc.title = section.getAttribute("data-title");
    var label = $("#topbar-chapter");
    if (label) label.textContent = section.getAttribute("data-label") || "";
    $$(".chapter-list a").forEach(function (a) {
      if (isChapter && a.getAttribute("href") === "#" + section.id) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    initScrollSpy(isChapter ? section : null);
  }

  function route() {
    var fresh = freshNav, y = restoreY;
    freshNav = false;
    restoreY = null;
    var id = "";
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { id = location.hash.slice(1); }
    var el = id ? doc.getElementById(id) : null;
    var section = el ? el.closest(".cover, .chapter") : null;
    if (el && !section) {
      /* #main など、章でも表紙でもない場所。表紙表示中なら1章目を出す */
      if (!current || current.classList.contains("cover")) showSection($(".chapter") || $(".cover"));
      if (el.focus) el.focus({ preventScroll: true });
      return;
    }
    if (!section) section = $(".cover");
    var changed = section !== current;
    showSection(section);
    if (body.classList.contains("nav-open")) setDrawer(false, false);

    if (!fresh && typeof y === "number") {
      window.scrollTo(0, y);
    } else if (el && el !== section) {
      el.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
    if (fresh && changed && section.classList.contains("chapter")) {
      var main = $("#main");
      if (main) main.focus({ preventScroll: true });
    }
    updateProgress();
  }

  /* ---------- 入力 ---------- */
  function initEvents() {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";

    doc.addEventListener("click", function (e) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var a = e.target.closest("a[href]");
      if (!a) return;
      var href = a.getAttribute("href");
      if (href.charAt(0) !== "#" || href === "#" || a.classList.contains("menu-btn")) return;
      saveScroll();
      freshNav = true;
      if (href === location.hash) {
        /* 同じハッシュでは hashchange が起きないので、自分で表示し直す */
        e.preventDefault();
        route();
      }
    }, true);

    window.addEventListener("popstate", function (e) {
      clearTimeout(saveTimer);
      if (!freshNav && e.state && typeof e.state.bookY === "number") restoreY = e.state.bookY;
    });
    window.addEventListener("hashchange", function () {
      clearTimeout(saveTimer);
      route();
    });
    window.addEventListener("scroll", function () {
      updateProgress();
      scheduleSave();
    }, { passive: true });

    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && body.classList.contains("nav-open")) { setDrawer(false, true); return; }
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      var t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      var rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : null;
      if (!rel || !current || !current.classList.contains("chapter")) return;
      var link = $('.pager a[rel="' + rel + '"]', current);
      if (link) { e.preventDefault(); link.click(); }
    });
  }

  function init() {
    if (!$(".cover") || !$(".chapter")) throw new Error("book layout not found");
    initCopy();
    initProgress();
    initDrawer();
    initEvents();
    var st = history.state;
    if (st && typeof st.bookY === "number") restoreY = st.bookY; /* 再読み込み時 */
    route();
    root.classList.add("js-ready");
  }

  try {
    init();
  } catch (err) {
    /* 想定外の環境でも読めるように、縦に並べた表示へ戻す */
    root.classList.remove("js", "js-ready");
    body.classList.remove("is-cover", "nav-open");
    if (window.console && console.error) console.error(err);
  }
})();
