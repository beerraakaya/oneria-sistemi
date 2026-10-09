"""Pencere açmadan çalıştıran .vbs dosyaları Windows'ta denenmeden önce burada okunur."""

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _run_argumani(satir: str, degiskenler: dict[str, str]) -> tuple[str, str]:
    """`Run` çağrısının ilk argümanını VBScript gibi okur: "" bir tırnaktır, & birleştirir."""
    i, parcalar = 0, []
    while True:
        while satir[i] == " ":
            i += 1
        if satir[i] == '"':
            i, dize = i + 1, []
            while True:
                assert i < len(satir), f"kapanmamış dize: {satir}"
                if satir[i] == '"' and satir[i + 1 : i + 2] == '"':
                    dize.append('"')
                    i += 2
                elif satir[i] == '"':
                    i += 1
                    break
                else:
                    dize.append(satir[i])
                    i += 1
            parcalar.append("".join(dize))
        else:
            ad = re.match(r"\w+", satir[i:]).group()
            parcalar.append(degiskenler[ad])
            i += len(ad)
        while i < len(satir) and satir[i] == " ":
            i += 1
        if i == len(satir) or satir[i] == ",":
            return "".join(parcalar), satir[i:]
        assert satir[i] == "&", f"beklenmeyen karakter: {satir[i:]}"
        i += 1


@pytest.mark.parametrize(
    ("vbs", "bat"),
    [("calistir_gizli.vbs", "calistir.bat"), ("acilista_gizli.vbs", "acilista_calistir.bat")],
)
def test_gizli_baslatici_bat_dosyasini_calistirir(vbs, bat):
    satir = next(s for s in (KOK / vbs).read_text().splitlines() if ".Run " in s)
    komut, kalan = _run_argumani(satir.split(".Run ", 1)[1], {"klasor": r"C:\Program Klasoru"})
    assert komut == rf'"C:\Program Klasoru\{bat}"'
    assert kalan.replace(" ", "") == ",0,True"  # pencere gizli, bitmesi beklenir
    assert (KOK / bat).exists()
