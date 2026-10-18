# Synthetic inputs

Generate versioned inputs rather than copying a bulk dataset:
`python -m pp_routecraft.cli generate --customers 25 --seed 1729 --output /tmp/rc-input`.
`pp_routecraft.fixtures.tiny()` is the hand-derived directed oracle fixture:
forward tour arcs all cost 2 (objective 1,8), reverse arcs cost 6,8,9,7.
`demo` emits an expanded matrix and actual loaded manifests in
`replanned-instance.json`; use it as a complete rolling-state example.
