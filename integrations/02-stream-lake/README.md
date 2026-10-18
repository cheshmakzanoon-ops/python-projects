# Corrected stream results and historical lake snapshots

Run `python scripts/portfolio.py integration stream-lake` from the repository root after setting up Current and Quarry. Each stage executes in its own installed project environment; the boundary is JSON files, with no sibling imports.

A 10-second tumbling window first contains 10, then receives an accepted-late reading of 7. Its stable key gets revision 2 with sum 17. The bridge sends revisions 1, 1, 2, 1 without manufacturing new versions. Quarry retains the latest value, keeps a pinned historical value of 10, and rejects a conflicting replay of the historical version. The independent full rebuild selects the greatest explicit version per namespaced key.

The run creates fresh owned state under `.local/integrations/stream-lake/`. Its report includes source/control records, exact delivery IDs, mapping, and snapshot manifests. This verifies the named local source/sink contract, not arbitrary exactly-once network effects.
