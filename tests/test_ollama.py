import socket

import pytest

from oneri.ollama import GecersizCevap, Ollama, OllamaHatasi, model_yuklu_mu


def test_yuklu_modelleri_listeler(sahte_ollama):
    yuklu = Ollama(sahte_ollama.adres).yuklu_modeller()
    assert model_yuklu_mu("qwen2.5", yuklu)
    assert model_yuklu_mu("bge-m3:latest", yuklu)
    assert not model_yuklu_mu("qwen2.5:14b", yuklu)


def test_gomme_istegi(sahte_ollama):
    vektorler = Ollama(sahte_ollama.adres).gom("bge-m3", ["bir", "iki"])
    assert len(vektorler) == 2
    assert sahte_ollama.istekler[-1] == ("/api/embed", {"model": "bge-m3", "input": ["bir", "iki"]})


def test_sohbet_istegi_cevabi_semaya_zorlar(sahte_ollama):
    sema = {"type": "object"}
    cevap = Ollama(sahte_ollama.adres).json_sohbet(
        "qwen2.5", [{"role": "user", "content": "merhaba"}], sema, {"num_ctx": 8192}
    )
    assert cevap["gerekce"] == "Geçerli öneri"
    _, govde = sahte_ollama.istekler[-1]
    assert govde["format"] == sema
    assert govde["stream"] is False
    assert govde["options"] == {"num_ctx": 8192}


def test_json_olmayan_cevap(sahte_ollama):
    sahte_ollama.sohbet_cevabi = "bu JSON değil"
    with pytest.raises(GecersizCevap, match="geçerli JSON"):
        Ollama(sahte_ollama.adres).json_sohbet("qwen2.5", [], {}, {})


def test_yuklu_olmayan_model_icin_ne_yapilacagini_soyler(sahte_ollama):
    with pytest.raises(OllamaHatasi, match="ollama pull qwen2.5:32b"):
        Ollama(sahte_ollama.adres).gom("qwen2.5:32b", ["metin"])


def test_ollama_kapaliysa_anlasilir_hata():
    with socket.socket() as soket:
        soket.bind(("127.0.0.1", 0))
        bos_port = soket.getsockname()[1]
    with pytest.raises(OllamaHatasi, match="bağlanılamadı"):
        Ollama(f"http://127.0.0.1:{bos_port}").yuklu_modeller()


def test_model_bellekte_tutma_suresi_gonderilir(sahte_ollama):
    ollama = Ollama(sahte_ollama.adres, bekleme="40m")
    ollama.json_sohbet("qwen2.5", [{"role": "user", "content": "x"}], {"type": "object"}, {})
    ollama.gom("bge-m3", ["metin"])
    govdeler = [govde for yol, govde in sahte_ollama.istekler if yol in ("/api/chat", "/api/embed")]
    assert [g["keep_alive"] for g in govdeler] == ["40m", "40m"]


def test_bellekte_tutma_suresi_bossa_gonderilmez(sahte_ollama):
    Ollama(sahte_ollama.adres).gom("bge-m3", ["metin"])
    assert all("keep_alive" not in govde for _, govde in sahte_ollama.istekler)
