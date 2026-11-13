"""Checks a running Docker stack with several backend replicas (CI: the scalable job).

    python scripts/check_stack.py http://localhost:8080 --email root@example.com \\
        --password ... [--link-file link.txt]

Needs AUTH_ENABLED, ADMIN_ENABLED, FILES_ENABLED with FILES_STORAGE=s3 and the root user;
only the standard library, so it runs without the project's requirements. What it proves:

- the API is ready (database, Redis, broker);
- the sign-in cookie works on every replica (one SECRET_KEY, shared sessions);
- a form sent by a visitor is stored as a lead and found in the admin;
- a file uploaded through one replica is served by the others, from the bucket;
- the sign-in rate limit counts once for all replicas (Redis), not per replica.

Requests go through the frontend's nginx, which spreads them over the replicas.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

ROUNDS = 9  # requests per check: with 3 replicas each one gets some


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("base", help="The site, e.g. http://localhost:8080")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--link-file", help="Write the file's download link here")
    args = parser.parse_args()
    api = args.base.rstrip("/") + "/api/v1"
    opener = build_opener(HTTPCookieProcessor(CookieJar()), NoRedirect())

    def call(method: str, path: str, data: bytes | None = None, headers=None):
        request = Request(api + path, data=data, method=method, headers=headers or {})
        try:
            with opener.open(request, timeout=15) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {name}{f': {detail}' if detail else ''}")
        if not ok:
            sys.exit(1)

    status, _, body = call("GET", "/ready")
    check("ready", status == 200, body.decode())

    form = f"username={args.email}&password={args.password}".encode()
    status, _, body = call(
        "POST", "/auth/login", form, {"Content-Type": "application/x-www-form-urlencoded"}
    )
    check("sign in", status in (200, 204), str(status))

    statuses = [call("GET", "/auth/users/me")[0] for _ in range(ROUNDS)]
    check("the session works on every replica", set(statuses) == {200}, str(statuses))

    # A visitor's form, then the lead in the admin (any replica: one database)
    marker = f"stack check {uuid.uuid4().hex}"
    status, _, body = call("GET", "/forms/contact")
    check("the contact form is described", status == 200, str(status))
    lead = {
        "name": "Stack Check",
        "email": "stack-check@example.com",
        "message": marker,
        "consent": True,
    }
    status, _, body = call(
        "POST", "/forms/contact", json.dumps(lead).encode(), {"Content-Type": "application/json"}
    )
    check("send the form", status == 200, body.decode()[:200])
    status, _, body = call("GET", "/admin/leads?" + urlencode({"q": marker}))
    found = json.loads(body).get("items", []) if status == 200 else []
    check(
        "the lead is in the admin",
        len(found) == 1 and found[0]["data"].get("message") == marker,
        f"{status}, {len(found)} found",
    )

    boundary = uuid.uuid4().hex
    content = f"stack check {uuid.uuid4()}".encode()
    multipart = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="check.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    status, _, body = call(
        "POST", "/files", multipart, {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    check("upload a file", status == 201, body.decode()[:200])
    file_id = json.loads(body)["id"]

    links = []
    for _ in range(ROUNDS):
        status, headers, _ = call("GET", f"/files/{file_id}")
        links.append((status, headers.get("Location", "")))
    check(
        "every replica serves it with a bucket link",
        all(status == 307 and "X-Amz-Signature=" in link for status, link in links),
        str([status for status, _ in links]),
    )
    if args.link_file:
        with open(args.link_file, "w") as out:
            out.write(f"{links[-1][1]}\n{content.decode()}\n")

    # The sign-in above counted too: with one shared counter the limit (10/minute) is
    # reached within 10 more attempts; counted per replica it would take about 30
    wrong = f"username=nobody-{uuid.uuid4().hex}@example.com&password=wrong".encode()
    attempts = []
    for _ in range(11):
        status, _, _ = call(
            "POST", "/auth/login", wrong, {"Content-Type": "application/x-www-form-urlencoded"}
        )
        attempts.append(status)
        if status == 429:
            break
    check("the rate limit is shared by the replicas", attempts[-1] == 429, str(attempts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
