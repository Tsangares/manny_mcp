# 2026-07-19 — FINDING: pproxy cannot carry dataimpulse sticky/geo username tokens

**Type:** lesson for future agents (proxy relay). **Status:** blocker identified + root-caused, fix
direction given. No relay code changed in this session (a concurrent session owns `proxy_relay.sh`).

## TL;DR

The opt-in proxy relay we built (`scripts/remote/proxy_relay.sh`, commit `403e235`) uses **pproxy**.
**pproxy's `-r` upstream-URI parser rejects any dataimpulse session/geo token in the username** —
not just the `;`, but the `.` too. So a US-pinned sticky session (`login__cr.us;sessid.<id>`) cannot
be expressed to pproxy in any form. The relay must be swapped to a tool that accepts arbitrary
upstream auth (`gost` / `microsocks` / `3proxy`), or the sticky/geo must be configured dashboard-side.

## Evidence (manual pproxy probes, laptop, throwaway ports, torn down)

All forms fed to `pproxy ... -r <uri>` on a local test port, then `curl -x socks5h://127.0.0.1:<p>`:

| Upstream username form | Result |
|---|---|
| `<login>` (bare, `#user:pass`) | ✅ relay up, egress `123.24.202.113` |
| `<login>__cr.us` (geo only, `#user:pass`) | ❌ `invalid proxies_by_uri value` (parse-reject) |
| `<login>__cr.us;sessid.osrs-tut-01` (raw `;`) | ❌ parse-reject |
| `<login>__cr.us%3Bsessid…` in `@`-userinfo form | ❌ parse-reject |
| `<login>__cr.us` in `@`-userinfo form (geo only) | ❌ parse-reject |

**Conclusion 1:** pproxy rejects the `.` in `__cr.us` (form 2 fails with no `;` present at all), so
percent-encoding the `;` cannot fix it. pproxy's URI grammar is too strict for token-style auth.

**Conclusion 2 (independently important):** the *only* form pproxy accepts — the bare login —
egressed a **non-US** residential IP (`123.24.202.113`; an earlier smoke test gave `82.0.170.71`).
Without the `cr.us` token dataimpulse hands out **random-country** exits. A game account logging in
from a rotating set of countries is itself a ban signal, so "just use pproxy with the bare login" is
**not** an acceptable shortcut — the US geo-pin genuinely matters.

## dataimpulse token syntax (confirmed from their docs — this part is correct)

- Sticky: `sessid.<id>` in the username (caller-chosen id, ~30-min TTL, no username param to extend).
- Geo: `cr.<iso>` (e.g. `cr.us`). Params: `__` after login, `.` key/value, `;` between params.
- Port `:10000`–`:20000` are already sticky ports; `:823`/`:824` rotate.
- Full form: `socks5h://<login>__cr.us;sessid.<id>:<pass>@gw.dataimpulse.com:10000`

The token is **right**; pproxy just can't consume it.

## Fix direction (for whoever owns proxy_relay.sh)

1. **Swap the relay tool.** `gost -L socks5://127.0.0.1:<port> -F 'socks5://<login>__cr.us;sessid.<id>:<pass>@gw.dataimpulse.com:10000'`
   (or `microsocks`/`3proxy`) — these pass the upstream auth string through verbatim. Re-run the
   probe table above to confirm the chosen tool accepts the token AND egresses a US IP.
2. Keep the relay's `credentials.yaml`→pproxy conversion logic only if staying on pproxy for the
   bare-login case; otherwise replace it with the tool's native `-F`/upstream flag.
3. Verification gate is unchanged: same US IP across repeated `curl`s (sticky held) + `ipinfo`
   `country=US`, THEN prove the raw game socket (43594) traverses it on a throwaway/banned alias.

## Durable artifact left this session

`~/.manny/proxies.yaml` (600, **not** in repo) — proxy creds in a **Bolt-immune** file, separate from
`credentials.yaml`. Holds the correct `__cr.us;sessid.osrs-tut-01` sticky+US socks5 token, ready for
the swapped relay as-is. Motivation: a Bolt credential re-import at ~11:02 this day **wiped the
`proxies:` section out of `credentials.yaml`** (the same recurring hazard that resets `default:` to a
banned alias) — which is why the previously-working relay suddenly had no creds. `proxy_relay.sh`
already honors a `MANNY_CREDS` override, so pointing it at `~/.manny/proxies.yaml` sidesteps the wipe.

## Cross-refs

- [`2026-07-19_proxy_egress_implementation.md`](2026-07-19_proxy_egress_implementation.md) — the relay build.
- [`2026-07-19_proxy_ip_wiring_plan.md`](2026-07-19_proxy_ip_wiring_plan.md) — plan + verification gate.
