# Searchable code-analysis evidence

Run `python scripts/portfolio.py integration code-search` after setting up PyTrace and Atlas. The stages run in separate project environments and exchange JSON files. The authored input files are analyzed, never imported or executed.

PyTrace emits shell, SQL, and async-blocking findings. The adapter maps stable diagnostic identities to search documents, with the SQL finding restricted to a synthetic operator principal. It fixes the shell call, emits the updated findings and obsolete-document deletion list, then changes only the hidden SQL source. Atlas must expose only current authorized evidence; hidden changes must preserve the public query's score, count, and snippets. Query judgments are declared from the authored fixtures rather than inferred from ranking output.

Reports live under a fresh `.local/integrations/code-search/` run. A retrieval score is not a vulnerability severity score or proof of a finding's correctness.
