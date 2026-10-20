# Small reproducible inputs

The default input is original generated equipment data. `generate --output /tmp/pg-staged --seed 1729` creates 5,000 observations, 50 assets and 12 sensors with 2.5% missingness, a six-hour label horizon and correlated asset/time effects. No external data is downloaded.

A staged example:

```bash
uv run --locked python -m pp_proving_ground.cli generate --output /tmp/pg-staged --seed 1729
uv run --locked python -m pp_proving_ground.cli train --output /tmp/pg-staged --estimator logistic --seed 1729
uv run --locked python -m pp_proving_ground.cli promote --output /tmp/pg-staged --version 1 --expected-generation 0
uv run --locked python -m pp_proving_ground.cli evaluate --output /tmp/pg-staged --version 1 --role test
uv run --locked python -m pp_proving_ground.cli model-card --output /tmp/pg-staged
```

Use `generate --split-policy entity` to ask an unseen-asset question. This changes the scientific question and is not a substitute for temporal forecasting validation. The API accepts a list of records whose exact sensor names come from `split.json`'s referenced dataset contract; missing sensor *values* use JSON `null`, while missing sensor *keys* are refused.

For an existing legacy registry, follow the [upgrade procedure](../docs/OPERATIONS.md#upgrade-legacy-evaluation-evidence).
`reevaluate-registry` leaves its fresh target undeployed. Use `--registry` on
train/evaluate/promote/serve to adopt that target without replacing historical
registry bytes. The selected output remains the dataset/split/model-store root;
retain it with every external registry that depends on it.
