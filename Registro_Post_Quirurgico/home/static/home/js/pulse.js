/* Línea de pulso del hero — motivo visual de "telemetría / vigilancia continua".
   Respeta prefers-reduced-motion (dibuja una vez, sin animar). */
(function () {
  var c = document.getElementById('pulse');
  if (!c) return;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var ctx = c.getContext('2d');
  var w, h, dpr;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    w = c.clientWidth; h = c.clientHeight;
    c.width = w * dpr; c.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener('resize', resize);

  function color() {
    return getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#0E5A54';
  }

  // Forma de un latido tipo ECG, repetida horizontalmente.
  function beatY(x, phase) {
    var t = ((x * 0.012 + phase) % 6);
    var base = h * 0.62;
    if (t < 2.6 || t > 3.9) return base + Math.sin(x * 0.02) * 4;
    var p = (t - 2.6) / 1.3;
    if (p < 0.15) return base - p / 0.15 * 8;
    if (p < 0.30) return base - 8 + (p - 0.15) / 0.15 * 8;
    if (p < 0.42) return base + (p - 0.30) / 0.12 * 10;
    if (p < 0.58) return base + 10 - (p - 0.42) / 0.16 * (10 + h * 0.30);
    if (p < 0.72) return base - h * 0.30 + (p - 0.58) / 0.14 * (h * 0.30 + 16);
    if (p < 0.85) return base + 16 - (p - 0.72) / 0.13 * 16;
    return base;
  }

  function draw(phase) {
    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    for (var x = 0; x <= w; x += 2) {
      var y = beatY(x, phase);
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color();
    ctx.globalAlpha = 0.7;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.stroke();
  }

  if (reduce) { draw(0); return; }
  var phase = 0;
  (function loop() {
    phase += 0.05;
    draw(phase);
    requestAnimationFrame(loop);
  })();
})();
