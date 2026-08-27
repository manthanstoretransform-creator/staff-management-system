import sys
import os

def get_active_window_details():
    """
    Detects detailed active window information on Windows:
    returns (app_name, window_title, exe_path, pid).
    """
    if sys.platform != "win32":
        return "Unknown System", "Active Tracking Only Supported on Windows", None, None

    import ctypes
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return "Idle/System", "No Active Window", None, None

    # Get Window Title
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    window_title = buf.value

    # Get Process Name and Executable Path
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    pid_val = pid.value
    
    app_name = None
    exe_path = None
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_val)
    if h_process:
        buf = ctypes.create_unicode_buffer(512)
        size = ctypes.c_ulong(512)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            exe_path = buf.value
            app_name = os.path.basename(exe_path)
        ctypes.windll.kernel32.CloseHandle(h_process)

    if not app_name:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 260)
        app_name = buf.value or "Unknown Application"

    clean_app_name = app_name[:-4] if app_name.lower().endswith(".exe") else app_name

    return clean_app_name, window_title, exe_path, pid_val


def get_active_window_info():
    """
    Detects the active window title and application name.
    Backward-compatible 2-tuple return.
    """
    app_name, window_title, _, _ = get_active_window_details()
    return app_name, window_title
