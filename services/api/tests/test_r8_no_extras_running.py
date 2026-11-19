"""Nothing that is not part of running EA Explorer comes up in regular operation (owner, 19 Nov 2026, 05:45: "please
ensure sonar and other non essential containers do not come up during regular operations of the platform"; D793).

The containers of the test and platform profiles (SonarQube and its scanner, k6, the test runner and the platform's
always-on test runner) are not started by up; and because compose's own down leaves a profile's containers alone, and a
container with a restart policy comes back whenever Docker starts, every form of eax removes them on up and down."""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _stack():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import stack
    return stack


def test_every_test_or_platform_container_is_in_a_profile_and_on_the_list():
    stack = _stack()
    svc = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    profiled = {n for n, s in svc.items() if set(s.get("profiles") or []) & {"test", "platform"}}
    assert profiled == {*stack.EXTRA_CONTAINERS, "testrunner"}       # a new one must be added to the list too
    for name in (*stack.EXTRA_CONTAINERS, "testrunner"):
        assert svc[name].get("profiles"), f"{name} would start with every up"


def test_a_running_test_is_never_stopped():
    stack = _stack()
    assert "testrunner" in stack.extras_to_remove(test_running=False)
    assert "testrunner" not in stack.extras_to_remove(test_running=True)
    assert {"sonarqube", "sonar-scanner", "k6", "testrunner-service"} <= set(stack.extras_to_remove(True))


def test_every_form_of_eax_removes_them_on_up_and_down():
    ps1 = (ROOT / "eax.ps1").read_text(encoding="utf-8")
    sh = (ROOT / "eax.sh").read_text(encoding="utf-8")
    py = (ROOT / "eaxcli" / "stack.py").read_text(encoding="utf-8")
    main = (ROOT / "eaxcli" / "main.py").read_text(encoding="utf-8")
    stack = _stack()
    want = " ".join(stack.EXTRA_CONTAINERS)
    assert '$ExtraContainers = @("' + '", "'.join(stack.EXTRA_CONTAINERS) + '")' in ps1      # the same list (D331)
    assert f'EXTRA_CONTAINERS="{want}"' in sh
    # up: at the end of the second tier; down: after compose's own down
    assert "Remove-Extras      # nothing that is not part of running EA Explorer" in ps1
    assert '"down"    { Invoke-Compose @("down") | Out-Null; Remove-Extras }' in ps1
    assert "remove_extras      # nothing that is not part of running EA Explorer" in sh
    assert "down)    run_compose down; remove_extras ;;" in sh
    assert "remove_extras()        # nothing that is not part of running EA Explorer" in py
    assert "stack.remove_extras()" in main
    for text in (ps1, sh):
        assert "rm" in text and "--profile" in text and "platform" in text
