"""Exact insertion certificates for a fixed directed route and snapshot boundary.

Forward departures and backward latest service starts make one insertion check
constant work. These are optimizer caches, never an independent verification path.
"""

from dataclasses import dataclass

from pp_routecraft.domain.instance import Route, RoutingInstance, VehicleState


@dataclass(frozen=True)
class RouteProfile:
    route: Route
    travel: int
    demand: int
    latest: tuple[int, ...]
    state: VehicleState | None

    @classmethod
    def build(
        cls,
        instance: RoutingInstance,
        vehicle_index: int,
        evaluated: tuple[Route, int],
        state: VehicleState | None,
    ) -> "RouteProfile":
        route, travel = evaluated
        latest = [0] * len(route.stops)
        deadline = instance.vehicles[vehicle_index].end
        successor = 0
        for position in range(len(route.stops) - 1, -1, -1):
            node = route.stops[position]
            stop = instance.stops[node - 1]
            deadline = min(stop.due, deadline - stop.service - instance.travel[node][successor])
            latest[position] = deadline
            successor = node
        return cls(
            route,
            travel,
            sum(instance.stops[node - 1].demand for node in route.stops),
            tuple(latest),
            state,
        )

    def insertion(
        self, instance: RoutingInstance, vehicle_index: int, job: int, position: int
    ) -> int | None:
        """Return exact directed travel after insertion, or no feasible schedule."""
        jobs = self.route.stops
        before = jobs[position - 1] if position else 0
        after = jobs[position] if position < len(jobs) else 0
        departure = (
            self.route.schedule[position - 1].departure
            if position
            else instance.vehicles[vehicle_index].start
        )
        if self.state and position == len(self.state.executed):
            departure = self.state.time
        stop = instance.stops[job - 1]
        begin = max(departure + instance.travel[before][job], stop.ready)
        if begin > stop.due:
            return None
        arrival_after = begin + stop.service + instance.travel[job][after]
        deadline = (
            self.latest[position] if position < len(jobs) else instance.vehicles[vehicle_index].end
        )
        if arrival_after > deadline:
            return None
        return (
            self.travel
            + instance.travel[before][job]
            + instance.travel[job][after]
            - instance.travel[before][after]
        )
