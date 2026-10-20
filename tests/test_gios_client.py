from datetime import datetime

import pytest

from aq_pipeline.gios import GiosClient, extract_records, filter_city_stations, total_pages
from aq_pipeline.http import ApiError, HttpClient

from .conftest import FakeResponse, FakeSession


def make_client(responses, page_size=2):
    sleeps = []
    http = HttpClient({"metadata": 0, "current": 0, "archive": 0}, session=FakeSession(responses),
                      sleep=lambda s: sleeps.append(s), backoff_base_s=1)
    return GiosClient(http, "https://api.example/pjp-api/v1/rest", page_size=page_size), http, sleeps


def test_extract_records_ignores_links_and_meta():
    payload = {
        "links": [{"rel": "self", "href": "x"}],
        "meta": {"count": 2},
        "Lista danych pomiarowych": [{"Data": "2024-01-01 01:00:00", "Wartość": 12.5}],
        "totalPages": 1,
    }
    assert extract_records(payload) == [{"Data": "2024-01-01 01:00:00", "Wartość": 12.5}]
    assert total_pages(payload) == 1
    assert extract_records([{"a": 1}, "junk"]) == [{"a": 1}]
    assert extract_records({"links": []}) == []


def test_pagination_follows_total_pages():
    pages = [
        FakeResponse({"Lista": [{"id": 1}, {"id": 2}], "totalPages": 2}),
        FakeResponse({"Lista": [{"id": 3}], "totalPages": 2}),
    ]
    client, http, _ = make_client(pages)
    assert [r["id"] for r in client.stations()] == [1, 2, 3]
    requested = [params["page"] for _, params in http.session.requests]
    assert requested == [0, 1]
    assert all(params["size"] == 2 for _, params in http.session.requests)


def test_pagination_without_total_pages_stops_on_short_page():
    pages = [FakeResponse({"Lista": [{"id": 1}, {"id": 2}]}), FakeResponse({"Lista": []})]
    client, _, _ = make_client(pages)
    assert len(client.current_data(42)) == 2


def test_retry_on_429_honours_retry_after():
    pages = [FakeResponse({}, status=429, headers={"Retry-After": "30"}),
             FakeResponse({"Lista": [{"id": 1}], "totalPages": 1})]
    client, _, sleeps = make_client(pages)
    assert client.stations() == [{"id": 1}]
    assert 30.0 in sleeps


def test_archive_request_parameters_and_windows():
    pages = [FakeResponse({"Lista archiwalnych wyników pomiarów": [], "totalPages": 0})]
    client, http, _ = make_client(pages)
    client.archive_by_sensor(3497, datetime(2019, 1, 1, 0), datetime(2019, 12, 31, 23))
    url, params = http.session.requests[0]
    assert url.endswith("/archivalData/getDataBySensor/3497")
    assert params["dateFrom"] == "2019-01-01 00:00" and params["dateTo"] == "2019-12-31 23:00"

    windows = client.archive_windows(datetime(2016, 1, 1), datetime(2019, 6, 30, 23))
    assert windows[0][0] == datetime(2016, 1, 1)
    assert all((end - start).days < 366 for start, end in windows)
    assert windows[-1][1] == datetime(2019, 6, 30, 23)
    # windows are contiguous, without overlap or gap
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:], strict=False):
        assert (next_start - prev_end).total_seconds() == 3600


def test_filter_city_stations_handles_diacritics_and_field_names():
    stations = [
        {"Identyfikator stacji": 1, "Nazwa miasta": "Kraków"},
        {"Identyfikator stacji": 2, "Nazwa miasta": "KRAKOW"},
        {"Identyfikator stacji": 3, "Nazwa miasta": "Krakówka"},
        {"Identyfikator stacji": 4, "Miejscowość": "Kraków"},
        {"Identyfikator stacji": 5, "Nazwa miasta": "Skawina"},
    ]
    assert [s["Identyfikator stacji"] for s in filter_city_stations(stations, "Kraków")] == [1, 2, 4]


def test_gios_error_body_raises_api_error_without_retry():
    body = {"error_code": "API-ERR-100003", "error_reason": "manual sensor"}
    client, http, sleeps = make_client([FakeResponse(body, status=400)])
    with pytest.raises(ApiError) as info:
        client.current_data(2793)
    assert info.value.code == "API-ERR-100003"
    assert len(http.session.requests) == 1 and sleeps == []
