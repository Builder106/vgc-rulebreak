// Global keys: a key press clicks the hint-row control with the matching data-key.
// Menus ([data-menu]) also move the cursor with the arrow keys.
import { onPage } from '../engine';

const typing = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName));

function keyName(e: KeyboardEvent) {
  if (e.key === 'Escape') return 'Esc';
  if (e.key.length === 1) return e.key.toUpperCase();
  return e.key;
}

onPage(() => {
  const onKey = (e: KeyboardEvent) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
    const onControl = e.target instanceof HTMLElement && e.target.closest('a, button, summary');
    if ((e.key === 'Enter' || e.key === ' ') && onControl && !onControl.closest('[data-menu]')) return;

    const menu = document.querySelector<HTMLElement>('[data-menu]');
    if (menu && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      const items = [...menu.querySelectorAll<HTMLAnchorElement>('a')];
      const current = items.findIndex((a) => a === document.activeElement || a.hasAttribute('data-selected'));
      const next = (current + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items.forEach((a) => a.removeAttribute('data-selected'));
      items[next].setAttribute('data-selected', '');
      items[next].focus();
      e.preventDefault();
      return;
    }

    const control = document.querySelector<HTMLElement>(`.hints [data-key="${CSS.escape(keyName(e))}"]:not([hidden])`);
    if (!control) return;
    e.preventDefault();
    control.click();
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
});
