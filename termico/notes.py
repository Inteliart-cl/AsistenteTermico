from pathlib import Path
import hashlib
import json
import os

def note_path(root: Path, batch_key: str) -> Path:
    return root/(hashlib.sha256(batch_key.encode()).hexdigest()[:24]+'.json')

def load_notes(root: Path, batch_key: str) -> list:
    path=note_path(root,batch_key)
    if not path.exists(): return []
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,list): raise ValueError('Se esperaba una lista')
        return value
    except (ValueError,OSError) as exc:
        raise ValueError('No se pudo leer el archivo de anotaciones; consérvalo para revisarlo.') from exc

def save_notes(root: Path, batch_key: str, notes: list):
    root.mkdir(parents=True,exist_ok=True)
    path=note_path(root,batch_key)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)
