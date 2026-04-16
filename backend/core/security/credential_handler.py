"""
credential_handler.py
=====================
Handles credential requests for web automation.
Shows popup to user when login is needed.
"""

import os
import json
import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import Optional, Dict


class CredentialHandler:
    """
    Manages credential requests during web automation.
    Shows popup dialogs to user when login is needed.
    """
    
    def __init__(self):
        self.credentials_cache = {}
        self.creds_file_path = self._get_creds_path()
        self._load_cache()

    def _get_creds_path(self) -> str:
        base_dir = os.environ.get(
            "NEXUS_CONFIG_PATH",
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
        )
        if base_dir.endswith("config.json"):
            base_dir = os.path.dirname(base_dir)
        
        # Ensure dir exists
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "credentials.json")

    def _load_cache(self):
        try:
            if os.path.exists(self.creds_file_path):
                with open(self.creds_file_path, 'r') as f:
                    self.credentials_cache = json.load(f)
        except Exception as e:
            print(f"Error loading credentials: {e}")
            self.credentials_cache = {}

    def _save_cache(self):
        try:
            with open(self.creds_file_path, 'w') as f:
                json.dump(self.credentials_cache, f)
        except Exception as e:
            print(f"Error saving credentials: {e}")
    
    def request_credentials(
        self,
        site: str,
        fields: list = None,
        force: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Requests credentials from user via popup.
        
        Args:
            site: Website name (e.g., "Gmail", "Amazon")
            fields: List of field names (default: ["username", "password"])
            force: If True, bypasses the cache and forces the user popup.
        
        Returns:
            {"username": "...", "password": "..."} or None if cancelled
        """
        if fields is None:
            fields = ["username", "password"]
        
        # Check cache first
        cache_key = f"{site}:{','.join(fields)}"
        if not force and cache_key in self.credentials_cache:
            return self.credentials_cache[cache_key]
        
        # Show credential dialog
        credentials = {}
        
        # Create root window (hidden)
        root = tk.Tk()
        root.withdraw()
        
        # Show message
        messagebox.showinfo(
            "Credentials Needed",
            f"The automation needs to login to {site}.\n\n"
            f"Please provide your credentials in the next dialogs."
        )
        
        # Request each field
        for field in fields:
            if "password" in field.lower():
                value = simpledialog.askstring(
                    f"{site} - {field}",
                    f"Enter your {field}:",
                    show='*'  # Hide password
                )
            else:
                value = simpledialog.askstring(
                    f"{site} - {field}",
                    f"Enter your {field}:"
                )
            
            if value is None:  # User cancelled
                root.destroy()
                return None
            
            credentials[field] = value
        
        # Automatically save credentials
        self.credentials_cache[cache_key] = credentials
        self._save_cache()
        
        root.destroy()
        return credentials
    
    def clear_cache(self, site: Optional[str] = None):
        """Clears cached credentials."""
        if site:
            keys_to_remove = [k for k in self.credentials_cache.keys() if k.startswith(site)]
            for key in keys_to_remove:
                del self.credentials_cache[key]
        else:
            self.credentials_cache.clear()
        self._save_cache()


# Global instance
credential_handler = CredentialHandler()


# ─────────────────────────────────────────────────────
# USAGE EXAMPLE
# ─────────────────────────────────────────────────────

if __name__ == "__main__":
    handler = CredentialHandler()
    
    # Request Gmail credentials
    creds = handler.request_credentials("Gmail", ["email", "password"])
    
    if creds:
        print(f"Email: {creds['email']}")
        print(f"Password: {'*' * len(creds['password'])}")
    else:
        print("User cancelled")
