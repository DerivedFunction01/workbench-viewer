// The content scroller, resolved from the DOM.
//
// The phone presentation is plain document flow (the
// owner's ruling): no element in the app scrolls. What
// scrolls is whatever hosts the app — the document
// itself when the build is served bare, or the space
// host's fixed overflow container when embedded (the
// same shape the reference apps rely on: they ship no
// scroll code at all). The two places that must move
// the scroll — the route-change reset and the
// questions card's post-swap anchor restore — resolve
// that host scroller by walking up from <main> to the
// first ancestor that actually scrolls, and fall back
// to the window when there is none.

export function contentScroller(): HTMLElement | null {
  let el: HTMLElement | null = document.querySelector("main");
  while (el) {
    el = el.parentElement;
    if (!el || el === document.body || el === document.documentElement) break;
    const overflowY = getComputedStyle(el).overflowY;
    if ((overflowY === "auto" || overflowY === "scroll") && el.scrollHeight > el.clientHeight + 1) {
      return el;
    }
  }
  return null;
}

export function resetContentScroll(): void {
  const scroller = contentScroller();
  if (scroller) scroller.scrollTo(0, 0);
  else window.scrollTo(0, 0);
}

export function scrollContentBy(deltaY: number): void {
  const scroller = contentScroller();
  if (scroller) scroller.scrollBy(0, deltaY);
  else window.scrollBy(0, deltaY);
}
