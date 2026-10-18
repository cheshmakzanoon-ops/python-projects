# Development evidence

`development-ci.json` and `development-quality.json` are actual local development
runs. They record the tested source digest and `source_dirty=true`; they do not
claim to test their own later artifact commit. Large state is under ignored
`.local/`. Final committed evidence is generated separately by the coordinator
from an immutable clean clone. Per-query failures are preserved rather than
removed from the quality report.
