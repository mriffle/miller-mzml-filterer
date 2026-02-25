"""Generate deterministic mzML fixture files used by tests."""

from __future__ import annotations

import base64
import zlib
from pathlib import Path

import numpy as np
from lxml import etree

ROOT = Path(__file__).resolve().parent
NS = "http://psi.hupo.org/ms/mzml"


def _cv(accession: str, name: str, value: str | None = None, **attrs: str) -> etree._Element:
    el = etree.Element(f"{{{NS}}}cvParam")
    el.set("cvRef", "MS")
    el.set("accession", accession)
    el.set("name", name)
    if value is not None:
        el.set("value", value)
    for k, v in attrs.items():
        el.set(k, v)
    return el


def _bda(values: np.ndarray, *, array_type: str, compression: str) -> etree._Element:
    bda = etree.Element(f"{{{NS}}}binaryDataArray")
    if compression == "zlib":
        bda.append(_cv("MS:1000574", "zlib compression"))
    else:
        bda.append(_cv("MS:1000576", "no compression"))
    bda.append(_cv("MS:1000523", "64-bit float"))
    if array_type == "mz":
        bda.append(_cv("MS:1000514", "m/z array"))
    elif array_type == "intensity":
        bda.append(_cv("MS:1000515", "intensity array"))
    elif array_type == "time":
        bda.append(_cv("MS:1000595", "time array", unitAccession="UO:0000031", unitName="minute"))
    payload = values.astype("<f8").tobytes(order="C")
    if compression == "zlib":
        payload = zlib.compress(payload)
    encoded = base64.b64encode(payload).decode("ascii")
    bda.set("encodedLength", str(len(encoded)))
    binary = etree.SubElement(bda, f"{{{NS}}}binary")
    binary.text = encoded
    return bda


def _make_spectrum(scan_id: str, ms_level: int, rt_min: float, mz: list[float], intensity: list[float], compression: str, precursor: str | None = None) -> etree._Element:
    spec = etree.Element(f"{{{NS}}}spectrum")
    spec.set("id", scan_id)
    spec.set("index", str(int(scan_id.split("=")[1]) - 1001))
    spec.set("defaultArrayLength", str(len(mz)))
    spec.append(_cv("MS:1000511", "ms level", str(ms_level)))

    scan_list = etree.SubElement(spec, f"{{{NS}}}scanList")
    scan_list.set("count", "1")
    scan = etree.SubElement(scan_list, f"{{{NS}}}scan")
    scan.append(
        _cv(
            "MS:1000016",
            "scan start time",
            str(rt_min),
            unitAccession="UO:0000031",
            unitName="minute",
        )
    )

    if precursor is not None:
        precursor_list = etree.SubElement(spec, f"{{{NS}}}precursorList")
        precursor_list.set("count", "1")
        precursor_el = etree.SubElement(precursor_list, f"{{{NS}}}precursor")
        if precursor:
            precursor_el.set("spectrumRef", precursor)

    bdal = etree.SubElement(spec, f"{{{NS}}}binaryDataArrayList")
    bdal.set("count", "2")
    bdal.append(_bda(np.asarray(mz, dtype=np.float64), array_type="mz", compression=compression))
    bdal.append(_bda(np.asarray(intensity, dtype=np.float64), array_type="intensity", compression=compression))
    return spec


def _make_chromatogram(chrom_id: str, accession: str, name: str, times: np.ndarray, values: np.ndarray, compression: str) -> etree._Element:
    chrom = etree.Element(f"{{{NS}}}chromatogram")
    chrom.set("id", chrom_id)
    chrom.set("defaultArrayLength", str(len(times)))
    chrom.append(_cv(accession, name))
    bdal = etree.SubElement(chrom, f"{{{NS}}}binaryDataArrayList")
    bdal.set("count", "2")
    bdal.append(_bda(times, array_type="time", compression=compression))
    bdal.append(_bda(values, array_type="intensity", compression=compression))
    return chrom


