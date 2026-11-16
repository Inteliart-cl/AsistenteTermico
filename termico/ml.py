"""Predicción térmica con regresión Ridge y validación cronológica por lote."""

from datetime import timedelta

import numpy as np
import pandas as pd

HORIZON_MIN = 5
MIN_WINDOWS = 30
FEATURES = ['pv_actual', 'cambio_1min', 'cambio_5min']


def windows(pv, start, end, max_gap):
    """Forma ventanas de diez minutos a partir de segmentos sin huecos largos."""
    samples = pv.loc[pv.time.between(start, end, inclusive='left')].sort_values('time')
    blocks = samples.time.diff().dt.total_seconds().gt(max_gap).cumsum()
    frames = []
    for _, block in samples.groupby(blocks):
        first = block.time.iloc[0].ceil('min')
        last = block.time.iloc[-1].floor('min')
        if last - first < timedelta(minutes=2 * HORIZON_MIN):
            continue
        grid = pd.date_range(first, last, freq='min')
        # Cada entrada del pronóstico solo conoce muestras disponibles a esa hora.
        frame = pd.merge_asof(
            pd.DataFrame({'hora': grid}), block.rename(columns={'time': 'hora', 'value': 'pv_actual'}),
            on='hora', direction='backward', tolerance=pd.Timedelta(timedelta(seconds=max_gap)),
        )
        frame['cambio_1min'] = frame.pv_actual.diff()
        frame['cambio_5min'] = frame.pv_actual.diff(HORIZON_MIN)
        frame['pv_futura'] = frame.pv_actual.shift(-HORIZON_MIN)
        frames.append(frame.dropna())
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=['hora', *FEATURES, 'pv_futura']
    )


def evaluate(pv, start, end, earlier_batches, max_gap):
    """Entrena con lotes previos y evalúa contra el lote que se inspecciona."""
    test = windows(pv, start, end, max_gap)
    historical = [(row.batch, windows(pv, row.start, row.end, max_gap))
                  for row in earlier_batches.itertuples() if row.closed and row.end <= start]
    historical = [(batch, frame) for batch, frame in historical if not frame.empty]
    if not historical or test.empty:
        return None, test

    reference = pd.concat([frame for _, frame in historical], ignore_index=True).sort_values('hora')
    split = reference.hora.iloc[int(len(reference) * 0.75)]
    margin = timedelta(minutes=HORIZON_MIN)
    train = reference[reference.hora + margin < split]
    calibration = reference[reference.hora - margin >= split]
    if min(len(train), len(calibration), len(test)) < MIN_WINDOWS:
        return None, test

    x = train[FEATURES].to_numpy()
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1
    x = (x - center) / scale
    change = (train.pv_futura - train.pv_actual).to_numpy()
    intercept = change.mean()
    coefficients = np.linalg.solve(x.T @ x + np.eye(len(FEATURES)), x.T @ (change - intercept))

    def predict(frame):
        normalized = (frame[FEATURES].to_numpy() - center) / scale
        return frame.pv_actual.to_numpy() + intercept + normalized @ coefficients

    calibration_errors = (calibration.pv_futura - predict(calibration)).abs()
    threshold = float(calibration_errors.quantile(0.99))
    test['pronóstico'] = predict(test)
    test['error_abs'] = (test.pv_futura - test['pronóstico']).abs()
    test['inusual'] = test.error_abs > threshold
    test['hora_objetivo'] = test.hora + margin
    # Inyectar una excursión sobre ventanas no señaladas prueba sensibilidad con
    # un cambio conocido. Las ventanas industriales carecen de etiquetas.
    normal = test.loc[~test.inusual]
    artificial_hits = ((normal.pv_futura + 2 - normal['pronóstico']).abs() > threshold).sum()
    top = test.loc[test.inusual].nlargest(5, 'error_abs')
    findings = [
        {'hora_objetivo': row['hora_objetivo'].isoformat(), 'pv': round(float(row['pv_futura']), 3),
         'pronostico': round(float(row['pronóstico']), 3), 'error_abs_c': round(float(row['error_abs']), 3)}
        for row in top.to_dict('records')
    ]
    return {
        'modelo': 'Regresión Ridge', 'horizonte_min': HORIZON_MIN,
        'lotes_referencia': [batch for batch, _ in historical],
        'ventanas_entrenamiento': len(train), 'ventanas_calibracion': len(calibration),
        'ventanas_evaluadas': len(test),
        'umbral_residuo_c': threshold,
        'mae_modelo_c': float(test.error_abs.mean()),
        'mae_persistencia_c': float((test.pv_futura - test.pv_actual).abs().mean()),
        'ventanas_inusuales': int(test.inusual.sum()),
        'prueba_artificial': {'aumento_c': 2, 'detectadas': int(artificial_hits), 'evaluadas': len(normal)},
        'ejemplos': findings,
    }, test
