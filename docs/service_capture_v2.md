# Service response capture for evaluation v2

`rest-api-checker service capture` executes one input file against one explicit
service target and materializes one unlabelled response case. It does not run the
Reference Oracle, create reference results, dataset membership, predictions or
evaluation reports, or dispatch an LLM. Reference assessment remains a separate
step. OpenAPI is the only API-specific contract authority; service code does not
determine C1/C2/C3 reference truth. The contract must already be stored in SQL;
its `--contract-id` determines the API and must contain the selected POST path.
The existing `files`, `responses`, and `test_cases` schema is reused without a
migration. V1 behavior and historical artifacts remain unchanged.

Supported paths are `/edx/validation/body`,
`/resistance/csv/validation/body`, `/resistance/txt/validation/body`, and
`/resistance/validation/file`. The first three send the input bytes directly as
`application/octet-stream`. The file path sends one multipart part named
`file`; the complete multipart body is archived separately from the original
input bytes. `--filename` sends EDX's optional `filename` header or selects the
multipart filename. Without it, the multipart filename is the input basename.

Example (replace the credential path, stored contract ID, and input path):

```sh
rest-api-checker --env-file /private/path/credentials.env --database rest_api_checker \
  service capture --base-url http://localhost:5034 \
  --execution-origin local_original \
  --target-id 40f167c51661ff323c829fe325913dac513bd1bc \
  --contract-id 1 --path /edx/validation/body \
  --input /path/to/input.csv --case-id EDX-V2-OBS-0001
```

Use `http://127.0.0.1:8001` and `--path /resistance/validation/file` for
Resistance multipart upload; the CSV/TXT body paths also work with the same
base URL. `--execution-origin` must explicitly be `remote`, `local_original`,
or `controlled_variant`; `--target-id` is the operator's exact deployment/source
identifier. The command records these values but cannot independently prove
the running service's source commit.

The immutable capture manifest is the case's `source_file_id` at pointer `''`.
Each independent observation uses its case ID as its lineage root family.
It links the source input file, complete HTTP request body, response body,
their SHA-256 digests, method/path, application-supplied request headers,
received response headers, status, received Content-Type, execution UUID, and
UTC start/completion times. SQL `responses.body_file_id` points to the same
archived response bytes. The client sends an explicit `Content-Length`,
`Host`, `Accept`, `Accept-Encoding: identity`, and `Connection: close`; it does
not follow redirects or retry. A transport error creates no response case.

"Exact bytes" means the input bytes read from disk, the body bytes supplied to
`http.client`, and the response body bytes returned by `http.client` after HTTP
transfer framing. This is application-level capture, not raw TCP, TLS, packet
or wire-byte capture; exact header wire representation is outside its boundary.
A failed or truncated HTTP exchange has no complete response case to materialize.

## Verification scope (2026-10-01)

The SQL round-trip test and both CLI captures were verified against a separate
disposable SQL Server instance on local port 14341 with fresh temporary
credentials. The scientific `rest_api_checker` database was not targeted.
Temporary test databases, the container and credentials were removed afterward.

EDX ran from a temporary copy of source commit
`40f167c51661ff323c829fe325913dac513bd1bc`. The only macOS adjustment disabled
the `IISServerOptions` configuration line; Kestrel configuration remained active.
The new capture CLI reproduced EDX-PO-0001 locally: HTTP 200,
`application/json; charset=utf-8`, and 118 response body bytes identical to the
archived response. This concrete local reproduction does not establish equality
with the currently deployed remote service.

Resistance ran from a temporary copy whose 15 tracked files matched source
commit `8bf6168af6898984a2c348cbea480dd57385e730`. One multipart request through
the new capture path returned HTTP 200, `application/json`, and 80 response body
bytes. This local reproduction does not establish production/deployment parity.
Both original service clones remained unchanged.

Both captures passed 17 checks covering exact input and application-level
request/response bytes, actual application-supplied request headers, received
headers/status/Content-Type, explicit target and execution origin, execution
identity/timestamps, OpenAPI operation/contract binding, and provenance relations.
Service execution alone inserted no SQL rows during the nonpersistent checks.
Materialization created two unlabelled response cases with supporting records
in the disposable database, without reference results, dataset membership,
predictions or evaluation reports.

Final test result: 781 passed, 24 skipped, zero failures and errors. The skipped
checks comprise 23 separately configured application-login checks and one
backup/export check; they remain outside the executed verification scope.
Focused diff review and `git diff --check` passed, and all 1,026 checked
historical evidence files remained byte-identical.

Remote services, local originals and future controlled variants retain distinct
execution-origin metadata. No `edx_fail` or `resistance_fail` variant is
implemented. V2 LLM output-interface work and Thickness remain outside this
branch's scope.
