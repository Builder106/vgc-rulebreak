// The battle screen: steps through recorded turn frames and plays the rule switch.
import { gsap } from 'gsap';
import { ease, onPage, prefersReducedMotion } from '../engine';

type Side = 'p1' | 'p2';
interface Mon {
  species: string;
  hp: number;
  maxhp?: number;
  fainted: boolean;
  status: string | null;
}
interface MoveOption {
  name: string;
  pp: number | null;
  maxpp: number | null;
  disabled: boolean;
  protect: boolean;
}
interface SlotChoice {
  slot: 'a' | 'b';
  species: string;
  moves: MoveOption[];
  chosen: { kind: string; index?: number; name?: string; species?: string };
}
interface Frame {
  turn: number;
  field: Record<Side, (Mon | null)[]>;
  after: Record<Side, (Mon | null)[]>;
  events: string[];
  choices?: Partial<Record<Side, SlotChoice[]>>;
}
interface Payload {
  id: string;
  ally: Side;
  foe: Side;
  labels: Record<Side, string>;
  cap: number;
  frames: Frame[];
  sigils: Record<string, { points: string; colors: string[]; speedTip: [number, number] }>;
}

const CELL = '60,12 101.57,36 101.57,84 60,108 18.43,84 18.43,36';
const pct = (m: Mon | null) => (m && m.maxhp ? Math.round((100 * m.hp) / m.maxhp) : 0);
const level = (p: number) => (p > 50 ? 'high' : p > 20 ? 'mid' : 'low');

