import zipfile

from openpyxl import Workbook

from aq_pipeline.gios_archive_files import parse_archive, parse_filename


def _workbook(path, with_sensor_row=True):
    wb = Workbook()
    ws = wb.active
    ws.append(["Nr", 1, 2, 3])
    ws.append(["Kod stacji", "MpKrakAlKras", "MpKrakBujaka", "SlKatoKossut"])
    ws.append(["Wskaźnik", "PM10", "PM10", "PM10"])
    ws.append(["Czas uśredniania", "1g", "1g", "1g"])
    ws.append(["Jednostka", "ug/m3", "ug/m3", "ug/m3"])
    if with_sensor_row:
        ws.append(["Kod stanowiska", "MpKrakAlKras-PM10-1g", "MpKrakBujaka-PM10-1g", "SlKatoKossut-PM10-1g"])
    ws.append(["2019-01-01 01:00:00", 55.2, "48,3", 30])
    ws.append(["2019-01-01 02:00:00", None, 47.0, 31])
    ws.append(["2019-01-01 03:00:00", 60.1, "", 29])
    wb.save(path)


def test_parse_filename():
    assert parse_filename("2019_PM25_1g.xlsx") == {"year": "2019", "pollutant": "PM2.5", "averaging": "1g"}
    assert parse_filename("Wyniki/2015_PM10_24g.xlsx")["averaging"] == "24g"
    assert parse_filename("metadane.xlsx") is None


def test_parse_zip_filters_stations_and_skips_empty_cells(tmp_path):
    xlsx = tmp_path / "2019_PM10_1g.xlsx"
    _workbook(xlsx)
    ignored = tmp_path / "2019_PM10_24g.xlsx"
    _workbook(ignored)
    archive = tmp_path / "2019.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(xlsx, "2019/2019_PM10_1g.xlsx")
        zf.write(ignored, "2019/2019_PM10_24g.xlsx")

    results = list(parse_archive(archive, ["PM10", "PM2.5"], ["MpKrak"]))
    assert [name for name, _ in results] == ["2019_PM10_1g.xlsx"]
    records = results[0][1]
    assert len(records) == 4  # 3 + 2 values minus one empty cell per station
    first = records[0]
    assert first == {"Kod stanowiska": "MpKrakAlKras-PM10-1g", "Kod stacji": "MpKrakAlKras",
                     "Data": "2019-01-01 01:00:00", "Wartość": 55.2, "Plik": "2019_PM10_1g.xlsx"}
    assert {r["Kod stacji"] for r in records} == {"MpKrakAlKras", "MpKrakBujaka"}
    assert any(r["Wartość"] == 48.3 for r in records)  # comma decimal parsed


def test_sensor_code_is_derived_when_header_row_missing(tmp_path):
    xlsx = tmp_path / "2016_PM25_1g.xlsx"
    _workbook(xlsx, with_sensor_row=False)
    _, records = next(parse_archive(tmp_path, ["PM2.5"], ["MpKrak"]))
    assert records[0]["Kod stanowiska"] == "MpKrakAlKras-PM2.5-1g"
