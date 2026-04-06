from fastapi import APIRouter
import psutil
import platform
import subprocess

router = APIRouter(prefix="/system", tags=["System"])

import threading

# Cache static system specs to avoid slow WMI calls every 3 seconds
STATIC_SYS_INFO = None

def fetch_wmi_gpu_data():
    gpu_names = []
    try:
        # CREATE_NO_WINDOW = 0x08000000
        output = subprocess.check_output(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            creationflags=0x08000000,
            timeout=5
        ).decode("utf-8")
        lines = [line.strip() for line in output.split('\n') if line.strip() and "Name" not in line]
        gpu_names = list(set(lines))
    except Exception:
        pass
        
    if STATIC_SYS_INFO is not None and gpu_names:
        STATIC_SYS_INFO["gpu_names"] = gpu_names

def get_static_sys_info():
    global STATIC_SYS_INFO
    if STATIC_SYS_INFO is not None:
        return STATIC_SYS_INFO

    os_name = f"{platform.system()} {platform.release()}"
    sys_name = platform.node()
    
    STATIC_SYS_INFO = {
        "os_name": os_name,
        "sys_name": sys_name,
        "gpu_names": ["-"], # Placeholder while loading
        "mem_total": psutil.virtual_memory().total,
        "cpu_cores": psutil.cpu_count(logical=True)
    }
    
    if platform.system() == "Windows":
        # Launch background thread so API doesn't hang waiting for wmic
        threading.Thread(target=fetch_wmi_gpu_data, daemon=True).start()

    return STATIC_SYS_INFO

@router.get("/info")
def get_system_info():
    static = get_static_sys_info()
    
    # interval=None calculates instantly based on time since the last call. 
    # Perfect for our 3-second UI polling tick!
    cpu_percent = psutil.cpu_percent(interval=None)
    
    # Memory
    mem = psutil.virtual_memory()
    
    # Battery
    try:
        battery = psutil.sensors_battery()
        bat_percent = battery.percent if battery else None
        bat_plugged = battery.power_plugged if battery else None
    except Exception:
        bat_percent = None
        bat_plugged = None

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": static["cpu_cores"]
        },
        "memory": {
            "total": static["mem_total"],
            "used": mem.used,
            "percent": mem.percent
        },
        "battery": {
            "percent": bat_percent,
            "plugged": bat_plugged
        },
        "os": {
            "node": static["sys_name"],
            "system": static["os_name"]
        },
        "gpu": static["gpu_names"]
    }
