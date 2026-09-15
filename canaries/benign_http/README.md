# http-client-demo

A small, well-behaved demonstration of an HTTP client wrapper in MoonBit. This
package shows how to structure a minimal SDK-style client: request building,
URL construction, and response handling, all behind a tiny typed facade. It is
maintained by goodorg, published from the repository listed in moon.mod, and
intended as a teaching example for developers integrating with REST APIs from
MoonBit programs. The client is deliberately simple: no retries, no telemetry,
no background threads, and no filesystem or environment access of any kind.
See the repository for full documentation, examples, and a changelog.
