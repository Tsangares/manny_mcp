#!/usr/bin/env python3
"""socks_relay.py — no-auth loopback SOCKS5 relay -> dataimpulse upstream (auth).

WHY THIS EXISTS (replaces pproxy for the upstream leg):
  pproxy's `-r` URI parser REJECTS the dataimpulse session/geo token in the
  username (the `.` in `__cr.us` and the `;` between params both blow up its
  `proxies_by_uri` grammar — see
  journals/2026-07-19_pproxy_incompatible_with_dataimpulse_tokens.md). A live
  OSRS session needs BOTH a US geo-pin (`cr.us`) and a sticky session
  (`sessid.<id>`), so the token is mandatory and pproxy is a dead end.

  This is a ~200-line pure-asyncio SOCKS5 forwarder with ZERO third-party deps.
  It accepts a NO-AUTH SOCKS5 on 127.0.0.1:<port> (what the JVM speaks via
  -DsocksProxyHost/-DsocksProxyPort) and forwards every CONNECT to the
  dataimpulse gateway, doing username/password auth with the token string
  passed through VERBATIM. Domain-name targets are forwarded as ATYP=domain so
  the EXIT resolves DNS (no local-DNS leak of the home resolver). The raw OSRS
  game socket (TCP 43594) is just another CONNECT, so it traverses too.

SECRETS: the upstream user/pass are read from the creds file INSIDE this process
and never printed, never put on argv, never logged. Connection logs show only
the (non-secret) target host:port so a smoke test can confirm traffic flow.

Creds: reads proxies.dataimpulse.socks5 (socks5h://user:pass@host:port) from the
first of --creds / ~/.manny/proxies.yaml / ~/.manny/credentials.yaml that has it.
"""
import argparse
import asyncio
import os
import sys

DEFAULT_CREDS = [
    os.path.expanduser("~/.manny/proxies.yaml"),
    os.path.expanduser("~/.manny/credentials.yaml"),
]


def _apply_token_overrides(user, session, drop_session):
    """Rewrite the dataimpulse username token params in `user`.

    The username is `<login>__<param>;<param>;...` where each param is
    `key.value` (e.g. `cr.us`, `sessid.osrs-tut-01`). The geo pin (`cr.*`) is
    ALWAYS preserved. `session` sets/replaces the `sessid` param; `drop_session`
    removes it (used by the port-per-lane model, where the gateway PORT — not a
    sessid token — pins the sticky exit IP). If neither is given, the token is
    returned unchanged. Never prints the secret (login is untouched, passed
    through)."""
    login, sep, tokenstr = user.partition("__")
    params = [p for p in tokenstr.split(";") if p] if sep else []

    def setparam(key, value):
        out, found = [], False
        for p in params:
            if p.split(".", 1)[0] == key:
                found = True
                if value is not None:
                    out.append("%s.%s" % (key, value))
            else:
                out.append(p)
        if value is not None and not found:
            out.append("%s.%s" % (key, value))
        return out

    if drop_session:
        params = setparam("sessid", None)
    elif session is not None:
        params = setparam("sessid", session)
    return "%s__%s" % (login, ";".join(params)) if params else login


def load_upstream(explicit, upstream_port=None, session=None, drop_session=False):
    """Return (host, port, user, pass) from the first creds file that has
    proxies.dataimpulse.socks5. Never prints the secret.

    upstream_port overrides the gateway port (port-per-lane sticky model).
    session / drop_session rewrite the sessid token via _apply_token_overrides."""
    import yaml
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(DEFAULT_CREDS)
    seen = set()
    tried = []
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        tried.append(path)
        try:
            data = yaml.safe_load(open(path)) or {}
        except FileNotFoundError:
            continue
        raw = ((data.get("proxies") or {}).get("dataimpulse") or {}).get("socks5")
        if not raw:
            continue
        after = raw.split("://", 1)[1]
        userinfo, _, hostport = after.rpartition("@")
        user, _, pw = userinfo.partition(":")
        host, _, port = hostport.rpartition(":")
        if not (host and port and user):
            sys.stderr.write(
                "socks_relay: malformed socks5 value in %s\n" % path)
            sys.exit(4)
        user = _apply_token_overrides(user, session, drop_session)
        if upstream_port is not None:
            port = upstream_port
        return host, int(port), user, pw
    sys.stderr.write(
        "socks_relay: proxies.dataimpulse.socks5 not found in any of: %s\n"
        % ", ".join(tried))
    sys.exit(3)


async def _readn(reader, n):
    return await reader.readexactly(n)


async def _read_addr(reader):
    """Read ATYP + address + port from a SOCKS5 stream. Returns the raw
    (atyp_byte + addr_bytes + port_bytes) so it can be forwarded verbatim, plus
    a human label for logging."""
    atyp = (await _readn(reader, 1))[0]
    if atyp == 0x01:      # IPv4
        addr = await _readn(reader, 4)
        label = ".".join(str(b) for b in addr)
    elif atyp == 0x03:    # domain
        ln = (await _readn(reader, 1))[0]
        addr = bytes([ln]) + await _readn(reader, ln)
        # label is for logging only — plain-ascii decode (idna codec rejects the
        # 'replace' error handler, which used to crash every hostname CONNECT).
        label = addr[1:].decode("ascii", "replace") if ln else ""
    elif atyp == 0x04:    # IPv6
        addr = await _readn(reader, 16)
        label = ":ipv6:"
    else:
        raise ValueError("bad ATYP %d" % atyp)
    port_b = await _readn(reader, 2)
    port = int.from_bytes(port_b, "big")
    return bytes([atyp]) + addr + port_b, "%s:%d" % (label, port)


async def _pipe(src, dst):
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        try:
            dst.close()
        except OSError:
            pass


