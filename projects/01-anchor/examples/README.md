# Inputs

`export.json` is the canonical synthetic export DAG used by the CLI demo; `payload.json`
is its generated input. Use the demo to supply its registered local export activities.
Ordinary worker CLI exposes built-in identity, publish, cleanup and deliberate failure;
custom exports register `export_registry(owned_output)` through the Python SDK. Raw
submission alone does not register arbitrary activity code from an input document.
