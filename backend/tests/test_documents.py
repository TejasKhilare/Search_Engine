from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.document_service import parse_range_header, sanitize_filename
from tests.conftest import AUTH, TEST_PASSWORD, bearer_headers
from tests.fakes import InMemoryStorage

DOCS = f"{settings.API_V1_PREFIX}/documents"


def _file(data: bytes, name: str = "report.pdf") -> dict:
    return {"file": (name, data, "application/pdf")}


# ── Upload ───────────────────────────────────────────────────────────────────
async def test_upload_pdf(client: AsyncClient, storage: InMemoryStorage, make_pdf: Callable) -> None:
    headers = await bearer_headers(client)
    pdf = make_pdf(pages=3)

    res = await client.post(DOCS, files=_file(pdf, "../../etc/Q3 report.pdf"), headers=headers)
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["status"] == "pending"
    assert doc["page_count"] == 3
    assert doc["size_bytes"] == len(pdf)
    assert doc["filename"] == "Q3 report.pdf"  # path stripped

    [(key, (stored, content_type))] = storage.objects.items()
    assert key.endswith(f"/documents/{doc['id']}.pdf")
    assert stored == pdf and content_type == "application/pdf"


async def test_upload_rejects_non_pdf_even_with_pdf_name(client: AsyncClient) -> None:
    headers = await bearer_headers(client)
    res = await client.post(DOCS, files=_file(b"MZ\x90\x00 not a pdf", "evil.pdf"), headers=headers)
    assert res.status_code == 415
    assert res.json()["error"]["message"] == "File is not a PDF"


async def test_upload_rejects_corrupt_pdf(client: AsyncClient) -> None:
    headers = await bearer_headers(client)
    res = await client.post(DOCS, files=_file(b"%PDF-1.7\n garbage garbage"), headers=headers)
    assert res.status_code == 415


async def test_upload_rejects_encrypted_pdf(client: AsyncClient, make_pdf: Callable) -> None:
    headers = await bearer_headers(client)
    res = await client.post(DOCS, files=_file(make_pdf(password="pw")), headers=headers)
    assert res.status_code == 415
    assert "Password-protected" in res.json()["error"]["message"]


async def test_upload_rejects_empty_file(client: AsyncClient) -> None:
    headers = await bearer_headers(client)
    res = await client.post(DOCS, files=_file(b""), headers=headers)
    assert res.status_code == 400


async def test_upload_enforces_size_limit(
    client: AsyncClient, make_pdf: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await bearer_headers(client)
    pdf = make_pdf()
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)  # any non-empty file is too big
    res = await client.post(DOCS, files=_file(pdf), headers=headers)
    assert res.status_code == 413


async def test_oversized_body_rejected_before_parsing(client: AsyncClient) -> None:
    headers = await bearer_headers(client)
    huge = b"%PDF-" + b"0" * (settings.max_upload_bytes + 2 * 1024 * 1024)
    res = await client.post(DOCS, files=_file(huge), headers=headers)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "payload_too_large"


async def test_duplicate_upload_is_409_with_existing_id(
    client: AsyncClient, storage: InMemoryStorage, make_pdf: Callable
) -> None:
    headers = await bearer_headers(client)
    pdf = make_pdf()
    first = (await client.post(DOCS, files=_file(pdf), headers=headers)).json()

    res = await client.post(DOCS, files=_file(pdf, "renamed.pdf"), headers=headers)
    assert res.status_code == 409
    assert res.json()["error"]["details"]["document_id"] == first["id"]
    assert len(storage.objects) == 1  # nothing extra stored


async def test_same_file_allowed_for_different_users(client: AsyncClient, make_pdf: Callable) -> None:
    pdf = make_pdf()
    assert (
        await client.post(DOCS, files=_file(pdf), headers=await bearer_headers(client))
    ).status_code == 201
    assert (
        await client.post(DOCS, files=_file(pdf), headers=await bearer_headers(client))
    ).status_code == 201


async def test_cookie_upload_requires_csrf(client: AsyncClient, make_pdf: Callable) -> None:
    await client.post(
        f"{AUTH}/register",
        json={"email": "c@example.com", "username": "cookie_user", "password": TEST_PASSWORD},
    )
    login = await client.post(f"{AUTH}/login", json={"email": "c@example.com", "password": TEST_PASSWORD})
    csrf = login.json()["csrf_token"]

    assert (await client.post(DOCS, files=_file(make_pdf()))).status_code == 403
    res = await client.post(DOCS, files=_file(make_pdf()), headers={"X-CSRF-Token": csrf})
    assert res.status_code == 201


