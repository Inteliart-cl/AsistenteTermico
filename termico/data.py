from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, BadZipFile
import hashlib
import math
import pandas as pd

TAGS = {
    "PV": "PROM_SOBRE_N5,31", "SP": "00TT2004,29",
    "Retorno": "POS_ACTUAL_RET_N5,22", "Fresco": "POS_ACTUAL_FRES_N5,25",
    "Batch": "NUM_BATCH_NAVE_5,10",
}
MAX_BYTES = 100 * 1024 * 1024

@dataclass
class Dataset:
    signals: dict[str, pd.DataFrame]
    issues: pd.DataFrame
    fingerprint: str
    files: int

def manifest(root: str) -> tuple:
    path = Path(root)
    if not path.is_dir():
        raise ValueError("La carpeta de históricos no existe o no está disponible.")
    return tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns)
                 for p in sorted(path.rglob("*.dat")))

def load_folder(files: tuple) -> Dataset:
    total = sum(size for _, size, _ in files)
    if total > MAX_BYTES:
        raise ValueError("Los archivos .dat exceden el límite de 100 MB.")
    return parse_files([(name, Path(name).read_bytes()) for name, _, _ in files])

def load_zip(blob: bytes) -> Dataset:
    if len(blob) > MAX_BYTES:
        raise ValueError("El ZIP excede 100 MB.")
    try:
        with ZipFile(BytesIO(blob)) as archive:
            members = [p for p in archive.infolist() if p.filename.lower().endswith('.dat')]
            if len(members) > 10000 or sum(p.file_size for p in members) > MAX_BYTES:
                raise ValueError("El contenido descomprimido excede los límites permitidos.")
            # Read in memory: never extract paths from an uploaded archive.
            return parse_files([(p.filename, archive.read(p)) for p in members])
    except BadZipFile as exc:
        raise ValueError("El archivo no es un ZIP válido.") from exc

def parse_files(files: list[tuple[str, bytes]]) -> Dataset:
    rows: dict[str, list[tuple[pd.Timestamp, str | float]]] = {key: [] for key in TAGS}
    issues = []
    digest = hashlib.sha256()
    accepted = 0
    for name, blob in sorted(files):
        role = next((key for key, tag in TAGS.items() if name.endswith(f" {tag}.dat")), None)
        if role is None:
            continue
        accepted += 1
        digest.update(name.replace('\\', '/').split('/')[-1].encode())
        digest.update(blob)
        try:
            content = blob.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = blob.decode('cp1252')
        for line_no, line in enumerate(content.splitlines()[1:], 2):
            if not line.strip():
                continue
            try:
                ts, raw = line.split('\t')
                timestamp = pd.to_datetime(ts.strip(), format='%d-%m-%Y %H:%M:%S')
                raw = raw.strip()
                value: str | float
                if role == 'Batch':
                    value=raw
                else:
                    numeric=float(raw.replace(',', '.'))
                    if not math.isfinite(numeric):
                        raise ValueError('Valor no finito')
                    if role in ('Fresco', 'Retorno') and not 0 <= numeric <= 100:
                        raise ValueError('Posición fuera de 0–100 %')
                    value=numeric
                if role == 'Batch' and raw and not raw.isdigit():
                    raise ValueError('Identificador de batch inválido')
                if role == 'Batch' and not raw:
                    issues.append((name, line_no, 'Batch vacío: intervalo sin asignación confiable'))
                rows[role].append((timestamp, value))
            except (ValueError, TypeError, OverflowError) as exc:
                issues.append((name, line_no, f'Registro no utilizado: {exc}'))
    signals = {}
    for role, records in rows.items():
        frame = pd.DataFrame(records, columns=['time', 'value'])
        if frame.empty:
            frame['time'] = pd.to_datetime(frame['time'])
        else:
            frame = frame.sort_values('time', kind='stable')
            conflicts = frame.groupby('time')['value'].nunique()
            ambiguous = conflicts[conflicts > 1].index
            if len(ambiguous):
                issues.append((role, 0, f'{len(ambiguous)} instantes con valores contradictorios: excluidos'))
                frame = frame[~frame.time.isin(ambiguous)]
            frame = frame.drop_duplicates('time').reset_index(drop=True)
        signals[role] = frame
    missing = [r for r in ('PV', 'SP', 'Batch') if signals[r].empty]
    if missing:
        raise ValueError('Faltan registros válidos de: ' + ', '.join(missing))
    return Dataset(signals, pd.DataFrame(issues, columns=['archivo', 'línea', 'observación']),
                   digest.hexdigest(), accepted)

def batch_catalog(data: Dataset) -> pd.DataFrame:
    frame = data.signals['Batch']
    changes = frame.loc[frame.value.ne(frame.value.shift())].reset_index(drop=True)
    pv = data.signals['PV']
    rows = []
    for i, change in changes.iterrows():
        if not change.value:
            continue
        end = changes.iloc[i+1].time if i+1 < len(changes) else pv.time.max()
        values = pv[(pv.time >= change.time) & (pv.time < end if i+1 < len(changes) else pv.time <= end)]
        if values.empty or end <= change.time:
            continue
        closed = i+1 < len(changes) and bool(changes.iloc[i+1].value)
        rows.append(dict(key=f'{change.value}_{change.time.isoformat()}', batch=change.value,
                         start=change.time, end=end, closed=closed, count=len(values),
                         first=values.time.min(), last=values.time.max()))
    if not rows:
        raise ValueError('No hay batches con registros de PV asignables.')
    return pd.DataFrame(rows)
