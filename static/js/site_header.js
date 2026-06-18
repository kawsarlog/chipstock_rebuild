(function () {
  var masthead = document.getElementById("masthead");
  var openBtn = document.getElementById("cs-header-open");
  var closeBtn = document.getElementById("cs-header-close");
  var menu = document.getElementById("cs-header-menu");
  var backdrop = document.getElementById("cs-header-backdrop");
  if (!masthead || !openBtn || !menu) return;

  var mq = window.matchMedia("(max-width: 1023px)");

  function isMobile() {
    return mq.matches;
  }

  function syncAria() {
    if (!isMobile()) {
      menu.setAttribute("aria-hidden", "false");
      masthead.classList.remove("is-menu-open");
      document.body.classList.remove("cs-header-menu-open");
      openBtn.setAttribute("aria-expanded", "false");
      if (backdrop) backdrop.setAttribute("aria-hidden", "true");
      return;
    }
    var open = masthead.classList.contains("is-menu-open");
    menu.setAttribute("aria-hidden", open ? "false" : "true");
    openBtn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function openMenu() {
    if (!isMobile()) return;
    masthead.classList.add("is-menu-open");
    document.body.classList.add("cs-header-menu-open");
    if (backdrop) backdrop.setAttribute("aria-hidden", "false");
    syncAria();
  }

  function closeMenu() {
    masthead.classList.remove("is-menu-open");
    document.body.classList.remove("cs-header-menu-open");
    if (backdrop) backdrop.setAttribute("aria-hidden", "true");
    syncAria();
  }

  openBtn.addEventListener("click", function () {
    if (masthead.classList.contains("is-menu-open")) closeMenu();
    else openMenu();
  });
  if (closeBtn) closeBtn.addEventListener("click", closeMenu);
  if (backdrop) backdrop.addEventListener("click", closeMenu);
  menu.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () {
      if (isMobile()) closeMenu();
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMenu();
  });
  if (mq.addEventListener) {
    mq.addEventListener("change", syncAria);
  } else if (mq.addListener) {
    mq.addListener(syncAria);
  }
  syncAria();
})();
