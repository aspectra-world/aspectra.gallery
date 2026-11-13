/* aspectra.gallery: the moving starfield of aspectra.world, the default backdrop when
   no wallpaper is set. Built with esbuild from aspectra.world
   src/components/starfield/starfield.ts (the original), unchanged; do not edit here. */
(() => {
  // starfield.ts
  var DEFAULT_PALETTE = {
    base: [220, 228, 237],
    // #dce4ed
    tints: [
      { rgb: [150, 196, 235], share: 0.12 },
      // Blue-Bell tint
      { rgb: [206, 198, 245], share: 0.08 }
      // Wisteria tint
    ]
  };
  var LAYERS = [
    { density: 1.3, radius: [0.35, 0.7], alpha: [0.14, 0.4], depth: 0.15, drift: 1.2 },
    { density: 0.6, radius: [0.6, 1.1], alpha: [0.28, 0.62], depth: 0.45, drift: 2.4 },
    { density: 0.14, radius: [1, 1.7], alpha: [0.5, 0.9], depth: 1, drift: 4 }
  ];
  var MAX_POINTER_SHIFT = 18;
  var SCROLL_FACTOR = 0.12;
  var EDGE_PAD = 24;
  function mulberry32(seed) {
    let a = seed >>> 0;
    return () => {
      a = a + 1831565813 >>> 0;
      let t = a;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var lerp = (a, b, t) => a + (b - a) * t;
  function wrap(value, size) {
    const span = size + EDGE_PAD * 2;
    return ((value + EDGE_PAD) % span + span) % span - EDGE_PAD;
  }
  function makeStarSprite(rgb, size = 64) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const g = c.getContext("2d");
    const [r, gr, b] = rgb;
    const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    grad.addColorStop(0, `rgba(${r},${gr},${b},1)`);
    grad.addColorStop(0.12, `rgba(${r},${gr},${b},0.9)`);
    grad.addColorStop(0.28, `rgba(${r},${gr},${b},0.32)`);
    grad.addColorStop(0.55, `rgba(${r},${gr},${b},0.07)`);
    grad.addColorStop(1, `rgba(${r},${gr},${b},0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, size, size);
    return c;
  }
  function isLowPowerDevice() {
    const nav = navigator;
    return (nav.hardwareConcurrency ?? 8) <= 4 || (nav.deviceMemory ?? 8) <= 4 || nav.connection?.saveData === true || window.matchMedia("(pointer: coarse)").matches;
  }
  function createStarfield(canvas, options = {}) {
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return { destroy() {
    } };
    const opts = {
      density: 1,
      intensity: 1,
      parallax: true,
      twinkle: true,
      shootingStars: false,
      shootingStarMinWidth: 800,
      seed: 1709,
      palette: DEFAULT_PALETTE,
      still: false,
      ...options
    };
    const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finePointer = window.matchMedia("(pointer: fine)").matches;
    const lowPower = isLowPowerDevice();
    const colors = [opts.palette.base, ...opts.palette.tints.map((t) => t.rgb)];
    const sprites = colors.map((c) => makeStarSprite(c));
    const meteorHalo = makeStarSprite([150, 190, 255]);
    let quality = opts.still ? 2 : lowPower ? 1 : 0;
    let reducedMotion = reducedMotionQuery.matches;
    let width = 0;
    let height = 0;
    let dpr = 1;
    let stars = [];
    let builtForArea = 0;
    const pointerTarget = { x: 0, y: 0 };
    const pointer = { x: 0, y: 0 };
    let scroll = window.scrollY;
    let meteors = [];
    let meteorTimer = 0;
    let raf = 0;
    let lastFrame = 0;
    let startTime = performance.now();
    let destroyed = false;
    let sampleFrames = 0;
    let sampleTime = 0;
    function densityFactor() {
      return opts.density * (quality >= 1 ? 0.55 : 1);
    }
    function buildStars() {
      const rand = mulberry32(opts.seed);
      const area = width * height / 1e4;
      const tintShares = opts.palette.tints.map((t) => t.share);
      stars = [];
      LAYERS.forEach((layer, layerIndex) => {
        const count = Math.round(area * layer.density * densityFactor());
        for (let i = 0; i < count; i++) {
          let color = 0;
          let roll = rand();
          for (let t = 0; t < tintShares.length; t++) {
            if (roll < tintShares[t]) {
              color = t + 1;
              break;
            }
            roll -= tintShares[t];
          }
          const twinkles = layerIndex > 0 && rand() < 0.18;
          stars.push({
            nx: rand(),
            ny: rand(),
            r: lerp(layer.radius[0], layer.radius[1], rand() ** 1.6),
            alpha: lerp(layer.alpha[0], layer.alpha[1], rand()) * opts.intensity,
            color,
            layer: layerIndex,
            twinkle: twinkles ? 0.6 + rand() * 1.6 : 0,
            phase: rand() * Math.PI * 2
          });
        }
      });
      builtForArea = width * height;
    }
    function resize() {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, Math.round(rect.width));
      height = Math.max(1, Math.round(rect.height));
      dpr = Math.min(window.devicePixelRatio || 1, lowPower ? 1.5 : 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      const area = width * height;
      if (!builtForArea || area / builtForArea > 1.3 || builtForArea / area > 1.3) buildStars();
    }
    function drawStars(time, animate) {
      const seconds = (time - startTime) / 1e3;
      for (const star of stars) {
        const layer = LAYERS[star.layer];
        let alpha = star.alpha;
        if (animate && star.twinkle && opts.twinkle && quality === 0) {
          alpha *= 0.55 + 0.45 * Math.sin(seconds * star.twinkle + star.phase);
        }
        if (alpha <= 0.01) continue;
        let x = star.nx * width;
        let y = star.ny * height;
        if (animate) {
          x += pointer.x * layer.depth - seconds * layer.drift;
          y += pointer.y * layer.depth - scroll * SCROLL_FACTOR * layer.depth;
        }
        const px = wrap(x, width);
        const py = wrap(y, height);
        const size = star.r * 6.4;
        ctx.globalAlpha = alpha;
        ctx.drawImage(sprites[star.color], px - size / 2, py - size / 2, size, size);
      }
      ctx.globalAlpha = 1;
    }
    function drawMeteors(time) {
      meteors = meteors.filter((m) => time - m.start < m.duration);
      for (const m of meteors) {
        const p = (time - m.start) / m.duration;
        const eased = 1 - (1 - p) ** 2.2;
        const opacity = p < 0.1 ? p / 0.1 * m.peak : p < 0.82 ? m.peak : (1 - p) / 0.18 * m.peak;
        const hx = m.x0 + m.dx * eased;
        const hy = m.y0 + m.dy * eased;
        const dist = Math.hypot(m.dx, m.dy);
        const ux = m.dx / dist;
        const uy = m.dy / dist;
        const tx = hx - ux * m.length;
        const ty = hy - uy * m.length;
        ctx.globalAlpha = opacity;
        const grad = ctx.createLinearGradient(tx, ty, hx, hy);
        grad.addColorStop(0, "rgba(255,255,255,0)");
        grad.addColorStop(0.55, "rgba(220,228,237,0.55)");
        grad.addColorStop(1, "rgba(255,255,255,0.95)");
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.6;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(hx, hy);
        ctx.stroke();
        for (const [offset, phase] of [
          [0.35, 0],
          [0.6, 1.7]
        ]) {
          const flicker = 0.5 + 0.5 * Math.sin(time / 110 + phase);
          const sx = hx - ux * m.length * offset - uy * 3 * flicker;
          const sy = hy - uy * m.length * offset + ux * 3 * flicker;
          ctx.globalAlpha = opacity * flicker * 0.8;
          ctx.drawImage(sprites[0], sx - 3, sy - 3, 6, 6);
        }
        ctx.globalAlpha = opacity * 0.55;
        ctx.drawImage(meteorHalo, hx - 22, hy - 22, 44, 44);
        ctx.globalAlpha = opacity;
        ctx.drawImage(sprites[0], hx - 8, hy - 8, 16, 16);
      }
      ctx.globalAlpha = 1;
    }
    function render(time, animate) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      drawStars(time, animate);
      if (animate) drawMeteors(time);
    }
    function renderStatic() {
      cancelAnimationFrame(raf);
      raf = 0;
      render(performance.now(), false);
      canvas.classList.add("is-ready");
    }
    function frame(time) {
      if (destroyed) return;
      raf = requestAnimationFrame(frame);
      const dt = lastFrame ? time - lastFrame : 16.7;
      lastFrame = time;
      if (lowPower && dt < 30 && sampleFrames > 0) {
        lastFrame = time - dt;
        return;
      }
      monitorFps(dt);
      if (quality >= 2) return;
      const ease = 1 - Math.pow(0.94, dt / 16.7);
      pointer.x += (pointerTarget.x - pointer.x) * ease;
      pointer.y += (pointerTarget.y - pointer.y) * ease;
      if (opts.parallax) scroll += (window.scrollY - scroll) * ease;
      render(time, true);
      canvas.classList.add("is-ready");
    }
    function monitorFps(dt) {
      sampleFrames++;
      if (sampleFrames < 30 || dt > 250) return;
      sampleTime += dt;
      if (sampleFrames === 150) {
        const avg = sampleTime / 120;
        const budget = lowPower ? 40 : 22;
        if (avg > budget) {
          quality++;
          if (quality >= 2) {
            stopMeteors();
            renderStatic();
            return;
          }
          buildStars();
        }
        sampleFrames = 0;
        sampleTime = 0;
      }
    }
    function start() {
      cancelAnimationFrame(raf);
      stopMeteors();
      if (reducedMotion || quality >= 2) {
        renderStatic();
        return;
      }
      lastFrame = 0;
      sampleFrames = 0;
      sampleTime = 0;
      raf = requestAnimationFrame(frame);
      scheduleMeteor();
    }
    function spawnMeteor() {
      if (width < opts.shootingStarMinWidth) return;
      const angle = (-35 + Math.random() * 50) * Math.PI / 180;
      const distance = (0.55 + Math.random() * 0.6) * width;
      meteors.push({
        x0: (Math.random() * 0.7 - 0.2) * width,
        y0: Math.random() * 0.6 * height,
        dx: Math.cos(angle) * distance,
        dy: Math.sin(angle) * distance,
        length: 80 + Math.random() * 120,
        start: performance.now(),
        duration: 1800 + Math.random() * 1400,
        peak: 0.7 + Math.random() * 0.3
      });
    }
    function burst() {
      spawnMeteor();
      if (Math.random() < 0.32) window.setTimeout(spawnMeteor, 300 + Math.random() * 700);
      if (Math.random() < 0.08) window.setTimeout(spawnMeteor, 900 + Math.random() * 600);
    }
    function scheduleMeteor() {
      if (!opts.shootingStars) return;
      meteorTimer = window.setTimeout(
        () => {
          if (!document.hidden) burst();
          scheduleMeteor();
        },
        4500 + Math.random() * 11e3
      );
    }
    function stopMeteors() {
      window.clearTimeout(meteorTimer);
      meteors = [];
    }
    function onPointerMove(e) {
      pointerTarget.x = (e.clientX / window.innerWidth - 0.5) * -2 * MAX_POINTER_SHIFT;
      pointerTarget.y = (e.clientY / window.innerHeight - 0.5) * -2 * MAX_POINTER_SHIFT;
    }
    let resizeTimer = 0;
    const resizeObserver = new ResizeObserver(() => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(
        () => {
          resize();
          if (!raf) renderStatic();
        },
        width > 1 ? 150 : 0
      );
    });
    function onVisibility() {
      if (document.hidden) {
        cancelAnimationFrame(raf);
        raf = 0;
        stopMeteors();
      } else {
        start();
      }
    }
    function onMotionPreference() {
      reducedMotion = reducedMotionQuery.matches;
      start();
    }
    if (opts.parallax && finePointer) window.addEventListener("pointermove", onPointerMove, { passive: true });
    resizeObserver.observe(canvas);
    document.addEventListener("visibilitychange", onVisibility);
    reducedMotionQuery.addEventListener("change", onMotionPreference);
    resize();
    startTime = performance.now();
    start();
    return {
      destroy() {
        destroyed = true;
        cancelAnimationFrame(raf);
        stopMeteors();
        window.clearTimeout(resizeTimer);
        window.removeEventListener("pointermove", onPointerMove);
        resizeObserver.disconnect();
        document.removeEventListener("visibilitychange", onVisibility);
        reducedMotionQuery.removeEventListener("change", onMotionPreference);
      }
    };
  }

  // entry.ts
  document.querySelectorAll("canvas[data-starfield]").forEach((canvas) => {
    createStarfield(canvas, { intensity: Number(canvas.dataset.intensity) || 0.8, density: 1 });
  });
})();
