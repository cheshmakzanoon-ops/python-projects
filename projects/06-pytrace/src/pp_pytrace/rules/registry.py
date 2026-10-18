"""Configured semantic call summaries, not executable plugins."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Config:
    sources: tuple[str, ...] = (
        "input",
        "os.getenv",
        "os.environ.get",
        "request.args.get",
        "flask.request.args.get",
    )
    shell_sinks: tuple[str, ...] = (
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_call",
        "subprocess.check_output",
        "os.system",
    )
    sql_methods: tuple[str, ...] = ("execute", "executemany")
    blocking: tuple[str, ...] = (
        "time.sleep",
        "requests.get",
        "requests.post",
        "requests.put",
        "urllib.request.urlopen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
    )
    shell_sanitizers: tuple[str, ...] = ("shlex.quote",)
    sql_sanitizers: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


RULES = {
    "PT001": "Untrusted shell command",
    "PT002": "String-built SQL",
    "PT003": "Blocking call in async function",
    "PT900": "Analysis coverage uncertainty",
    "PT901": "Source parse failure",
}
