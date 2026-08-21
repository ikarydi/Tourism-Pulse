# Tourism Pulse

Tourism intelligence platform scaffold.

## Repository layout

- `apps/`: API and dashboard applications
- `services/`: domain processing services
- `agents/`: research and intelligence agents
- `packages/`: shared Python packages
- `connectors/`: external data connectors
- `infrastructure/`: local and deployed infrastructure
- `tests/`: unit, integration, evaluation, and fixture data
- `docs/`: architecture, API, ADR, and research documentation
- `data/`: raw, seed, and evaluation data

## Development

The project uses Python tooling configured in `pyproject.toml`. Run `make test` to execute the test suite once tests are added.

## Testing

`pytest` never touches the database configured in `.env`. `tests/conftest.py`
derives an isolated database (same connection, `_test` appended to the
database name - e.g. `tourism_pulse_test`), creates it if missing, and resets
its schema at the start of every test session. Override the target with the
`TEST_DATABASE_URL` environment variable if you need something other than
the `_test` convention (e.g. in CI).
