import pytest


def pytest_sessionfinish(session, exitstatus):
    """Treat an empty test suite as success.

    Since pytest 5.0, collecting zero tests yields exit code 5
    (EXIT_NOTESTSCOLLECTED). The Task 1 scaffold ships with no tests yet, so
    map that one case to OK (0). Real passes (0) and failures (1) are
    untouched, so this never masks a genuine failure once tests exist.
    """
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