onPage(({ intro }) => {
  const root = document.querySelector<HTMLElement>('[data-battle]');
  const dataEl = document.getElementById('battle-data');
  if (!root || !dataEl) return;
  const data = JSON.parse(dataEl.textContent ?? '{}') as Payload;
  const motion = !prefersReducedMotion();
  const $ = <T extends Element>(sel: string, scope: ParentNode = root) => scope.querySelector<T>(sel);
  const $$ = <T extends Element>(sel: string, scope: ParentNode = root) => [...scope.querySelectorAll<T>(sel)];

  playRuleSwitch(root, data.cap, intro, motion);
  setupProvenance(root);
  if (!data.frames.length) return;

  let index = 0;
  let perspective: Side = data.ally;
  const shown = new Map<string, string | null>();

  const turnParam = Number(new URLSearchParams(location.search).get('turn'));
  if (turnParam) {
    const found = data.frames.findIndex((f) => f.turn === turnParam);
    if (found >= 0) index = found;
  }

  function renderSlot(side: Side, i: number, mon: Mon | null, frame: Frame) {
    const slot = $<HTMLElement>(`[data-slot="${side}${'ab'[i]}"]`);
    if (!slot) return;
    const p = pct(mon);
    $<HTMLElement>('[data-name]', slot)!.textContent = mon?.species ?? 'Empty';
    $<HTMLElement>('[data-hp-text]', slot)!.textContent = mon ? `${p}%` : '';
    $<HTMLElement>('[data-status]', slot)!.textContent = mon?.status ?? '';
    $<HTMLElement>('.hp', slot)!.dataset.hpLevel = level(p);
    slot.toggleAttribute('data-fainted', Boolean(mon?.fainted));
    slot.toggleAttribute('data-empty', !mon);

    const fill = $<HTMLElement>('[data-hp-fill]', slot)!;
    const clip = `inset(0% ${100 - p}% 0% 0%)`;
    if (motion) gsap.to(fill, { clipPath: clip, duration: 0.45, ease: ease.out, overwrite: true });
    else fill.style.clipPath = clip;

    const svg = $<SVGSVGElement>('svg.sigil', slot)!;
    const species = mon?.species ?? null;
    const sigil = species ? data.sigils[species] : undefined;
    const key = `${side}${i}`;
    if (shown.get(key) !== species) {
      shown.set(key, species);
      const shape = $<SVGPolygonElement>('[data-shape]', svg)!;
      const speed = $<SVGLineElement>('[data-speed]', svg)!;
      shape.setAttribute('points', sigil?.points ?? CELL);
      const [a, b] = sigil ? [sigil.colors[0], sigil.colors[1] ?? sigil.colors[0]] : ['#4A3F73', '#4A3F73'];
      $$<SVGStopElement>('[data-stop]', svg).forEach((stop) => stop.setAttribute('stop-color', stop.dataset.stop === 'a' ? a : b));
      speed.setAttribute('x2', String(sigil?.speedTip[0] ?? 60));
      speed.setAttribute('y2', String(sigil?.speedTip[1] ?? 60));
      svg.setAttribute('aria-label', species ? `${species} stat sigil` : '');
    }
    // The shape shrinks toward the center as HP falls and drains to an outline on a knockout.
    const body = $<SVGGElement>('[data-body]', svg)!;
    const scale = mon && !mon.fainted ? 0.45 + 0.55 * (p / 100) : 1;
    const vars = { scale, svgOrigin: '60 60', duration: motion ? 0.45 : 0, ease: ease.out, overwrite: true };
    gsap.to(body, vars);
    const shape = $<SVGPolygonElement>('[data-shape]', svg)!;
    gsap.to(shape, { fillOpacity: mon && !mon.fainted ? 1 : 0, opacity: mon ? 1 : 0, duration: motion ? 0.3 : 0, overwrite: true });

    const label = data.labels[side];
    const guarded = Boolean(mon) && frame.events.includes(`${label}'s ${mon!.species} protected itself.`);
    slot.toggleAttribute('data-guarded', guarded);
    if (guarded && motion) {
      gsap.fromTo($('.slot__guard', slot), { scale: 0.6, opacity: 0, transformOrigin: '50% 50%' }, { scale: 1, opacity: 1, duration: 0.35, ease: ease.snap });
    }
  }

  function renderMoves(frame: Frame) {
    $<HTMLElement>('[data-perspective-label]')!.textContent = data.labels[perspective];
    const choices = frame.choices?.[perspective] ?? [];
    $$<HTMLElement>('[data-move-slot]').forEach((panel, i) => {
      const choice = choices.find((c) => c.slot === 'ab'[i]);
      const mon = frame.field[perspective][i];
      $<HTMLElement>('[data-move-who]', panel)!.textContent = choice?.species ?? mon?.species ?? 'Empty';
      $$<HTMLLIElement>('[data-move]', panel).forEach((li, k) => {
        const mv = choice?.moves[k];
        li.hidden = !mv;
        if (!mv) return;
        $<HTMLElement>('[data-move-name]', li)!.textContent = mv.name;
        $<HTMLElement>('[data-move-pp]', li)!.textContent = mv.pp !== null ? `${mv.pp} / ${mv.maxpp}` : '';
        li.toggleAttribute('data-protect', mv.protect);
        li.toggleAttribute('data-disabled', mv.disabled);
        const chosen = choice?.chosen.kind === 'move' && choice.chosen.index === k;
        li.toggleAttribute('data-chosen', chosen);
        if (chosen && motion) {
          gsap.fromTo($('.move__arrow', li), { x: -8, opacity: 0 }, { x: 0, opacity: 1, duration: 0.18, ease: ease.snap, overwrite: true });
        }
      });
      const note = !choice
        ? 'No decision this turn.'
        : choice.chosen.kind === 'switch'
          ? `Switched to ${choice.chosen.species}.`
          : choice.chosen.kind === 'pass'
            ? 'Passed.'
            : `Chose ${choice.chosen.name}.`;
      $<HTMLElement>('[data-move-note]', panel)!.textContent = note;
    });
  }

  function render(next: number, { push = true } = {}) {
    index = Math.max(0, Math.min(data.frames.length - 1, next));
    const frame = data.frames[index];
    $$<HTMLElement>('[data-turn]').forEach((el) => (el.textContent = String(frame.turn)));
    for (const side of [data.ally, data.foe]) frame.after[side].forEach((m, i) => renderSlot(side, i, m, frame));
    renderMoves(frame);

    const list = $<HTMLOListElement>('[data-events]')!;
    list.replaceChildren(...frame.events.map((e) => Object.assign(document.createElement('li'), { textContent: e })));
    list.scrollTop = 0;
    if (motion) gsap.from(list.children, { x: -10, opacity: 0, duration: 0.22, stagger: 0.025, ease: ease.out });

    const scrub = $<HTMLInputElement>('[data-scrub]')!;
    scrub.value = String(index);
    $<HTMLButtonElement>('[data-step="-1"]')!.disabled = index === 0;
    $<HTMLButtonElement>('[data-step="1"]')!.disabled = index === data.frames.length - 1;
    $$<HTMLElement>('.gamelog__turn').forEach((li) => li.toggleAttribute('data-current', li.id === `turn-${frame.turn}`));

    if (push) {
      const url = new URL(location.href);
      url.searchParams.set('turn', String(frame.turn));
      history.replaceState(history.state, '', url);
    }
  }

  const step = (d: number) => render(index + d);
  const listeners: [EventTarget, string, EventListener][] = [];
  const on = (el: EventTarget | null, type: string, fn: EventListener) => {
    if (!el) return;
    el.addEventListener(type, fn);
    listeners.push([el, type, fn]);
  };

  $$<HTMLButtonElement>('[data-step]').forEach((btn) => on(btn, 'click', () => step(Number(btn.dataset.step))));
  on(document.getElementById('hint-prev'), 'click', () => step(-1));
  on(document.getElementById('hint-next'), 'click', () => step(1));
  on(document.getElementById('hint-side'), 'click', () => {
    perspective = perspective === data.ally ? data.foe : data.ally;
    renderMoves(data.frames[index]);
  });
  on($('[data-scrub]'), 'input', (e) => render(Number((e.target as HTMLInputElement).value)));
  $$<HTMLAnchorElement>('[data-goto]').forEach((a) =>
    on(a, 'click', (e) => {
      e.preventDefault();
      render(Number(a.dataset.goto));
      $('.battle-grid')?.scrollIntoView({ behavior: motion ? 'smooth' : 'auto', block: 'start' });
    }),
  );

  // Swipe on the field to step turns on touch screens.
  let startX: number | null = null;
  const stage = $('.stage');
  on(stage, 'pointerdown', (e) => (startX = (e as PointerEvent).clientX));
  on(stage, 'pointerup', (e) => {
    if (startX === null) return;
    const dx = (e as PointerEvent).clientX - startX;
    startX = null;
    if (Math.abs(dx) > 48) step(dx < 0 ? 1 : -1);
  });

  render(index, { push: false });
  return () => listeners.forEach(([el, type, fn]) => el.removeEventListener(type, fn));
});

