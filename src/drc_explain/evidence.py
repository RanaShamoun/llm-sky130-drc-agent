"""Keep original oracle evidence in one verified archive instead of loose files."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def archive_reports(source, destination):
    """Write atomically and verify every member before the caller removes files."""
    source = Path(source)
    destination = Path(destination)
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if not files:
        raise ValueError("No oracle evidence to archive.")
    temporary = destination.with_suffix(".zip.tmp")
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())
    with ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Oracle archive failed its integrity check.")
        for path in files:
            if archive.read(path.relative_to(source).as_posix()) != path.read_bytes():
                raise RuntimeError(f"Oracle evidence changed during archiving: {path}")
    temporary.replace(destination)
    return len(files)


def report_bytes(gold_root, case_id):
    """Read a regenerated loose report or the preserved archive; never extract paths."""
    if not case_id.isalnum():
        raise ValueError("Invalid case ID.")
    gold_root = Path(gold_root)
    loose = gold_root / "reports" / case_id / "report.lyrdb"
    if loose.is_file():
        return loose.read_bytes()
    with ZipFile(gold_root / "oracle_reports.zip") as archive:
        return archive.read(f"{case_id}/report.lyrdb")
