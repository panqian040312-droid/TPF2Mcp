"""Local read-only HTTP/SSE host for the TPF2 railway dispatch map."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPOSITORY = next(p for p in Path(__file__).resolve().parents if (p / ".git").is_dir())
sys.path.insert(0, str(REPOSITORY / "mcp_server" / "src"))

from tpf2_mcp.bridge import BridgeClient, BridgeError  # noqa: E402
from tpf2_mcp.config import bridge_dir  # noqa: E402
from tpf2_mcp.dispatch import vehicle_dispatch_state  # noqa: E402
from tpf2_mcp.rail_live import RailSpatialIndex, derive_blocks, normalize_live_state, normalize_signals  # noqa: E402
from tpf2_mcp.save_scope import snapshot_save_id  # noqa: E402
from tpf2_mcp.snapshot import SnapshotIndex  # noqa: E402
from tpf2_mcp.station_log import StationEventStore  # noqa: E402
from tpf2_mcp.work_log import McpWorkLogStore  # noqa: E402


TILE_KEY = re.compile(r"^-?[0-9]+_-?[0-9]+$")
# 图层名只允许小写字母开头 + 字母/数字/下划线/连字符，防止路径穿越到 layers/ 之外
LAYER_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
# One full round trip on this large save can exceed fifteen real minutes.  Keep
# the UI from proposing another consist until the recently added train has had a
# realistic chance to leave its depot and contribute representative demand data.
FLEET_CHANGE_STABILIZATION_SECONDS = 60 * 60
HIGH_SPEED_CONSIST_THRESHOLD_KMH = 250.0
WORK_ACTION_LABELS = {
    "BUY_VEHICLE": "购买车辆",
    "ASSIGN_VEHICLE_TO_LINE": "车辆分配到线路",
    "SET_LINE_STOP_POLICY": "调整停站策略",
    "SET_LINE_STOPS": "调整线路停靠站台",
    "CREATE_LINE": "创建线路",
    "CREATE_LINE_FROM_SOURCE_ROUTE": "创建线路",
    "SELL_VEHICLE": "出售车辆",
    "RENAME_LINE": "重命名线路",
    "HOLD_VEHICLE": "扣停列车",
    "HOLD_VEHICLE_AT_TERMINAL": "扣停列车",
    "RELEASE_VEHICLE": "放行列车",
}


_OTHER_VEHICLE_CARRIERS = {"AIR", "WATER"}
_OTHER_VEHICLE_CACHE: dict = {"mtime": 0.0, "by_line": {}}


def carrier_by_line(bridge: Path) -> dict:
    """线路 id → 载具种类（AIR / WATER / ROAD / RAIL）。

    ⚠ 每轮 live（约 1.5 s）都会调用 → **按 mtime 缓存**，不要每次重新解析整个文件。
    `layer-lines.json` 是 mod 直接写出来的（271 条线，几十 KB），解析一次就够。
    """
    path = bridge / "layer-lines.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _OTHER_VEHICLE_CACHE["by_line"]
    if mtime != _OTHER_VEHICLE_CACHE["mtime"]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        mapping: dict = {}
        for line in data.get("lines") or []:
            entity_id = line.get("entity_id")
            if entity_id is not None and line.get("carrier"):
                mapping[str(entity_id)] = line["carrier"]
        _OTHER_VEHICLE_CACHE["mtime"] = mtime
        _OTHER_VEHICLE_CACHE["by_line"] = mapping
    return _OTHER_VEHICLE_CACHE["by_line"]


def build_other_vehicles(telemetry: dict, bridge: Path) -> tuple[list, list]:
    """船和飞机走**单独一路**，不进 `normalize_live_state`。

    原因（2026-09-29 实测）：它们的 `current_edge_id` **全为空** —— 不挂在
    `BASE_EDGE_TRACK` / `BASE_EDGE_STREET` 上，所以既会被铁路线路过滤掉，
    也没有轨道可以吸附。它们**只有包围盒坐标**（实测 88 艘 + 48 架全带位置）。

    前端按用户要求取用：飞机跟列车一样 500 ms 刷新，船 90 s 刷新一次。
    """
    carriers = carrier_by_line(bridge)
    air: list = []
    water: list = []
    for raw in telemetry.get("vehicles") or []:
        carrier = raw.get("carrier") or carriers.get(str(raw.get("line_id")))
        if carrier not in _OTHER_VEHICLE_CARRIERS:
            continue
        position = raw.get("position")
        if not isinstance(position, dict):
            continue
        x, y = position.get("x"), position.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        entry = {
            "entity_id": raw.get("entity_id"),
            "name": raw.get("name"),
            "line_id": raw.get("line_id"),
            "carrier": carrier,
            "x": round(float(x), 2),
            "y": round(float(y), 2),
            "z": round(float(position.get("z") or 0.0), 2),
            "speed_mps": raw.get("speed_mps") if isinstance(raw.get("speed_mps"), (int, float)) else None,
        }
        (air if carrier == "AIR" else water).append(entry)
    return air, water


def game_clock_status(simulation: dict | None) -> dict | None:
    """游戏内时间相对挂钟的推进速率。

    本机 CPU 跟不上时，TPF2 的仿真会跑得比挂钟慢：引擎自己给出的
    `simulation.deltas` 里同时含游戏毫秒与挂钟秒，两者之比就是速率。
    速率 < 1 时，用挂钟测出的时长必须除以 wall_seconds_per_game_second
    才是游戏内时间——运行图（相位图）用的是游戏时间，两者不能直接比。
    """
    deltas = (simulation or {}).get("deltas") or {}
    game_ms = deltas.get("game_time")
    wall = deltas.get("wall_seconds")
    if not isinstance(game_ms, (int, float)) or not isinstance(wall, (int, float)) or wall <= 0:
        return None
    rate = (game_ms / 1000.0) / wall
    if rate <= 0:
        return None
    return {
        "rate": round(rate, 3),
        "wall_seconds_per_game_second": round(1 / rate, 2),
        "window_seconds": round(wall, 2),
        "speed_multiplier": (simulation or {}).get("speed_multiplier"),
    }


class RailMapState:
    def __init__(self, root: Path, bridge: Path, exporter: Path, live_poll_seconds: float = 1.5):
        self.root = root
        self.bridge = bridge
        self.exporter = exporter
        self.stop = threading.Event()
        self.generation_lock = threading.Lock()
        self.live_lock = threading.Lock()
        self.live_poll_seconds = max(0.5, live_poll_seconds)
        self.last_live_poll = 0.0
        self.last_signal_poll = 0.0
        self.last_snapshot_poll = 0.0
        self.snapshot_poll_seconds = 3.0
        self.active_save_id: str | None = None
        self.save_switch_error: str | None = None
        self.live_error: str | None = None
        self.live_index: RailSpatialIndex | None = None
        self.live_network_mtime = 0
        self.live_control = None
        self.last_bridge_network_mtime = self._mtime(bridge / "rail-network.json")
        # 多图层：mod 侧自驱写出的 bridge/layer-*.json 由同目录的 export-layer-map.py 切块。
        # 从铁路 exporter 的目录推导，避免再多一个构造参数。
        self.exporter_layers = exporter.parent / "export-layer-map.py"
        self.last_layer_signature = None
        self.layers_error: str | None = None
        self.station_events = StationEventStore(bridge / "station-events.sqlite3")
        state_directory = bridge.parent / "tpf2_mcp_state"
        self.work_log = McpWorkLogStore(state_directory / "mcp-work-log.sqlite3")
        self.task_journal = state_directory / "tasks.jsonl"
        # --- 真实客流（引擎 get_line_demand）---
        self.demand_cache: dict[int, dict] = {}
        self.demand_lock = threading.Lock()
        self.demand_sweep = {"running": False, "done": 0, "total": 0, "started_at": None,
                             "finished_at": None, "errors": [], "last_error": None}
        self.demand_last_persist = 0.0
        self.demand_min_interval_seconds = 6.0   # 同一条线的最短重采间隔
        self.demand_stale_seconds = 900.0        # 超过这个时长算过期，触发自动全量采样
        # 货运线的判据是"候运是否持续增长"，不是实载率 → 需要留时间序列：
        # 每次采样记一条 (game_s, waiting, onboard)，供面板判断队列是否在积压。
        self.freight_history: dict[int, list[dict]] = {}
        self.freight_history_limit = 40
        self._live_clock_cache = (0.0, None)
        cached = self.read_json(bridge / "line-demand-live.json")
        if isinstance(cached, dict) and isinstance(cached.get("lines"), dict):
            for key, value in cached["lines"].items():
                try:
                    self.demand_cache[int(key)] = value
                except (TypeError, ValueError):
                    continue
        if isinstance(cached, dict) and isinstance(cached.get("cargo_history"), dict):
            for key, value in cached["cargo_history"].items():
                try:
                    line_id = int(key)
                except (TypeError, ValueError):
                    continue
                if isinstance(value, list):
                    self.freight_history[line_id] = value[-self.freight_history_limit:]

    def _plan_path(self) -> Path:
        return self.root.parents[1] / "diagnostics" / "rail-operations" / "line-timetable-plan.json"

    def current_save_id(self) -> str:
        return snapshot_save_id(self.read_json(self.bridge / "state.json"))

    @staticmethod
    def _mtime(path: Path) -> int:
        try:
            return path.stat().st_mtime_ns
        except FileNotFoundError:
            return 0

    @staticmethod
    def read_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

    def status(self) -> dict:
        heartbeat = self.read_json(self.bridge / "heartbeat.json")
        state = self.read_json(self.bridge / "state.json")
        manifest = self.read_json(self.root / "rail-network-manifest.json")
        save_id = self.current_save_id()
        telemetry = self.read_json(self.bridge / "operational-telemetry.json")
        live = self.read_json(self.bridge / "live-rail-state.json")
        age = max(0.0, time.time() - float(heartbeat.get("last_update", 0))) if heartbeat else None
        return {
            "bridge_connected": bool(heartbeat.get("bridge_ready")) and age is not None and age < 10,
            "heartbeat_age_seconds": round(age, 2) if age is not None else None,
            "snapshot_sequence": state.get("sequence") or heartbeat.get("snapshot_seq"),
            "snapshot_timestamp": state.get("timestamp"),
            "rail_generation": manifest.get("generated_at"),
            "save_id": save_id,
            "rail_save_id": manifest.get("save_id"),
            "save_transition": manifest.get("save_id") != save_id,
            "save_switch_error": self.save_switch_error,
            "rail_counts": manifest.get("counts"),
            "telemetry_generation": telemetry.get("generated_at"),
            "telemetry_counts": telemetry.get("counts"),
            "live_generation": live.get("sampled_at"),
            "live_counts": live.get("counts"),
            "simulation": live.get("simulation"),
            "game_clock": game_clock_status(live.get("simulation")),
            "live_error": self.live_error,
        }

    def operations_context(self) -> dict:
        """Return the compact operational subset needed by the station detail panel."""
        state = self.read_json(self.bridge / "state.json")
        plan = self.read_json(self._plan_path())
        save_id = snapshot_save_id(state)
        if plan.get("save_id") != save_id:
            plan = {}
        plan_by_line = {item.get("line_id"): item for item in plan.get("lines", [])}
        active_passenger_vehicles_by_line: dict[int, dict[str, int | float]] = {}
        for vehicle in state.get("vehicles", []):
            line_id = vehicle.get("line_id")
            if not isinstance(line_id, int) or isinstance(line_id, bool) or vehicle.get("raw_state") not in (1, 2):
                continue
            capacities = vehicle.get("capacity_by_cargo", [])
            carries_passengers = any(
                isinstance(item, dict)
                and item.get("cargo_id") == 0
                and isinstance(item.get("capacity"), (int, float))
                and item.get("capacity") > 0
                for item in capacities
            )
            if not carries_passengers:
                carries_passengers = 0 in vehicle.get("supported_cargo_ids", [])
            if not carries_passengers:
                continue
            profile = active_passenger_vehicles_by_line.setdefault(line_id, {
                "total": 0,
                "high_speed": 0,
                "conventional": 0,
                "unknown_speed": 0,
                "threshold_kmh": HIGH_SPEED_CONSIST_THRESHOLD_KMH,
            })
            profile["total"] += 1
            top_speed = vehicle.get("consist_top_speed_kmh")
            if not isinstance(top_speed, (int, float)):
                profile["unknown_speed"] += 1
            elif top_speed >= HIGH_SPEED_CONSIST_THRESHOLD_KMH - 0.5:
                # Engine values can contain small floating-point conversion noise
                # around an exact 250 km/h vehicle definition.
                profile["high_speed"] += 1
            else:
                profile["conventional"] += 1
        lines = []
        for line in state.get("lines", []):
            line_id = line.get("entity_id")
            timetable = plan_by_line.get(line_id, {})
            timetable_stops = {item.get("stop_index"): item for item in timetable.get("stops", [])}
            stops = []
            for stop in line.get("raw_stops", line.get("stops", [])):
                index = stop.get("sequence_index", stop.get("index"))
                scheduled = timetable_stops.get(index, {})
                stops.append({
                    "sequence_index": index,
                    "station_id": stop.get("station_id"),
                    "station_index": stop.get("station_index"),
                    "terminal_id": stop.get("terminal_id"),
                    "alternative_terminals": stop.get("alternative_terminals", []),
                    "policy": stop.get("policy", {}),
                    "scheduled_dwell_seconds": scheduled.get("scheduled_dwell_seconds"),
                    "arrival_offset_seconds": scheduled.get("arrival_offset_seconds"),
                    "departure_offset_seconds": scheduled.get("departure_offset_seconds"),
                })
            lines.append({
                "line_id": line_id,
                "name": line.get("name"),
                "frequency_seconds": line.get("frequency_seconds"),
                "vehicle_count": timetable.get("vehicle_count"),
                "headway_seconds": timetable.get("headway_seconds"),
                "active_passenger_vehicles": active_passenger_vehicles_by_line.get(line_id, {
                    "total": 0,
                    "high_speed": 0,
                    "conventional": 0,
                    "unknown_speed": 0,
                    "threshold_kmh": HIGH_SPEED_CONSIST_THRESHOLD_KMH,
                }),
                "stops": stops,
            })
        return {
            "schema_version": 1,
            "source_status": "ENGINE_SNAPSHOT_WITH_DERIVED_TIMETABLE",
            "snapshot_sequence": state.get("sequence"),
            "save_id": save_id,
            "lines": lines,
        }

    def line_demand(self) -> dict:
        """Capacity-side view: engine `line.rate` per line plus configured fleet capacity.

        CORRECTION (2026-09-27, measured on 271 lines): `line.rate` (the native UI field
        labelled 吞吐量) is a CAPACITY figure, not measured traffic. It satisfies
        `rate = round(730.5 * capacity_per_train / frequency_seconds)` — 269 of 271 lines
        matched exactly and the residuals are bounded by integer rounding. It therefore
        carries no independent demand information: it is the theoretical full-load
        throughput (运力供给), not 客流/货流.

        Measured demand is UNAVAILABLE in this evidence model: vehicle load, station
        waiting and per-line revenue all read back nil.

        NOTE: the earlier `annual_volume_estimate = throughput * stop_count` was wrong
        (rate is already a whole-line figure, not per stop) and has been removed.
        """
        state = self.read_json(self.bridge / "state.json")
        lines = state.get("lines", [])
        capacity_total: dict[int, int] = {}
        seats_total: dict[int, int] = {}
        assigned: dict[int, int] = {}
        consist_parts: dict[int, int] = {}
        for vehicle in state.get("vehicles", []):
            line_id = vehicle.get("line_id")
            if not isinstance(line_id, int) or isinstance(line_id, bool):
                continue
            capacity_total[line_id] = capacity_total.get(line_id, 0) + int(vehicle.get("capacity_total") or 0)
            assigned[line_id] = assigned.get(line_id, 0) + 1
            consist_parts[line_id] = consist_parts.get(line_id, 0) + len(vehicle.get("consist_parts") or [])
            for entry in vehicle.get("capacity_by_cargo") or []:
                if entry.get("cargo_id") == 0:  # PASSENGERS
                    seats_total[line_id] = seats_total.get(line_id, 0) + int(entry.get("capacity") or 0)
        payload_lines = []
        for line in lines:
            line_id = line.get("entity_id")
            if not isinstance(line_id, int) or isinstance(line_id, bool):
                continue
            stop_count = line.get("stop_count") or 0
            throughput = line.get("throughput")
            vehicles = assigned.get(line_id, 0)
            per_train = (capacity_total.get(line_id, 0) / vehicles) if vehicles else 0.0
            frequency = line.get("frequency_seconds") or 0
            seats = seats_total.get(line_id, 0)
            if seats and seats == capacity_total.get(line_id, 0):
                service = "PASSENGER"
            elif seats:
                service = "MIXED"
            else:
                service = "FREIGHT"
            payload_lines.append({
                "line_id": line_id,
                "name": line.get("name"),
                "throughput": throughput,
                "rate_is_capacity": True,
                "rate_formula_check": round(730.5 * per_train / frequency) if per_train and frequency else None,
                "stop_count": stop_count,
                "frequency_seconds": frequency,
                "vehicle_count": vehicles,
                "fleet_capacity_total": capacity_total.get(line_id, 0),
                "seats_total": seats,
                "capacity_per_train": per_train,
                "capacity_per_vehicle_per_year": (throughput / vehicles) if (throughput and vehicles) else None,
                "service_class": service,
                "consist_parts": consist_parts.get(line_id, 0),
                "max_waiting_time_seconds": max(
                    (stop.get("policy", {}).get("max_waiting_time") or 0 for stop in line.get("stops", [])),
                    default=0,
                ),
            })
        return {
            "schema_version": 1,
            "source_status": "ENGINE_SNAPSHOT_CAPACITY_DERIVED",
            "snapshot_sequence": state.get("sequence"),
            "snapshot_timestamp": state.get("timestamp"),
            "save_id": snapshot_save_id(state),
            "company": state.get("company"),
            "field_notes": {
                "throughput": "game.interface.getEntity(line).rate。实测为运力公式：rate = round(730.5 × 单车容量 ÷ 发车间隔)，271 条线中 269 条精确吻合 → 语义是『满载口径的理论年运力』，不是实测客流/货流",
                "capacity_per_vehicle_per_year": "rate ÷ 车辆数，反映每辆车的运力配置水平，不代表实际载运量",
                "unavailable": "实测客流/货流不可得：车辆装载、车站候客、分线收入在引擎与 Mod 中均返回 nil；需求侧数据只能从游戏内 UI（车站候客数、车辆财务图收入）人工读取",
            },
            "lines": payload_lines,
        }

    # ------------------------------------------------------------------
    # 真实客流（引擎 get_line_demand）：车上 / 候车 / 平均等待 / OD
    # 数据来自 api.engine.system.simPersonSystem|simCargoSystem.getSimPersonsForLine，
    # 由 mod 的 collectors/line_demand.lua 分类后经 Bridge 返回。只读，不改变游戏状态。
    # ------------------------------------------------------------------
    COMPACT_JOURNEYS = 15

    def _rail_line_ids(self) -> list[int]:
        network = self.read_json(self.bridge / "rail-network.json")
        ids: list[int] = []
        for line in network.get("lines", []):
            line_id = line.get("entity_id")
            if isinstance(line_id, int) and not isinstance(line_id, bool):
                ids.append(line_id)
        return sorted(set(ids))

    def _fleet_capacity(self) -> dict:
        """{line_id: {seats, cargo, vehicles: {vehicle_id: {seats, cargo}}}}"""
        state = self.read_json(self.bridge / "state.json")
        out: dict[int, dict] = {}
        for vehicle in state.get("vehicles", []):
            line_id = vehicle.get("line_id")
            if not isinstance(line_id, int) or isinstance(line_id, bool):
                continue
            seats = cargo = 0
            for entry in vehicle.get("capacity_by_cargo") or []:
                capacity = int(entry.get("capacity") or 0)
                if entry.get("cargo_id") == 0:
                    seats += capacity
                else:
                    cargo += capacity
            bucket = out.setdefault(line_id, {"seats": 0, "cargo": 0, "vehicles": {}})
            bucket["seats"] += seats
            bucket["cargo"] += cargo
            vehicle_id = vehicle.get("entity_id")
            if isinstance(vehicle_id, int):
                bucket["vehicles"][vehicle_id] = {"seats": seats, "cargo": cargo}
        return out

    @staticmethod
    def _compact_demand(raw: dict, line_id: int) -> dict:
        passengers = raw.get("passengers") or {}
        cargo = raw.get("cargo") or {}

        def side(payload: dict) -> dict:
            return {
                "onboard": payload.get("onboard") or 0,
                "waiting": payload.get("waiting") or 0,
                "total": payload.get("total_for_line") or 0,
                "avg_wait_s": payload.get("average_waiting_seconds"),
                # 均值会被个别超长等待拉高；中位数/分位数更可靠（需 mod 侧新版采集器）
                "median_wait_s": payload.get("median_waiting_seconds"),
                "p90_wait_s": payload.get("p90_waiting_seconds"),
                "max_wait_s": payload.get("max_waiting_seconds"),
                "waiting_over_1h": payload.get("waiting_over_1h"),
                "wait_samples": payload.get("waiting_seconds_samples"),
                "journey_unknown": payload.get("journey_unknown"),
                "truncated": payload.get("truncated"),
            }

        journeys = []
        for item in (passengers.get("by_journey") or [])[:RailMapState.COMPACT_JOURNEYS]:
            journeys.append({"from": item.get("line_stop_0"), "to": item.get("line_stop_1"),
                             "onboard": item.get("onboard"), "waiting": item.get("waiting"),
                             "total": item.get("total")})
        cargo_types = [{"cargo_id": item.get("cargo_id"), "onboard": item.get("onboard"),
                        "waiting": item.get("waiting"), "total": item.get("total")}
                       for item in (cargo.get("by_cargo") or [])]
        vehicles = {}
        for key, value in (passengers.get("vehicles") or {}).items():
            try:
                vehicles[str(int(key))] = value
            except (TypeError, ValueError):
                continue
        return {"line_id": line_id, "sampled_at": time.time(), "pax": side(passengers),
                "cargo": side(cargo), "cargo_types": cargo_types, "vehicles": vehicles,
                "by_journey": journeys, "source_status": raw.get("source_status")}

    def sample_line_demand(self, line_id: int, force: bool = False,
                           timeout_seconds: float = 15.0) -> dict:
        if not force:
            with self.demand_lock:
                cached = self.demand_cache.get(line_id)
            if cached and time.time() - float(cached.get("sampled_at") or 0) < self.demand_min_interval_seconds:
                return cached
        client = BridgeClient(self.bridge, timeout_seconds=timeout_seconds, poll_seconds=0.04)
        compact = self._compact_demand(client.line_demand(line_id, 20000), line_id)
        with self.demand_lock:
            self.demand_cache[line_id] = compact
            self._record_cargo_history(line_id, compact)
        self.persist_demand()
        return compact

    def live_game_seconds(self) -> float | None:
        """当前游戏内时间（秒）。带 1 秒缓存，避免每次都读大文件。"""
        now = time.time()
        cached_at, cached_value = self._live_clock_cache
        if now - cached_at < 1.0:
            return cached_value
        value: float | None = None
        try:
            live = self.read_json(self.bridge / "live-rail-state.json")
            clock = ((live.get("simulation") or {}).get("clock") or {})
            game_ms = clock.get("game_time")
            if isinstance(game_ms, (int, float)):
                value = float(game_ms) / 1000.0
        except (OSError, ValueError, TypeError):
            value = None
        self._live_clock_cache = (now, value)
        return value

    def _record_cargo_history(self, line_id: int, compact: dict) -> None:
        """记录货运队列的时间序列（调用方已持有 demand_lock）。"""
        cargo = compact.get("cargo") or {}
        entry = {
            "game_s": self.live_game_seconds(),
            "wall": round(float(compact.get("sampled_at") or time.time()), 1),
            "waiting": int(cargo.get("waiting") or 0),
            "onboard": int(cargo.get("onboard") or 0),
        }
        history = self.freight_history.setdefault(line_id, [])
        # 同一时刻重复采样只保留最后一条
        if history and entry["game_s"] is not None and history[-1].get("game_s") == entry["game_s"]:
            history[-1] = entry
        else:
            history.append(entry)
        if len(history) > self.freight_history_limit:
            del history[:-self.freight_history_limit]

    @staticmethod
    def _cargo_trend(history: list[dict]) -> dict:
        """从货运时间序列判断"运不走"的三条证据。

        游戏逻辑：货运只要「每次都能运完、供给 ≥ 消耗、站点不溢出」就是健康的，
        因此实载率、绝对候运量都不能作为判据；唯一有意义的是队列是否在**持续增长**，
        以及车是否**真的在取货**（onboard 是否出现过 > 0）。
        """
        points = [p for p in (history or []) if isinstance(p, dict)]
        if not points:
            return {"observations": 0}
        waiting = [int(p.get("waiting") or 0) for p in points]
        onboard = [int(p.get("onboard") or 0) for p in points]
        first, last = waiting[0], waiting[-1]
        delta = last - first
        rising = len(waiting) >= 2 and delta > 0 and last > first * 1.2 and last - first >= 20
        return {
            "observations": len(points),
            "waiting_first": first,
            "waiting_last": last,
            "waiting_min": min(waiting),
            "waiting_max": max(waiting),
            "waiting_delta": delta,
            "ever_onboard": max(onboard) > 0,
            "max_onboard": max(onboard),
            "rising": bool(rising),
            # 三条同时成立才算"可能运不走"：队列在涨 + 从未见到装货 + 至少 3 次观测
            "suspect_stuck": bool(rising and max(onboard) == 0 and len(points) >= 3),
            "game_span_s": (points[-1].get("game_s") - points[0].get("game_s"))
            if isinstance(points[-1].get("game_s"), (int, float)) and isinstance(points[0].get("game_s"), (int, float))
            else None,
        }

    def persist_demand(self) -> None:
        now = time.time()
        if now - self.demand_last_persist < 2.0:
            return
        self.demand_last_persist = now
        with self.demand_lock:
            payload = {"schema_version": 1, "source_status": "ENGINE_GET_LINE_DEMAND",
                       "written_at": now, "sweep": dict(self.demand_sweep),
                       "lines": {str(k): v for k, v in self.demand_cache.items()},
                       "cargo_history": {str(k): v for k, v in self.freight_history.items()}}
        try:
            self.write_json(self.bridge / "line-demand-live.json", payload)
        except OSError:
            pass

    def demand_live(self) -> dict:
        fleet = self._fleet_capacity()
        state = self.read_json(self.bridge / "state.json")
        names = {int(item["entity_id"]): item.get("name") for item in state.get("lines", [])
                 if isinstance(item.get("entity_id"), int)}
        with self.demand_lock:
            cache = dict(self.demand_cache)
            sweep = dict(self.demand_sweep)
            cargo_history = {k: list(v) for k, v in self.freight_history.items()}
        lines: dict[int, dict] = {}
        for line_id, item in cache.items():
            capacity = fleet.get(line_id, {})
            seats = capacity.get("seats") or 0
            pax = item.get("pax") or {}
            onboard = pax.get("onboard") or 0
            waiting = pax.get("waiting") or 0
            entry = dict(item)
            entry["line_name"] = names.get(line_id) or item.get("line_name")
            entry["seats"] = seats
            cargo_capacity = capacity.get("cargo") or 0
            entry["cargo_capacity"] = cargo_capacity
            # 客/货类型由车队容量推出：只拉人=客运，只拉货=货运，两者都有=混编。
            # 面板要用它区分判据（客运看实载率，货运看队列是否持续增长）。
            if seats and cargo_capacity:
                entry["service_class"] = "MIXED"
            elif seats:
                entry["service_class"] = "PASSENGER"
            elif cargo_capacity:
                entry["service_class"] = "FREIGHT"
            else:
                entry["service_class"] = None
            entry["load_factor"] = (onboard / seats) if seats else None
            entry["wait_ratio"] = (waiting / onboard) if onboard else None
            vehicle_load = []
            for raw_id, count in (item.get("vehicles") or {}).items():
                vehicle_capacity = (capacity.get("vehicles") or {}).get(int(raw_id), {})
                vehicle_load.append({"vehicle_id": int(raw_id), "onboard": count,
                                     "seats": vehicle_capacity.get("seats"),
                                     "cargo": vehicle_capacity.get("cargo")})
            entry["vehicle_load"] = sorted(vehicle_load, key=lambda row: -(row.get("onboard") or 0))
            # 货运判据：只看队列是否持续增长 + 车是否真的在取货（见 _cargo_trend 注释）
            entry["cargo_trend"] = self._cargo_trend(cargo_history.get(line_id) or [])
            for side_key in ("pax", "cargo"):
                payload_side = entry.get(side_key)
                if isinstance(payload_side, dict):
                    payload_side["wait_reliable"] = payload_side.get("median_wait_s") is not None
                    if payload_side.get("median_wait_s") is None and payload_side.get("avg_wait_s") is not None:
                        # 旧版采集器只给均值：超过 1 小时基本可判定被超长等待拉高，标出来别当真
                        payload_side["wait_suspect"] = payload_side["avg_wait_s"] > 3600
            lines[line_id] = entry
        return {"schema_version": 1, "sampled_lines": len(lines), "sweep": sweep, "lines": lines,
                "cargo_history": {str(k): v for k, v in cargo_history.items()},
                "notes": {
                    "cargo_criterion": "货运线的健康判据是「队列不持续增长 + 车确实在取货」，"
                                       "不是实载率，也不是候运的绝对量；供给≥消耗且不溢出即为正常。",
                    "passenger_criterion": "客运线看「实载率 + 候车 + 等待中位」三者同看，单次快照不作判据。",
                }}

    def _bridge_ready(self) -> bool:
        heartbeat = self.read_json(self.bridge / "heartbeat.json")
        if not heartbeat or not heartbeat.get("bridge_ready"):
            return False
        try:
            return time.time() - float(heartbeat.get("last_update") or 0) <= 10
        except (TypeError, ValueError):
            return False

    def start_demand_sweep(self, force: bool = False) -> dict:
        with self.demand_lock:
            if self.demand_sweep.get("running"):
                return dict(self.demand_sweep)
        if not self._bridge_ready():
            return {"running": False, "skipped": "bridge not ready（游戏未运行或未进档）"}
        line_ids = self._rail_line_ids()
        if not line_ids:
            return {"running": False, "skipped": "rail line list unavailable"}
        if not force:
            newest = max((float(item.get("sampled_at") or 0) for item in self.demand_cache.values()), default=0)
            if newest and time.time() - newest < self.demand_stale_seconds:
                return {"running": False, "skipped": "cache fresh", "sampled_lines": len(self.demand_cache),
                        "age_seconds": round(time.time() - newest, 1)}
        with self.demand_lock:
            self.demand_sweep = {"running": True, "done": 0, "total": len(line_ids),
                                 "started_at": time.time(), "finished_at": None,
                                 "errors": [], "last_error": None}
        threading.Thread(target=self._demand_sweep_worker, args=(line_ids, force), daemon=True,
                         name="tpf2-demand-sweep").start()
        return dict(self.demand_sweep)

    def _demand_sweep_worker(self, line_ids: list[int], force_all: bool) -> None:
        for line_id in line_ids:
            if not force_all:
                with self.demand_lock:
                    cached = self.demand_cache.get(line_id)
                if cached and time.time() - float(cached.get("sampled_at") or 0) < self.demand_stale_seconds:
                    with self.demand_lock:
                        self.demand_sweep["done"] += 1
                    continue
            try:
                self.sample_line_demand(line_id, force=True)
            except Exception as exc:  # noqa: BLE001 - 单线失败不能中断整轮采集
                with self.demand_lock:
                    if len(self.demand_sweep["errors"]) < 20:
                        self.demand_sweep["errors"].append({"line_id": line_id, "error": str(exc)})
                    self.demand_sweep["last_error"] = str(exc)
            with self.demand_lock:
                self.demand_sweep["done"] += 1
            time.sleep(0.5)
        with self.demand_lock:
            self.demand_sweep["running"] = False
            self.demand_sweep["finished_at"] = time.time()
        self.demand_last_persist = 0.0
        self.persist_demand()

    def vehicle_detail(self, vehicle_id: int) -> dict:
        """Compose one click-oriented vehicle view from cached motion and a bounded Bridge demand probe."""
        state = self.read_json(self.bridge / "state.json")
        index = SnapshotIndex(state)
        vehicle = index.vehicle_by_id.get(vehicle_id)
        if vehicle is None:
            return {"error": "vehicle not found", "vehicle_id": vehicle_id}
        live_frame = self.read_json(self.bridge / "live-rail-state.json")
        live = next((item for item in live_frame.get("vehicles", []) if item.get("entity_id") == vehicle_id), None)
        line_id = (live or {}).get("line_id") if isinstance((live or {}).get("line_id"), int) else vehicle.get("line_id")
        demand = None
        if isinstance(line_id, int):
            demand = BridgeClient(self.bridge, timeout_seconds=12, poll_seconds=.04).line_demand(line_id, 50000)
        return vehicle_dispatch_state(index, vehicle_id, live, demand)

    def ai_suggestions(self) -> dict:
        """Render bounded, evidence-backed templates only for work MCP cannot finish autonomously."""
        plan_path = self._plan_path()
        plan = self.read_json(plan_path)
        save_id = self.current_save_id()
        if plan.get("save_id") != save_id:
            return {
                "schema_version": 2, "save_id": save_id, "policy": "Observation only; stale plans from another save are hidden.",
                "generated_at": time.time(), "suggestions": [], "total": 0, "stale_plan_hidden": bool(plan),
                "templates": {"PARALLEL_LINE_IMBALANCE": "并行线路分配失衡"},
            }
        generated_at = plan_path.stat().st_mtime if plan_path.exists() else time.time()
        now = time.time()
        recent_fleet_changes = {
            item.get("line_id")
            for item in self.work_log.query(save_id, 500)
            if item.get("applied")
            and item.get("action_type") in {
                "EXPAND_LINE_WITH_VEHICLE", "ASSIGN_VEHICLE_TO_LINE", "FLEET_EXPANSION_ROLLED_BACK",
            }
            and isinstance(item.get("line_id"), int)
            and now - float(item.get("occurred_at") or 0) < FLEET_CHANGE_STABILIZATION_SECONDS
        }
        suggestions = []
        for line in plan.get("lines", []):
            line_id, name = line.get("line_id"), line.get("line_name") or f"线路 {line.get('line_id')}"
            fleet = line.get("fleet_policy") or {}
            # Historic demand samples remain high immediately after a verified fleet
            # change.  Suppress another add proposal until the new service has had a
            # bounded period to circulate and produce representative samples.
            if fleet.get("decision") == "ADD_ONE_PROPOSAL" and line_id not in recent_fleet_changes:
                eligible = fleet.get("execution_eligibility") == "PROPOSAL_READY"
                suggestions.append({
                    "created_at": generated_at,
                    "template": "ADD_TRAIN", "template_label": "加车建议", "severity": "ACTION" if eligible else "BLOCKED",
                    "line_id": line_id, "line_name": name,
                    "title": f"{name} 建议加车 1 组" if eligible else f"{name} 加车被编组约束阻止",
                    "reason": f"候车 {((line.get('demand') or {}).get('waiting') or 0)}，连续样本 {((line.get('demand') or {}).get('sample_count') or 0)}",
                    "required_action": "需要批准受控购车任务" if eligible else "先解决编组速度、货物兼容性或站台长度硬约束",
                    "automation_status": "REQUIRES_APPROVAL" if eligible else "REQUIRES_MANUAL_FLEET_CORRECTION",
                })
            platform = line.get("platform_feasibility") or {}
            if platform.get("status") == "TOO_SHORT":
                bad = [stop for stop in line.get("stops", []) if (stop.get("platform_fit") or {}).get("status") == "TOO_SHORT"]
                affected = []
                for stop in bad:
                    fit = stop.get("platform_fit") or {}
                    short = [option for option in fit.get("options", []) if option.get("fits_longest_assigned_train") is False]
                    affected.append({"station_name": stop.get("station_name"), "train_length_m": fit.get("train_length_m"),
                                     "short_platform_lengths_m": sorted({option.get("platform_length_m") for option in short if option.get("platform_length_m") is not None})})
                detail = "；".join(f"{item.get('station_name') or '未知车站'} 站台 {','.join(str(value) for value in item['short_platform_lengths_m']) or 'UNKNOWN'} m" for item in affected[:4])
                suggestions.append({
                    "created_at": generated_at,
                    "template": "PLATFORM_TOO_SHORT", "template_label": "站台不足", "severity": "BLOCKED", "line_id": line_id, "line_name": name,
                    "title": f"{name} 存在站台短于列车", "reason": f"最长编组 {platform.get('longest_assigned_train_m')} m；{detail}",
                    "required_action": "人工延长站台，或人工指定经验证足够长的可选站台",
                    "automation_status": "REQUIRES_INFRASTRUCTURE_OR_ROUTE_DECISION", "affected_stops": affected,
                })
            elif platform.get("status") == "UNKNOWN":
                suggestions.append({
                    "created_at": generated_at,
                    "template": "PLATFORM_LENGTH_UNKNOWN", "template_label": "长度待采", "severity": "DATA", "line_id": line_id, "line_name": name,
                    "title": f"{name} 暂不能验证站台长度", "reason": "列车或至少一个可选站台缺少可靠长度",
                    "required_action": "等待长度采集完成；在此之前禁止自动扩编和站台分配",
                    "automation_status": "WAITING_FOR_VERIFIED_DATA",
                })
        for group in plan.get("parallel_service_diagnostics", []):
            if group.get("status") != "OBSERVED_PARALLEL_OD_IMBALANCE":
                continue
            members = sorted(group.get("lines", []), key=lambda item: item.get("demand_share", 0), reverse=True)
            labels = " / ".join(f"{item.get('line_name') or ('线路 ' + str(item.get('line_id')))} {item.get('demand') or 0}（{round((item.get('demand_share') or 0) * 100)}%）" for item in members)
            station_names = group.get("shared_station_names") or group.get("shared_station_pair") or []
            corridor = " ↔ ".join(str(value) for value in station_names)
            demand_kind = group.get("cargo_name") or ("乘客" if group.get("cargo_id") == 0 else f"货物 {group.get('cargo_id')}")
            suggestions.append({
                "created_at": generated_at,
                "template": "PARALLEL_LINE_IMBALANCE", "template_label": "分配失衡", "severity": "REVIEW", "title": f"{corridor} · {demand_kind}分配失衡",
                "reason": labels, "required_action": "仅记录并提交 AI 建议；当前不生成或执行调车、扩编、班次、停站或装卸调整",
                "automation_status": "OBSERVATION_ONLY", "station_pair": group.get("shared_station_pair"),
                "cargo_id": group.get("cargo_id"), "observation_only": True,
            })
        rank = {"BLOCKED": 0, "ACTION": 1, "REVIEW": 2, "DATA": 3}
        suggestions.sort(key=lambda item: (-float(item.get("created_at") or 0), rank.get(item.get("severity"), 9), -(next((line.get("demand", {}).get("waiting", 0) for line in plan.get("lines", []) if line.get("line_id") == item.get("line_id")), 0))))
        return {
            "schema_version": 2, "save_id": save_id,
            "policy": "Only unresolved, approval-gated, infrastructure, or unavailable-capability work appears here. Completed verified actions appear in MCP work log.",
            "templates": {
                "ADD_TRAIN": "线路建议加车", "PLATFORM_TOO_SHORT": "站台长度不足",
                "PLATFORM_LENGTH_UNKNOWN": "长度数据待验证", "PARALLEL_LINE_IMBALANCE": "并行线路分配失衡",
            },
            "generated_at": generated_at, "suggestions": suggestions, "total": len(suggestions),
        }

    def _task_audit_entries(self, save_id: str) -> list[dict]:
        try:
            raw_lines = self.task_journal.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return []
        latest: dict[str, dict] = {}
        for raw in raw_lines:
            try:
                task = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if task.get("save_id") == save_id and isinstance(task.get("task_id"), str):
                latest[task["task_id"]] = task
        entries = []
        for task in latest.values():
            task_status = str(task.get("status") or "UNKNOWN")
            if task_status == "COMPLETED":
                # Verified completed steps are already represented by the
                # durable SQLite entries and must not be shown twice.
                continue
            if task_status in {"BLOCKED", "FAILED", "PARTIALLY_COMPLETED"}:
                category = "BLOCKED"
            elif task_status == "CANCELLED":
                category = "CANCELLED"
            else:
                category = "PENDING"
            steps = task.get("steps") or []
            plans = task.get("planned_steps") or []
            action = (steps[-1] if steps else task.get("next_step") or (plans[0] if plans else {})) or {}
            target = action.get("target") or {}
            goal = task.get("goal") or {}
            line_id = target.get("line_id") if isinstance(target.get("line_id"), int) else goal.get("target_line_id") or goal.get("line_id")
            vehicle_id = target.get("vehicle_id") if isinstance(target.get("vehicle_id"), int) else goal.get("vehicle_id") or goal.get("created_vehicle_id")
            action_type = str(action.get("operation_type") or task.get("goal_type") or "UNKNOWN")
            label = WORK_ACTION_LABELS.get(action_type, action_type.removesuffix("_GOAL"))
            targets = []
            if isinstance(line_id, int):
                targets.append(f"线路 {line_id}")
            if isinstance(vehicle_id, int):
                targets.append(f"车辆 {vehicle_id}")
            result = task.get("result") or {}
            reason = result.get("reason") or result.get("execution_status")
            if not reason:
                reason = {
                    "CREATED": "等待规划",
                    "WAITING_FOR_APPROVAL": "等待批准",
                    "READY": "等待执行",
                    "REPLANNING": "等待重新规划",
                    "CANCELLED": "任务已取消",
                }.get(task_status, task_status)
            timeline = task.get("timeline") or []
            occurred_at = McpWorkLogStore._timestamp((timeline[-1] if timeline else {}).get("at"))
            entries.append({
                "id": f"task:{task['task_id']}",
                "task_id": task["task_id"],
                "save_id": save_id,
                "occurred_at": occurred_at,
                "action_type": action_type,
                "summary": " · ".join([label, *targets]) if targets else label,
                "line_id": line_id if isinstance(line_id, int) else None,
                "vehicle_id": vehicle_id if isinstance(vehicle_id, int) else None,
                "applied": bool((task.get("budget") or {}).get("writes_used")),
                "verification_status": (steps[-1] if steps else {}).get("status") or task_status,
                "task_status": task_status,
                "category": category,
                "reason": str(reason),
            })
        return entries

    def mcp_work_logs(self, limit: int | None = 30) -> dict:
        save_id = self.current_save_id()
        self.work_log.sync_task_journal(self.task_journal, save_id)
        self.work_log.sync_timetable_plan(self._plan_path(), save_id)
        rows = self.work_log.query(save_id, limit)
        for row in rows:
            row["category"] = "EXECUTED" if row.get("applied") else "TEST"
            row["reason"] = row.get("verification_status")
        rows.extend(self._task_audit_entries(save_id))
        rows.sort(key=lambda item: (float(item.get("occurred_at") or 0), str(item.get("id"))), reverse=True)
        if limit is not None:
            rows = rows[:max(1, min(500, int(limit)))]
        status_counts = {key: sum(item.get("category") == key for item in rows) for key in ("EXECUTED", "BLOCKED", "PENDING", "CANCELLED", "TEST")}
        return {"schema_version": 3, "save_id": save_id, "database": str(self.work_log.path), "entries": rows, "count": len(rows), "status_counts": status_counts}

    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, path)

    def refresh_live(self) -> None:
        now = time.time()
        if now - self.last_live_poll < self.live_poll_seconds or not self.live_lock.acquire(blocking=False):
            return
        try:
            heartbeat = self.read_json(self.bridge / "heartbeat.json")
            age = now - float(heartbeat.get("last_update", 0)) if heartbeat else 999
            if not heartbeat.get("bridge_ready") or age >= 10:
                return
            client = BridgeClient(self.bridge, timeout_seconds=8, poll_seconds=.04)
            if now - self.last_signal_poll > 300 or not (self.bridge / "operational-telemetry-signals.json").exists():
                client.operational_telemetry("signals")
                self.last_signal_poll = now
                self.live_control = None
            client.operational_telemetry("vehicles_live")
            vehicle_payload = self.read_json(self.bridge / "operational-telemetry-vehicles_live.json")
            signal_payload = self.read_json(self.bridge / "operational-telemetry-signals.json")
            telemetry = {"vehicles": vehicle_payload.get("vehicles", []), "simulation_clock": vehicle_payload.get("simulation_clock"), "signal_edge_objects": signal_payload.get("signal_edge_objects", []), "track_edge_objects": signal_payload.get("track_edge_objects", [])}
            network = self.read_json(self.bridge / "rail-network.json")
            manifest = self.read_json(self.root / "rail-network-manifest.json")
            if manifest.get("save_id") != self.current_save_id():
                return
            previous = self.read_json(self.bridge / "live-rail-state.json")
            network_mtime = self._mtime(self.bridge / "rail-network.json")
            if self.live_index is None or self.live_network_mtime != network_mtime:
                self.live_index = RailSpatialIndex(network)
                self.live_network_mtime = network_mtime
                self.live_control = None
            if self.live_control is None:
                signals = normalize_signals(telemetry, self.live_index)
                blocks, atoms = derive_blocks(network, signals, self.live_index)
                self.live_control = (signals, blocks, atoms)
                confirmed = sum(signal["source_status"] != "TRACK_OBJECT_CANDIDATE" for signal in signals)
                self.write_json(self.bridge / "rail-control-state.json", {"schema_version": 1, "source_status": "ENGINE_OBSERVED_STATIC_CONTROL", "sampled_at": now, "signals": signals, "blocks": blocks, "counts": {"signal_candidates": len(signals), "confirmed_signals": confirmed, "blocks": len(blocks)}})
            value = normalize_live_state(telemetry, network, manifest, previous, now, spatial_index=self.live_index, control=self.live_control)
            frame = {key: item for key, item in value.items() if key not in {"signals", "blocks"}}
            # 船 / 飞机：不走铁路归一化（没有可吸附的轨道），位置直接用包围盒中心。
            # 前端据此让飞机跟列车同频（500 ms）、船 90 s 更新一次。
            air_vehicles, water_vehicles = build_other_vehicles(telemetry, self.bridge)
            frame["air_vehicles"] = air_vehicles
            frame["water_vehicles"] = water_vehicles
            counts = dict(frame.get("counts") or {})
            counts["air_vehicles"] = len(air_vehicles)
            counts["water_vehicles"] = len(water_vehicles)
            frame["counts"] = counts
            self.write_json(self.bridge / "live-rail-state.json", frame)
            self.station_events.record_frame(frame, manifest, self.current_save_id())
            self.live_error = None
        except (BridgeError, OSError, ValueError, KeyError, TypeError) as exc:
            self.live_error = str(exc)
        finally:
            self.last_live_poll = now
            self.live_lock.release()

    def refresh_save_scope(self) -> None:
        """Detect an in-game save switch and refresh all save-bound static data."""
        now = time.time()
        if now - self.last_snapshot_poll < self.snapshot_poll_seconds or not self.live_lock.acquire(blocking=False):
            return
        try:
            heartbeat = self.read_json(self.bridge / "heartbeat.json")
            age = now - float(heartbeat.get("last_update", 0)) if heartbeat else 999
            if not heartbeat.get("bridge_ready") or age >= 10:
                return
            # state.json is the mod's continuously refreshed save snapshot.  Save
            # detection must stay file-only: issuing get_game_state every three
            # seconds monopolizes the single Bridge mailbox and starves live vehicle
            # sampling on large saves.
            snapshot = self.read_json(self.bridge / "state.json")
            if not snapshot:
                return
            save_id = snapshot_save_id(snapshot)
            manifest = self.read_json(self.root / "rail-network-manifest.json")
            # A web-server restart must not request and rebuild the entire railway
            # network when the on-disk manifest already belongs to this save.  The
            # old condition also required active_save_id, which is necessarily None
            # after restart and could hold live polling behind a very expensive
            # get_rail_network call for minutes.
            if manifest.get("save_id") == save_id:
                self.active_save_id = save_id
                self.save_switch_error = None
                return
            self.active_save_id = save_id
            self.live_index = None
            self.live_control = None
            self.live_network_mtime = 0
            self.last_signal_poll = 0
            self.write_json(self.bridge / "live-rail-state.json", {
                "schema_version": 2, "save_id": save_id, "source_status": "SAVE_TRANSITION", "sampled_at": now,
                "simulation": snapshot.get("simulation"), "vehicles": [], "counts": {"rail_vehicles": 0},
            })
            self.write_json(self.bridge / "rail-control-state.json", {
                "schema_version": 2, "save_id": save_id, "source_status": "SAVE_TRANSITION",
                "sampled_at": now, "signals": [], "blocks": [], "counts": {"signals": 0, "blocks": 0},
            })
            client = BridgeClient(self.bridge, timeout_seconds=30, poll_seconds=.04)
            client.call("get_rail_network", {})
            self.save_switch_error = None
        except (BridgeError, OSError, ValueError, KeyError, TypeError) as exc:
            self.save_switch_error = str(exc)
        finally:
            self.last_snapshot_poll = now
            self.live_lock.release()

    def regenerate_if_changed(self) -> None:
        source = self.bridge / "rail-network.json"
        current = self._mtime(source)
        if not current or current == self.last_bridge_network_mtime:
            return
        with self.generation_lock:
            current = self._mtime(source)
            if current == self.last_bridge_network_mtime:
                return
            completed = subprocess.run(
                [sys.executable, str(self.exporter), "--input", str(source), "--output-directory", str(self.root),
                 "--save-id", self.current_save_id()],
                cwd=self.root.parents[1], capture_output=True, text=True, timeout=180,
            )
            if completed.returncode == 0:
                self.last_bridge_network_mtime = current

    def regenerate_layers_if_changed(self) -> None:
        """bridge/layer-*.json 有变动就重切图块。

        与 regenerate_if_changed 的区别：那个盯单个铁路文件，这里盯一组图层文件，
        且用"文件名→修改时间"的整体签名判断，避免同一轮里重复切块。
        """
        if not self.exporter_layers or not self.exporter_layers.is_file():
            return
        stamps = sorted((path.name, self._mtime(path)) for path in self.bridge.glob("layer-*.json"))
        if not stamps:
            return
        signature = hash(tuple(stamps))
        if signature == self.last_layer_signature:
            return
        with self.generation_lock:
            if signature == self.last_layer_signature:
                return
            completed = subprocess.run(
                [sys.executable, str(self.exporter_layers),
                 "--bridge-directory", str(self.bridge),
                 "--output-directory", str(self.root / "layers"),
                 "--bounds-manifest", str(self.root / "rail-network-manifest.json")],
                cwd=self.root.parents[1], capture_output=True, text=True, timeout=180,
            )
            if completed.returncode == 0:
                self.last_layer_signature = signature
                self.layers_error = None
            else:
                # 切块失败要留痕，否则前端只会看到图层数据永远不更新，查不出原因
                detail = (completed.stderr or completed.stdout or "").strip()
                self.layers_error = detail[-400:] or f"export-layer-map.py exited {completed.returncode}"

    def watch(self) -> None:
        while not self.stop.wait(1.0):
            self.refresh_save_scope()
            self.regenerate_if_changed()
            self.regenerate_layers_if_changed()
            self.refresh_live()


def handler_factory(app: RailMapState):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(app.root), **kwargs)

        def log_message(self, format_string: str, *args) -> None:
            sys.stdout.write("[rail-map] " + format_string % args + "\n")
            sys.stdout.flush()

        def end_headers(self) -> None:
            static_path = urlparse(self.path).path
            # 🔴 **按后缀判断，不按文件名逐个列举**（2026-10-02 改）。
            #    原来是一张写死的文件名白名单，只列了当时存在的那几个 JS/CSS ——
            #    后来新增的前端文件全漏在外面（station-struct.js / industry-icons.js /
            #    freight-flow.js / industry-kinds.js / road-congestion.js / town-layer.js /
            #    ui-persist.js …），浏览器就按 heuristic 缓存它们，
            #    表现是「刷新了也不更新」，只能靠 `?v=` 撞开。
            #    按后缀一条覆盖全，以后再加文件不必记得回来改这里。
            #    （图片不在此列：它们几乎不变，留默认缓存。）
            lowered = static_path.lower()
            if (static_path == "/"
                    or lowered.endswith((".html", ".htm", ".js", ".css", ".json"))
                    or static_path.startswith("/templates/")
                    or static_path.startswith("/station-previews/")
                    or static_path.startswith("/layers/")):
                self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def send_json(self, value: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/status":
                self.send_json(app.status())
                return
            if path == "/api/rail/manifest":
                self.send_json(app.read_json(app.root / "rail-network-manifest.json"))
                return
            if path == "/api/telemetry":
                value = app.read_json(app.bridge / "operational-telemetry.json")
                self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                return
            if path == "/api/live":
                value = app.read_json(app.bridge / "live-rail-state.json")
                self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                return
            if path == "/api/control":
                value = app.read_json(app.bridge / "rail-control-state.json")
                self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                return
            if path == "/api/timetable-plan":
                value = app.read_json(app._plan_path())
                self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                return
            if path == "/api/ai-suggestions":
                self.send_json(app.ai_suggestions())
                return
            if path == "/api/mcp-work-log":
                raw_limit = parse_qs(parsed.query).get("limit", ["30"])[0]
                if raw_limit.lower() == "all":
                    limit = None
                else:
                    try:
                        limit = int(raw_limit)
                    except ValueError:
                        self.send_json({"error": "invalid limit"}, HTTPStatus.BAD_REQUEST)
                        return
                self.send_json(app.mcp_work_logs(limit))
                return
            if path == "/api/operations-context":
                value = app.operations_context()
                self.send_json(value, HTTPStatus.OK if value.get("lines") else HTTPStatus.NOT_FOUND)
                return
            if path == "/api/line-demand":
                self.send_json(app.line_demand())
                return
            if path == "/api/demand-live":
                # 缓存为空或过期时自动开一轮全量采样（已在跑则忽略）
                app.start_demand_sweep()
                self.send_json(app.demand_live())
                return
            if path == "/api/demand/sweep":
                self.send_json(app.start_demand_sweep(force=True))
                return
            if path == "/api/demand/line":
                raw_line = parse_qs(parsed.query).get("line_id", [""])[0]
                if not raw_line.isdigit():
                    self.send_json({"error": "invalid line_id"}, HTTPStatus.BAD_REQUEST)
                    return
                try:
                    self.send_json(app.sample_line_demand(int(raw_line), force=True))
                except (BridgeError, ValueError, OSError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if path.startswith("/api/vehicle-detail/"):
                raw_id = path.rsplit("/", 1)[-1]
                if not raw_id.isdigit():
                    self.send_json({"error": "invalid vehicle id"}, HTTPStatus.BAD_REQUEST)
                    return
                try:
                    value = app.vehicle_detail(int(raw_id))
                except (BridgeError, ValueError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
                    return
                self.send_json(value, HTTPStatus.OK if "error" not in value else HTTPStatus.NOT_FOUND)
                return
            if path.startswith("/api/station-logs/"):
                raw_id = path.rsplit("/", 1)[-1]
                if not raw_id.isdigit():
                    self.send_json({"error": "invalid station id"}, HTTPStatus.BAD_REQUEST)
                    return
                raw_limit = parse_qs(parsed.query).get("limit", ["100"])[0]
                try:
                    limit = int(raw_limit)
                except ValueError:
                    self.send_json({"error": "invalid limit"}, HTTPStatus.BAD_REQUEST)
                    return
                save_id = app.current_save_id()
                rows = app.station_events.query(int(raw_id), save_id, limit)
                self.send_json({"save_id": save_id, "station_id": int(raw_id), "events": rows, "count": len(rows)})
                return
            if path.startswith("/api/rail/tile/"):
                key = path.rsplit("/", 1)[-1]
                if not TILE_KEY.fullmatch(key):
                    self.send_json({"error": "invalid tile key"}, HTTPStatus.BAD_REQUEST)
                    return
                value = app.read_json(app.root / "rail-network-tiles" / f"tile-{key}.json")
                self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                return
            if path.startswith("/api/layers/"):
                # /api/layers/<layer>/manifest            → 图层总览 + 分块索引
                # /api/layers/<layer>/tile/<ix>_<iy>      → 单个分块
                # 数据由 export-layer-map.py 从 bridge/layer-<layer>.json 切出来，
                # 与铁路共用同一份 bounds 与 tile 网格（叠加不错位的前提）。
                tail = path[len("/api/layers/"):].split("/")
                if len(tail) == 2 and tail[1] == "manifest":
                    if not LAYER_NAME.match(tail[0]):
                        self.send_json({"error": "invalid layer name"}, HTTPStatus.BAD_REQUEST)
                        return
                    value = app.read_json(app.root / "layers" / f"{tail[0]}-manifest.json")
                    self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                    return
                if len(tail) == 3 and tail[1] == "tile" and LAYER_NAME.match(tail[0]) and TILE_KEY.fullmatch(tail[2]):
                    value = app.read_json(app.root / "layers" / f"{tail[0]}-tiles" / f"tile-{tail[2]}.json")
                    self.send_json(value, HTTPStatus.OK if value else HTTPStatus.NOT_FOUND)
                    return
                self.send_json({"error": "unknown layer endpoint"}, HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/events":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                last = None
                try:
                    while not app.stop.is_set():
                        current = app.status()
                        if current != last:
                            payload = json.dumps(current, ensure_ascii=False, separators=(",", ":"))
                            self.wfile.write(f"event: status\ndata: {payload}\n\n".encode("utf-8"))
                            self.wfile.flush()
                            last = current
                        time.sleep(1)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return
            super().do_GET()

    return Handler


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--ui-directory", type=Path, default=repository / "ui" / "rail-map")
    parser.add_argument("--bridge-directory", type=Path, default=bridge_dir())
    parser.add_argument("--live-poll-seconds", type=float, default=1.5)
    args = parser.parse_args()
    app = RailMapState(args.ui_directory.resolve(), args.bridge_directory.resolve(), repository / "1_data_collection" / "exporters" / "export-rail-network-map.py", args.live_poll_seconds)
    watcher = threading.Thread(target=app.watch, name="rail-map-watcher", daemon=True)
    watcher.start()
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(app))
    print(f"TPF2 rail map: http://{args.host}:{args.port}/?view=network", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
