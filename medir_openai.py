"""Compara dos solicitudes reales equivalentes y guarda la evidencia de la API."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from termico.ai import generate_report, report_markdown
from termico.analysis import Rules, analyze, payload
from termico.data import batch_catalog, load_folder, manifest
from termico.ml import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparar', action='store_true', required=True,
                        help='Autoriza dos generaciones del mismo batch con tu cuenta de OpenAI.')
    parser.parse_args()
    root = Path(__file__).resolve().parent
    env_from = os.getenv('ASISTENTE_OPENAI_ENV')
    load_dotenv(env_from or root / '.env', override=False)
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        parser.error('Configura OPENAI_API_KEY en el entorno o en .env.')
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    data = load_folder(manifest(str(root / 'data' / 'historicos')))
    catalog = batch_catalog(data)
    batch = catalog.loc[catalog.batch == '26310'].iloc[0]
    rules = Rules()
    result = analyze(data, batch, rules)
    summary = payload(result, [])
    summary['machine_learning'], _ = evaluate(data.signals['PV'], batch.start, batch.end, catalog, rules.max_gap)
    raw = {name: json.loads(frame.to_json(orient='split', index=False, date_format='iso'))['data']
           for name, frame in result['raw'].items()}
    baseline = summary | {'muestras_crudas': {'columnas': ['hora', 'valor'], 'series': raw}}

    # Ambas variantes incluyen exactamente la misma evidencia calculada.
    # La variante de referencia adjunta además todas las muestras del batch.
    target = root / 'evidencia'
    target.mkdir(exist_ok=True)
    optimized = generate_report(summary, key, model)
    (target / 'informe_openai_26310.md').write_text(report_markdown(summary, optimized), encoding='utf-8')
    full = generate_report(baseline, key, model, metrics_only=True)
    if not optimized['uso'] or not full['uso']:
        raise RuntimeError('La API no devolvió métricas de uso en ambas respuestas.')
    if optimized['modelo'] != full['modelo']:
        raise RuntimeError('La API devolvió modelos distintos. Repite la comparación con un modelo fijo.')
    base_tokens = full['uso']['input_tokens']
    optimized_tokens = optimized['uso']['input_tokens']
    comparison = {
        'batch': summary['batch'],
        'metodo': 'Una respuesta por variante en el mismo modelo. La referencia adjunta las muestras a la evidencia.',
        'modelo_solicitado': model,
        'linea_base': {field: value for field, value in full.items() if field != 'contenido'},
        'optimizado': {field: value for field, value in optimized.items() if field != 'contenido'},
        'reduccion_tokens_entrada_pct': 100 * (1 - optimized_tokens / base_tokens),
        'nota_latencia': 'Los tiempos corresponden a una ejecución por variante y pueden variar al repetirla.',
    }
    (target / 'comparacion_openai_26310.json').write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8'
    )
    print(f'Tokens de entrada: {base_tokens:,} → {optimized_tokens:,}.')
    print(f"Latencia: {full['latencia_s']:.2f} s → {optimized['latencia_s']:.2f} s.")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
