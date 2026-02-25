"""Input mzML reading and scan metadata extraction."""

from __future__ import annotations

from pathlib import Path

from lxml import etree
from pyteomics import mzml as pyteomics_mzml

from .errors import InputFileError
from .models import ScanInfo

MZML_NS = "http://psi.hupo.org/ms/mzml"
NS = {"mz": MZML_NS}


class MzMLSource:
    """In-memory XML representation of source mzML and extracted scan metadata."""

    def __init__(self, path: Path):
        self.path = path
        try:
            parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
            self.tree = etree.parse(str(path), parser)
        except Exception as exc:  # noqa: BLE001
            raise InputFileError(f"Invalid or unreadable mzML file: {path}") from exc

        root = self.tree.getroot()
        self.is_indexed = _local_name(root.tag) == "indexedmzML"
        if self.is_indexed:
            mzml = root.find("mz:mzML", NS)
            if mzml is None:
                mzml = root.find(".//{http://psi.hupo.org/ms/mzml}mzML")
            if mzml is None:
                raise InputFileError("indexedmzML root found but no mzML child exists")
            self.mzml_root = mzml
        else:
            if _local_name(root.tag) != "mzML":
                raise InputFileError("Root element is not mzML/indexedmzML")
            self.mzml_root = root

        run = self.mzml_root.find("mz:run", NS)
        if run is None:
            raise InputFileError("mzML file is missing <run>")
        self.run = run

        spectrum_list = self.run.find("mz:spectrumList", NS)
        if spectrum_list is None:
            raise InputFileError("mzML file is missing <spectrumList>")
        self.spectrum_list = spectrum_list
        self.spectra = list(self.spectrum_list.findall("mz:spectrum", NS))
        self.scan_infos = self._extract_scan_infos_with_pyteomics()
        self.scan_index = {info.scan_id: idx for idx, info in enumerate(self.scan_infos)}
        self.spectrum_by_id = {spec.get("id"): spec for spec in self.spectra if spec.get("id")}

    def _extract_scan_infos_with_pyteomics(self) -> list[ScanInfo]:
        infos: list[ScanInfo] = []
        try:
            reader_cls = pyteomics_mzml.PreIndexedMzML if self.is_indexed else pyteomics_mzml.MzML
            with reader_cls(str(self.path)) as reader:
                for idx, spectrum in enumerate(reader):
                    scan_id_obj = spectrum.get("id")
                    if not isinstance(scan_id_obj, str):
                        continue
                    ms_level = _extract_ms_level_pyteomics(spectrum)
                    precursor_ref = _extract_precursor_ref_pyteomics(spectrum)
                    infos.append(
                        ScanInfo(
                            scan_id=scan_id_obj,
                            index=idx,
                            ms_level=ms_level,
                            precursor_ref=precursor_ref,
                        )
                    )
        except Exception:  # noqa: BLE001
            infos = []

        if infos:
            return infos
        # Fallback to XML extraction for files that pyteomics cannot iterate.
        for idx, spectrum in enumerate(self.spectra):
            scan_id = spectrum.get("id")
            if not scan_id:
                continue
            ms_level = _extract_ms_level(spectrum)
            precursor_ref = _extract_precursor_ref(spectrum)
            infos.append(
                ScanInfo(
                    scan_id=scan_id,
                    index=idx,
                    ms_level=ms_level,
                    precursor_ref=precursor_ref,
                )
            )
        return infos


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _extract_ms_level(spectrum: etree._Element) -> int | None:
    for cv in spectrum.findall("mz:cvParam", NS):
        if cv.get("accession") == "MS:1000511":
            value = cv.get("value")
            if value is None:
                return None
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _extract_precursor_ref(spectrum: etree._Element) -> str | None:
    precursor = spectrum.find("mz:precursorList/mz:precursor", NS)
    if precursor is None:
        return None
    ref = precursor.get("spectrumRef")
    return ref if ref else None


def _extract_ms_level_pyteomics(spectrum: dict[str, object]) -> int | None:
    value = spectrum.get("ms level")
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_precursor_ref_pyteomics(spectrum: dict[str, object]) -> str | None:
    precursor_list = spectrum.get("precursorList")
    if not isinstance(precursor_list, dict):
        return None
    precursors = precursor_list.get("precursor")
    if not isinstance(precursors, list) or not precursors:
        return None
    first = precursors[0]
    if not isinstance(first, dict):
        return None
    ref = first.get("spectrumRef")
    return ref if isinstance(ref, str) and ref else None