def build_nonindexed(path: Path) -> None:
    nsmap = {None: NS, "xsi": "http://www.w3.org/2001/XMLSchema-instance"}
    root = etree.Element(f"{{{NS}}}mzML", nsmap=nsmap)
    root.set("version", "1.1.0")

    cv_list = etree.SubElement(root, f"{{{NS}}}cvList")
    cv_list.set("count", "1")
    cv = etree.SubElement(cv_list, f"{{{NS}}}cv")
    cv.set("id", "MS")
    cv.set("fullName", "Mass spectrometry ontology")
    cv.set("URI", "https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/master/psi-ms.obo")
    cv.set("version", "4.1.188")

    etree.SubElement(root, f"{{{NS}}}fileDescription")
    etree.SubElement(root, f"{{{NS}}}referenceableParamGroupList", count="0")
    etree.SubElement(root, f"{{{NS}}}sampleList", count="0")

    software_list = etree.SubElement(root, f"{{{NS}}}softwareList")
    software_list.set("count", "1")
    software = etree.SubElement(software_list, f"{{{NS}}}software")
    software.set("id", "sw1")
    software.set("version", "1.0")

    ic_list = etree.SubElement(root, f"{{{NS}}}instrumentConfigurationList")
    ic_list.set("count", "1")
    etree.SubElement(ic_list, f"{{{NS}}}instrumentConfiguration", id="IC1")

    dp_list = etree.SubElement(root, f"{{{NS}}}dataProcessingList")
    dp_list.set("count", "1")
    etree.SubElement(dp_list, f"{{{NS}}}dataProcessing", id="DP1")

    run = etree.SubElement(root, f"{{{NS}}}run")
    run.set("id", "run1")
    run.set("defaultInstrumentConfigurationRef", "IC1")

    spectrum_list = etree.SubElement(run, f"{{{NS}}}spectrumList")

    specs = [
        ("scan=1001", 1, 1.0, [100.0, 101.0], [10.0, 20.0], "none", None),
        ("scan=1002", 2, 2.0, [200.0, 201.0], [15.0, 25.0], "zlib", "scan=1001"),
        ("scan=1003", 2, 3.0, [210.0, 211.0], [30.0, 5.0], "none", ""),
        ("scan=1004", 1, 4.0, [120.0, 121.0], [11.0, 22.0], "zlib", None),
        ("scan=1005", 2, 5.0, [220.0, 221.0], [13.0, 26.0], "none", "scan=9999"),
        ("scan=1006", 3, 6.0, [300.0, 301.0], [9.0, 12.0], "zlib", "scan=1002"),
        ("scan=1007", 1, 7.0, [130.0, 131.0], [20.0, 10.0], "none", None),
        ("scan=1008", 2, 8.0, [230.0, 231.0], [14.0, 16.0], "zlib", "scan=1007"),
        ("scan=1009", 2, 9.0, [240.0, 241.0], [18.0, 4.0], "none", "scan=1007"),
        ("scan=1010", 3, 10.0, [310.0, 311.0], [7.0, 8.0], "zlib", "scan=1008"),
        ("scan=1011", 1, 11.0, [140.0, 141.0], [5.0, 9.0], "zlib", None),
        ("scan=1012", 2, 12.0, [250.0, 251.0], [12.0, 3.0], "none", "scan=1011"),
        ("scan=1013", 2, 13.0, [260.0, 261.0], [6.0, 2.0], "zlib", ""),
        ("scan=1014", 1, 14.0, [150.0, 151.0], [17.0, 5.0], "none", None),
        ("scan=1015", 2, 15.0, [270.0, 271.0], [4.0, 11.0], "zlib", "scan=12345"),
        ("scan=1016", 3, 16.0, [320.0, 321.0], [10.0, 10.0], "none", "scan=1012"),
        ("scan=1017", 1, 17.0, [160.0, 161.0], [21.0, 1.0], "zlib", None),
        ("scan=1018", 2, 18.0, [280.0, 281.0], [8.0, 14.0], "none", "scan=1017"),
        ("scan=1019", 2, 19.0, [290.0, 291.0], [19.0, 1.0], "zlib", "scan=1017"),
        ("scan=1020", 1, 20.0, [170.0, 171.0], [13.0, 12.0], "none", None),
    ]
    spectrum_list.set("count", str(len(specs)))

    spectra = [
        _make_spectrum(scan_id, ms_level, rt, mz, intensity, compression, precursor=precursor)
        for scan_id, ms_level, rt, mz, intensity, compression, precursor in specs
    ]
    for spectrum in spectra:
        spectrum_list.append(spectrum)

    times = np.array([spec[2] for spec in specs], dtype=np.float64)
    tic = np.array([float(sum(spec[4])) for spec in specs], dtype=np.float64)
    bpc = np.array([float(max(spec[4])) for spec in specs], dtype=np.float64)
    xic = np.full(shape=len(specs), fill_value=5.0, dtype=np.float64)

    chromatogram_list = etree.SubElement(run, f"{{{NS}}}chromatogramList")
    chromatogram_list.set("count", "3")
    chromatogram_list.append(_make_chromatogram("TIC", "MS:1000235", "total ion current chromatogram", times, tic, "none"))
    chromatogram_list.append(_make_chromatogram("BPC", "MS:1000628", "basepeak chromatogram", times, bpc, "none"))
    chromatogram_list.append(_make_chromatogram("XIC", "MS:1000627", "selected ion current chromatogram", times, xic, "zlib"))

    xml = etree.tostring(root, pretty_print=False, encoding="UTF-8", xml_declaration=True)
    path.write_bytes(xml + b"\n")


def build_indexed(source_nonindexed: Path, target_indexed: Path) -> None:
    # Reuse the package writer so fixture and implementation stay consistent.
    import sys

    repo_root = ROOT.parent.parent
    sys.path.insert(0, str(repo_root / "src"))

    from miller.reader import MzMLSource
    from miller.writer import write_subset

    source = MzMLSource(source_nonindexed)
    selected = [s.scan_id for s in source.scan_infos]
    write_subset(source, selected, target_indexed, indexed=True, compression="source")


def main() -> None:
    nonindexed = ROOT / "sample_nonindexed.mzML"
    indexed = ROOT / "sample_indexed.mzML"
    build_nonindexed(nonindexed)
    build_indexed(nonindexed, indexed)


if __name__ == "__main__":
    main()
