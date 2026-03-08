import sys
import time


def wait_for_spooler(file_name: str, timeout: int = 30) -> bool:
    """
    Windows 인쇄 스풀러에 작업이 등록되었는지 확인한다.
    비-Windows 환경에서는 항상 True를 반환한다.
    """
    if sys.platform != "win32":
        return True

    import win32print

    deadline = time.time() + timeout
    while time.time() < deadline:
        printer_handle = win32print.OpenPrinter(
            win32print.GetDefaultPrinter()
        )
        try:
            jobs = win32print.EnumJobs(printer_handle, 0, -1, 1)
            for job in jobs:
                if file_name.lower() in job.get("pDocument", "").lower():
                    return True
        finally:
            win32print.ClosePrinter(printer_handle)
        time.sleep(2)

    return False
