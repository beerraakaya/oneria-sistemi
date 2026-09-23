"""Testler gerçek şirket verisi yerine uydurma bir Excel ve sahte bir Ollama sunucusu kullanır."""

import json
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import openpyxl
import pytest

from oneri.ayarlar import Ayarlar

from yardimci import BASLIKLAR, SATIRLAR, sahte_gomucu


@pytest.fixture
def ornek_excel(tmp_path):
    kitap = openpyxl.Workbook()
    kitap.active.title = "Dashboard"
    sayfa = kitap.create_sheet("Genel Tablo")
    sayfa.append(BASLIKLAR)
    for _, degerler in SATIRLAR:
        sayfa.append(degerler)
    yol = tmp_path / "oneri.xlsx"
    kitap.save(yol)
    return yol


class SahteOllama:
    def __init__(self):
        self.adres = ""
        self.istekler: list[tuple[str, dict]] = []
        self.modeller = ["qwen2.5:latest", "bge-m3:latest"]
        # Sohbet isteğine verilecek cevap: sözlük JSON'a çevrilir, metin olduğu gibi gönderilir.
        self.sohbet_cevabi: dict | str = {
            "onay_durumu": "Öneri",
            "degerlendirme": "Uygulanabilir bir iyileştirmedir. Maliyet ve fayda hesaplanmalıdır.",
        }

    def sohbetler(self) -> list[dict]:
        return [govde for yol, govde in self.istekler if yol == "/api/chat"]


@pytest.fixture
def sahte_ollama():
    durum = SahteOllama()

    class Isleyici(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _cevap(self, kod: int, veri: dict) -> None:
            govde = json.dumps(veri, ensure_ascii=False).encode()
            self.send_response(kod)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)

        def do_GET(self):
            if self.path == "/api/tags":
                self._cevap(200, {"models": [{"name": ad} for ad in durum.modeller]})
            else:
                self._cevap(404, {"error": "not found"})

        def do_POST(self):
            govde = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            durum.istekler.append((self.path, govde))
            model = govde.get("model", "")
            if model not in durum.modeller and f"{model}:latest" not in durum.modeller:
                return self._cevap(404, {"error": f'model "{model}" not found, try pulling it first'})
            if self.path == "/api/embed":
                return self._cevap(200, {"embeddings": sahte_gomucu(govde["input"])})
            if self.path == "/api/chat":
                cevap = durum.sohbet_cevabi
                icerik = cevap if isinstance(cevap, str) else json.dumps(cevap, ensure_ascii=False)
                return self._cevap(200, {"message": {"role": "assistant", "content": icerik}, "done": True})
            self._cevap(404, {"error": "not found"})

    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), Isleyici)
    Thread(target=sunucu.serve_forever, daemon=True).start()
    durum.adres = f"http://127.0.0.1:{sunucu.server_port}"
    yield durum
    sunucu.shutdown()
    sunucu.server_close()


@pytest.fixture
def ayarlar(tmp_path, ornek_excel, sahte_ollama):
    kurallar = tmp_path / "kurallar.md"
    kurallar.write_text("Rutin bakım işleri öneri sayılmaz.", encoding="utf-8")
    return replace(
        Ayarlar(),
        excel_yolu=ornek_excel,
        kurallar_yolu=kurallar,
        veri_klasoru=tmp_path / "veri",
        ollama_adresi=sahte_ollama.adres,
    )
