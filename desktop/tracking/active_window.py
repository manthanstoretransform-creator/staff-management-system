import sys
import os

def get_active_window_info():
    """
    Detects the active window title and application name.
    Currently only supports Windows. On other systems, returns generic info.
    """
    if sys.platform != "win32":
        return "Unknown System", "Active Tracking Only Supported on Windows"

    import ctypes
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return "Idle/System", "No Active Window"

    # Get Window Title
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    window_title = buf.value

    # Get Process Name
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    app_name = None
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h_process:
        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.c_ulong(260)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            app_name = os.path.basename(buf.value)
        ctypes.windll.kernel32.CloseHandle(h_process)

    if not app_name:
        # Fallback to class name
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 260)
        app_name = buf.value or "Unknown Application"

    # Normalize app name (remove .exe if present)
    if app_name.lower().endswith(".exe"):
        app_name = app_name[:-4]

    return app_name, window_title
