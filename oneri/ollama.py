"""Bilgisayarda çalışan Ollama ile konuşan küçük istemci."""

import json

import requests


class OllamaHatasi(RuntimeError):
    """Ollama'ya ulaşılamadı ya da istek başarısız oldu."""


class GecersizCevap(OllamaHatasi):
    """Model cevap verdi ama cevap beklenen biçimde değil."""


def model_yuklu_mu(model: str, yuklu: list[str]) -> bool:
    """Ollama etiketsiz model adlarını ":latest" olarak listeler."""
    return (model if ":" in model else f"{model}:latest") in yuklu


class Ollama:
    def __init__(self, adres: str, zaman_asimi: float = 900):
        self._adres = adres.rstrip("/")
        self._zaman_asimi = zaman_asimi
        self._oturum = requests.Session()
        # Ollama şirket içinde çalışır; bilgisayardaki proxy ayarları ona giden istekleri bozmasın.
        self._oturum.trust_env = False

    def yuklu_modeller(self) -> list[str]:
        return [model["name"] for model in self._istek("GET", "/api/tags")["models"]]

    def gom(self, model: str, metinler: list[str]) -> list[list[float]]:
        """Her metin için bir anlam vektörü döndürür."""
        return self._istek("POST", "/api/embed", {"model": model, "input": metinler})["embeddings"]

    def json_sohbet(self, model: str, mesajlar: list[dict], sema: dict, secenekler: dict) -> dict:
        """Modelden `sema`ya uyan bir JSON cevap ister."""
        cevap = self._istek(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": mesajlar,
                "format": sema,
                "stream": False,
                "options": secenekler,
            },
        )
        icerik = cevap["message"]["content"]
        try:
            return json.loads(icerik)
        except json.JSONDecodeError as hata:
            raise GecersizCevap(f"Model geçerli JSON döndürmedi: {icerik[:300]}") from hata

    def _istek(self, yontem: str, yol: str, govde: dict | None = None) -> dict:
        try:
            cevap = self._oturum.request(
                yontem, f"{self._adres}{yol}", json=govde, timeout=self._zaman_asimi
            )
        except requests.ConnectionError as hata:
            raise OllamaHatasi(
                f"Ollama'ya bağlanılamadı ({self._adres}). Ollama açık mı?"
            ) from hata
        except requests.Timeout as hata:
            raise OllamaHatasi(
                f"Ollama {self._zaman_asimi:.0f} saniyede cevap vermedi."
            ) from hata

        if cevap.status_code == 404 and govde and "model" in govde:
            raise OllamaHatasi(
                f"'{govde['model']}' modeli yüklü değil. Önce şunu çalıştırın: ollama pull {govde['model']}"
            )
        if not cevap.ok:
            raise OllamaHatasi(f"Ollama hata döndürdü ({cevap.status_code}): {cevap.text[:300]}")
        return cevap.json()
