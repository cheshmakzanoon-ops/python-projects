"""Synthetic export reference application, generated locally without external assets."""

import asyncio
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from pp_anchor import ActivityContext, ActivityRegistry, Definition, Step
from pp_anchor.definitions.model import JSON


def export_definition() -> Definition:
    return Definition(
        "synthetic-export",
        1,
        (
            Step("validate", activity="validate"),
            *(Step(f"partition_{i}", activity="fetch", after=("validate",)) for i in range(3)),
            Step("join", after=tuple(f"partition_{i}" for i in range(3)), kind="join"),
            Step("archive", activity="archive", after=("join",), compensate="cleanup"),
            Step("cooldown", after=("archive",), kind="timer", delay=0.01),
            Step("approval", after=("cooldown",), kind="signal", signal="approve"),
            Step("publish", activity="publish", after=("approval",), compensate="cleanup"),
        ),
    )


def export_registry(output: Path) -> ActivityRegistry:
    registry = ActivityRegistry()

    async def validate(context: ActivityContext) -> JSON:
        rows = context.task.payload.get("rows")
        if not isinstance(rows, int) or not 1 <= rows <= 10000:
            raise ValueError("rows must be in 1..10000")
        return {"validated_rows": rows}

    async def fetch(context: ActivityContext) -> JSON:
        partition = int(context.task.step.rsplit("_", 1)[1])
        rows = int(str(context.task.payload["rows"]))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "value"])
        for index in range(partition, rows, 3):
            writer.writerow([index, index * index])
        content = buffer.getvalue()
        path = output / f"partition-{partition}.csv"
        await asyncio.to_thread(path.write_text, content)
        return {"partition": partition, "sha256": hashlib.sha256(content.encode()).hexdigest()}

    async def archive(context: ActivityContext) -> JSON:
        def build() -> JSON:
            path = output / "dataset.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive_file:
                for index in range(3):
                    content = (output / f"partition-{index}.csv").read_bytes()
                    info = zipfile.ZipInfo(
                        f"partition-{index}.csv", date_time=(2020, 1, 1, 0, 0, 0)
                    )
                    archive_file.writestr(info, content)
            return {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }

        return await asyncio.to_thread(build)

    registry.register("validate", validate)
    registry.register("fetch", fetch)
    registry.register("archive", archive)
    return registry


def definition_json(path: Path) -> Definition:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("definition must be an object")
    return Definition.from_dict(value)
