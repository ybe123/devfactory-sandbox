# Rules for the Dev Factory agents (sandbox, fictitious data)

- Work only in this checkout. Do not use git, gh, curl, package managers or the network.
- Never modify `.github/`, `.devfactory/`, `CODEOWNERS`, `CLAUDE.md`, `.gitignore` or `.gitattributes`:
  the publication job refuses the whole patch.
- Developer: change `availability.py` and `tests/test_unit.py` only. Never touch `tests/acceptance/`.
- Reviewer: add or change files under `tests/acceptance/` only, one test per acceptance criterion, then write
  `.devfactory-verdicts.json`: `[{"criterion": "...", "status": "pass" | "fail"}]` (outside the patch).
- Run `python3 -m pytest -q` before finishing. You have no network except the model API, and no git. Do not invent business rules: the ticket gives all of them.
