/* Простые линейные графики на canvas (без внешних библиотек). */
"use strict";

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Подогнать размер буфера canvas под CSS-размер и devicePixelRatio. */
function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
  const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width: canvas.clientWidth, height: canvas.clientHeight };
}

function formatTick(v) {
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.01 || a >= 1e4)) return v.toExponential(1);
  return Number(v.toPrecision(3)).toString();
}

class LineChart {
  constructor(canvas, { xLabel = "", reference = null } = {}) {
    this.canvas = canvas;
    this.xLabel = xLabel;
    this.reference = reference; // горизонтальная линия (например g = 1)
  }

  /** series: [{label, color, x: [], y: []}] */
  draw(series) {
    const { ctx, width, height } = fitCanvas(this.canvas);
    const pad = { l: 52, r: 10, t: 22, b: 26 };
    ctx.clearRect(0, 0, width, height);
    ctx.font = "11px system-ui, sans-serif";

    const xs = series.flatMap(s => s.x);
    const ys = series.flatMap(s => s.y).filter(Number.isFinite);
    if (this.reference !== null) ys.push(this.reference);
    if (xs.length < 2 || ys.length === 0) {
      ctx.fillStyle = cssVar("--muted");
      ctx.fillText("нет данных — запустите моделирование", pad.l, height / 2);
      return;
    }
    let [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    let [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    if (x1 === x0) x1 = x0 + 1;
    if (y1 - y0 < 1e-9) { y0 -= 0.5; y1 += 0.5; }
    const margin = (y1 - y0) * 0.08;
    y0 -= margin; y1 += margin;

    const px = x => pad.l + (x - x0) / (x1 - x0) * (width - pad.l - pad.r);
    const py = y => height - pad.b - (y - y0) / (y1 - y0) * (height - pad.t - pad.b);

    // сетка и подписи осей
    ctx.strokeStyle = cssVar("--grid");
    ctx.fillStyle = cssVar("--muted");
    ctx.lineWidth = 1;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const y = y0 + (y1 - y0) * i / 4;
      ctx.beginPath(); ctx.moveTo(pad.l, py(y)); ctx.lineTo(width - pad.r, py(y)); ctx.stroke();
      ctx.fillText(formatTick(y), pad.l - 6, py(y));
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let i = 0; i <= 4; i++) {
      const x = x0 + (x1 - x0) * i / 4;
      ctx.fillText(formatTick(x), px(x), height - pad.b + 6);
    }
    if (this.xLabel) {
      ctx.textAlign = "right";
      ctx.fillText(this.xLabel, width - pad.r, height - pad.b - 14);
    }

    if (this.reference !== null) {
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = cssVar("--box");
      ctx.beginPath();
      ctx.moveTo(pad.l, py(this.reference)); ctx.lineTo(width - pad.r, py(this.reference));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // линии
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    for (const s of series) {
      ctx.strokeStyle = s.color;
      ctx.beginPath();
      s.x.forEach((x, i) => {
        const fn = i === 0 ? "moveTo" : "lineTo";
        ctx[fn](px(x), py(s.y[i]));
      });
      ctx.stroke();
    }

    // легенда
    if (series.length > 1) {
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      let lx = pad.l;
      for (const s of series) {
        ctx.fillStyle = s.color;
        ctx.fillRect(lx, 6, 12, 3);
        ctx.fillStyle = cssVar("--text");
        ctx.fillText(s.label, lx + 16, 8);
        lx += ctx.measureText(s.label).width + 34;
      }
    }
  }
}

window.LineChart = LineChart;
window.cssVar = cssVar;
window.fitCanvas = fitCanvas;
