from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_navigation_and_api_key_gate(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: False)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=40).run()
    assert not app.exception
    assert '26310' in app.selectbox(key='batch_key').value
    for page in ['Eventos','Datos y validación','Análisis con IA','Resumen']:
        app.radio(key='page').set_value(page).run()
        assert not app.exception
    app.button(key='analyze_batch').click().run()
    assert not app.exception
    assert app.radio(key='page').value=='Análisis con IA'
    if not app.text_input(key='api_key_input').value:
        assert app.button(key='generate_report').disabled
    app.radio(key='page').set_value('Resumen').run()
    app.selectbox(key='batch_key').select_index(0).run()
    assert not app.exception

def test_annotation_invalid_interval_is_rejected():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=40).run()
    app.radio(key='page').set_value('Eventos').run()
    batch_key = app.selectbox(key='batch_key').value
    begin = app.datetime_input(key=f'note_start_{batch_key}').value
    app.datetime_input(key=f'note_end_{batch_key}').set_value(begin)
    app.button(key='save_note').click().run()
    assert not app.exception
    assert any('intervalo válido' in e.value for e in app.error)


def test_annotation_saves_dates_selected_in_form(monkeypatch):
    from datetime import timedelta

    saved = []
    monkeypatch.setattr('termico.notes.load_notes', lambda *args: [])
    monkeypatch.setattr('termico.notes.save_notes', lambda path, key, notes: saved.extend(notes))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=40).run()
    app.radio(key='page').set_value('Eventos').run()
    batch_key = app.selectbox(key='batch_key').value
    begin = app.datetime_input(key=f'note_start_{batch_key}').value + timedelta(minutes=7)
    finish = begin + timedelta(minutes=13)
    app.datetime_input(key=f'note_start_{batch_key}').set_value(begin)
    app.datetime_input(key=f'note_end_{batch_key}').set_value(finish)
    app.button(key='save_note').click().run()
    assert not app.exception
    assert not app.error
    assert [(note['inicio'], note['fin']) for note in saved] == [(begin.isoformat(), finish.isoformat())]
