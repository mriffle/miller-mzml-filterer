"""Output mzML writer."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from .chromatogram import rebuild_chromatogram_list
from .codec import NS, decode_binary_data_array, encode_binary_data_array
from .errors import OutputWriteError
from .reader import MzMLSource


def write_subset(
    source: MzMLSource,
    selected_scan_ids: list[str],
    output_path: Path,
    *,
    indexed: bool,
    compression: str,
) -> None:
    mzml_copy = etree.fromstring(etree.tostring(source.mzml_root))
    run = mzml_copy.find("mz:run", NS)
    if run is None:
        raise OutputWriteError("Cannot locate <run> in source mzML")

    spectrum_list = run.find("mz:spectrumList", NS)
    if spectrum_list is None:
        raise OutputWriteError("Cannot locate <spectrumList> in source mzML")

    for child in list(spectrum_list):
        spectrum_list.remove(child)

    selected_spectra = []
    for scan_id in selected_scan_ids:
        original = source.spectrum_by_id[scan_id]
        spec_copy = etree.fromstring(etree.tostring(original))
        if compression in {"zlib", "none"}:
            _rewrite_spectrum_binary(spec_copy, compression)
        selected_spectra.append(spec_copy)
        spectrum_list.append(spec_copy)

    spectrum_list.set("count", str(len(selected_spectra)))

    chrom_list = run.find("mz:chromatogramList", NS)
    if chrom_list is not None:
        source_chroms = list(chrom_list.findall("mz:chromatogram", NS))
        rebuilt = rebuild_chromatogram_list(source_chroms, selected_spectra, compression=compression)
        for child in list(chrom_list):
            chrom_list.remove(child)
        for chrom in rebuilt:
            chrom_list.append(chrom)
        chrom_list.set("count", str(len(rebuilt)))

    xml_decl = b'<?xml version="1.0" encoding="UTF-8"?>\n'
    mzml_bytes = etree.tostring(mzml_copy, encoding="UTF-8", xml_declaration=False)

    try:
        if indexed:
            payload = _build_indexed_document(xml_decl, mzml_bytes)
            output_path.write_bytes(payload)
        else:
            output_path.write_bytes(xml_decl + mzml_bytes + b"\n")
    except Exception as exc:  # noqa: BLE001
        raise OutputWriteError(f"Cannot write output file: {output_path}") from exc


def _rewrite_spectrum_binary(spectrum: etree._Element, compression: str) -> None:
    bdas = spectrum.findall("mz:binaryDataArrayList/mz:binaryDataArray", NS)
    for bda in bdas:
        values = decode_binary_data_array(bda)
        encode_binary_data_array(bda, values, compression)


def _build_indexed_document(xml_decl: bytes, mzml_bytes: bytes) -> bytes:
    # Offsets are absolute byte positions in the output file.
    indexed_open = (
        b"<indexedmzML xmlns=\"http://psi.hupo.org/ms/mzml\" "
        b"xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">\n"
    )
    mzml_start = len(xml_decl) + len(indexed_open)

    spectrum_offsets = _find_offsets(mzml_bytes, b"<spectrum ")
    chromatogram_offsets = _find_offsets(mzml_bytes, b"<chromatogram ")

    spectrum_ids = _extract_ids_in_order(mzml_bytes, b"<spectrum ")
    chromatogram_ids = _extract_ids_in_order(mzml_bytes, b"<chromatogram ")

    sections: list[bytes] = []

    spectrum_section = [b"  <index name=\"spectrum\">\n"]
    for sid, off in zip(spectrum_ids, spectrum_offsets, strict=False):
        spectrum_section.append(
            f"    <offset idRef=\"{sid}\">{mzml_start + off}</offset>\n".encode("utf-8")
        )
    spectrum_section.append(b"  </index>\n")
    sections.append(b"".join(spectrum_section))

    if chromatogram_ids and chromatogram_offsets:
        chromatogram_section = [b"  <index name=\"chromatogram\">\n"]
        for cid, off in zip(chromatogram_ids, chromatogram_offsets, strict=False):
            chromatogram_section.append(
                f"    <offset idRef=\"{cid}\">{mzml_start + off}</offset>\n".encode("utf-8")
            )
        chromatogram_section.append(b"  </index>\n")
        sections.append(b"".join(chromatogram_section))

    index_list = [f"<indexList count=\"{len(sections)}\">\n".encode("utf-8")]
    index_list.extend(sections)
    index_list.append(b"</indexList>\n")
    index_blob = b"".join(index_list)

    index_offset = len(xml_decl) + len(indexed_open) + len(mzml_bytes) + 1
    tail = (
        index_blob
        + f"<indexListOffset>{index_offset}</indexListOffset>\n".encode("utf-8")
        + b"</indexedmzML>\n"
    )
    return xml_decl + indexed_open + mzml_bytes + b"\n" + tail


def _find_offsets(blob: bytes, token: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        idx = blob.find(token, start)
        if idx < 0:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def _extract_ids_in_order(blob: bytes, token: bytes) -> list[str]:
    ids: list[str] = []
    start = 0
    while True:
        idx = blob.find(token, start)
        if idx < 0:
            break
        id_idx = blob.find(b'id="', idx)
        if id_idx < 0:
            break
        id_end = blob.find(b'"', id_idx + 4)
        if id_end < 0:
            break
        ids.append(blob[id_idx + 4 : id_end].decode("utf-8"))
        start = id_end + 1
    return ids
