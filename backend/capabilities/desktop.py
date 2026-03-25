import os
import subprocess
import psutil
import pyautogui
from AppOpener import open as ao_open, close as ao_close
import logging

logger = logging.getLogger(__name__)

# Basic safety: No clicking in corners (failsafe)
pyautogui.FAILSAFE = True

def list_processes():
    """Return a list of running process names."""
    processes = []
    for proc in psutil.process_iter(['name']):
        try:
            processes.append(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return sorted(list(set(processes)))

def open_app(app_name: str):
    """Launch an application using AppOpener."""
    try:
        logger.info(f"Opening app: {app_name}")
        ao_open(app_name, match_closest=True)
        return {"success": True, "message": f"Opened {app_name}"}
    except Exception as e:
        logger.error(f"Failed to open app {app_name}: {e}")
        return {"success": False, "message": str(e)}

def close_app(app_name: str):
    """Close an application using AppOpener."""
    try:
        logger.info(f"Closing app: {app_name}")
        ao_close(app_name, match_closest=True)
        return {"success": True, "message": f"Closed {app_name}"}
    except Exception as e:
        logger.error(f"Failed to close app {app_name}: {e}")
        return {"success": False, "message": str(e)}

def open_path(path: str):
    """Open a file or directory using the OS default handler."""
    try:
        if os.path.exists(path):
            os.startfile(path)
            return {"success": True, "message": f"Opened path: {path}"}
        else:
            return {"success": False, "message": "Path not found"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def delete_path(path: str):
    """Delete a file or directory."""
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            return {"success": False, "message": "Path not found"}
        return {"success": True, "message": f"Deleted path: {path}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- New Interaction Functions ---

def type_text(text: str):
    """Type text into the focused window."""
    try:
        logger.info(f"Typing text: {text}")
        pyautogui.write(text, interval=0.05)
        return {"success": True, "message": f"Typed: {text}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def press_key(key: str):
    """Press a specific key (e.g. 'extra', 'enter', 'esc')."""
    try:
        logger.info(f"Pressing key: {key}")
        pyautogui.press(key)
        return {"success": True, "message": f"Pressed: {key}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def click_at(x: int, y: int):
    """Perform a mouse click at specific coordinates."""
    try:
        logger.info(f"Clicking at: ({x}, {y})")
        pyautogui.click(x, y)
        return {"success": True, "message": f"Clicked at ({x}, {y})"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_screen_size():
    """Return width and height of the primary monitor."""
    width, height = pyautogui.size()
    return {"width": width, "height": height}
