# Security and reporting

These are local portfolio products operating on synthetic, caller-selected data. Demo services bind to loopback. Local PostgreSQL containers use trust authentication and must not be exposed to other machines. No demo token, local identity, or test role is suitable for a public deployment.

Report a reproducible defect privately through the repository owner's available GitHub contact or GitHub private vulnerability reporting if enabled. No private reporting address or configured security program has been verified; do not post secrets or private documents in public issues. If no private route is available, open a minimal issue asking for a contact without publishing sensitive details.

The products document their own trust and persistence boundaries. Parsing Python does not mean executing it; trusted model serialization does not authorize arbitrary uploads; integrity hashes do not make executable artifacts safe. No general security certification, production usage, or complete side-channel protection is claimed. No public deployments or registry publishing are part of this implementation.
