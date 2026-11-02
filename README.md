# Dev Factory sandbox (fictitious code)

Public sandbox used to validate the isolated agent runs of the Dev Factory. **Everything here is fictitious**: a demo
guest house with invented units and bookings. No client data, no production system.

| Path | Role |
|---|---|
| `availability.py`, `tests/` | fictitious code the agents work on |
| `CLAUDE.md` | rules of the agents (developer and reviewer roles; tooling is off limits) |
| `CODEOWNERS` | every change needs the review of the human owner |
| `.github/workflows/devfactory-agent.yml` | `agent` job (no secret, read-only token, isolated user, network lock) then `publish` job (deterministic, the only one holding the App key) |
| `.github/workflows/ci.yml` | tests of every pull request, read-only |
| `.devfactory/` | trusted tooling of the two jobs, always taken from `main` |

Guarantees enforced by the repository settings:
- `main` accepts changes only through a pull request reviewed by the code owner, with the `test` check green; nobody
  bypasses it, and nobody force-pushes or deletes it;
- only the Dev Factory App creates or updates `agent/*` branches; it cannot push to `main`, create another branch, tag,
  approve or merge;
- only actions owned by GitHub, pinned by full commit SHA; the workflow token is read-only and cannot approve pull
  requests; workflows of outside contributors wait for an approval;
- agent runs are dispatched only from `main`.

Contributions are not expected: this repository exists for automated tests of the Dev Factory.
