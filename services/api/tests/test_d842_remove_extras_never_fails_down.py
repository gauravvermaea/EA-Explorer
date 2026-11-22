"""D842: `eax down` failed with exit 1 on Windows (owner, 22 Nov 2026, 07:49: ".\\eax down failed (exit 1);
clean-restart stopped there"). Remove-Extras, the last step of down and up, listed the test containers with
--format '{{.Names}} {{.Label "eaexplorer.test"}}'; Windows PowerShell 5.1 drops the inner double quotes on the way to
docker, which then refuses the format and ends with 1, and that exit code became down's. The format now has no double
quote, the run folder is read from the labels, and tidying up never fails down or up."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PS1 = (REPO / "eax.ps1").read_text(encoding="utf-8")
FN = PS1[PS1.index("function Remove-Extras {"):PS1.index("# start-later:")]


def test_no_double_quote_inside_an_argument_to_docker():
    for line in FN.splitlines():
        if "docker @(" in line and "--format" in line:
            fmt = line[line.index('"--format"') + len('"--format"'):]
            assert '\\"' not in fmt and '{{.Label "' not in fmt and "'{{" not in fmt, line
    assert '"--format", "{{.Names}} {{.Labels}}"' in FN


def test_the_run_folder_is_read_from_the_labels():
    pattern = re.search(r"-match '(.+?)'\) \{ \$Matches\[1\] \}", FN).group(1).replace("\\\\", "\\")
    for labels, folder in [
        ("com.docker.compose.project=eaexplorer,eaexplorer.test=20261121T142504Z", "20261121T142504Z"),
        ("eaexplorer.test=full-20261121T184936Z,maintainer=x", "full-20261121T184936Z"),
        ("com.docker.compose.project=eaexplorer", None),
        ("x.eaexplorer.test=evil", None),
    ]:
        m = re.search(pattern, labels)
        assert (m.group(1) if m else None) == folder, labels


def test_tidying_up_never_fails_down_or_up():
    assert FN.rstrip().endswith("$global:LASTEXITCODE = 0   # tidying up is best effort: what it could not remove never fails down or up\n}")
    assert all(ord(c) < 128 for c in PS1)          # eax.ps1 stays ASCII
