from datetime import timedelta

import numpy as np
import pandas as pd

from termico.ml import evaluate, windows


def test_predictor_uses_readings_available_at_prediction_time():
    start = pd.Timestamp('2026-11-01')
    times = pd.date_range(start + timedelta(seconds=30), periods=13, freq='min')
    pv = pd.DataFrame({'time': times, 'value': np.arange(len(times), dtype=float)})
    result = windows(pv, start, start + timedelta(hours=1), 90)
    first = result.iloc[0]
    assert first.hora == start + timedelta(minutes=6)
    assert first.pv_actual == 5
    assert first.pv_futura == 10
    gapped = pv.drop(index=range(4, 8))
    assert windows(gapped, start, start + timedelta(hours=1), 90).empty


def test_holdout_batch_does_not_train_or_calibrate_its_own_model():
    start = pd.Timestamp('2026-11-01')
    hours = timedelta(hours=8)
    end = start + hours
    test_end = end + hours
    timestamps = pd.date_range(start, test_end, freq='min', inclusive='left')
    pv = pd.DataFrame({'time': timestamps, 'value': 19 + np.sin(np.arange(len(timestamps)) / 20)})
    catalog = pd.DataFrame([{'batch': 'A', 'start': start, 'end': end, 'closed': True},
                            {'batch': 'B', 'start': end, 'end': test_end, 'closed': True}])
    original, _ = evaluate(pv, end, test_end, catalog, 90)
    pv.loc[pv.time >= end, 'value'] += 6
    changed, _ = evaluate(pv, end, test_end, catalog, 90)
    assert original['lotes_referencia'] == ['A']
    assert changed['umbral_residuo_c'] == original['umbral_residuo_c']
    assert changed['ventanas_entrenamiento'] == original['ventanas_entrenamiento']
    assert evaluate(pv, start, end, catalog, 90)[0] is None
