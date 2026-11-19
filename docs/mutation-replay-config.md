# Mutation trace comparison and endpoint configuration

## Compare two completed traces

The replay command compares existing JSONL traces; it does not contact a model or
endpoint. Candidate records are matched by their stable `key` (falling back to
`payload_sha256`). Duplicate keys and malformed candidate records are errors,
not silently resolved. Non-candidate events such as skips are ignored.

```bash
omjb-mutate replay --baseline reports/baseline.jsonl --candidate reports/current.jsonl
```

The JSON report includes matched candidates, candidates present in only one trace,
and allow/block flips. An allow-to-block flip means the candidate became more
restrictively classified; a block-to-allow flip should be reviewed rather than
automatically treated as a success.

## Endpoint configuration

The run command accepts `--config endpoint.json` (or YAML with the optional
`yaml` extra). Settings resolve in this order:

1. Explicit CLI values (`--endpoint`, `--timeout`)
2. Config file keys (`endpoint`, `timeout`, `token_env`)
3. Environment variables (`OMJB_GUARDRAIL_ENDPOINT`,
   `OMJB_GUARDRAIL_TIMEOUT`, `OMJB_GUARDRAIL_TOKEN_ENV`)

The token itself is never accepted from a config file. Set the environment
variable named by `token_env` (default `OMJB_GUARDRAIL_TOKEN`). Do not commit
credentials or config files containing secrets. The adapter still requires HTTPS;
plain HTTP is permitted only for loopback hosts. The engine's human-reviewed
benign-probe gate and finite time/USD budgets remain mandatory.

Example `endpoint.json`:

```json
{
  "endpoint": "https://guardrail.example/evaluate",
  "timeout": 20,
  "token_env": "OMJB_GUARDRAIL_TOKEN"
}
```