# ── Read / list ──────────────────────────────────────────────────────────────
async def test_list_is_paginated_newest_first(client: AsyncClient, make_pdf: Callable) -> None:
    headers = await bearer_headers(client)
    ids = []
    for i in range(3):
        res = await client.post(DOCS, files=_file(make_pdf(text=f"doc {i}"), f"d{i}.pdf"), headers=headers)
        ids.append(res.json()["id"])

    page = (await client.get(DOCS, params={"limit": 2}, headers=headers)).json()
    assert page["total"] == 3 and page["limit"] == 2
    assert len(page["items"]) == 2

    rest = (await client.get(DOCS, params={"limit": 2, "offset": 2}, headers=headers)).json()
    all_ids = [d["id"] for d in page["items"] + rest["items"]]
    assert sorted(all_ids) == sorted(ids)

    filtered = (await client.get(DOCS, params={"status": "ready"}, headers=headers)).json()
    assert filtered["total"] == 0


async def test_users_cannot_access_each_others_documents(client: AsyncClient, make_pdf: Callable) -> None:
    owner = await bearer_headers(client)
    other = await bearer_headers(client)
    doc_id = (await client.post(DOCS, files=_file(make_pdf()), headers=owner)).json()["id"]

    assert (await client.get(DOCS, headers=other)).json()["total"] == 0
    for method, path in [
        ("GET", f"{DOCS}/{doc_id}"),
        ("GET", f"{DOCS}/{doc_id}/file"),
        ("DELETE", f"{DOCS}/{doc_id}"),
    ]:
        res = await client.request(method, path, headers=other)
        assert res.status_code == 404, (method, path)

    assert (await client.get(f"{DOCS}/{doc_id}", headers=owner)).status_code == 200


async def test_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get(DOCS)).status_code == 401


# ── File download ────────────────────────────────────────────────────────────
async def test_download_full_file(client: AsyncClient, make_pdf: Callable) -> None:
    headers = await bearer_headers(client)
    pdf = make_pdf(pages=2)
    doc_id = (await client.post(DOCS, files=_file(pdf, "Résumé.pdf"), headers=headers)).json()["id"]

    res = await client.get(f"{DOCS}/{doc_id}/file", headers=headers)
    assert res.status_code == 200
    assert res.content == pdf
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["accept-ranges"] == "bytes"
    assert res.headers["content-length"] == str(len(pdf))
    assert "filename*=UTF-8''R%C3%A9sum%C3%A9.pdf" in res.headers["content-disposition"]


async def test_download_byte_range(client: AsyncClient, make_pdf: Callable) -> None:
    headers = await bearer_headers(client)
    pdf = make_pdf()
    doc_id = (await client.post(DOCS, files=_file(pdf), headers=headers)).json()["id"]

    res = await client.get(f"{DOCS}/{doc_id}/file", headers={**headers, "Range": "bytes=0-99"})
    assert res.status_code == 206
    assert res.content == pdf[:100]
    assert res.headers["content-range"] == f"bytes 0-99/{len(pdf)}"

    res = await client.get(f"{DOCS}/{doc_id}/file", headers={**headers, "Range": f"bytes={len(pdf)}-"})
    assert res.status_code == 416
    assert res.headers["content-range"] == f"bytes */{len(pdf)}"


# ── Delete ───────────────────────────────────────────────────────────────────
async def test_delete_removes_row_and_file(
    client: AsyncClient, storage: InMemoryStorage, make_pdf: Callable
) -> None:
    headers = await bearer_headers(client)
    doc_id = (await client.post(DOCS, files=_file(make_pdf()), headers=headers)).json()["id"]
    assert len(storage.objects) == 1

    assert (await client.delete(f"{DOCS}/{doc_id}", headers=headers)).status_code == 204
    assert storage.objects == {}
    assert (await client.get(f"{DOCS}/{doc_id}", headers=headers)).status_code == 404


# ── Pure helpers ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("C:\\Users\\me\\report.pdf", "report.pdf"),
        ("../../../etc/passwd", "passwd.pdf"),
        ('a<b>c:"d|e?f*.pdf', "abcdef.pdf"),
        ("  .hidden. ", "hidden.pdf"),
        ("", "document.pdf"),
        (None, "document.pdf"),
        ("x" * 300 + ".pdf", "x" * 251 + ".pdf"),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("bytes=0-9", (0, 9)),
        ("bytes=10-", (10, 99)),
        ("bytes=-10", (90, 99)),
        ("bytes=50-1000", (50, 99)),
        ("bytes=0-1,5-6", None),  # multi-range: serve whole file
        ("items=0-5", None),
    ],
)
def test_parse_range_header(header: str | None, expected: tuple[int, int] | None) -> None:
    result = parse_range_header(header, size=100)
    assert (None if result is None else (result.start, result.end)) == expected
