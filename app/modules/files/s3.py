"""A small S3 client (AWS Signature Version 4) on the standard library.

Enough for file storage: put, delete and presigned download links, path-style
(`<endpoint>/<bucket>/<key>`), so it works with AWS S3 and S3-compatible
services (MinIO, Cloudflare R2, Yandex Object Storage, ...). For more of the
S3 API use boto3 instead.
"""

import hashlib
import hmac
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import BinaryIO
from urllib.parse import quote, urlsplit

ALGORITHM = "AWS4-HMAC-SHA256"
UNSIGNED = "UNSIGNED-PAYLOAD"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class S3Error(Exception):
    pass


def _encode(value: str, safe: str = "-_.~") -> str:
    return quote(value, safe=safe)


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def signing_key(secret_key: str, date: str, region: str, service: str = "s3") -> bytes:
    key = _hmac(f"AWS4{secret_key}".encode(), date)
    for part in (region, service, "aws4_request"):
        key = _hmac(key, part)
    return key


def signature(
    *,
    method: str,
    host: str,
    path: str,
    query: dict[str, str],
    headers: dict[str, str],
    payload_hash: str,
    secret_key: str,
    region: str,
    now: datetime,
) -> tuple[str, str]:
    """(signature, signed header names) for a request; `headers` exclude `host`."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    all_headers = {"host": host, **{name.lower(): value for name, value in headers.items()}}
    names = sorted(all_headers)
    canonical_request = "\n".join(
        [
            method,
            _encode(path, safe="-_.~/"),
            "&".join(f"{_encode(k)}={_encode(v)}" for k, v in sorted(query.items())),
            "".join(f"{name}:{all_headers[name].strip()}\n" for name in names),
            ";".join(names),
            payload_hash,
        ]
    )
    scope = f"{date}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [ALGORITHM, amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()]
    )
    key = signing_key(secret_key, date, region)
    return hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest(), ";".join(names)


class S3Client:
    def __init__(
        self, endpoint: str, bucket: str, region: str, access_key: str, secret_key: str
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        parts = urlsplit(self.endpoint)
        self.host = parts.netloc
        self.base_path = parts.path
        self.bucket = bucket
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key

    def _path(self, key: str) -> str:
        return f"{self.base_path}/{self.bucket}/{key}"

    def _request(
        self,
        method: str,
        key: str,
        body: BinaryIO | None = None,
        headers: dict[str, str] | None = None,
        payload_hash: str = EMPTY_SHA256,
    ) -> None:
        now = datetime.now(UTC)
        headers = {
            **(headers or {}),
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": now.strftime("%Y%m%dT%H%M%SZ"),
        }
        path = self._path(key)
        sig, signed = signature(
            method=method,
            host=self.host,
            path=path,
            query={},
            headers=headers,
            payload_hash=payload_hash,
            secret_key=self.secret_key,
            region=self.region,
            now=now,
        )
        scope = f"{now:%Y%m%d}/{self.region}/s3/aws4_request"
        headers["Authorization"] = (
            f"{ALGORITHM} Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed}, Signature={sig}"
        )
        url = f"{urlsplit(self.endpoint).scheme}://{self.host}{_encode(path, safe='-_.~/')}"
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30):
                pass
        except urllib.error.HTTPError as exc:
            raise S3Error(f"{method} {key}: HTTP {exc.code} {exc.read(300)!r}") from exc

    def put(self, key: str, body: BinaryIO, size: int, sha256: str, content_type: str) -> None:
        headers = {"Content-Length": str(size), "Content-Type": content_type}
        self._request("PUT", key, body, headers, payload_hash=sha256)

    def delete(self, key: str) -> None:
        self._request("DELETE", key)

    def presigned_get(self, key: str, expires: int, params: dict[str, str] | None = None) -> str:
        """A link that downloads the object without credentials for `expires` seconds;
        `params` may set response-content-disposition / response-content-type."""
        now = datetime.now(UTC)
        query = {
            **(params or {}),
            "X-Amz-Algorithm": ALGORITHM,
            "X-Amz-Credential": f"{self.access_key}/{now:%Y%m%d}/{self.region}/s3/aws4_request",
            "X-Amz-Date": now.strftime("%Y%m%dT%H%M%SZ"),
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": "host",
        }
        path = self._path(key)
        sig, _ = signature(
            method="GET",
            host=self.host,
            path=path,
            query=query,
            headers={},
            payload_hash=UNSIGNED,
            secret_key=self.secret_key,
            region=self.region,
            now=now,
        )
        encoded = "&".join(f"{_encode(k)}={_encode(v)}" for k, v in sorted(query.items()))
        url = f"{urlsplit(self.endpoint).scheme}://{self.host}{_encode(path, safe='-_.~/')}"
        return f"{url}?{encoded}&X-Amz-Signature={sig}"
