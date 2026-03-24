import os
import re
from typing import Dict, Tuple

class SecurityManager:
    """
    Handles the sanitization of sensitive data (passwords, API keys) from user prompts
    and their secure re-injection during tool execution.
    """
    def __init__(self):
        self._secret_store: Dict[str, str] = {}
        self._counter = 0

    def sanitize_input(self, text: str) -> str:
        """
        Scans the input text for potential secrets and replaces them with placeholders.
        Currently detects:
        - Quoted strings following "password", "secret", "key"
        - Explicit environment variable references are left as is (e.g. $MY_VAR)
        """
        # 1. Reset store for a new turn (optional, but good for statelessness if needed)
        # self._secret_store.clear() 
        
        # Regex to find "password is '12345'" or 'password "12345"'
        # Captures: 1=Label, 2=Quote, 3=Secret, 4=Quote
        pattern = r'(password|secret|key|token|pin)\s*(?:is|:|=)?\s*([\'"])(.*?)([\'"])'
        
        def replace_match(match):
            label = match.group(1)
            secret_val = match.group(3)
            
            # If it looks like an env var reference, leave it
            if secret_val.startswith("$") or secret_val.startswith("%"):
                return match.group(0)
                
            placeholder = f"__SECRET_{self._counter}__"
            self._secret_store[placeholder] = secret_val
            self._counter += 1
            
            return f"{label} {match.group(2)}{placeholder}{match.group(4)}"

        sanitized_text = re.sub(pattern, replace_match, text, flags=re.IGNORECASE)
        return sanitized_text

    def get_formatted_secrets(self) -> str:
        """
        Returns a string description of available secrets for the LLM context.
        """
        if not self._secret_store:
            return ""
        return "Secrets available (use these placeholders exactly): " + ", ".join(self._secret_store.keys())

    def inject_secrets(self, value: str) -> str:
        """
        Replaces placeholders in a command string with the actual secret values.
        """
        if not isinstance(value, str):
            return value
            
        # Check for placeholder keys
        for placeholder, secret in self._secret_store.items():
            if placeholder in value:
                return value.replace(placeholder, secret)
                
        # Also check for Environment Variables
        if value.startswith("$"):
             env_var = value[1:]
             return os.environ.get(env_var, value)
             
        return value

# Singleton instance
security_manager = SecurityManager()
