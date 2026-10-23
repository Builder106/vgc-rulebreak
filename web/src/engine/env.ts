export const prefersReducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const isTouch = () => matchMedia('(hover: none), (pointer: coarse)').matches;

// Shared easing vocabulary: menus snap, so everything decelerates hard.
export const ease = {
  out: 'power3.out',
  inOut: 'power3.inOut',
  snap: 'back.out(2.2)',
} as const;
