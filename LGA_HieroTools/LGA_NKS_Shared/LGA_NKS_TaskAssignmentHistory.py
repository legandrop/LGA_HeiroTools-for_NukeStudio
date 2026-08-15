"""
____________________________________________________________________

  LGA_NKS_TaskAssignmentHistory v1.00 | Lega

  Historial de artistas de una task (quien estuvo asignado y cuando), leido
  de `task_assignment_history` en `pipesync_stats.db`.

  Port de `TaskAssignmentHistory.cpp` / `TaskAssignmentHistory.h` de PipeSync.
  Solo lectura. Si la stats DB o la tabla no existen todavia, devuelve lista
  vacia (estado normal: maquina recien instalada o sync pendiente).

  Usado por:
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py
____________________________________________________________________

"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from LGA_NKS_PipeSyncPaths import get_pipesync_db_path

STATS_DB_FILENAME = "pipesync_stats.db"
_LOG = logging.getLogger("LGA_NKS_TaskAssignmentHistory")


@dataclass
class Span:
    """Un tramo de asignacion de una persona a una task."""

    user_id: int
    user_name: str
    from_dt: Optional[datetime] = None
    to_dt: Optional[datetime] = None
    ended: bool = False

    def is_active(self) -> bool:
        return (not self.ended) and (self.to_dt is None)


def _parse_flow_date(raw: Optional[str]) -> Optional[datetime]:
    """ISO 8601 con offset -> datetime aware en hora local (naive local)."""
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    # fromisoformat entiende "2026-05-28T09:50:59-03:00" y con milis.
    iso = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text[:26], fmt) if "%f" in fmt else datetime.strptime(text[:19], fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # A hora local naive, igual que PipeSync (toLocalTime) para comparar vs notas.
    return dt.astimezone().replace(tzinfo=None)


def _open_stats_ro() -> Optional[sqlite3.Connection]:
    import os

    path = get_pipesync_db_path(STATS_DB_FILENAME)
    if not path or not os.path.exists(path):
        _LOG.warning(
            "No existe todavia la stats DB (%s). Las notas se muestran sin historial.",
            path,
        )
        return None
    try:
        # Sin URI mode=ro: en algunos entornos el sandbox bloquea file: URIs.
        # Solo leemos; no hay writes en este modulo.
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        _LOG.error("No se pudo abrir la stats DB (%s): %s", path, exc)
        return None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    )
    return cur.fetchone() is not None


def load_for_task(task_sg_id: int) -> List[Span]:
    """Carga los tramos de asignacion de una task (id de Flow)."""
    spans: List[Span] = []
    if not task_sg_id or task_sg_id <= 0:
        return spans

    conn = _open_stats_ro()
    if conn is None:
        return spans

    try:
        if not _table_exists(conn, "task_assignment_history"):
            _LOG.warning(
                "La stats DB no tiene todavia task_assignment_history para task %s.",
                task_sg_id,
            )
            return spans

        events: List[Tuple[int, str, bool, Optional[datetime]]] = []
        cur = conn.execute(
            "SELECT user_id, user_name, action, changed_at, event_id "
            "FROM task_assignment_history "
            "WHERE task_id = ? "
            "ORDER BY changed_at ASC, event_id ASC, action ASC",
            (task_sg_id,),
        )
        for row in cur.fetchall():
            uid = int(row["user_id"] or 0)
            if uid <= 0:
                continue
            events.append(
                (
                    uid,
                    (row["user_name"] or "").strip(),
                    (row["action"] or "").strip() == "added",
                    _parse_flow_date(row["changed_at"]),
                )
            )

        current: Dict[int, str] = {}
        try:
            cur = conn.execute(
                "SELECT ta.user_id, COALESCE(u.name, '') AS name "
                "FROM task_assignments ta "
                "LEFT JOIN users u ON u.id = ta.user_id "
                "WHERE ta.task_id = ? AND ta.role = 'assignee'",
                (task_sg_id,),
            )
            for row in cur.fetchall():
                uid = int(row["user_id"] or 0)
                if uid > 0:
                    current[uid] = (row["name"] or "").strip()
        except sqlite3.Error as exc:
            _LOG.error(
                "Fallo la consulta de assignees actuales de la task %s: %s",
                task_sg_id,
                exc,
            )

        open_index: Dict[int, int] = {}
        for uid, uname, added, when in events:
            if added:
                if uid in open_index:
                    continue
                spans.append(Span(user_id=uid, user_name=uname, from_dt=when))
                open_index[uid] = len(spans) - 1
            else:
                idx = open_index.pop(uid, -1)
                if idx >= 0:
                    spans[idx].to_dt = when
                    spans[idx].ended = True
                else:
                    spans.append(
                        Span(user_id=uid, user_name=uname, to_dt=when, ended=True)
                    )

        for uid, uname in current.items():
            if uid in open_index:
                continue
            has_open = any(s.user_id == uid and s.is_active() for s in spans)
            if not has_open:
                spans.append(Span(user_id=uid, user_name=uname))

        for span in spans:
            current_name = current.get(span.user_id, "").strip()
            if current_name:
                span.user_name = current_name

        if current:
            for span in spans:
                if span.is_active() and span.user_id not in current:
                    span.ended = True

        def _sort_key(s: Span):
            active = s.is_active()
            key = s.from_dt if active else s.to_dt
            # Activos primero; dentro, mas reciente primero; sin fecha al final del grupo.
            return (
                0 if active else 1,
                0 if key is None else 1,
                -(key.timestamp()) if key is not None else 0,
                s.user_name.casefold(),
            )

        spans.sort(key=_sort_key)
        return spans
    finally:
        conn.close()


def currently_active(spans: List[Span]) -> List[str]:
    names: List[str] = []
    seen: Set[int] = set()
    for span in spans:
        if span.is_active() and span.user_name.strip() and span.user_id not in seen:
            seen.add(span.user_id)
            names.append(span.user_name.strip())
    return names


def active_at(spans: List[Span], moment: Optional[datetime]) -> List[str]:
    if moment is None:
        return currently_active(spans)
    # Normalizar a naive local para comparar con los tramos (tambien naive local).
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)

    names: List[str] = []
    seen: Set[int] = set()
    for span in spans:
        started = span.from_dt is None or span.from_dt <= moment
        if span.to_dt is not None:
            not_ended = span.to_dt >= moment
        else:
            not_ended = not span.ended
        if started and not_ended and span.user_name.strip() and span.user_id not in seen:
            seen.add(span.user_id)
            names.append(span.user_name.strip())
    return names


@dataclass
class PersonHistory:
    """Resumen por persona para la franja UI (un nodo/chip, no un tramo)."""

    user_id: int
    name: str
    active: bool = False
    active_since: Optional[datetime] = None
    first_from: Optional[datetime] = None
    last_to: Optional[datetime] = None
    periods: List[str] = field(default_factory=list)


def persons_from_spans(spans: List[Span], history_date_fmt) -> List[PersonHistory]:
    """Agrupa tramos por persona y ordena como la UI de PipeSync."""
    order: List[int] = []
    people: Dict[int, PersonHistory] = {}

    for span in spans:
        name = (span.user_name or "").strip()
        if not name:
            continue
        if span.user_id not in people:
            order.append(span.user_id)
            people[span.user_id] = PersonHistory(user_id=span.user_id, name=name)
        person = people[span.user_id]
        person.name = name
        if span.is_active():
            person.active = True
            if span.from_dt and (
                person.active_since is None or span.from_dt > person.active_since
            ):
                person.active_since = span.from_dt
        if span.from_dt and (
            person.first_from is None or span.from_dt < person.first_from
        ):
            person.first_from = span.from_dt
        if span.to_dt and (person.last_to is None or span.to_dt > person.last_to):
            person.last_to = span.to_dt
        person.periods.append(_describe_span(span, history_date_fmt))

    ordered = [people[uid] for uid in order]

    def _cmp_key(p: PersonHistory):
        # Activos primero. Entre past: sale mas reciente primero. Entre empates:
        # el que entro ultimo mas a la izquierda. Sin fecha de inicio = lo mas viejo.
        if p.active:
            a_from = p.active_since
            return (
                0,
                0 if a_from is not None else 1,
                -(a_from.timestamp()) if a_from is not None else 0,
                p.name.casefold(),
            )
        return (
            1,
            0 if p.last_to is not None else 1,
            -(p.last_to.timestamp()) if p.last_to is not None else 0,
            0 if p.first_from is not None else 1,
            -(p.first_from.timestamp()) if p.first_from is not None else 0,
            p.name.casefold(),
        )

    ordered.sort(key=_cmp_key)
    return ordered


def _describe_span(span: Span, history_date_fmt) -> str:
    if span.is_active():
        if span.from_dt:
            return f"desde {history_date_fmt(span.from_dt)}"
        return "asignado (sin fecha de alta)"
    if span.from_dt and span.to_dt:
        a = history_date_fmt(span.from_dt)
        b = history_date_fmt(span.to_dt)
        return a if a == b else f"{a} – {b}"
    if span.to_dt:
        return f"hasta {history_date_fmt(span.to_dt)}"
    if span.from_dt:
        return f"desde {history_date_fmt(span.from_dt)}"
    return "periodo desconocido"
