import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        # Store in the user's home directory under .openclaw/nexus_memory.json
        self.storage_dir = os.path.join(os.path.expanduser("~"), ".openclaw")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, "nexus_memory.json")
        self.history: List[str] = []
        self.folders: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.folders = data.get("folders", [])
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Failed to load memory: {e}")
                self.history = []
                self.folders = []
        else:
            self.history = []
            self.folders = []

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self.history,
                    "folders": self.folders
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def get_history(self) -> List[str]:
        return self.history

    def add_to_history(self, prompt: str):
        # Remove if already exists to move to top
        if prompt in self.history:
            self.history.remove(prompt)
        
        self.history.insert(0, prompt)
        # Limit to last 10 as requested
        self.history = self.history[:10]
        self._save()

    def save_history(self, history: List[str]):
        self.history = history[:10]
        self._save()

    def get_folders(self) -> List[Dict[str, Any]]:
        return self.folders

    def save_folders(self, folders: List[Dict[str, Any]]):
        self.folders = folders
        self._save()

# Global instance
memory_manager = MemoryManager()
