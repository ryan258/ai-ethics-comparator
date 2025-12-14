"""
Storage Module - Arsenal Module
Filesystem-based run persistence
Copy-paste ready: Just provide results_root path
"""

import json
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class RunStorage:
    """Storage manager for experimental runs"""

    def __init__(self, results_root: str):
        self.results_root = Path(results_root)

    async def ensure_results_dir(self):
        """Ensure results directory exists"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.results_root.mkdir(parents=True, exist_ok=True))

    async def generate_run_id(self, model_name: str) -> str:
        """
        Generate unique run ID with sequential numbering
        
        Args:
            model_name: Model identifier
            
        Returns:
            Unique run ID
        """
        await self.ensure_results_dir()
        
        loop = asyncio.get_running_loop()

        def _get_next_id():
            # Sanitize model name for filesystem
            sanitized = re.sub(r'[/:]', '-', model_name.lower())
            sanitized = re.sub(r'[^a-z0-9-]', '', sanitized)
            
            # Find existing runs for this model (support directories and flat files)
            existing_names = []
            if self.results_root.exists():
                for entry in self.results_root.iterdir():
                    if entry.name.startswith(sanitized):
                        if entry.is_dir():
                            existing_names.append(entry.name)
                        elif entry.is_file() and entry.name.endswith(".json") and entry.name != "run.json":
                            existing_names.append(entry.stem)
            
            # Extract sequential numbers
            numbers = []
            for name in existing_names:
                match = re.search(r'-(\d+)$', name)
                if match:
                    numbers.append(int(match.group(1)))
            
            next_number = max(numbers) + 1 if numbers else 1
            padded_number = str(next_number).zfill(3)
            return f"{sanitized}-{padded_number}"

        return await loop.run_in_executor(None, _get_next_id)

    async def save_run(self, run_id: str, run_data: Dict[str, Any]):
        """
        Save run data to filesystem (flat file)

        Args:
            run_id: Unique run identifier
            run_data: Complete run data
        """
        await self.ensure_results_dir()
        
        loop = asyncio.get_running_loop()
        run_file = self.results_root / f"{run_id}.json"
        
        def _write():
            with open(run_file, 'w') as f:
                json.dump(run_data, f, indent=2)
                
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

            runs = []
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
                        runs.append({
                            "runId": run_data.get("runId", entry.stem),
                            "timestamp": run_data.get("timestamp", ""),
                            "modelName": run_data.get("modelName", "Unknown"),
                            "paradoxId": run_data.get("paradoxId", "Unknown"),
                            "iterationCount": run_data.get("iterationCount", 0),
                            "filePath": f"results/{entry.name}"
                        })

                except Exception as e:
                    # Log error but continue listing other files
                    print(f"Error reading run file {entry}: {e}")

            # Sort by timestamp, newest first
            runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return runs

        return await loop.run_in_executor(None, _list)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """
        Get specific run by ID

        Args:
            run_id: Run identifier

        Returns:
            Complete run data
        """
        # Basic validation to prevent traversal
        if not run_id or "/" in run_id or ".." in run_id:
            raise ValueError("Invalid run_id")
             
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

    async def update_run(self, run_id: str, updates: Dict[str, Any]):
        """
        Update existing run (e.g., adding insights)

        Args:
            run_id: Run identifier
            updates: Partial data to merge
        """
        loop = asyncio.get_running_loop()
        
        def _update():
            # Determine path (prefer flat if exists, else legacy, else create flat)
            flat_path = self.results_root / f"{run_id}.json"
            legacy_path = self.results_root / run_id / "run.json"
            
            target_path = flat_path
            if legacy_path.exists() and not flat_path.exists():
                target_path = legacy_path
                
            if target_path.exists():
                with open(target_path, 'r') as f:
                    run_record = json.load(f)
            else:
                run_record = {}

            run_record.update(updates)

            with open(target_path, 'w') as f:
                json.dump(run_record, f, indent=2)

        await loop.run_in_executor(None, _update)
