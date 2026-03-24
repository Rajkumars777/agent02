"""
credential_handler.py
=====================
Handles credential requests for web automation.
Shows popup to user when login is needed.
"""

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
    
    def request_credentials(
        self,
        site: str,
        fields: list = None
    ) -> Optional[Dict[str, str]]:
        """
        Requests credentials from user via popup.
        
        Args:
            site: Website name (e.g., "Gmail", "Amazon")
            fields: List of field names (default: ["username", "password"])
        
        Returns:
            {"username": "...", "password": "..."} or None if cancelled
        """
        if fields is None:
            fields = ["username", "password"]
        
        # Check cache first
        cache_key = f"{site}:{','.join(fields)}"
        if cache_key in self.credentials_cache:
            reuse = messagebox.askyesno(
                "Credentials Found",
                f"Use saved credentials for {site}?"
            )
            if reuse:
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
        
        # Ask to save
        save = messagebox.askyesno(
            "Save Credentials?",
            f"Save these credentials for {site}?\n\n"
            f"(They will only be stored for this session)"
        )
        
        if save:
            self.credentials_cache[cache_key] = credentials
        
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
