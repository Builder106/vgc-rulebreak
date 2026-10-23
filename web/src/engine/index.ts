// Page lifecycle on one GSAP clock. onPage(fn) runs on every page load inside a gsap.context,
// so tweens it creates are reverted on navigation. Return a cleanup for listeners.
import { gsap } from 'gsap';
import { playEnter, playLeave } from './transition';
import { prefersReducedMotion } from './env';

export { ease, isTouch, prefersReducedMotion } from './env';

export type PageFn = (page: { intro: gsap.core.Timeline; path: string }) => void | (() => void);
const pageFns = new Set<PageFn>();
const cleanups: (() => void)[] = [];
let ctx: gsap.Context | null = null;
let intro: gsap.core.Timeline | null = null;
let ready = false;
let booted = false;

export function onPage(fn: PageFn) {
  pageFns.add(fn);
  if (ready) runPageFn(fn);
  return () => {
    pageFns.delete(fn);
  };
}

function runPageFn(fn: PageFn) {
  ctx?.add(() => {
    const c = fn({ intro: intro!, path: location.pathname });
    if (typeof c === 'function') cleanups.push(c);
  });
}

export function syncFlags() {
  const h = document.documentElement.classList;
  h.add('js');
  h.toggle('motion', !prefersReducedMotion());
}

function initPage() {
  syncFlags();
  ctx = gsap.context(() => {
    intro = gsap.timeline({ paused: true });
    if (!prefersReducedMotion()) {
      // Panels arrive along their slant, staggered top to bottom.
      const panels = gsap.utils.toArray<HTMLElement>('[data-enter]');
      if (panels.length) {
        intro.from(panels, { x: -24, y: 5, autoAlpha: 0, duration: 0.28, ease: 'power3.out', stagger: 0.04 }, 0);
      }
    }
  });
  ready = true;
  pageFns.forEach(runPageFn);
}

export function boot() {
  if (booted) return;
  booted = true;
  initPage();
  intro?.play();
}

export async function leave() {
  await playLeave();
}

export function cleanup() {
  if (!ready) return;
  ready = false;
  cleanups.splice(0).forEach((c) => c());
  ctx?.revert();
  ctx = null;
}

export async function enter({ transition = true } = {}) {
  if (!booted) return;
  cleanup();
  window.scrollTo(0, 0);
  initPage();
  if (transition) await playEnter();
  intro?.play();
}
