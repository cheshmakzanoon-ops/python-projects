"""Integer-unit, immutable delivery-routing records (schema version 1)."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class Stop:
    id: int
    demand: int
    ready: int = 0
    due: int = 100000
    service: int = 0
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class Vehicle:
    id: int
    capacity: int
    start: int = 0
    end: int = 100000


@dataclass(frozen=True)
class LoadedJob:
    stop_id: int
    quantity: int


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: int
    started: bool
    executed: tuple[int, ...]
    node: int
    time: int
    onboard: int
    loaded: tuple[LoadedJob, ...]
    boundary: str = "departure"


@dataclass(frozen=True)
class RoutingInstance:
    stops: tuple[Stop, ...]
    vehicles: tuple[Vehicle, ...]
    travel: tuple[tuple[int, ...], ...]
    depot: int = 0
    matrix_version: str = "synthetic-v1"
    states: tuple[VehicleState, ...] = ()


@dataclass(frozen=True)
class VisitSchedule:
    stop_id: int
    arrival: int
    service_start: int
    departure: int
    onboard_after: int


@dataclass(frozen=True)
class Route:
    vehicle_id: int
    stops: tuple[int, ...]
    schedule: tuple[VisitSchedule, ...] = ()
    return_time: int | None = None


@dataclass(frozen=True)
class Plan:
    routes: tuple[Route, ...]
    objective: tuple[int, int]
    schema_version: int = 1


class Status(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    PROVEN_INFEASIBLE = "PROVEN_INFEASIBLE"
    NO_FEASIBLE_PLAN_FOUND = "NO_FEASIBLE_PLAN_FOUND"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class SearchBudget:
    iterations: int = 100
    seconds: float | None = None


@dataclass(frozen=True)
class SolveResult:
    status: Status
    plan: Plan | None
    iterations: int
    stopping_reason: str
    elapsed_seconds: float
    first_feasible_seconds: float | None
    trajectory: tuple[tuple[int, int, int], ...]
    operator_counts: tuple[tuple[str, int], ...]
    diagnostics: tuple[str, ...] = ()
    optimality_gap: str = "unknown"