class Relay:
    def __init__(self, up_host, up_port, up_user, up_pass, game_443=False):
        self.up_host = up_host
        self.up_port = up_port
        self.up_user = up_user.encode()
        self.up_pass = up_pass.encode()
        # game_443: rewrite an outbound CONNECT to the raw OSRS game port 43594
        # into port 443. dataimpulse BLOCKS 43594 (SOCKS REP!=0) but allows 443,
        # and the OSRS world host serves the SAME *.runescape.com TLS game
        # service on both ports (proven 2026-07-19: full TLS to :443 traverses
        # the exit; :43594 is refused). Lets the game socket ride the proxy over
        # 443 with NO client/Java change. OFF by default; opt-in + verify with a
        # throwaway login before any real session.
        self.game_443 = game_443

    async def handle(self, c_reader, c_writer):
        peer = c_writer.get_extra_info("peername")
        sys.stderr.write("relay: client connected %s\n" % (peer,))
        try:
            # --- client greeting (JVM -> us), no-auth ---
            ver, nmethods = await _readn(c_reader, 2)  # each is an int
            if ver != 0x05:
                c_writer.close(); return
            await _readn(c_reader, nmethods)  # discard the method list
            c_writer.write(b"\x05\x00"); await c_writer.drain()
            # --- client request ---
            hdr = await _readn(c_reader, 3)  # VER CMD RSV
            if hdr[0] != 0x05 or hdr[1] != 0x01:  # only CONNECT
                c_writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
                await c_writer.drain(); c_writer.close(); return
            addr_raw, label = await _read_addr(c_reader)
            # opt-in game-port rewrite: 43594 -> 443 (proxy blocks 43594, allows
            # 443; same TLS game service on both). Only the trailing port bytes.
            if self.game_443 and addr_raw[-2:] == (43594).to_bytes(2, "big"):
                addr_raw = addr_raw[:-2] + (443).to_bytes(2, "big")
                label = "%s->443(game-rewrite)" % label
        except (asyncio.IncompleteReadError, ConnectionError, ValueError, OSError) as e:
            sys.stderr.write("relay: client parse error from %s: %r\n" % (peer, e))
            try:
                c_writer.close()
            except OSError:
                pass
            return

        # --- open upstream + SOCKS5 username/password auth ---
        try:
            u_reader, u_writer = await asyncio.wait_for(
                asyncio.open_connection(self.up_host, self.up_port), timeout=20)
            u_writer.write(b"\x05\x01\x02")  # 1 method: user/pass
            await u_writer.drain()
            sel = await _readn(u_reader, 2)
            if sel[1] != 0x02:
                raise ConnectionError("upstream refused user/pass auth")
            u_writer.write(bytes([0x01, len(self.up_user)]) + self.up_user
                           + bytes([len(self.up_pass)]) + self.up_pass)
            await u_writer.drain()
            ok = await _readn(u_reader, 2)
            if ok[1] != 0x00:
                raise ConnectionError("upstream auth rejected")
            # forward the CONNECT verbatim (preserves domain -> exit resolves DNS)
            u_writer.write(b"\x05\x01\x00" + addr_raw)
            await u_writer.drain()
            rep = await _readn(u_reader, 3)
            _, up_label = await _read_addr(u_reader)  # consume BND.ADDR/PORT
            if rep[1] != 0x00:
                sys.stderr.write("relay: upstream CONNECT %s failed rep=%d\n"
                                 % (label, rep[1]))
                c_writer.write(bytes([0x05, rep[1], 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
                await c_writer.drain(); c_writer.close()
                u_writer.close(); return
        except (asyncio.IncompleteReadError, ConnectionError,
                asyncio.TimeoutError, OSError) as e:
            sys.stderr.write("relay: upstream error for %s: %s\n" % (label, e))
            try:
                c_writer.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
                await c_writer.drain(); c_writer.close()
            except OSError:
                pass
            return

        # success reply to client, then splice
        sys.stderr.write("relay: CONNECT %s -> upstream OK\n" % label)
        c_writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await c_writer.drain()
        await asyncio.gather(_pipe(c_reader, u_writer),
                             _pipe(u_reader, c_writer))


async def _amain(args):
    host, port, user, pw = load_upstream(
        args.creds, upstream_port=args.upstream_port,
        session=args.session, drop_session=args.no_session)
    relay = Relay(host, port, user, pw, game_443=args.game_port_443)
    server = await asyncio.start_server(relay.handle, args.listen_host, args.port)
    sys.stderr.write("relay: listening no-auth SOCKS5 on %s:%d -> %s:%d "
                     "(secret hidden)\n" % (args.listen_host, args.port,
                                            host, port))
    async with server:
        await server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="loopback SOCKS5 -> dataimpulse relay")
    ap.add_argument("--listen-host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1080)
    ap.add_argument("--creds", default=None,
                    help="creds file (default: ~/.manny/proxies.yaml then credentials.yaml)")
    ap.add_argument("--upstream-port", type=int, default=None,
                    help="override the dataimpulse gateway port (port-per-lane "
                         "sticky model: each port = an independent stable exit IP)")
    ap.add_argument("--session", default=None,
                    help="set/replace the sessid token param (sticky-by-token model)")
    ap.add_argument("--no-session", action="store_true",
                    help="strip the sessid token param (rely on gateway PORT for "
                         "stickiness; keeps the geo pin). Ignored if --session given.")
    ap.add_argument("--game-port-443", action="store_true",
                    help="rewrite outbound CONNECT :43594 -> :443 (dataimpulse "
                         "blocks 43594 but allows 443; the OSRS world serves the "
                         "same TLS game service on both). OFF by default; verify "
                         "with a throwaway login before any real session.")
    args = ap.parse_args()
    try:
        asyncio.run(_amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
