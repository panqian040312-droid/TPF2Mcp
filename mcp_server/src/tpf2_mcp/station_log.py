"""Persistent station stop/pass event log derived from live rail frames."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from .save_scope import LEGACY_SAVE_ID


class StationEventStore:
    # 同一（车、站、类型）在该游戏时间窗口内重复上报，视为同一次到站。
    DUPLICATE_WINDOW_MS = 8000
    # 车辆连续缺帧超过该帧数后，放弃其 presence 记录（防止误判为重新到站）。
    PRESENCE_TTL_FRAMES = 5

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._presence: dict[int, str] = {}
        self._active_save_id: str | None = None
        self._last_emit: dict[tuple[int, int, str], int | None] = {}
        self._frame_index = 0
        self._presence_frame: dict[int, int] = {}

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS station_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id INTEGER NOT NULL,
                station_name TEXT NOT NULL,
                observed_at REAL NOT NULL,
                game_time_ms INTEGER,
                event_type TEXT NOT NULL CHECK(event_type IN ('STOP','PASS')),
                line_id INTEGER,
                line_name TEXT NOT NULL,
                vehicle_id INTEGER NOT NULL,
                vehicle_name TEXT NOT NULL
            )"""
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(station_events)")}
        if "save_id" not in columns:
            connection.execute(
                f"ALTER TABLE station_events ADD COLUMN save_id TEXT NOT NULL DEFAULT '{LEGACY_SAVE_ID}'"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS station_events_station_time ON station_events(station_id, observed_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS station_events_save_station_time ON station_events(save_id,station_id,observed_at DESC)"
        )
        return connection

    def record_frame(self, frame: dict[str, Any], manifest: dict[str, Any], save_id: str, observed_at: float | None = None) -> int:
        if not isinstance(save_id, str) or not save_id:
            raise ValueError("station event frame requires save_id")
        if self._active_save_id != save_id:
            self._presence = {}
            self._last_emit = {}
            self._presence_frame = {}
            self._active_save_id = save_id
        self._frame_index += 1
        lines = {line.get("entity_id"): line for line in manifest.get("lines", [])}
        stations = manifest.get("stations", [])
        station_by_id = {station.get("entity_id"): station for station in stations}
        stations_by_platform_edge: dict[int, list[dict[str, Any]]] = {}
        for station in stations:
            for terminal in station.get("terminals", []):
                for edge_id in terminal.get("platform_edge_ids", []):
                    values = stations_by_platform_edge.setdefault(edge_id, [])
                    if station not in values:
                        values.append(station)
        now = time.time() if observed_at is None else observed_at
        game_time = ((frame.get("simulation") or {}).get("clock") or {}).get("game_time")
        current: dict[int, str] = {}
        pending: list[tuple[Any, ...]] = []
        for vehicle in frame.get("vehicles", []):
            vehicle_id = vehicle.get("entity_id")
            if not isinstance(vehicle_id, int):
                continue
            line = lines.get(vehicle.get("line_id"), {})
            stops = line.get("stops", [])
            stop_index = vehicle.get("stop_index")
            target = stops[stop_index] if isinstance(stop_index, int) and 0 <= stop_index < len(stops) else {}
            station = station_by_id.get(target.get("station_group_id")) if vehicle.get("raw_state") == 2 else None
            event_type = "STOP" if station is not None else None
            if station is None and float(vehicle.get("speed_kmh") or 0) > 2:
                # A station's broad construction bounds can include adjacent
                # main lines, especially at marshalling yards. A pass event is
                # valid only on an observed platform/terminal track edge.
                candidates = stations_by_platform_edge.get(vehicle.get("edge_id"), [])
                station = next((item for item in candidates if not any(
                    stop.get("station_group_id") == item.get("entity_id") for stop in stops)), None)
                if station is not None:
                    event_type = "PASS"
            if station is None or event_type is None:
                continue
            station_id = station.get("entity_id")
            presence = f"{station_id}:{event_type}"
            current[vehicle_id] = presence
            self._presence_frame[vehicle_id] = self._frame_index
            stamp = int(game_time) if isinstance(game_time, (int, float)) else None
            if self._presence.get(vehicle_id) == presence:
                continue
            # 车辆可能因采样缺帧、或在站内短暂脱离站台轨道而丢失 presence，
            # 下一帧在同一站、同一类型重新出现——那不是新的到站事件。
            # 按（车、站、类型）在游戏时间窗口内去重，避免同一次停站被记两次。
            ledger_key = (vehicle_id, station_id, event_type)
            previous = self._last_emit.get(ledger_key)
            if stamp is not None and previous is not None and 0 <= stamp - previous < self.DUPLICATE_WINDOW_MS:
                continue
            self._last_emit[ledger_key] = stamp if stamp is not None else previous
            pending.append((save_id, station_id, station.get("name") or f"车站 {station_id}", now,
                            stamp, event_type,
                            vehicle.get("line_id"), line.get("name") or f"线路 {vehicle.get('line_id')}",
                            vehicle_id, vehicle.get("name") or f"列车{vehicle_id}"))
        # 保留短暂缺帧车辆的 presence：缺帧不等于离开车站，否则回到同站会被当成新到站。
        merged = {
            vehicle_id: presence
            for vehicle_id, presence in self._presence.items()
            if self._frame_index - self._presence_frame.get(vehicle_id, -(10 ** 9)) <= self.PRESENCE_TTL_FRAMES
        }
        merged.update(current)
        self._presence = merged
        if not pending:
            return 0
        with self._lock, closing(self._connect()) as connection:
            with connection:
                connection.executemany(
                    """INSERT INTO station_events
                       (save_id,station_id,station_name,observed_at,game_time_ms,event_type,line_id,line_name,vehicle_id,vehicle_name)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""", pending)
        return len(pending)

    def query(self, station_id: int, save_id: str, limit: int = 100) -> list[dict[str, Any]]:
        bounded = max(1, min(500, int(limit)))
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                    """SELECT id,save_id,station_id,station_name,observed_at,game_time_ms,event_type,
                              line_id,line_name,vehicle_id,vehicle_name
                       FROM station_events WHERE save_id=? AND station_id=? ORDER BY observed_at DESC,id DESC LIMIT ?""",
                    (save_id, station_id, bounded),
                ).fetchall()
        return [dict(row) for row in rows]
