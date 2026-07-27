"""Dependency-free CSV/TXT/XLSX contact import parsing and explicit column mapping."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET
import zipfile


MAX_IMPORT_BYTES = 25 * 1024 * 1024
MAX_IMPORT_ROWS = 100_000
_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _column_number(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    value = 0
    for character in letters:
        value = value * 26 + ord(character) - 64
    return max(0, value - 1)


def _xlsx_rows(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
            raise ValueError("Expanded XLSX content exceeds the 100 MB safety limit.")
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("x:si", _NS):
                shared.append("".join(node.text or "" for node in item.iterfind(".//x:t", _NS)))
        sheet_names = sorted(
            name for name in names
            if PurePosixPath(name).parts[:2] == ("xl", "worksheets") and name.endswith(".xml")
        )
        if not sheet_names:
            return []
        root = ET.fromstring(archive.read(sheet_names[0]))
        result: list[list[str]] = []
        for row in root.findall(".//x:sheetData/x:row", _NS):
            values: dict[int, str] = {}
            for cell in row.findall("x:c", _NS):
                index = _column_number(cell.attrib.get("r", ""))
                kind = cell.attrib.get("t")
                if kind == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iterfind(".//x:t", _NS))
                else:
                    node = cell.find("x:v", _NS)
                    raw = node.text if node is not None and node.text is not None else ""
                    if kind == "s" and raw.isdigit() and int(raw) < len(shared):
                        value = shared[int(raw)]
                    elif kind == "b":
                        value = "بله" if raw == "1" else "خیر"
                    else:
                        value = raw
                values[index] = value.strip()
            if values:
                result.append([values.get(index, "") for index in range(max(values) + 1)])
            if len(result) > MAX_IMPORT_ROWS:
                raise ValueError("Import exceeds the 100000-row safety limit.")
        return result


def parse_tabular(content: bytes, file_name: str) -> tuple[list[str], list[list[str]]]:
    if len(content) > MAX_IMPORT_BYTES:
        raise ValueError("Import file exceeds the 25 MB safety limit.")
    suffix = PurePosixPath(file_name.lower()).suffix
    if suffix == ".xlsx":
        rows = _xlsx_rows(content)
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("cp1256")
        if suffix == ".txt":
            rows = [["شماره تماس"], *[[line.strip()] for line in text.splitlines() if line.strip()]]
        elif suffix == ".csv":
            sample = text[:8_192]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = [[cell.strip() for cell in row] for row in csv.reader(StringIO(text), dialect)]
        else:
            raise ValueError("Only XLSX, CSV, and TXT contact files are supported.")
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) > MAX_IMPORT_ROWS + 1:
        raise ValueError("Import exceeds the 100000-row safety limit.")
    if not rows:
        return [], []
    width = max(len(row) for row in rows)
    headers = [
        (rows[0][index].strip() if index < len(rows[0]) else "") or f"ستون {index + 1}"
        for index in range(width)
    ]
    return headers, [row + [""] * (width - len(row)) for row in rows[1:]]


def map_contact_rows(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    mapping: Mapping[str, object],
) -> list[dict[str, Any]]:
    allowed = {"first_name", "last_name", "phone", "organization", "notes", "username", "category"}
    indexes: dict[str, int] = {}
    for field, raw in mapping.items():
        if field not in allowed or raw is None or raw == "":
            continue
        index = int(raw)
        if index < 0 or index >= len(headers):
            raise ValueError("Column mapping is outside the imported sheet.")
        indexes[field] = index
    if "phone" not in indexes:
        raise ValueError("Phone-number column mapping is required.")
    result: list[dict[str, Any]] = []
    for row in rows:
        get = lambda field: str(row[indexes[field]]).strip() if field in indexes and indexes[field] < len(row) else ""
        phone = get("phone")
        if not phone:
            continue
        result.append(
            {
                "first_name": get("first_name"),
                "last_name": get("last_name"),
                "phones": [phone],
                "organization": get("organization"),
                "notes": get("notes"),
                "username": get("username"),
                "category_names": [
                    value.strip()
                    for value in get("category").replace("؛", "،").split("،")
                    if value.strip()
                ],
                "source": "xlsx" if str(mapping.get("_format") or "") == "xlsx" else "file",
            }
        )
    return result
