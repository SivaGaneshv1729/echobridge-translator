"""System and Hardware Inspection Script for EchoBridge."""
import platform
import sys
import shutil
import os
import json
import ctypes

def get_ram_info():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return {
        "total_ram_gb": round(stat.ullTotalPhys / (1024 ** 3), 2),
        "available_ram_gb": round(stat.ullAvailPhys / (1024 ** 3), 2),
        "memory_load_percent": stat.dwMemoryLoad,
    }

def get_system_info():
    ram = get_ram_info()
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": sys.version.split()[0],
        "cpu_name": platform.processor(),
        "cpu_logical_cores": os.cpu_count(),
        "total_ram_gb": ram["total_ram_gb"],
        "available_ram_gb": ram["available_ram_gb"],
        "ram_load_percent": ram["memory_load_percent"],
    }

    # Disk space on current drive
    cwd = os.getcwd()
    drive = os.path.splitdrive(cwd)[0] or 'C:'
    total, used, free = shutil.disk_usage(cwd)
    info["disk_drive"] = drive
    info["disk_total_gb"] = round(total / (1024 ** 3), 2)
    info["disk_free_gb"] = round(free / (1024 ** 3), 2)

    # Check GPU via torch
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
            info["cuda_device_count"] = torch.cuda.device_count()
        else:
            info["cuda_device_name"] = "None (CPU only)"
    except Exception as e:
        info["torch_status"] = f"Torch import error: {e}"
        info["cuda_available"] = False
        info["cuda_device_name"] = "None"

    return info

if __name__ == "__main__":
    data = get_system_info()
    print(json.dumps(data, indent=2))
