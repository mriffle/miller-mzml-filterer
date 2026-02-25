from __future__ import annotations

import base64

import numpy as np
import pytest
from lxml import etree

from miller.codec import (
    CV_FLOAT32,
    CV_FLOAT64,
    CV_INT32,
    CV_INT64,
    NS,
    decode_binary_data_array,
    encode_binary_data_array,
    is_no_compression,
    is_zlib_array,
)


def _bda(accessions: list[str], payload: bytes | None = None) -> etree._Element:
    bda = etree.Element(f"{{{NS['mz']}}}binaryDataArray")
    for acc in accessions:
        cv = etree.SubElement(bda, f"{{{NS['mz']}}}cvParam")
        cv.set("cvRef", "MS")
        cv.set("accession", acc)
        cv.set("name", acc)
    binary = etree.SubElement(bda, f"{{{NS['mz']}}}binary")
    if payload is not None:
        binary.text = base64.b64encode(payload).decode("ascii")
    return bda


def test_is_no_compression_and_zlib_flags() -> None:
    bda = _bda(["MS:1000576", CV_FLOAT64])
    assert is_no_compression(bda)
    assert not is_zlib_array(bda)


def test_decode_binary_dtype_variants() -> None:
    values32 = np.array([1.5, 2.5], dtype=np.float32)
    bda32 = _bda(["MS:1000576", CV_FLOAT32], values32.tobytes())
    assert np.array_equal(decode_binary_data_array(bda32), values32)

    values_i32 = np.array([1, 2], dtype=np.int32)
    bdai32 = _bda(["MS:1000576", CV_INT32], values_i32.tobytes())
    assert np.array_equal(decode_binary_data_array(bdai32), values_i32)

    values_i64 = np.array([1, 2], dtype=np.int64)
    bdai64 = _bda(["MS:1000576", CV_INT64], values_i64.tobytes())
    assert np.array_equal(decode_binary_data_array(bdai64), values_i64)


def test_decode_binary_defaults_and_empty() -> None:
    bda = _bda(["MS:1000576"])  # default float64 path
    decoded = decode_binary_data_array(bda)
    assert decoded.size == 0


def test_encode_binary_invalid_and_source_noop() -> None:
    bda = _bda(["MS:1000576", CV_FLOAT64], np.array([1.0], dtype=np.float64).tobytes())
    before = etree.tostring(bda)
    encode_binary_data_array(bda, np.array([1.0], dtype=np.float64), "source")
    assert etree.tostring(bda) == before

    with pytest.raises(ValueError):
        encode_binary_data_array(bda, np.array([1.0], dtype=np.float64), "bad")


def test_encode_binary_creates_binary_element_when_missing() -> None:
    bda = etree.Element(f"{{{NS['mz']}}}binaryDataArray")
    cv = etree.SubElement(bda, f"{{{NS['mz']}}}cvParam")
    cv.set("cvRef", "MS")
    cv.set("accession", CV_FLOAT64)
    cv.set("name", "64-bit float")

    encode_binary_data_array(bda, np.array([1.0, 2.0], dtype=np.float64), "none")
    binary = bda.find("mz:binary", NS)
    assert binary is not None
    assert isinstance(binary.text, str)
