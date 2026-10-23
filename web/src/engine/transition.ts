// Page transitions: a slanted panel sweeps across like a menu change, covering the swap.
import { gsap } from 'gsap';
import { ease, prefersReducedMotion } from './env';

const curtain = () => document.getElementById('curtain') as HTMLElement;

export function playLeave(): Promise<unknown> {
  const c = curtain();
  const panel = c.querySelector('.curtain__panel');
  if (prefersReducedMotion()) return Promise.resolve(gsap.set(c, { autoAlpha: 0 }));
  return Promise.resolve(
    gsap.timeline()
      .set(c, { autoAlpha: 1 })
      .fromTo(panel, { xPercent: 110 }, { xPercent: 0, duration: 0.32, ease: ease.inOut }),
  );
}

export function playEnter(): Promise<unknown> {
  const c = curtain();
  const panel = c.querySelector('.curtain__panel');
  if (prefersReducedMotion()) return Promise.resolve(gsap.set(c, { autoAlpha: 0 }));
  return Promise.resolve(
    gsap.timeline()
      .to(panel, { xPercent: -110, duration: 0.36, ease: ease.inOut })
      .set(c, { autoAlpha: 0 }),
  );
}
