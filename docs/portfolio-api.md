# Equity and options portfolio API

## MCP integration (preferred)

Connect an MCP client to `http://localhost:8080/mcp` using Streamable HTTP; the existing API process serves both transports on the same port. Use `get_portfolio`, `add_holding`, `update_holding`, `delete_holding`, `clear_portfolio`, and `portfolio_summary`. See [client setup and access controls](MCP.md) and [all tool schemas](mcp-route-mapping.json).

With an initialized `ClientSession` named `client`:

```python
result = await client.call_tool("get_portfolio", {"query": {"user_id": "user_123"}})
if result.isError:
    raise RuntimeError(result.structuredContent)
print(result.structuredContent["body"])
```

To create/upsert an equity, call `add_holding` with `{"body":{"user_id":"user_123","asset_class":"equity","ticker":"AAPL","shares":100,"avg_price":175}}`. This mutates the portfolio. For update/delete, put `position_key` in `path` and use the discovered body/query schema for user scoping. The original HTTP status (including create versus upsert) is preserved in `structuredContent.status_code`.

## REST alternative and shared portfolio semantics

The REST examples below remain supported. The schema/migration requirements, position identity, option behavior and confirmation rules apply equally through MCP.


The explicit portfolio CRUD API stores positions in PostgreSQL. Options support requires [migration 025](../migrations/postgres/025_options_support.up.sql). The request and response models live in [the portfolio router](../src/routers/portfolio.py); lifecycle and symbol helpers live in [the portfolio service](../src/services/portfolio_service.py).

## Create or upsert

`POST /v1/portfolio/holding` returns a holding with `created: true` and HTTP 201 for a new position, or `created: false` and HTTP 200 for an existing position. Repeating a contract updates one position; it does not append a trade or create a separate lot.

Equity example:

```bash
curl -X POST http://localhost:8080/v1/portfolio/holding \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user_123","asset_class":"equity","ticker":"AAPL","shares":100,"avg_price":175}'
```

Option example (illustrative data):

```bash
curl -X POST http://localhost:8080/v1/portfolio/holding \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user_123","asset_class":"option","underlying_ticker":"TLN","option_type":"put","action_type":"sell_to_open","strike_price":300,"expiration_date":"2026-12-18","contracts":1,"premium":500,"collateral_required":30000}'
```

This generates `ticker: "TLN261218P00300000"`: underlying + YYMMDD + C/P + strike multiplied by 1000, padded to eight digits. The database retains one row per `(user_id, ticker)`.

| Input | Contract |
| --- | --- |
| `user_id` | Required for every write |
| `asset_class` | `equity` or `option`; omitted defaults to equity unless option type, strike, or expiration is supplied |
| Equity fields | `ticker` required; `asset_name`, `shares`, `avg_price` optional |
| Option identity | `underlying_ticker` (or `ticker` as underlying fallback), `option_type` (`put` / `call`), positive `strike_price`, ISO `expiration_date` |
| Option action | Required: `sell_to_open`, `buy_to_open`, `sell_to_close`, or `buy_to_close` |
| `contracts` | Positive integer; defaults to 1 on creation (one contract represents 100 shares) |
| `premium` | Optional caller-supplied amount; the API does not calculate it |
| `collateral_required` | Optional caller-supplied nonnegative amount; the API does not infer cash/margin requirements or covered-call backing |

Options cannot carry `shares` or `avg_price`; equities cannot carry option fields. Invalid asset-class/contract combinations are rejected. Business validation commonly returns 400; model/type validation can return 422.

## Read positions and collateral

```bash
curl 'http://localhost:8080/v1/portfolio?user_id=user_123'
curl 'http://localhost:8080/v1/portfolio?user_id=user_123&include_inactive=true'
```

The response contains `user_id`, flat `holdings`, grouped `equities` and `options`, `total_holdings`, `last_updated`, and `summary`:

- `total_equities` and `total_options`: counts in the returned view.
- `active_options`: returned options whose computed status is `active`.
- `total_committed_options_collateral`: sum of supplied collateral for active `sell_to_open` positions, rounded to two decimals. Missing collateral contributes zero; long, closed, and expired positions do not contribute.

Options have computed status `closed` for either `*_to_close` action, otherwise `expired` when expiration is before the server's current date, otherwise `active`. Expiration day itself remains active. Equities have no option status. The default excludes closed/expired options; `include_inactive=true` includes them. This is position tracking, not order execution, market pricing, assignment processing, or an automatic collateral calculator.

The older `GET /v1/portfolio/summary` endpoint retains a different summary shape; it does not provide these grouped lifecycle/collateral aggregates.

## Update or close

`PUT /v1/portfolio/holding/{position_key}` takes `user_id` in the JSON body. Keys resolve by UUID first, then the option key tuple if supplied, then equity/OCC symbol.

```bash
curl -X PUT http://localhost:8080/v1/portfolio/holding/TLN261218P00300000 \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user_123","action_type":"buy_to_close"}'
```

Updates are partial: omitted/null values preserve existing values. Options can update `asset_name`, `contracts`, `premium`, `collateral_required`, and `action_type`. Equities can update `asset_name`, `shares`, and `avg_price`. A missing position returns 404.

To address an option by tuple, use the underlying in the path and supply `option_type`, `strike_price`, and `expiration_date` together in the body; `underlying_ticker` may override the path underlying. These fields locate a contract, not modify its terms. Close/remove the old contract and add a new one to record a roll. Closing changes the current position row; it does not create a transaction history entry.

## Delete

`DELETE /v1/portfolio/holding/{position_key}?user_id=...` accepts a UUID or equity/OCC symbol. Tuple lookup uses `option_type`, `strike_price`, and `expiration_date` query parameters together, optionally `underlying_ticker`. `DELETE /v1/portfolio?user_id=...` removes all holdings for that user. Deletion removes records; use a close action to retain an inactive position.

## Upgrade

Apply pending migrations using the [migration manager](../migrations/README.md) before serving options requests. Migration 025 defaults existing positions to `equity`, adds contract fields, widens `ticker`, and enforces per-class constraints. Its [down migration](../migrations/postgres/025_options_support.down.sql) **deletes all option positions** before removing the columns; preserve/export any option records before a rollback.

Existing regression coverage: [portfolio API tests](../tests/unit/test_portfolio_api.py).
