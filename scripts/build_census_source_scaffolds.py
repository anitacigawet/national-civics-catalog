#!/usr/bin/env python3
"""Build state-by-state source scaffolds from the Census government roster.

Each active county, municipal, or township government begins with the same
source-record shape used by reviewed endpoints. Endpoint-specific fields stay
``null`` and the status stays ``needs_source`` until a contribution supplies
evidence. Existing reviewed records are preserved and suppress a matching
Census placeholder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


CATALOG_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN "
    "MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA "
    "WV WI WY AS GU MP PR VI".split()
)
UNIT_TYPES = {
    "1 - COUNTY": "county",
    "2 - MUNICIPAL": "municipality",
    "3 - TOWNSHIP": "township",
}
TYPE_ORDER = {"state": 0, "county": 1, "municipality": 2, "township": 3}
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56", "AS": "60", "GU": "66", "MP": "69", "PR": "72",
    "VI": "78",
}
SOURCE_URL = (
    "https://www.census.gov/data/datasets/2022/econ/gus/"
    "public-use-files.html"
)
_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_CELL_COLUMN = re.compile(r"^([A-Z]+)")


def _column_number(reference: str) -> int:
    match = _CELL_COLUMN.match(reference)
    if match is None:
        raise ValueError(f"invalid XLSX cell reference: {reference!r}")
    number = 0
    for char in match.group(1):
        number = number * 26 + (ord(char) - ord("A") + 1)
    return number - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(part.text or "" for part in item.findall(".//x:t", _NS))
        for item in root.findall("x:si", _NS)
    ]


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    value = cell.find("x:v", _NS)
    if value is None or value.text is None:
        inline = cell.find("x:is", _NS)
        if inline is None:
            return ""
        return "".join(part.text or "" for part in inline.findall(".//x:t", _NS))
    if cell.attrib.get("t") == "s":
        return shared[int(value.text)]
    return value.text


def _rows(workbook: Path) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(workbook) as archive:
        shared = _shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = sheet.findall(".//x:sheetData/x:row", _NS)
        if not rows:
            raise ValueError("General Purpose sheet has no rows")

        header_cells: dict[int, str] = {}
        for cell in rows[0].findall("x:c", _NS):
            header_cells[_column_number(cell.attrib["r"])] = _cell_text(cell, shared)
        width = max(header_cells) + 1
        headers = [header_cells.get(index, "") for index in range(width)]
        required = {
            "CENSUS_ID_PID6",
            "CENSUS_ID_GIDID",
            "UNIT_NAME",
            "UNIT_TYPE",
            "STATE",
            "FIPS_STATE",
            "FIPS_COUNTY",
            "FIPS_PLACE",
            "COUNTY_AREA_NAME",
            "IS_ACTIVE",
        }
        missing = sorted(required - set(headers))
        if missing:
            raise ValueError(f"workbook is missing required columns: {missing}")

        for row in rows[1:]:
            values = [""] * width
            for cell in row.findall("x:c", _NS):
                index = _column_number(cell.attrib["r"])
                if index < width:
                    values[index] = _cell_text(cell, shared).strip()
            yield dict(zip(headers, values))


def _display_name(census_name: str, place_type: str) -> str:
    value = " ".join(census_name.split()).strip()
    upper = value.upper()
    if place_type == "county":
        county_prefixes = (
            ("CITY AND BOROUGH OF ", " City and Borough"),
            ("MUNICIPALITY OF ", " Municipality"),
            ("BOROUGH OF ", " Borough"),
            ("PARISH OF ", " Parish"),
            ("COUNTY OF ", " County"),
        )
        for prefix, suffix in county_prefixes:
            if upper.startswith(prefix):
                return value[len(prefix) :].title() + suffix
    else:
        for prefix in (
            "CONSOLIDATED GOVERNMENT OF ",
            "METROPOLITAN GOVERNMENT OF ",
            "CHARTER TOWNSHIP OF ",
            "TOWNSHIP OF ",
            "MUNICIPALITY OF ",
            "BOROUGH OF ",
            "VILLAGE OF ",
            "TOWN OF ",
            "CITY OF ",
        ):
            if upper.startswith(prefix):
                return value[len(prefix) :].title()
    return value.title()


def _county_area_name(raw: str) -> str | None:
    value = " ".join(raw.split()).strip()
    if not value or value.upper() in {
        "MULTIPLE COUNTIES",
        "MULTI-COUNTY",
        "STATEWIDE",
        "NOT APPLICABLE",
    }:
        return None
    upper = value.upper()
    if upper.endswith((" COUNTY", " PARISH", " BOROUGH", " CENSUS AREA")):
        return value.title()
    return value.title() + " County"


def _census_geoid(row: dict[str, str], place_type: str) -> str | None:
    state = row["FIPS_STATE"].zfill(2)
    if not re.fullmatch(r"[0-9]{2}", state):
        return None
    if place_type == "county":
        county = row["FIPS_COUNTY"].zfill(3)
        return state + county if re.fullmatch(r"[0-9]{3}", county) else None
    place = row["FIPS_PLACE"].zfill(5)
    if not re.fullmatch(r"[0-9]{5}", place) or place.startswith("99"):
        return None
    return state + place


def _placeholder_record(
    *,
    source_id: str,
    name: str,
    publisher_type: str,
    state: str,
    county_names: list[str],
    census_geoid: str | None,
) -> dict[str, object]:
    cover_type = "state" if publisher_type == "state" else publisher_type
    return {
        "source_id": source_id,
        "publisher_name": name,
        "publisher_type": publisher_type,
        "state_codes": [state],
        "county_names": county_names,
        "official_website_url": None,
        "endpoint_type": None,
        "url": None,
        "platform": None,
        "access_method": None,
        "source_relationship": None,
        "status": "needs_source",
        "last_checked": None,
        "provenance_url": SOURCE_URL,
        "covers": [
            {
                "name": name,
                "type": cover_type,
                "state_codes": [state],
                "county_names": county_names,
                "relationship": "direct_jurisdiction",
                "ocd_division_id": None,
                "census_geoid": census_geoid,
            }
        ],
    }


def build_records(
    workbook: Path,
    state_names: dict[str, str],
) -> dict[str, list[dict[str, object]]]:
    records = {code: [] for code in sorted(CATALOG_CODES)}
    seen_ids: set[str] = set()
    for state in sorted(CATALOG_CODES):
        source_id = f"us-{state.lower()}-state--primary-meeting-source"
        records[state].append(
            _placeholder_record(
                source_id=source_id,
                name=state_names[state],
                publisher_type="state",
                state=state,
                county_names=[],
                census_geoid=STATE_FIPS[state],
            )
        )
        seen_ids.add(source_id)
    for row in _rows(workbook):
        if row["IS_ACTIVE"].upper() != "Y":
            continue
        state = row["STATE"].upper()
        place_type = UNIT_TYPES.get(row["UNIT_TYPE"].upper())
        if state not in CATALOG_CODES or place_type is None:
            continue
        census_id = row["CENSUS_ID_PID6"].strip()
        if not re.fullmatch(r"[0-9]{6}", census_id):
            raise ValueError(f"invalid Census government ID: {census_id!r}")
        source_id = (
            f"us-{state.lower()}-census-government-{census_id}"
            "--primary-meeting-source"
        )
        if source_id in seen_ids:
            raise ValueError(f"duplicate Census government ID: {source_id}")
        seen_ids.add(source_id)
        county_area = _county_area_name(row["COUNTY_AREA_NAME"])
        name = _display_name(row["UNIT_NAME"], place_type)
        county_names = [county_area] if county_area else []
        records[state].append(
            _placeholder_record(
                source_id=source_id,
                name=name,
                publisher_type=place_type,
                state=state,
                county_names=county_names,
                census_geoid=_census_geoid(row, place_type),
            )
        )
    for state_records in records.values():
        state_records.sort(
            key=lambda record: (
                TYPE_ORDER[str(record["publisher_type"])],
                str(record["publisher_name"]).casefold(),
                str(record["publisher_name"]),
                str(record["source_id"]),
            )
        )
    return records


def _jsonl(records: list[dict[str, object]]) -> bytes:
    text = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )
    return text.encode("utf-8")


def _summary(records: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    counts = Counter(
        str(record["publisher_type"])
        for state_records in records.values()
        for record in state_records
    )
    return {
        "states_and_territories": len(records),
        "records": sum(len(rows) for rows in records.values()),
        "by_type": dict(sorted(counts.items())),
        "by_state": {code: len(records[code]) for code in sorted(records)},
    }


def _state_readme(
    state_name: str,
    total: int,
    reviewed: int,
    needs_source: int,
) -> str:
    return (
        f"# {state_name}\n\n"
        f"`sources.jsonl` contains **{total} preformed source records**: "
        f"**{reviewed} reviewed** and **{needs_source} still needing a meeting "
        "source**. Empty endpoint fields are intentional. The starting roster "
        "comes from active general-purpose governments in the 2022 Census of "
        "Governments; it does not claim that every local civic body is already "
        "represented.\n\n"
        "Choose the record for your area, then give your AI coding assistant "
        "[the contribution instructions](../../../contribute/AI-INSTRUCTIONS.md). "
        "The contribution fills that record with one continuing public meeting "
        "source and an evidence packet; it does not collect meetings or parser "
        "code.\n"
    )


def _state_names(root: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    for state_dir in (root / "data" / "states").iterdir():
        if not state_dir.is_dir() or state_dir.name.upper() not in CATALOG_CODES:
            continue
        readme = state_dir / "README.md"
        first = readme.read_text(encoding="utf-8").splitlines()[0]
        if not first.startswith("# "):
            raise ValueError(f"{readme} has no state heading")
        names[state_dir.name.upper()] = first[2:].strip()
    missing = sorted(CATALOG_CODES - set(names))
    if missing:
        raise ValueError(f"state folders are missing: {missing}")
    return names


def _load_existing_sources(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    result: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        result.append(value)
    return result


def _merge_existing(
    placeholders: list[dict[str, object]],
    existing: list[dict[str, object]],
) -> list[dict[str, object]]:
    existing_ids = {str(record.get("source_id") or "") for record in existing}
    existing_geoids = {
        str(place.get("census_geoid"))
        for record in existing
        for place in (record.get("covers") or [])
        if isinstance(place, dict) and place.get("census_geoid")
    }
    merged = list(existing)
    for record in placeholders:
        census_geoid = record["covers"][0]["census_geoid"]  # type: ignore[index]
        if record["source_id"] in existing_ids:
            continue
        if census_geoid and str(census_geoid) in existing_geoids:
            continue
        merged.append(record)
    ids = [str(record.get("source_id") or "") for record in merged]
    if len(ids) != len(set(ids)):
        raise ValueError("merged source inventory contains duplicate source_id values")
    merged.sort(key=lambda record: str(record["source_id"]))
    return merged


def write_scaffolds(root: Path, records: dict[str, list[dict[str, object]]]) -> None:
    state_names = _state_names(root)
    for code in sorted(records):
        state_dir = root / "data" / "states" / code.lower()
        source_path = state_dir / "sources.jsonl"
        merged = _merge_existing(records[code], _load_existing_sources(source_path))
        source_path.write_bytes(_jsonl(merged))
        reviewed = sum(record.get("status") != "needs_source" for record in merged)
        needs_source = len(merged) - reviewed
        (state_dir / "README.md").write_text(
            _state_readme(state_names[code], len(merged), reviewed, needs_source),
            encoding="utf-8",
            newline="\n",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if not args.workbook.is_file():
        parser.error(f"workbook not found: {args.workbook}")

    state_names = _state_names(args.catalog_root)
    records = build_records(args.workbook, state_names)
    summary = _summary(records)
    summary["workbook_sha256"] = hashlib.sha256(args.workbook.read_bytes()).hexdigest()
    if args.apply:
        write_scaffolds(args.catalog_root, records)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
