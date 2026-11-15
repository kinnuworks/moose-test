"""Log reading must page through every row. A run with more than one page of model calls
(open_deep_research made over 500 in one run) was capped at the first page and undercounted.
Written before the paging fix in moosetest/bifrost.py."""
from moosetest.bifrost import Bifrost


def fake_client(n_rows, page_cap=500, vk="vk1"):
    b = object.__new__(Bifrost)
    calls = []

    def _req(method, path, ok=(200, 201), params=None, **kw):
        params = params or {}
        calls.append(dict(params))
        limit = min(int(params.get("limit", 50)), page_cap)
        offset = int(params.get("offset", 0))
        rows = [{"id": f"r{i}", "virtual_key_id": vk} for i in range(n_rows)][offset:offset + limit]
        return {"logs": rows, "pagination": {"limit": limit, "offset": offset, "total_count": n_rows}}

    b._req = _req
    return b, calls


def test_llm_logs_reads_every_page():
    b, calls = fake_client(1234)
    rows = b.llm_logs("vk1")
    assert len(rows) == 1234
    assert len({r["id"] for r in rows}) == 1234
    assert len(calls) == 3


def test_relay_logs_reads_every_page():
    b, _ = fake_client(777)
    assert len(b.relay_logs("vk1")) == 777


def test_small_result_is_one_request():
    b, calls = fake_client(3)
    assert len(b.llm_logs("vk1")) == 3 and len(calls) == 1


def test_server_smaller_page_than_asked_still_reads_all():
    b, _ = fake_client(260, page_cap=100)
    assert len(b.llm_logs("vk1")) == 260
