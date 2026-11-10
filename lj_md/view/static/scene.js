/* Отрисовка атомов в ячейке. 2D — вид сверху, 3D — ортографическая проекция,
   камеру можно вращать мышью/пальцем (это чисто визуальное состояние View). */
"use strict";

function speedColor(t) {
  // t ∈ [0, 1]: синий → зелёный → жёлтый → красный
  const hue = 220 - 220 * Math.min(Math.max(t, 0), 1);
  return `hsl(${hue} 75% 52%)`;
}

class SceneRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.yaw = 0.6;
    this.pitch = 0.45;
    this.frame = null;
    this._bindRotation();
  }

  _bindRotation() {
    let last = null;
    this.canvas.addEventListener("pointerdown", e => {
      last = [e.clientX, e.clientY];
      this.canvas.setPointerCapture(e.pointerId);
    });
    this.canvas.addEventListener("pointermove", e => {
      if (!last || !this.frame || this.frame.dim !== 3) return;
      this.yaw += (e.clientX - last[0]) * 0.01;
      this.pitch = Math.max(-1.5, Math.min(1.5, this.pitch + (e.clientY - last[1]) * 0.01));
      last = [e.clientX, e.clientY];
      this.draw(this.frame);
    });
    const end = () => { last = null; };
    this.canvas.addEventListener("pointerup", end);
    this.canvas.addEventListener("pointercancel", end);
  }

  /** Повернуть точку (координаты относительно центра ячейки). */
  _rotate([x, y, z]) {
    const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw);
    const cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
    const x1 = cy * x + sy * z, z1 = -sy * x + cy * z;
    const y1 = cp * y - sp * z1, z2 = sp * y + cp * z1;
    return [x1, y1, z2];
  }

  draw(frame) {
    this.frame = frame;
    const { ctx, width, height } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, width, height);
    if (!frame) {
      ctx.fillStyle = cssVar("--muted");
      ctx.textAlign = "center";
      ctx.fillText("Система не создана — нажмите «Сброс»", width / 2, height / 2);
      return;
    }
    if (frame.dim === 2) this._draw2d(ctx, width, height, frame);
    else this._draw3d(ctx, width, height, frame);
  }

  _speedScale(speeds) {
    // нормируем по 95-му перцентилю, чтобы единичные быстрые атомы не «съели» шкалу
    const sorted = [...speeds].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length * 0.95)] || 1;
  }

  _draw2d(ctx, width, height, frame) {
    const pad = 12;
    const scale = (Math.min(width, height) - 2 * pad) / frame.box;
    const ox = (width - frame.box * scale) / 2, oy = (height - frame.box * scale) / 2;
    this._drawBoxOutline(ctx, frame, () => {
      ctx.strokeRect(ox, oy, frame.box * scale, frame.box * scale);
    });

    const r = Math.max(1.5, 0.5 * scale);   // радиус атома = σ/2
    const vmax = this._speedScale(frame.speeds);
    const periodic = frame.boundary === "periodic";
    ctx.save();
    ctx.beginPath();
    ctx.rect(ox, oy, frame.box * scale, frame.box * scale);
    ctx.clip();
    frame.positions.forEach(([x, y], i) => {
      ctx.fillStyle = speedColor(frame.speeds[i] / vmax);
      // при PBC дорисовываем «тень» атома у противоположной стенки
      const xs = [x], ys = [y];
      if (periodic) {
        if (x < 0.5) xs.push(x + frame.box); else if (x > frame.box - 0.5) xs.push(x - frame.box);
        if (y < 0.5) ys.push(y + frame.box); else if (y > frame.box - 0.5) ys.push(y - frame.box);
      }
      for (const xx of xs) for (const yy of ys) {
        ctx.beginPath();
        ctx.arc(ox + xx * scale, oy + (frame.box - yy) * scale, r, 0, 2 * Math.PI);
        ctx.fill();
      }
    });
    ctx.restore();
  }

  _draw3d(ctx, width, height, frame) {
    const L = frame.box, h = L / 2;
    const scale = (Math.min(width, height) - 24) / (L * Math.sqrt(3));
    const project = p => {
      const [x, y, z] = this._rotate([p[0] - h, p[1] - h, p[2] - h]);
      return [width / 2 + x * scale, height / 2 - y * scale, z];
    };

    // рёбра куба
    const corners = [];
    for (const a of [0, L]) for (const b of [0, L]) for (const c of [0, L]) corners.push(project([a, b, c]));
    const edges = [[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];
    this._drawBoxOutline(ctx, frame, () => {
      ctx.beginPath();
      for (const [i, j] of edges) {
        ctx.moveTo(corners[i][0], corners[i][1]);
        ctx.lineTo(corners[j][0], corners[j][1]);
      }
      ctx.stroke();
    });

    // атомы: сортировка по глубине (painter's algorithm)
    const vmax = this._speedScale(frame.speeds);
    const pts = frame.positions.map((p, i) => [...project(p), i]);
    pts.sort((a, b) => a[2] - b[2]);
    for (const [x, y, z, i] of pts) {
      const depth = 0.75 + 0.25 * (z / (L * 0.87));   // ближние крупнее и ярче
      ctx.globalAlpha = Math.min(1, Math.max(0.35, depth));
      ctx.fillStyle = speedColor(frame.speeds[i] / vmax);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(1.5, 0.5 * scale * depth), 0, 2 * Math.PI);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  _drawBoxOutline(ctx, frame, path) {
    ctx.strokeStyle = cssVar("--box");
    ctx.lineWidth = frame.boundary === "periodic" ? 1 : 3;
    ctx.setLineDash(frame.boundary === "periodic" ? [6, 5] : []);
    path();
    ctx.setLineDash([]);
  }
}

window.SceneRenderer = SceneRenderer;
