# Análisis térmico · Batch 26310

Período: 2026-11-03T20:56:52 → 2026-11-08T09:08:49 (hora local del histórico).

Cobertura conjunta PV/SP: 0.25 % del intervalo.

## Conclusiones térmicas

Con una banda de ±0.8 °C, la temperatura estuvo fuera de rango durante 0.14 % del tiempo total del batch (sobre la banda 0.08 %, bajo ella 0.05 %). En los tramos evaluables, estuvo fuera de rango 53.08 % (sobre 32.80 %, bajo 20.28 %). La cobertura conjunta PV/SP fue 0.25 % del batch. Los porcentajes sobre el batch corresponden solo a tiempo observado y pueden subestimar el total real.

## Recorrido de cortinas

Aire fresco: 8.15 m (cobertura temporal 1.22 %). Retorno: 8.67 m (cobertura temporal 1.55 %). Diferencia absoluta entre los recorridos observados: 0.52 m. Son distancias mínimas observadas. Los intervalos sin datos suficientes y los cambios entre muestras no se contabilizan; las coberturas pueden diferir.

## Pronóstico térmico a cinco minutos

Modelo Regresión Ridge. En 1211 ventanas evaluadas, el error absoluto medio fue 0.232 °C frente a 0.222 °C al mantener la última lectura. Se observaron 31 ventanas inusuales que requieren revisión.

## Métricas calculadas

```json
{
  "total_hours": 108.19916666666667,
  "evaluable_hours": 0.2752777777777778,
  "pv_coverage_pct": 59.637705157926355,
  "joint_coverage_pct": 0.2544176505775101,
  "off_hours": 0.0,
  "unknown_hours": 107.92388888888888,
  "within_pct": 46.92230070635721,
  "above_hours": 0.09027777777777778,
  "below_hours": 0.05583333333333333,
  "above_pct_evaluable": 32.79515640766902,
  "below_pct_evaluable": 20.282542885973765,
  "outside_pct_evaluable": 53.07769929364279,
  "above_pct_batch": 0.08343666643561128,
  "below_pct_batch": 0.051602369087870366,
  "outside_pct_batch": 0.13503903552348165,
  "mae": 1.3942893982349083,
  "hot_minutes": 0.9166666666666666,
  "curtain_hours": 0.05722222222222222,
  "curtain_bad_minutes": 0.0,
  "fresco_travel_m": 8.15,
  "fresco_travel_coverage_pct": 1.2225397094350183,
  "fresco_travel_gaps": 194,
  "retorno_travel_m": 8.67,
  "retorno_travel_coverage_pct": 1.5516652674979525,
  "retorno_travel_gaps": 219,
  "curtain_travel_difference_m": 0.5199999999999996,
  "thermal_events": 0
}
```

## Reglas y método

PV y feedback: interpolación lineal solo entre muestras separadas como máximo por max_gap. SP: retención acotada a max_gap. Huecos no se contabilizan. Duraciones estimadas; no son mediciones continuas.

```json
{
  "tolerance": 0.8,
  "event_minutes": 20.0,
  "critical_temperature": 22.0,
  "expected_seconds": 30.0,
  "gap_factor": 3.0,
  "curtain_tolerance": 5.0
}
```

## Limitaciones de cobertura

- Cobertura conjunta PV/SP inferior al 90 %: los resultados describen solo los tramos evaluables, no el lote completo. El 90 % es una referencia informativa del proyecto.
- Cadencia y tolerancia de huecos son parámetros provisionales; confirmar el intervalo real del histórico.

## Interpretación mediante OpenAI

Modelo: gpt-4.1-mini-2025-04-14 · 2026-11-16T17:46:56.218757-03:00

Respuesta: resp_052ff868a273a559016afb6bb994c087d2ac8c99b6cd4c96c6 · Tokens de entrada: 2202 · Tokens de salida: 657 · Latencia: 8.67 s

El lote presenta cobertura de datos limitada tanto en la cobertura conjunta de PV y SP, como en la cobertura de tramos evaluables, lo que restringe el análisis al segmento disponible. Se observaron breves eventos de temperatura por encima del umbral absoluto, con ausencia de eventos térmicos prolongados. El recorrido de las cortinas muestra una distancia mínima observada pequeña con cobertura baja por debajo del cinco por ciento, limitando las conclusiones sobre la uniformidad de flujo.

### Hallazgos

- **Cobertura de datos limitada**: La cobertura conjunta PV/SP es inferior al noventa por ciento y la cobertura evaluable es baja, concentrándose el análisis en un pequeño tramo evaluable. Límite: Los resultados describen solo los tramos evaluables, no el lote completo.
- **Eventos térmicos breves por encima del umbral absoluto**: Se registraron varios eventos de sobre tolerancia, con uno que supera la temperatura crítica de forma momentánea. Límite: Los eventos son breves y no persistentes, no se observa thermal_events prolongado.
- **Balance térmico con periodo considerable dentro y fuera de tolerancia**: En los tramos evaluables, la temperatura estuvo dentro del rango tolerado cerca de la mitad del tiempo, con momentos relevantes por encima y por debajo. Límite: No hay continuidad del control térmico en el lote completo debido a cobertura limitada.
- **Recorrido de cortinas con baja cobertura y pequeña diferencia**: La distancia mínima observada entre recorrido de fresco y retorno es pequeña, y la cobertura del recorrido está por debajo del dos por ciento en ambos casos. Límite: La baja cobertura limita la interpretación del recorrido del flujo.

### Hipótesis

- La baja cobertura podría deberse a falta de registros completos o interrupciones en el monitoreo.
- Los eventos térmicos breves podrían responder a ajustes manuales o condiciones puntuales del sistema.
- La pequeña diferencia en recorrido de cortinas indicaría poca variabilidad espacial observable en las zonas muestreadas.
- La dispersión térmica observada sugiere que las etapas de control térmico podrían no ser uniformes en el lote debido a intervalos sin datos.

### Verificaciones

- Confirmar la integridad y continuidad de los datos de sensores PV y SP para mejorar cobertura.
- Corroborar que los eventos breves no comprometan la calidad o proceso general de germinación.
- Validar parámetros provisionales de cadencia y tolerancia de huecos definidos en reglas.
- Comprobar la precisión y ubicación de sensores para recorrido de cortinas y su cobertura.
- Verificar la metodología de cálculo de métricas y extremos para asegurar consistencia.

### Limitaciones

- Cobertura conjunta PV/SP inferior al noventa por ciento limita análisis al tramo observado.
- Alta proporción de tiempo con datos desconocidos impide extrapolaciones a todo el lote.
- Duraciones estimadas no equivalen a mediciones continuas y pueden introducir incertidumbre.
- Baja cobertura del recorrido de cortinas reduce la confiabilidad en conclusiones sobre flujo.
- Faltan anotaciones de usuario que complementen con contexto operacional y eventos externos.

## Anotaciones del usuario

[]

## Trazabilidad

Huella de datos: f86e093f8ea723dc671aa2e5ae9aeedcaab25ce5e40ebbfae12aa3f9ac102301
