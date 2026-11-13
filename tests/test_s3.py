from datetime import UTC, datetime

import pytest

from app.modules.files.s3 import UNSIGNED, signature

pytestmark = pytest.mark.modules("files")

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
# AWS documentation example: presigned GET of examplebucket/test.txt (Signature Version 4)
SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def test_presigned_signature_matches_aws_example():
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": "AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request",
        "X-Amz-Date": "20130524T000000Z",
        "X-Amz-Expires": "86400",
        "X-Amz-SignedHeaders": "host",
    }
    sig, signed = signature(
        method="GET",
        host="examplebucket.s3.amazonaws.com",
        path="/test.txt",
        query=query,
        headers={},
        payload_hash=UNSIGNED,
        secret_key=SECRET,
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
    )
    assert signed == "host"
    assert sig == "aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"


def test_header_signature_matches_aws_example():
    # AWS documentation example: GET /test.txt with a Range header
    sig, signed = signature(
        method="GET",
        host="examplebucket.s3.amazonaws.com",
        path="/test.txt",
        query={},
        headers={
            "range": "bytes=0-9",
            "x-amz-content-sha256": EMPTY,
            "x-amz-date": "20130524T000000Z",
        },
        payload_hash=EMPTY,
        secret_key=SECRET,
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
    )
    assert signed == "host;range;x-amz-content-sha256;x-amz-date"
    assert sig == "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
