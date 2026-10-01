"""Process memory readings for the paper worker.

Values are byte counts from the local process. They are not account data,
credentials, or market payloads.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import os
import resource
import subprocess
import sys
from dataclasses import dataclass
from typing import TypedDict

from prometheus_client import Gauge

from app.observability.metrics import REGISTRY

PROCESS_RSS_BYTES = Gauge(
    "process_resident_memory_bytes",
    "Current process resident set size in bytes",
    registry=REGISTRY,
)
PROCESS_RSS_PEAK_BYTES = Gauge(
    "process_resident_memory_peak_bytes",
    "Peak process resident set size in bytes since process start",
    registry=REGISTRY,
)

_LIBC: ctypes.CDLL | None = None
_LIBC_READY = False


class MemoryStatusFields(TypedDict):
    """Integer RSS fields published on a runtime-status row."""

    process_rss_bytes: int
    process_rss_peak_bytes: int


@dataclass(frozen=True, slots=True)
class ProcessMemory:
    """Resident memory of this process, in bytes."""

    rss_bytes: int
    peak_rss_bytes: int


def read_process_memory() -> ProcessMemory:
    """Return current and peak RSS. Peak does not decrease for the life of the process."""

    rss_kb, peak_kb = _proc_status_kb()
    if rss_kb is None:
        # Darwin reports ru_maxrss in bytes; Linux reports KiB. A high-water
        # mark cannot measure release, so sample current RSS separately on Mac.
        current_kb = _darwin_rss_kb() if sys.platform == "darwin" else None
        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        peak_kb = peak // 1024 if sys.platform == "darwin" else peak
        rss_kb = peak_kb if current_kb is None else current_kb
        peak_kb = max(peak_kb, rss_kb)
    if peak_kb is None:
        peak_kb = rss_kb
    sample = ProcessMemory(rss_bytes=rss_kb * 1024, peak_rss_bytes=peak_kb * 1024)
    _observe(sample)
    return sample


def release_allocator_memory() -> ProcessMemory:
    """Collect unreachable objects and return free heap pages to the OS when possible."""

    gc.collect()
    _malloc_trim()
    return read_process_memory()


def memory_status_fields() -> MemoryStatusFields:
    """RSS fields for a runtime-status write. Integers only."""

    sample = read_process_memory()
    return {
        "process_rss_bytes": sample.rss_bytes,
        "process_rss_peak_bytes": sample.peak_rss_bytes,
    }


def _proc_status_kb() -> tuple[int | None, int | None]:
    rss_kb: int | None = None
    peak_kb: int | None = None
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                elif line.startswith("VmHWM:"):
                    peak_kb = int(line.split()[1])
    except OSError:
        return None, None
    return rss_kb, peak_kb


def _darwin_rss_kb() -> int | None:
    """Read this process's current RSS using macOS ps (which reports KiB)."""

    try:
        result = subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True,
            text=True,
            check=True,
            timeout=1,
        )
        value = int(result.stdout.strip())
        return value if value > 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _observe(sample: ProcessMemory) -> None:
    PROCESS_RSS_BYTES.set(sample.rss_bytes)
    PROCESS_RSS_PEAK_BYTES.set(sample.peak_rss_bytes)


def _malloc_trim() -> None:
    global _LIBC, _LIBC_READY
    if not _LIBC_READY:
        _LIBC_READY = True
        name = ctypes.util.find_library("c")
        if name is None:
            return
        try:
            library = ctypes.CDLL(name)
        except OSError:
            return
        if not hasattr(library, "malloc_trim"):
            return
        library.malloc_trim.argtypes = [ctypes.c_size_t]
        library.malloc_trim.restype = ctypes.c_int
        _LIBC = library
    if _LIBC is None:
        return
    _LIBC.malloc_trim(0)
