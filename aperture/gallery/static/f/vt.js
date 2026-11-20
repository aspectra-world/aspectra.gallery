/* SPDX-License-Identifier: AGPL-3.0-or-later · Copyright © 2026 lucya.systems — https://lucya.systems */
/* Aperture · the mode switch's circle, across the page load.
   Facet opens the new mode as a circle from the toggle (facet.js setTheme).
   The gallery's toggle is a link: the server keeps the choice and sends the
   page back in the new mode. gallery.js notes where the click was; here, on
   the page that arrives, the cross-document view transition draws the circle
   from that point. Every other navigation is not a transition at all.
   Loaded in <head>, not deferred: pagereveal fires before the first frame.
   Browsers without cross-document view transitions simply load the page. */
(() => {
  const KEY = 'g-theme-from';
  const take = (keep) => {
    try {
      const v = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (!keep) sessionStorage.removeItem(KEY);
      return v && Date.now() - v.t < 6000 ? v : null;
    } catch { return null; }
  };
  const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches ||
    document.documentElement.dataset.motion === 'reduced';

  // the page leaving: only a mode switch is captured
  addEventListener('pageswap', (e) => {
    if (e.viewTransition && (!take(true) || still())) e.viewTransition.skipTransition();
  });

  // the page arriving: the circle from the toggle
  addEventListener('pagereveal', (e) => {
    const from = take(false);   // read once: a note never outlives one page load
    if (!e.viewTransition) return;
    if (!from || still()) { e.viewTransition.skipTransition(); return; }
    const { x, y } = from;
    const end = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    e.viewTransition.ready.then(() => document.documentElement.animate(
      { clipPath: [`circle(0 at ${x}px ${y}px)`, `circle(${end}px at ${x}px ${y}px)`] },
      { duration: 650, easing: 'cubic-bezier(.16,1,.3,1)', pseudoElement: '::view-transition-new(root)' })).catch(() => {});
  });
})();
