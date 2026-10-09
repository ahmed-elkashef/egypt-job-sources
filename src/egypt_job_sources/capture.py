#!/usr/bin/env python3
"""Loopback-only public DOM capture handoff for operator-authorized source reads.

No browser control, credential access or external network access. A small local
form accepts the selected public DOM acquired by the operator and saves
an immutable, hashed checkpoint plus parser result. It is not a job application.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .sources import parse_browser_capture


def capture_directory() -> Path:
    """Use a local user cache; an explicit environment path may override it."""
    override = os.environ.get("EGYPT_JOBS_CAPTURE_DIR")
    if override is not None:
        if not override.strip():
            raise ValueError("EGYPT_JOBS_CAPTURE_DIR must name a local directory")
        return Path(override).expanduser().resolve()
    return Path.home() / ".cache" / "egypt-job-sources" / "public-captures"


MAX_CAPTURE_BYTES = 8_000_000
MAX_FORM_BYTES = MAX_CAPTURE_BYTES * 4 + 100_000
ADAPTER_VERSION = "0.1.0"
RECEIPT_PATTERN = r"[a-f0-9]{64}"


def encoded_capture(source, capture):
    # Canonical encoding preserves the submitted DOM, not executable code.
    return json.dumps(
        {"source": source, "capture": capture},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def save_capture(source, capture, directory=None):
    raw = encoded_capture(source, capture)
    if len(raw) > MAX_CAPTURE_BYTES:
        raise ValueError("Public capture exceeds byte limit")
    parsed = parse_browser_capture(source, capture)
    if parsed["status"] != "ok":
        raise ValueError(parsed["error"])
    digest = hashlib.sha256(raw).hexdigest()
    receipt = {
        "receipt_id": digest,
        "capture_sha256": digest,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "adapter_version": ADAPTER_VERSION,
        "evidence_purpose": "operator_capture_unregistered_supply",
        "payload": json.loads(raw),
        "parsed": parsed,
    }
    directory = capture_directory() if directory is None else Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / (digest + ".json")
    # Exclusive create keeps evidence immutable and repeated transfers idempotent.
    try:
        with target.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False)
        target.chmod(0o600)
    except FileExistsError:
        return read_capture(digest, directory)
    return parsed | {
        k: receipt[k]
        for k in (
            "receipt_id",
            "capture_sha256",
            "received_at",
            "adapter_version",
            "evidence_purpose",
        )
    }


def read_capture(receipt_id, directory=None):
    if not re.fullmatch(RECEIPT_PATTERN, receipt_id):
        raise ValueError("A canonical SHA-256 receipt ID is required")
    directory = capture_directory() if directory is None else Path(directory)
    target = directory / (receipt_id + ".json")
    if target.is_symlink() or target.stat().st_size > MAX_CAPTURE_BYTES * 3:
        raise ValueError("Invalid capture checkpoint")
    receipt = json.loads(target.read_text(encoding="utf-8"))
    raw = encoded_capture(receipt["payload"]["source"], receipt["payload"]["capture"])
    if hashlib.sha256(raw).hexdigest() != receipt_id or receipt.get("receipt_id") != receipt_id:
        raise ValueError("Capture digest mismatch")
    # Reparse the immutable original with current code; do not trust stored output.
    parsed = parse_browser_capture(receipt["payload"]["source"], receipt["payload"]["capture"])
    return parsed | {
        k: receipt[k]
        for k in (
            "receipt_id",
            "capture_sha256",
            "received_at",
            "adapter_version",
            "evidence_purpose",
        )
    }


FORM = """<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Egypt public source capture</title>
<style>body{font:17px system-ui;max-width:850px;margin:40px auto;padding:20px}label{display:block;margin:16px 0 8px}textarea{width:100%;height:240px}button{padding:10px 18px;margin-top:16px}small{color:#555}</style>
<h1>Save public source evidence</h1>
<p>Transfer the selected job-page capture from the authorized browser.</p>
<small>This local handoff preserves evidence. It does not review jobs or send applications.</small>
<form method=post action=/capture><label for=source>Source</label><select id=source name=source>
<option value=wuzzuf>WUZZUF</option><option value=forasna>Forasna</option><option value=arabjobs>ArabJobs</option></select>
<label for=capture>Public page capture</label><textarea id=capture name=capture required></textarea>
<br><button type=submit>Save capture</button></form></html>"""


def handler_for(directory):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never put raw page text or form values in server logs.

        def reply(self, status, body):
            body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def same_origin(self, mutation=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            return self.headers.get("Host") == expected and (
                not mutation or self.headers.get("Origin") == "http://" + expected
            )

        def do_GET(self):
            if not self.same_origin() or self.path != "/":
                return self.reply(403, "Unsupported local route")
            self.reply(200, FORM)

        def do_POST(self):
            if not self.same_origin(mutation=True) or self.path != "/capture":
                return self.reply(403, "Only the local capture form can submit evidence")
            if (
                self.headers.get("Content-Type", "").split(";")[0]
                != "application/x-www-form-urlencoded"
            ):
                return self.reply(415, "Use the local capture form")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_FORM_BYTES or self.headers.get("Transfer-Encoding"):
                    raise ValueError("Invalid form size")
                self.connection.settimeout(15)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("Incomplete form body")
                fields = parse_qs(body.decode("utf-8"), strict_parsing=True, max_num_fields=2)
                if set(fields) != {"source", "capture"} or any(
                    len(x) != 1 for x in fields.values()
                ):
                    raise ValueError("Exactly one source and public capture are required")
                source = fields["source"][0]
                if source not in {"wuzzuf", "forasna", "arabjobs"}:
                    raise ValueError("Unsupported public board")
                capture = json.loads(fields["capture"][0])
                result = save_capture(source, capture, directory)
                count = len(result.get("listings", []))
                receipt = escape(result["receipt_id"])
                link = escape(result["requested_url"])
                summary = (
                    f"{count} listing cards"
                    if capture["kind"] == "page"
                    else "Full description and requirements"
                )
                self.reply(
                    200,
                    f"<!doctype html><html lang=en><meta charset=utf-8><title>Capture saved</title><h1>Capture saved</h1><p>{escape(source)}: {summary}</p><p>Receipt: <code id=receipt>{receipt}</code></p><p>Source URL: {link}</p><p>Coverage remains incomplete. Individual review is pending.</p><a href=/>Save another capture</a></html>",
                )
            except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
                # Data error only; keep untrusted text escaped and exclude the HTML payload.
                self.reply(422, "Capture could not be saved: " + escape(str(exc)[:300]))

    return Handler


class LoopbackHTTPServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=0)
    show = sub.add_parser("show")
    show.add_argument("receipt_id")
    args = parser.parse_args()
    if args.command == "show":
        try:
            result = read_capture(args.receipt_id)
        except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
            result = {
                "status": "source_limited",
                "error": str(exc)[:300],
                "coverage_complete": False,
                "reviewed_by_model": False,
            }
        print(json.dumps(result, ensure_ascii=False))
        return
    server = LoopbackHTTPServer(("127.0.0.1", args.port), handler_for(capture_directory()))
    print(
        json.dumps(
            {
                "status": "ready",
                "local_url": f"http://127.0.0.1:{server.server_port}/",
                "capture_directory": str(capture_directory()),
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
