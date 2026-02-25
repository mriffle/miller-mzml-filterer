"""Chromatogram recalculation utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from lxml import etree

from .codec import NS, decode_binary_data_array, encode_binary_data_array, is_zlib_array

CV_TIC = "MS:1000235"
CV_BPC = "MS:1000628"
CV_TIME_ARRAY = "MS:1000595"
CV_INTENSITY_ARRAY = "MS:1000515"


def recalculate_tic(spectra: Iterable[etree._Element]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    times: list[float] = []
    intensities: list[float] = []
    for spectrum in spectra:
        times.append(_retention_time(spectrum))
        intensity_array = _spectrum_intensity_array(spectrum)
        intensities.append(float(np.sum(intensity_array)))
    return np.asarray(times, dtype=np.float64), np.asarray(intensities, dtype=np.float64)


def recalculate_bpc(spectra: Iterable[etree._Element]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    times: list[float] = []
    intensities: list[float] = []
    for spectrum in spectra:
        times.append(_retention_time(spectrum))
        intensity_array = _spectrum_intensity_array(spectrum)
        if intensity_array.size == 0:
            intensities.append(0.0)
        else:
            intensities.append(float(np.max(intensity_array)))
    return np.asarray(times, dtype=np.float64), np.asarray(intensities, dtype=np.float64)


def rebuild_chromatogram_list(
    source_chromatograms: list[etree._Element],
    retained_spectra: list[etree._Element],
    compression: str,
) -> list[etree._Element]:
    rebuilt: list[etree._Element] = []
    for chrom in source_chromatograms:
        accession_set = {cv.get("accession") for cv in chrom.findall("mz:cvParam", NS)}
        if CV_TIC in accession_set:
            rebuilt.append(_rebuild_single(chrom, retained_spectra, mode="tic", compression=compression))
        elif CV_BPC in accession_set:
            rebuilt.append(_rebuild_single(chrom, retained_spectra, mode="bpc", compression=compression))
        else:
            rebuilt.append(etree.fromstring(etree.tostring(chrom)))
    return rebuilt


def _rebuild_single(
    source_chrom: etree._Element,
    retained_spectra: list[etree._Element],
    *,
    mode: str,
    compression: str,
) -> etree._Element:
    result = etree.fromstring(etree.tostring(source_chrom))
    if mode == "tic":
        times, intensities = recalculate_tic(retained_spectra)
    else:
        times, intensities = recalculate_bpc(retained_spectra)

    result.set("defaultArrayLength", str(len(retained_spectra)))
    bdas = result.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)
    for bda in bdas:
        accessions = {cv.get("accession") for cv in bda.findall("mz:cvParam", NS)}
        if CV_TIME_ARRAY in accessions:
            encode_binary_data_array(bda, times, _chrom_compression(compression, source_bda=bda))
        elif CV_INTENSITY_ARRAY in accessions:
            encode_binary_data_array(bda, intensities, _chrom_compression(compression, source_bda=bda))
    return result


def _chrom_compression(requested: str, source_bda: etree._Element) -> str:
    if requested != "source":
        return requested
    return "zlib" if is_zlib_array(source_bda) else "none"


def _retention_time(spectrum: etree._Element) -> float:
    scan = spectrum.find("mz:scanList/mz:scan", NS)
    if scan is None:
        return 0.0
    for cv in scan.findall("mz:cvParam", NS):
        if cv.get("accession") == "MS:1000016":
            value = cv.get("value")
            if value is None:
                return 0.0
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 0.0


def _spectrum_intensity_array(spectrum: etree._Element) -> NDArray[Any]:
    for bda in spectrum.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS):
        accessions = {cv.get("accession") for cv in bda.findall("mz:cvParam", NS)}
        if CV_INTENSITY_ARRAY in accessions:
            return decode_binary_data_array(bda)
    return np.array([], dtype=np.float64)
