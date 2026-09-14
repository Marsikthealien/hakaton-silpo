/* Машрум Генадійович у чаті — та сама анімація, що на сайті «Сільпо» AI
   Factory (mushroom.riv, Rive), а не статична картинка. Рантайм беремо з
   jsdelivr збіркою canvas-advanced-single (WASM вшитий, один запит), файл —
   свій, /mushroom.riv. Підстраховка: PNG видно одразу, canvas проявляється
   лише після успішного старту; без інтернету на екрані просто лишається
   статичний Машрум.

   Живим тримаємо лише ОСТАННЬОГО: кожен новий аватар зупиняє цикли
   попередніх — вони завмирають на своєму кадрі. Інакше довга розмова
   тримала б десяток canvas-циклів одночасно. */
(function () {
  const RUNTIME = 'https://cdn.jsdelivr.net/npm/@rive-app/canvas-advanced-single@2.42.0/canvas_advanced_single.mjs';
  let boot = null;             // Promise<{rive, file}> — один на сторінку
  const live = [];             // активні цикли: {stop}

  function load() {
    if (boot) return boot;
    boot = (async () => {
      const mod = await import(RUNTIME);
      const RiveCanvas = mod.default || mod;
      const rive = await RiveCanvas();
      const bytes = new Uint8Array(await (await fetch('/mushroom.riv')).arrayBuffer());
      const file = await rive.load(bytes);
      return { rive, file };
    })();
    boot.catch(() => { /* офлайн — усюди лишається PNG */ });
    return boot;
  }

  async function mountAva(host) {
    if (!host || host.dataset.mounted) return;
    host.dataset.mounted = '1';
    let rt;
    try { rt = await load(); } catch (e) { return; }
    if (!host.isConnected) return;
    const { rive, file } = rt;
    try {
      const artboard = file.artboardByIndex(0);
      if (!artboard) return;
      let sm = null, anim = null;
      if (artboard.stateMachineCount && artboard.stateMachineCount() > 0) {
        sm = new rive.StateMachineInstance(artboard.stateMachineByIndex(0), artboard);
      } else if (artboard.animationCount && artboard.animationCount() > 0) {
        anim = new rive.LinearAnimationInstance(artboard.animationByIndex(0), artboard);
      } else {
        return;
      }
      const canvas = document.createElement('canvas');
      host.appendChild(canvas);
      const renderer = rive.makeRenderer(canvas);
      const fit = () => {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const r = host.getBoundingClientRect();
        canvas.width = Math.max(1, Math.round(r.width * dpr));
        canvas.height = Math.max(1, Math.round(r.height * dpr));
      };
      fit();

      // Попередні — завмирають на своєму кадрі, живий лише новий.
      live.splice(0).forEach(x => x.stop());
      let running = true, last = 0;
      const frame = (t) => {
        if (!running) return;
        if (!last) last = t;
        const dt = Math.min((t - last) / 1000, 0.1);
        last = t;
        renderer.clear();
        if (sm) { sm.advance(dt); } else { anim.advance(dt); anim.apply(1); }
        artboard.advance(dt);
        renderer.save();
        // Шапка Машрума виходить за межі артборда — даємо запас усередині,
        // інакше край зрізається прямою лінією.
        const pad = Math.round(Math.min(canvas.width, canvas.height) * 0.14);
        renderer.align(rive.Fit.contain, rive.Alignment.center,
          { minX: pad, minY: pad, maxX: canvas.width - pad, maxY: canvas.height - pad },
          artboard.bounds);
        artboard.draw(renderer);
        renderer.restore();
        if (renderer.flush) renderer.flush();
        rive.requestAnimationFrame(frame);
      };
      live.push({ stop: () => { running = false; } });
      rive.requestAnimationFrame(frame);
      host.classList.add('rive');
    } catch (e) { /* цей аватар лишається статичним */ }
  }

  window.mountAva = mountAva;
  // Аватари, що вже є в розмітці на момент завантаження.
  document.querySelectorAll('.mash').forEach(mountAva);
})();
