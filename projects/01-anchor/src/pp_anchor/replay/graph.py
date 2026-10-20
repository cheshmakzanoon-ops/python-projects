"""Compiled DAG indexes shared by forward scheduling and causal rollback."""

from dataclasses import dataclass, field

from pp_anchor.definitions.model import Definition, Step


@dataclass
class WorkflowGraph:
    definition: Definition
    steps: dict[str, Step] = field(init=False)
    successors: dict[str, list[str]] = field(init=False)
    order: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        self.steps = {step.name: step for step in self.definition.steps}
        self.order = {step.name: index for index, step in enumerate(self.definition.steps)}
        self.successors = {name: [] for name in self.steps}
        for step in self.definition.steps:
            for predecessor in step.after:
                self.successors[predecessor].append(step.name)

    def rollback_dependencies(self, targets: set[str]) -> dict[str, frozenset[str]]:
        """Nearest compensable descendants, traversing joins/timers/signals.

        Waiting on these barriers enforces the transitive reverse order without
        materializing the entire ancestor closure of a long chain.
        """
        barriers: dict[str, set[str]] = {}
        for step in reversed(self.definition.steps):
            required: set[str] = set()
            for successor in self.successors[step.name]:
                if successor in targets:
                    required.add(successor)
                else:
                    required.update(barriers[successor])
            barriers[step.name] = required
        return {name: frozenset(barriers[name]) for name in targets}
