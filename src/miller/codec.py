"""Binary array decoding/encoding helpers for mzML."""

from __future__ import annotations

import base64
import zlib
from typing import Any

import numpy as np
from numpy.typing import NDArray
from lxml import etree

NS = {"mz": "http://psi.hupo.org/ms/mzml"}

CV_ZLIB = "MS:1000574"
CV_NONE = "MS:1000576"
CV_FLOAT32 = "MS:1000521"
CV_FLOAT64 = "MS:1000523"
CV_INT32 = "MS:1000519"
CV_INT64 = "MS:1000522"


def is_zlib_array(binary_data_array: etree._Element) -> bool:
    return any(cv.get("accession") == CV_ZLIB for cv in binary_data_array.findall("mz:cvParam", NS))


def is_no_compression(binary_data_array: etree._Element) -> bool:
    return any(cv.get("accession") == CV_NONE for cv in binary_data_array.findall("mz:cvParam", NS))


def _dtype_for_array(binary_data_array: etree._Element) -> np.dtype[Any]:
    accessions = {cv.get("accession") for cv in binary_data_array.findall("mz:cvParam", NS)}
    if CV_FLOAT64 in accessions:
        return np.dtype("<f8")
    if CV_FLOAT32 in accessions:
        return np.dtype("<f4")
    if CV_INT64 in accessions:
        return np.dtype("<i8")
    if CV_INT32 in accessions:
        return np.dtype("<i4")
    return np.dtype("<f8")


def decode_binary_data_array(binary_data_array: etree._Element) -> NDArray[Any]:
    binary_el = binary_data_array.find("mz:binary", NS)
    raw_b64 = binary_el.text if binary_el is not None and binary_el.text is not None else ""
    payload = base64.b64decode(raw_b64) if raw_b64 else b""
    if is_zlib_array(binary_data_array):
        payload = zlib.decompress(payload)
    dtype = _dtype_for_array(binary_data_array)
    if not payload:
        return np.array([], dtype=dtype)
    return np.frombuffer(payload, dtype=dtype).copy()


def _remove_compression_cv(binary_data_array: etree._Element) -> None:
    for cv in list(binary_data_array.findall("mz:cvParam", NS)):
        if cv.get("accession") in {CV_ZLIB, CV_NONE}:
            binary_data_array.remove(cv)


def _append_compression_cv(binary_data_array: etree._Element, accession: str) -> None:
    cv = etree.Element(f"{{{NS['mz']}}}cvParam")
    cv.set("cvRef", "MS")
    cv.set("accession", accession)
    cv.set("name", "zlib compression" if accession == CV_ZLIB else "no compression")
    binary_data_array.insert(0, cv)


def encode_binary_data_array(
    binary_data_array: etree._Element,
    values: NDArray[Any],
    compression: str,
) -> None:
    if compression not in {"source", "zlib", "none"}:
        raise ValueError(f"Unsupported compression: {compression}")
    if compression == "source":
        return

    dtype = _dtype_for_array(binary_data_array)
    payload = np.asarray(values, dtype=dtype).tobytes(order="C")
    if compression == "zlib":
        payload = zlib.compress(payload)

    _remove_compression_cv(binary_data_array)
    _append_compression_cv(binary_data_array, CV_ZLIB if compression == "zlib" else CV_NONE)

    binary_el = binary_data_array.find("mz:binary", NS)
    if binary_el is None:
        binary_el = etree.SubElement(binary_data_array, f"{{{NS['mz']}}}binary")
    encoded = base64.b64encode(payload).decode("ascii")
    binary_el.text = encoded
    binary_data_array.set("encodedLength", str(len(encoded)))