/** The signature: under Champions rules the shield arrives whole at 16, then cracks to 8. */
function playRuleSwitch(root: HTMLElement, cap: number, intro: gsap.core.Timeline, motion: boolean) {
  const widget = root.querySelector<HTMLElement>('[data-cap-widget]');
  if (!widget || !motion) return;
  const right = widget.querySelector('[data-part="shield-right"]');
  const seam = widget.querySelector('[data-part="shield-seam"]');
  const cells = widget.querySelectorAll('[data-part^="shield-cell-"]');
  const oldNum = widget.querySelector<HTMLElement>('[data-cap-old]');
  const newNum = widget.querySelector<HTMLElement>('[data-cap-new]');
  if (!right || !seam || !oldNum || !newNum) return;

  intro.from(cells, { opacity: 0, duration: 0.2, stagger: 0.015, ease: 'none' }, 0.1);
  if (cap !== 8) return;

  gsap.set(right, { x: 0, y: 0, rotation: 0, opacity: 1, svgOrigin: '108 80' });
  gsap.set(seam, { opacity: 0.5 });
  gsap.set(oldNum, { position: 'static', visibility: 'visible' });
  gsap.set(newNum, { position: 'absolute', top: 0, left: 0, yPercent: 100 });
  intro
    .to(seam, { opacity: 1, duration: 0.12, ease: 'none' }, 0.75)
    .to(right, { x: 14, y: 10, rotation: 9, opacity: 0.35, svgOrigin: '108 80', duration: 0.5, ease: ease.snap }, 0.9)
    .to(seam, { opacity: 0, duration: 0.2 }, 0.9)
    .to(oldNum, { yPercent: -100, duration: 0.3, ease: ease.out }, 0.9)
    .to(newNum, { yPercent: 0, duration: 0.3, ease: ease.out }, 0.9)
    .set(oldNum, { position: 'absolute', visibility: 'hidden' })
    .set(newNum, { position: 'static' });
}

function setupProvenance(root: HTMLElement) {
  const panel = root.querySelector<HTMLElement>('[data-provenance]');
  const button = document.getElementById('hint-info');
  if (!panel || !button) return;
  button.setAttribute('aria-expanded', 'false');
  button.addEventListener('click', () => {
    const open = !panel.hasAttribute('data-open');
    panel.toggleAttribute('data-open', open);
    button.setAttribute('aria-expanded', String(open));
    if (open) panel.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'nearest' });
  });
}
