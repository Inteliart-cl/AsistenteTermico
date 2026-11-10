import pytest

@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    def blocked(*args,**kwargs):
        raise ValueError('Las llamadas reales a OpenAI están deshabilitadas durante las pruebas.')
    monkeypatch.setattr('termico.ai.OpenAI',blocked)
