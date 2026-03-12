"""
Storage Module - Arsenal Module
Filesystem-based run persistence
Copy-paste ready: Just provide results_root path
"""

import json
import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone
import base64

STRICT_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+-\d{3}$")
LEGACY_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
EXPERIMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class RunStorage:
    """Storage manager for experimental runs"""

    def __init__(self, results_root: str) -> None:
        self.results_root = Path(results_root)

    @staticmethod
    def _sanitize_base_name(raw: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', raw)
        sanitized = re.sub(r'-\d{3}$', '', sanitized)
        return sanitized or "run"

    def _next_run_id(self, base: str) -> str:
        numbers: List[int] = []
        if self.results_root.exists():
            pattern = re.compile(rf'^{re.escape(base)}-(\d{{3}})$')
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



    async def migrate_legacy_run_ids(self) -> Dict[str, str]:
        """
        Migrate legacy run IDs to strict `<base>-NNN` format.

        Returns:
            Mapping of legacy_id -> strict_run_id for migrated records.
        """
        await self.ensure_results_dir()
        loop = asyncio.get_running_loop()

        def _migrate() -> Dict[str, str]:
            migrated: Dict[str, str] = {}
            if not self.results_root.exists():
                return migrated

            for entry in sorted(self.results_root.iterdir(), key=lambda p: p.name):
                source_path: Path
                source_id: str
                source_data: Dict[str, Any]

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

                    with open(source_path, "r", encoding="utf-8") as f:
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
                except Exception:
                    continue

            return migrated

        return await loop.run_in_executor(None, _migrate)

    def _atomic_write(self, target_path: Path, data: Dict[str, Any], create_only: bool = False) -> bool:
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

    async def create_run(self, model_name: str, run_data: Dict[str, Any]) -> str:
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
            if not sanitized:
                sanitized = self._sanitize_base_name(base64.urlsafe_b64encode(model_name.encode()).decode()[:10])

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

    async def save_run(self, run_id: str, run_data: Dict[str, Any]) -> None:
        """
        Save run data to filesystem (flat file preference)

        Args:
            run_id: Unique run identifier
            run_data: Complete run data
        """
        await self.ensure_results_dir()

        loop = asyncio.get_running_loop()

        # Determine target file (Flat file only)
        # Legacy folders are no longer supported for new writes (migration required)
        run_file = self.results_root / f"{run_id}.json"

        def _write():
            self._atomic_write(run_file, run_data, create_only=False)

        await loop.run_in_executor(None, _write)

    async def list_runs(self) -> List[Dict[str, Any]]:
        """
        List all runs (metadata only) - Supports legacy folders and flat files

        Returns:
            Array of run metadata
        """
        loop = asyncio.get_running_loop()
        
        def _list():
            if not self.results_root.exists():
                return []

            runs_by_id: Dict[str, Dict[str, Any]] = {}
            for entry in self.results_root.iterdir():
                try:
                    run_data = None
                    
                    # Check for legacy folder structure
                    if entry.is_dir():
                        run_json_path = entry / "run.json"
                        if run_json_path.exists():
                            with open(run_json_path, 'r') as f:
                                data = json.load(f)
                                # Basic validation
                                if "runId" in data or "timestamp" in data:
                                    run_data = data
                                
                    # Check for flat file structure
                    elif entry.is_file() and entry.suffix == ".json":
                        with open(entry, 'r') as f:
                            data = json.load(f)
                            if "runId" in data or "timestamp" in data:
                                run_data = data
                    
                    if run_data:
                        run_id = run_data.get("runId", entry.stem)
                        if not isinstance(run_id, str):
                            continue
                        if not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
                            continue

                        metadata = {
                            "runId": run_id,
                            "timestamp": run_data.get("timestamp", ""),
                            "modelName": run_data.get("modelName", "Unknown"),
                            "paradoxId": run_data.get("paradoxId", "Unknown"),
                            "iterationCount": run_data.get("iterationCount", 0),
                            "status": run_data.get("status", "completed"),
                            "filePath": f"results/{entry.name}"
                        }
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
                    import logging
                    logging.getLogger(__name__).error(f"Error reading run file {entry}: {e}")

            # Helper for robust timestamp parsing
            def parse_ts(ts):
                # Sentinel: earliest possible time, strictly UTC-aware to match stored runs
                sentinel = datetime.min.replace(tzinfo=timezone.utc)
                if not ts: return sentinel

                # Handle 'Z' -> '+00:00'
                ts = ts.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(ts)
                    # If naive, force to UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    return sentinel

            # Sort by timestamp, newest first
            runs = list(runs_by_id.values())
            runs.sort(key=lambda x: parse_ts(x.get("timestamp", "")), reverse=True)
            return runs

        return await loop.run_in_executor(None, _list)

    async def list_incomplete_runs(self) -> List[Dict[str, Any]]:
        """Return persisted runs that were left in a resumable state."""
        loop = asyncio.get_running_loop()

        def _list_incomplete() -> List[Dict[str, Any]]:
            if not self.results_root.exists():
                return []

            resumable: List[Dict[str, Any]] = []
            for entry in sorted(self.results_root.iterdir(), key=lambda path: path.name):
                if not entry.is_file() or entry.suffix != ".json":
                    continue
                try:
                    with open(entry, "r", encoding="utf-8") as f:
                        run_data = json.load(f)
                except Exception:
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

    async def get_run(self, run_id: str) -> Dict[str, Any]:
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
                 with open(flat_path, 'r') as f:
                    return json.load(f)
            
            # Fallback to legacy folder
            legacy_path = self.results_root / run_id / "run.json"
            if legacy_path.exists():
                with open(legacy_path, 'r') as f:
                    return json.load(f)
                    
            raise FileNotFoundError(f"Run {run_id} not found")

        return await loop.run_in_executor(None, _read)

class ExperimentStorage:
    """Storage manager for defined experiments"""

    def __init__(self, experiments_root: str) -> None:
        self.experiments_root = Path(experiments_root)

    async def ensure_dir(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.experiments_root.mkdir(parents=True, exist_ok=True))

    async def save_experiment(self, exp_id: str, exp_data: Dict[str, Any]) -> None:
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

    async def get_experiment(self, exp_id: str) -> Dict[str, Any]:
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
                with open(exp_path, 'r') as f:
                    return json.load(f)
            raise FileNotFoundError(f"Experiment {exp_id} not found")

        return await loop.run_in_executor(None, _read)

    async def list_experiments(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        
        def _list():
            if not self.experiments_root.exists():
                return []
            
            exps = []
            for entry in self.experiments_root.iterdir():
                if entry.is_file() and entry.suffix == ".json":
                    try:
                        with open(entry, 'r') as f:
                            data = json.load(f)
                            if "id" in data:
                                exps.append(data)
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Error reading exp file {entry}: {e}")
            
            exps.sort(key=lambda x: x.get("id", ""))
            return exps

        return await loop.run_in_executor(None, _list)
