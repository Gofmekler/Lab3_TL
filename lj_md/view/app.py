"""View (серверная часть): тонкий HTTP-слой над ViewModel.

Здесь нет ни физики, ни бизнес-логики: каждый маршрут только передаёт
действие пользователя во ViewModel и возвращает её ``state()`` в JSON.
Каждому браузеру (сессии) — своя ViewModel.
"""

from __future__ import annotations

import secrets
import threading
from collections import OrderedDict

from flask import Flask, Response, jsonify, render_template, request

from ..viewmodel import SimulationViewModel

SESSION_COOKIE = "lj_md_session"
MAX_SESSIONS = 32


class ViewModelRegistry:
    """Хранит ViewModel для каждой сессии (вытесняет самые старые)."""

    def __init__(self, limit: int = MAX_SESSIONS) -> None:
        self._items: OrderedDict[str, SimulationViewModel] = OrderedDict()
        self._lock = threading.Lock()
        self.limit = limit

    def get(self, key: str) -> SimulationViewModel:
        with self._lock:
            vm = self._items.get(key)
            if vm is None:
                vm = self._items[key] = SimulationViewModel()
                while len(self._items) > self.limit:
                    self._items.popitem(last=False)
            self._items.move_to_end(key)
            return vm


def create_app() -> Flask:
    app = Flask(__name__)
    registry = ViewModelRegistry()

    def current_vm() -> tuple[SimulationViewModel, str | None]:
        sid = request.cookies.get(SESSION_COOKIE)
        new_sid = None
        if not sid:
            sid = new_sid = secrets.token_hex(16)
        return registry.get(sid), new_sid

    def respond(payload, new_sid: str | None, status: int = 200) -> Response:
        resp = jsonify(payload)
        resp.status_code = status
        if new_sid:
            resp.set_cookie(SESSION_COOKIE, new_sid, httponly=True, samesite="Lax")
        return resp

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/schema")
    def schema():
        return jsonify(SimulationViewModel.schema())

    @app.get("/api/state")
    def state():
        vm, sid = current_vm()
        return respond(vm.state(), sid)

    @app.post("/api/tick")
    def tick():
        vm, sid = current_vm()
        vm.tick()
        return respond(vm.state(), sid)

    @app.post("/api/command/<name>")
    def command(name: str):
        vm, sid = current_vm()
        try:
            vm.execute(name)
        except KeyError as exc:
            return respond({"error": str(exc)}, sid, 404)
        return respond(vm.state(), sid)

    @app.post("/api/params")
    def params():
        vm, sid = current_vm()
        vm.update_parameters(request.get_json(silent=True) or {})
        return respond(vm.state(), sid)

    @app.post("/api/preset/<name>")
    def preset(name: str):
        vm, sid = current_vm()
        try:
            vm.apply_preset(name)
        except KeyError as exc:
            return respond({"error": str(exc)}, sid, 404)
        return respond(vm.state(), sid)

    @app.get("/api/export.csv")
    def export_csv():
        vm, _ = current_vm()
        return Response(vm.export_csv(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=lj_md_history.csv"})

    @app.get("/api/export.json")
    def export_json():
        vm, _ = current_vm()
        return Response(vm.export_json(), mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=lj_md_report.json"})

    return app
