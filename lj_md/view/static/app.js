/* View (клиент): привязка DOM к состоянию ViewModel.

   Принцип MVVM: страница не хранит модель и ничего не считает.
   - data-bind="путь"     → текст элемента = значение из state по пути;
   - data-command="имя"   → клик вызывает команду ViewModel, disabled = !state.can[имя];
   - форма параметров строится по схеме полей, которую отдаёт ViewModel.
*/
"use strict";

const api = {
  async get(url) { return (await fetch(url)).json(); },
  async post(url, body) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return resp.json();
  },
};

const getPath = (obj, path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);

class View {
  constructor() {
    this.state = null;
    this.schema = null;
    this.loopActive = false;
    this.scene = new SceneRenderer(document.getElementById("scene"));
    this.charts = {
      energy: new LineChart(document.getElementById("chart-energy"), { xLabel: "t" }),
      temperature: new LineChart(document.getElementById("chart-temperature"), { xLabel: "t" }),
      pressure: new LineChart(document.getElementById("chart-pressure"), { xLabel: "t" }),
      rdf: new LineChart(document.getElementById("chart-rdf"), { xLabel: "r / σ", reference: 1 }),
    };
    this.form = document.getElementById("params-form");
  }

  async init() {
    this.schema = await api.get("/api/schema");
    this.buildForm();
    this.buildPresets();
    this.bindCommands();
    window.addEventListener("resize", () => this.render());
    window.matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", () => this.render());
    this.apply(await api.get("/api/state"), { syncForm: true });
  }

  // --- построение формы по схеме ViewModel -------------------------------

  buildForm() {
    const root = document.getElementById("fields");
    for (const f of this.schema.fields) {
      const wrap = document.createElement("div");
      wrap.className = "field";
      wrap.dataset.field = f.name;

      const label = document.createElement("label");
      label.htmlFor = `f-${f.name}`;
      label.textContent = f.label;
      if (f.live) {
        const tag = document.createElement("span");
        tag.className = "live-tag";
        tag.textContent = "live";
        label.appendChild(tag);
      }

      let input;
      if (f.kind === "choice") {
        input = document.createElement("select");
        for (const o of f.options) {
          const opt = document.createElement("option");
          opt.value = o.value;
          opt.textContent = o.label;
          input.appendChild(opt);
        }
      } else {
        input = document.createElement("input");
        input.type = "number";
        input.inputMode = f.kind === "int" ? "numeric" : "decimal";
        if (f.min !== null) input.min = f.min;
        if (f.max !== null) input.max = f.max;
        if (f.step !== null) input.step = f.step;
      }
      input.id = `f-${f.name}`;
      input.name = f.name;
      if (f.live) input.addEventListener("change", () => this.submitParams([f.name]));

      const error = document.createElement("div");
      error.className = "error";
      wrap.append(label, input, error);
      if (f.hint) {
        const hint = document.createElement("div");
        hint.className = "hint";
        hint.textContent = f.hint;
        wrap.appendChild(hint);
      }
      root.appendChild(wrap);
    }
    this.form.addEventListener("submit", e => {
      e.preventDefault();
      this.submitParams(this.schema.fields.map(f => f.name));
    });
  }

  buildPresets() {
    const root = document.getElementById("presets");
    for (const p of this.schema.presets) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn";
      btn.textContent = p.label;
      btn.addEventListener("click", async () => {
        this.apply(await api.post(`/api/preset/${p.name}`), { syncForm: true });
      });
      root.appendChild(btn);
    }
  }

  async submitParams(names) {
    const data = {};
    for (const n of names) data[n] = this.form.elements[n].value;
    const state = await api.post("/api/params", data);
    this.apply(state, { syncForm: Object.keys(state.errors).length === 0 });
  }

  syncForm() {
    for (const [name, value] of Object.entries(this.state.params)) {
      const el = this.form.elements[name];
      if (el) el.value = value;
    }
  }

  // --- команды -----------------------------------------------------------

  bindCommands() {
    document.querySelectorAll("[data-command]").forEach(btn => {
      btn.addEventListener("click", async () => {
        this.apply(await api.post(`/api/command/${btn.dataset.command}`));
      });
    });
  }

  // --- применение нового состояния ----------------------------------------

  apply(state, { syncForm = false } = {}) {
    if (state.error) { console.error(state.error); return; }
    this.state = state;
    if (syncForm) this.syncForm();
    this.render();
    if (state.is_running && !this.loopActive) this.loop();
  }

  async loop() {
    this.loopActive = true;
    while (this.state && this.state.is_running) {
      const started = performance.now();
      try {
        this.apply(await api.post("/api/tick"));
      } catch (err) {
        console.error(err);
        break;
      }
      // не чаще ~30 кадров в секунду
      const wait = 33 - (performance.now() - started);
      await new Promise(r => (wait > 0 ? setTimeout(r, wait) : requestAnimationFrame(r)));
    }
    this.loopActive = false;
  }

  render() {
    const s = this.state;
    if (!s) return;

    document.querySelectorAll("[data-bind]").forEach(el => {
      const v = getPath(s, el.dataset.bind);
      el.textContent = v === undefined || v === null ? "—" : v;
    });
    document.getElementById("rdf-samples").textContent = `(усреднено по ${s.rdf.samples} кадрам)`;

    document.querySelectorAll("[data-command]").forEach(btn => {
      btn.disabled = !s.can[btn.dataset.command];
    });

    const status = document.querySelector("[data-bind-status]");
    status.textContent = s.status.text;
    status.className = `status ${s.status.kind}${s.is_running && s.status.kind !== "error" ? " running" : ""}`;

    document.querySelectorAll(".field").forEach(el => {
      const msg = s.errors[el.dataset.field] || "";
      el.classList.toggle("invalid", Boolean(msg));
      el.querySelector(".error").textContent = msg;
    });

    document.getElementById("scene-hint").textContent =
      s.frame && s.frame.dim === 3 ? "Перетащите мышью, чтобы повернуть ячейку" : "";

    this.scene.draw(s.frame);
    this.renderCharts();
  }

  renderCharts() {
    const ser = this.state.series || {};
    const t = ser.time || [];
    const [c1, c2, c3] = ["--s1", "--s2", "--s3"].map(cssVar);
    this.charts.energy.draw([
      { label: "E_kin", color: c2, x: t, y: ser.kinetic || [] },
      { label: "E_pot", color: c1, x: t, y: ser.potential || [] },
      { label: "E", color: c3, x: t, y: ser.total || [] },
    ]);
    this.charts.temperature.draw([{ label: "T", color: c2, x: t, y: ser.temperature || [] }]);
    this.charts.pressure.draw([{ label: "P", color: c1, x: t, y: ser.pressure || [] }]);
    this.charts.rdf.draw([{ label: "g(r)", color: c3, x: this.state.rdf.r, y: this.state.rdf.g }]);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new View().init().catch(err => {
    document.querySelector("[data-bind-status]").textContent = `Ошибка: ${err}`;
  });
});
