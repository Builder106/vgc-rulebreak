// Astro adapter (ClientRouter): the leave animation runs while the next page loads.
import { boot, cleanup, enter, leave, syncFlags } from './index';

let navigating = false;
let backForward = false;

export function start() {
  document.addEventListener('astro:before-preparation', (e) => {
    navigating = true;
    backForward = e.navigationType === 'traverse';
    if (backForward) return;
    const load = e.loader;
    e.loader = async () => {
      await Promise.all([leave(), load()]);
    };
  });
  document.addEventListener('astro:before-swap', () => cleanup());
  document.addEventListener('astro:after-swap', () => syncFlags());
  document.addEventListener('astro:page-load', () => {
    if (!navigating) return void boot();
    navigating = false;
    enter({ transition: !backForward });
  });
  boot();
}
