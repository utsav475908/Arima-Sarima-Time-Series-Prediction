import argparse
import gzip
import os
import shutil
from pathlib import Path

from constants import GZ_EXTENSION

try:
    from process_results import ResultData
except ModuleNotFoundError:
    class ResultData:  # Fallback for standalone execution in this workspace.
        quip_status = []

try:
    from logger_util import info, error
except ModuleNotFoundError:
    def info(message, *_args):
        print(f"INFO: {message}")

    def error(message, exception, *_args):
        print(f"ERROR: {message}: {exception}")

try:
    from status import Status, WakeEvents
except ModuleNotFoundError:
    class Status:
        EXTRACTION_STARTED = "EXTRACTION_STARTED"
        EXTRACTION_QUIP_FOUND = "EXTRACTION_QUIP_FOUND"
        EXTRACTION_EXTRACTED = "EXTRACTION_EXTRACTED"
        EXTRACTION_FAILED = "EXTRACTION_FAILED"
        EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"

    class WakeEvents:
        EXTRACT_GZ_NO_DATA_ISSUE = "EXTRACT_GZ_NO_DATA_ISSUE"
        EXTRACT_GZ_DATA_ISSUE = "EXTRACT_GZ_DATA_ISSUE"


def extract_gz_files(directory_name, bucket=None, prefix=None):
    del bucket, prefix

    directory = Path(directory_name).expanduser().resolve()
    info(f"Extracting gz files for {directory}", Status.EXTRACTION_STARTED, "")

    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    info(f"Scanning {directory}", Status.EXTRACTION_QUIP_FOUND, "")
    file_count = 0
    file_fail_count = 0

    for file_path in directory.rglob(f"*{GZ_EXTENSION}"):
        if not file_path.is_file():
            continue

        file_count += 1
        out_file_path = file_path.with_suffix("")

        try:
            with gzip.open(file_path, "rb") as f_in, open(out_file_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            info(
                f"Extracted {file_path.name} to {out_file_path.name}",
                Status.EXTRACTION_EXTRACTED,
                str(file_path),
            )
            ResultData.quip_status.append(WakeEvents.EXTRACT_GZ_NO_DATA_ISSUE)
            file_path.unlink()
        except gzip.BadGzipFile as ex:
            error(
                f"Extracting {file_path.name} to {out_file_path.name}",
                ex,
                Status.EXTRACTION_FAILED,
                str(file_path),
            )
            ResultData.quip_status.append(WakeEvents.EXTRACT_GZ_DATA_ISSUE)
            file_fail_count += 1
            if out_file_path.exists():
                out_file_path.unlink()
        except Exception as ex:
            error(
                f"Extracting {file_path.name} to {out_file_path.name}",
                ex,
                Status.EXTRACTION_FAILED,
                str(file_path),
            )
            ResultData.quip_status.append(WakeEvents.EXTRACT_GZ_DATA_ISSUE)
            file_fail_count += 1
            if out_file_path.exists():
                out_file_path.unlink()

    info(
        f"Decompressed {file_count - file_fail_count} of {file_count} files from {directory}",
        Status.EXTRACTION_COMPLETED,
        "",
    )
    return file_count - file_fail_count, file_count


def main():
    parser = argparse.ArgumentParser(description="Extract all .gz files in a directory tree.")
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan recursively for .gz files. Defaults to the current directory.",
    )
    args = parser.parse_args()
    extract_gz_files(args.directory, None, None)


if __name__ == "__main__":
    main()
