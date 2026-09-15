"""
Storage Module - Arsenal Module
Filesystem-based run persistence
Copy-paste ready: Just provide results_root path
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STRICT_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+-\d{3,}$")
LEGACY_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
EXPERIMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

MAX_METADATA_CACHE_ENTRIES = 5000

logger = logging.getLogger(__name__)


class RunStorage:
    """Storage manager for experimental runs"""

    def __init__(self, results_root: str) -> None:
        self.results_root = Path(results_root)
        self._write_lock = asyncio.Lock()
        # path -> (mtime_ns, size, metadata|None). Invalidated by any write,
        # since a rewritten file changes mtime/size. Bounded to MAX_METADATA_CACHE_ENTRIES.
        self._metadata_cache: dict[str, tuple[int, int, dict[str, Any] | None]] = {}

    def _cached_metadata(
        self,
        path: Path,
        loader: Callable[[], dict[str, Any] | None],
    ) -> dict[str, Any] | None:
        """Return parsed metadata for path, reusing the cache when unchanged."""
        try:
            stat = path.stat()
        except OSError:
            self._metadata_cache.pop(str(path), None)
            return None

        key = str(path)
        cached = self._metadata_cache.get(key)
        if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]

        metadata = loader()
        if len(self._metadata_cache) >= MAX_METADATA_CACHE_ENTRIES:
            excess = len(self._metadata_cache) - MAX_METADATA_CACHE_ENTRIES + 1
            for k in list(self._metadata_cache.keys())[:excess]:
                self._metadata_cache.pop(k, None)
        self._metadata_cache[key] = (stat.st_mtime_ns, stat.st_size, metadata)
        return metadata

    @staticmethod
    def _sanitize_base_name(raw: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', raw)
        sanitized = re.sub(r'-\d{3,}$', '', sanitized)
        return sanitized or "run"

    def _next_run_id(self, base: str) -> str:
        numbers: list[int] = []
        if self.results_root.exists():
            pattern = re.compile(rf'^{re.escape(base)}-(\d{{3,}})$')
            for entry in self.results_root.iterdir():
                if entry.suffix != ".json":
                    continue
                match = pattern.match(entry.stem)
                if match:
                    numbers.append(int(match.group(1)))
        next_number = max(numbers) + 1 if numbers else 1
        return f"{base}-{next_number:03d}"

    async def ensure_results_dir(self) -> None:
        """Ensure results directory exists"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.results_root.mkdir(parents=True, exist_ok=True))



    async def migrate_legacy_run_ids(self) -> dict[str, str]:
        """
        Migrate legacy run IDs to strict `<base>-NNN` format.

        Returns:
            Mapping of legacy_id -> strict_run_id for migrated records.
        """
        await self.ensure_results_dir()
        loop = asyncio.get_running_loop()

        def _migrate() -> dict[str, str]:
            migrated: dict[str, str] = {}
            if not self.results_root.exists():
                return migrated

            for entry in sorted(self.results_root.iterdir(), key=lambda p: p.name):
                source_path: Path
                source_id: str
                source_data: dict[str, Any]

                try:
                    if entry.is_file() and entry.suffix == ".json":
                        source_path = entry
                        source_id = entry.stem
                    elif entry.is_dir():
                        candidate = entry / "run.json"
                        if not candidate.exists():
                            continue
                        source_path = candidate
                        source_id = entry.name
                    else:
                        continue

                    if STRICT_RUN_ID_PATTERN.fullmatch(source_id):
                        continue
                    if not LEGACY_RUN_ID_PATTERN.fullmatch(source_id):
                        continue

                    with open(source_path, encoding="utf-8") as f:
                        source_data = json.load(f)
                    if not isinstance(source_data, dict):
                        continue

                    base = self._sanitize_base_name(source_id)
                    strict_id = self._next_run_id(base)
                    strict_path = self.results_root / f"{strict_id}.json"
                    if strict_path.exists():
                        continue

                    source_data["runId"] = strict_id
                    with open(strict_path, "w", encoding="utf-8") as f:
                        json.dump(source_data, f, indent=2)

                    # Clean up legacy source after successful migration
                    try:
                        if entry.is_file():
                            entry.unlink()
                        elif entry.is_dir():
                            source_path.unlink()
                            # Remove dir only if now empty
                            if not any(entry.iterdir()):
                                entry.rmdir()
                    except OSError:
                        pass  # Best-effort cleanup

                    migrated[source_id] = strict_id
                except Exception:  # noqa: S112 - best-effort scan: one unreadable run must not abort migration
                    continue

            return migrated

        return await loop.run_in_executor(None, _migrate)

    def _atomic_write(self, target_path: Path, data: dict[str, Any], create_only: bool = False) -> bool:
        """
        Internal sync method. Write JSON to target_path atomically.

        If create_only is True, the write will not overwrite an existing file.
        It prefers a hard-link commit and falls back to an exclusive-name
        reservation on filesystems without hard-link support.

        Returns True on success, False if create_only=True and the file exists.
        """
        fd, tmp_path = tempfile.mkstemp(dir=str(self.results_root), suffix=".tmp")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2)
                
            if create_only:
                try:
                    # Try hard link first (strictly atomic)
                    os.link(tmp_path, target_path)
                    return True
                except FileExistsError:
                    return False
                except OSError:
                    # Fallback for filesystems without hard links.
                    # Use exclusive open ('x') to reserve the file name, then
                    # replace it with the fully-written temp file.
                    try:
                        with open(target_path, 'x'):
                            pass
                    except FileExistsError:
                        return False
                    try:
                        os.replace(tmp_path, target_path)
                    except Exception:
                        try:
                            os.unlink(target_path)
                        except OSError:
                            pass
                        raise
                    return True
            else:
                # Normal save, overwrite is fine
                os.replace(tmp_path, target_path)
                return True
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def create_run(self, model_name: str, run_data: dict[str, Any]) -> str:
        """
        Reserve a unique run ID, stamp it on run_data, and persist atomically.

        This prefers a hard-link commit that never exposes a placeholder file.
        On filesystems without hard-link support it falls back to reserving the
        final name with ``open('x')`` before replacing it with the temp file.

        Args:
            model_name: Model identifier (used to derive the run ID base).
            run_data: Complete run data; ``runId`` is set before writing.

        Returns:
            The generated run ID.
        """
        await self.ensure_results_dir()
        loop = asyncio.get_running_loop()

        def _create_and_save() -> str:
            sanitized = self._sanitize_base_name(model_name)

            for _ in range(20):
                run_id = self._next_run_id(sanitized)
                run_file = self.results_root / f"{run_id}.json"
                
                target_data = run_data.copy()
                target_data["runId"] = run_id
                
                if self._atomic_write(run_file, target_data, create_only=True):
                    # Successfully written!
                    run_data["runId"] = run_id
                    return run_id
                # Otherwise ID taken, continue loop
                
            raise RuntimeError("Failed to generate and save unique Run ID after multiple attempts")

        return await loop.run_in_executor(None, _create_and_save)

    async def update_run(self, run_id: str, change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        """Serialize read-modify-write within this single-process store."""
        async with self._write_lock:
            latest = await self.get_run(run_id)
            change(latest)
            await self._write_run(run_id, latest)
            return latest

    async def save_run(self, run_id: str, run_data: dict[str, Any]) -> None:
        """Save an execution snapshot while preserving independently derived fields."""
        async with self._write_lock:
            merged = dict(run_data)
            try:
                latest = await self.get_run(run_id)
            except FileNotFoundError:
                latest = {}
            for key in ("insights", "narrative", "narrativeEvidenceHash"):
                if key in latest:
                    merged[key] = latest[key]
            # Concurrent iteration callbacks may arrive out of order.
            if len(latest.get("responses", [])) > len(merged.get("responses", [])):
                for key in ("responses", "summary", "completedIterations"):
                    if key in latest:
                        merged[key] = latest[key]
            await self._write_run(run_id, merged)

    async def _write_run(self, run_id: str, run_data: dict[str, Any]) -> None:
        """
        Save run data to filesystem (flat file preference)

        Args:
            run_id: Unique run identifier
            run_data: Complete run data
        """
        # Validate before building any path: get_run() does the same, and an
        # unvalidated id here is an arbitrary-file-write primitive.
        if not isinstance(run_id, str) or not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid run_id")

        await self.ensure_results_dir()

        loop = asyncio.get_running_loop()

        # Determine target file (Flat file only)
        # Legacy folders are no longer supported for new writes (migration required)
        run_file = self.results_root / f"{run_id}.json"

        def _write():
            self._atomic_write(run_file, run_data, create_only=False)

        writing = loop.run_in_executor(None, _write)
        try:
            await asyncio.shield(writing)
        except asyncio.CancelledError:
            await writing
            raise

    async def list_runs(self) -> list[dict[str, Any]]:
        """
        List all runs (metadata only) - Supports legacy folders and flat files

        Returns:
            Array of run metadata
        """
        loop = asyncio.get_running_loop()
        
        def _list():
            if not self.results_root.exists():
                return []

            runs_by_id: dict[str, dict[str, Any]] = {}
            for entry in self.results_root.iterdir():
                try:
                    if entry.is_dir():
                        source = entry / "run.json"
                        if not source.exists():
                            continue
                    elif entry.is_file() and entry.suffix == ".json":
                        source = entry
                    else:
                        continue

                    def _parse(source_path: Path = source, entry_name: str = entry.name):
                        with open(source_path) as handle:
                            data = json.load(handle)
                        if not isinstance(data, dict):
                            return None
                        if "runId" not in data and "timestamp" not in data:
                            return None
                        run_id = data.get("runId", source_path.stem)
                        if not isinstance(run_id, str) or not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
                            return None
                        return {
                            "runId": run_id,
                            "timestamp": data.get("timestamp", ""),
                            "modelName": data.get("modelName", "Unknown"),
                            "paradoxId": data.get("paradoxId", "Unknown"),
                            "experimentId": data.get("experimentId"),
                            "iterationCount": data.get("iterationCount", 0),
                            "status": data.get("status", "completed"),
                            "filePath": f"results/{entry_name}",
                        }

                    metadata = self._cached_metadata(source, _parse)
                    if metadata:
                        run_id = metadata["runId"]
                        current = runs_by_id.get(run_id)
                        if current is None:
                            runs_by_id[run_id] = metadata
                        else:
                            # Prefer strict flat-file entry when duplicates are present.
                            preferred_name = f"{run_id}.json"
                            if entry.name == preferred_name:
                                runs_by_id[run_id] = metadata

                except Exception as e:
                    # Log error but continue listing other files
                    logger.error("Error reading run file %s: %s", entry, e)

            # Helper for robust timestamp parsing
            def parse_ts(ts: str | None) -> datetime:
                # Sentinel: earliest possible time, strictly UTC-aware to match stored runs
                sentinel = datetime.min.replace(tzinfo=UTC)
                if not ts:
                    return sentinel

                # Handle 'Z' -> '+00:00'
                ts_clean = ts.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(ts_clean)
                    # If naive, force to UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                except ValueError:
                    return sentinel

            # Sort by timestamp, newest first
            runs = list(runs_by_id.values())
            runs.sort(key=lambda x: parse_ts(x.get("timestamp", "")), reverse=True)
            return runs

        return await loop.run_in_executor(None, _list)

    async def list_incomplete_runs(self) -> list[dict[str, Any]]:
        """Return persisted runs that were left in a resumable state."""
        loop = asyncio.get_running_loop()

        def _list_incomplete() -> list[dict[str, Any]]:
            if not self.results_root.exists():
                return []

            resumable: list[dict[str, Any]] = []
            for entry in sorted(self.results_root.iterdir(), key=lambda path: path.name):
                if not entry.is_file() or entry.suffix != ".json":
                    continue
                try:
                    with open(entry, encoding="utf-8") as f:
                        run_data = json.load(f)
                except Exception:  # noqa: S112 - best-effort scan: one unreadable run must not abort the listing
                    continue

                if not isinstance(run_data, dict):
                    continue

                run_id = run_data.get("runId")
                if not isinstance(run_id, str) or not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
                    continue

                if run_data.get("status") != "running":
                    continue

                iteration_count = int(run_data.get("iterationCount", 0) or 0)
                completed_iterations = int(run_data.get("completedIterations", 0) or 0)
                if iteration_count > 0 and completed_iterations < iteration_count:
                    resumable.append(run_data)

            resumable.sort(key=lambda item: str(item.get("timestamp", "")))
            return resumable

        return await loop.run_in_executor(None, _list_incomplete)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """
        Get specific run by ID

        Args:
            run_id: Run identifier

        Returns:
            Complete run data
        """
        if not isinstance(run_id, str) or not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid run_id")
        
        try:
            flat_path = (self.results_root / f"{run_id}.json").resolve()
            legacy_path = (self.results_root / run_id / "run.json").resolve()
            root_path = self.results_root.resolve()
            if not flat_path.is_relative_to(root_path):
                raise ValueError("Path traversal attempt")
            if not legacy_path.is_relative_to(root_path):
                raise ValueError("Path traversal attempt")
        except Exception:
            raise ValueError("Invalid run_id path")
             
        loop = asyncio.get_running_loop()
        
        def _read():
            # Try flat file first
            flat_path = self.results_root / f"{run_id}.json"
            if flat_path.exists():
                 with open(flat_path) as f:
                    return json.load(f)
            
            # Fallback to legacy folder
            legacy_path = self.results_root / run_id / "run.json"
            if legacy_path.exists():
                with open(legacy_path) as f:
                    return json.load(f)
                    
            raise FileNotFoundError(f"Run {run_id} not found")

        return await loop.run_in_executor(None, _read)

class ExperimentStorage:
    """Storage manager for defined experiments"""

    def __init__(self, experiments_root: str) -> None:
        self._claim_lock = asyncio.Lock()
        self.experiments_root = Path(experiments_root)

    async def claim_experiment(self, exp_id: str) -> dict[str, Any]:
        """Claim a pending manifest once in the supported single process."""
        async with self._claim_lock:
            data = await self.get_experiment(exp_id)
            if data.get("status") != "pending":
                raise ValueError("Experiment must be pending to execute")
            data["status"] = "running"
            await self.save_experiment(exp_id, data)
            return data

    async def ensure_dir(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.experiments_root.mkdir(parents=True, exist_ok=True))

    async def save_experiment(self, exp_id: str, exp_data: dict[str, Any]) -> None:
        if not EXPERIMENT_ID_PATTERN.fullmatch(exp_id):
            raise ValueError("Invalid experiment ID format")
        await self.ensure_dir()
        loop = asyncio.get_running_loop()
        exp_file = self.experiments_root / f"{exp_id}.json"

        def _write():
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.experiments_root), suffix=".tmp"
            )
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(exp_data, f, indent=2)
                os.replace(tmp_path, str(exp_file))
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        await loop.run_in_executor(None, _write)

    async def get_experiment(self, exp_id: str) -> dict[str, Any]:
        if not isinstance(exp_id, str) or not EXPERIMENT_ID_PATTERN.fullmatch(exp_id):
            raise ValueError("Invalid exp_id")
        
        try:
            exp_path = (self.experiments_root / f"{exp_id}.json").resolve()
            root_path = self.experiments_root.resolve()
            if not exp_path.is_relative_to(root_path):
                raise ValueError("Path traversal attempt")
        except (RuntimeError, ValueError) as e:
            raise ValueError(f"Invalid exp_id path: {e}")
             
        loop = asyncio.get_running_loop()
        
        def _read():
            if exp_path.exists():
                with open(exp_path) as f:
                    return json.load(f)
            raise FileNotFoundError(f"Experiment {exp_id} not found")

        return await loop.run_in_executor(None, _read)

    async def list_experiments(self) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        
        def _list():
            if not self.experiments_root.exists():
                return []
            
            exps = []
            for entry in self.experiments_root.iterdir():
                if entry.is_file() and entry.suffix == ".json":
                    try:
                        with open(entry) as f:
                            data = json.load(f)
                            if "id" in data:
                                exps.append(data)
                    except Exception as e:
                        logger.error("Error reading exp file %s: %s", entry, e)
            
            exps.sort(key=lambda x: x.get("id", ""))
            return exps

        return await loop.run_in_executor(None, _list)
