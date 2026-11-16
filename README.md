# Asistente de análisis térmico de germinación

Aplicación interactiva en Streamlit para revisar el control térmico del grano durante la germinación en la nave N5. Organiza los datos históricos por lote, desde una carga hasta la siguiente.

- Compara la temperatura medida con la consigna y muestra la posición de las cortinas de aire fresco y retorno.
- Calcula el tiempo fuera de la banda térmica, identifica las desviaciones y muestra qué parte del lote se pudo evaluar.
- Estima el recorrido acumulado de ambas cortinas y su diferencia a partir de los registros disponibles.
- Permite anotar volteos y otros eventos operativos, y descargar los resultados del lote.
- A solicitud del usuario, OpenAI interpreta los indicadores y genera un informe con hallazgos y verificaciones sugeridas.

## Ejecutar desde una copia nueva en Windows

Clona el repositorio o descarga y extrae su ZIP. Instala Python 3.12 y abre en VS Code la carpeta que contiene `app.py`. Ejecuta estos comandos en la terminal PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abre la dirección que indique la terminal. Selecciona el batch `26310` para revisar las tendencias, los tiempos fuera de rango y el recorrido de las cortinas.

Para probar la integración, abre **Análisis con IA → Configuración de OpenAI**, ingresa tu propia clave en el campo protegido y pulsa **Generar informe con OpenAI**. Usa **Descargar informe** para guardar el resultado en Markdown. Puedes recorrer el resumen y los eventos antes de ingresar la clave.

## Configurar OpenAI de forma persistente (opcional)

Copia `.env.example` como `.env` y completa `OPENAI_API_KEY` localmente. El modelo inicial es `gpt-4.1-mini` y se puede cambiar en la interfaz. Nunca incluyas `.env`, claves o `secrets.toml` en una entrega o repositorio. La clave tiene prioridad desde el campo de sesión y, si está vacío, desde el entorno o `.env`.

La conexión usa la API Responses, salida estructurada con Pydantic y `store=False`. Enviamos reglas, métricas, cobertura, hasta 20 eventos de mayor duración/persistencia y hasta 50 anotaciones. No enviamos los archivos completos. La solicitud utiliza la cuenta de API del usuario. No se realizan llamadas al cargar el programa ni al cambiar de lote; el usuario debe pulsar el botón de análisis. Un error de conexión o credencial se muestra como error, nunca como un informe ficticio.

Documentación oficial consultada: [Responses y salidas estructuradas](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [modelo configurable inicial](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

## Datos incluidos y carga de nuevas exportaciones

`data/historicos` contiene una copia de 291 archivos `.dat` desde septiembre de 2026. Los originales no se modifican. Cada archivo contiene una cabecera y filas de fecha/hora y valor separadas por tabulador. Se admite coma decimal y UTF-8 o Windows-1252. Los `.bin` no se utilizan.

Desde **Origen de los datos** puedes usar los históricos incluidos, una carpeta local o un ZIP con los `.dat`. No se extraen rutas del ZIP al disco. Se limita el contenido a 100 MB y 10.000 archivos. Se reconocen estos sufijos de nombre:

| Variable | Señal |
|---|---|
| PV, temperatura real del grano | `PROM_SOBRE_N5,31` |
| SP, consigna | `00TT2004,29` |
| Feedback de retorno | `POS_ACTUAL_RET_N5,22` |
| Feedback de fresco | `POS_ACTUAL_FRES_N5,25` |
| Identificador de lote | `NUM_BATCH_NAVE_5,10` |

El identificador del lote se mantiene de carga a carga. Los batch vacíos generan períodos sin asignación confiable; los cambios breves no se corrigen automáticamente. Un mismo identificador que reaparece después de un vacío se trata como un episodio separado. No se deduce un fin de germinación a partir del cambio de batch.

## Reglas acordadas

- Dentro de tolerancia: error PV − SP entre −0,8 y +0,8 °C, incluidos los extremos.
- Evento persistente: excursión continua **estrictamente mayor que 20 minutos**. Exactamente 20 minutos no es persistente.
- Exceso de temperatura recibe mayor prioridad que defecto. PV >22 °C genera atención inmediata; su persistencia también se evalúa a los 20 minutos. El umbral absoluto se evalúa independientemente de la tolerancia relativa cuando se conoce operación.
- SP = 0 significa sistema apagado y se excluye del desempeño.
- Volteos: anotaciones manuales, sin atribución causal automática ni exclusión de métricas. Los cambios de SP se ven en la tendencia; no existe un período de recuperación acordado, por lo que no se excluyen transitorios automáticamente.
- Complementariedad esperada: fresco + retorno = 100 %. Tolerancia inicial de **5 puntos porcentuales**, provisional y configurable.

## Huecos, cadencia y límites importantes

El usuario confirmó registro a intervalos fijos; todavía no se conoce el intervalo exacto. Se propone inicialmente **30 segundos**, con separación máxima **90 segundos** (3 intervalos), ambos configurables. Son parámetros provisionales visibles, no hechos confirmados del proceso.

PV y feedback se interpolan linealmente solo entre dos muestras cuya separación no supera el máximo. SP se mantiene desde cada muestra por un tiempo máximo igual a ese límite, o hasta la siguiente muestra si llega antes. No se extiende una señal indefinidamente ni se atraviesan huecos para cálculos. Las duraciones resultantes son estimaciones locales; se calculan los cruces de umbral y el error absoluto por integración ponderada por tiempo.

Los eventos se interrumpen en huecos, apagados y períodos fuera de la condición. El tiempo desconocido nunca se cuenta como buen control. La cobertura térmica conjunta y la cobertura PV son distintas. La cobertura de cortinas exige ambos feedback y una SP reciente que confirme operación. La advertencia de cobertura inferior al 90 % es una referencia informativa del proyecto, no un estándar industrial.

Los gráficos muestran líneas finas sin marcadores y suavizado visual. La consigna se representa por escalones para no inventar rampas. Puedes unir visualmente registros distantes, pero esa opción nunca modifica los cálculos. Al desactivarla se hacen visibles los cortes. No se prolonga una curva antes del primer registro ni después del último.

**Resultado relevante con los históricos entregados:** hay PV para los batches 26304, 26310 y 26316, con 5.786, 7.029 y 2.052 registros respectivamente. En 26310 los extremos de PV casi coinciden con la carga y la siguiente carga, pero existen huecos internos. Con 30 s / 90 s, solo hay aproximadamente **0,254 % de cobertura conjunta PV/SP**, equivalente a **16,52 minutos de 108,20 horas**. Los indicadores calculados describen esos tramos; no permiten concluir el desempeño del lote completo. Se necesita una exportación más continua de SP y confirmar cadencia para un análisis representativo. No se amplía el límite de huecos para forzar cobertura.

## Pantallas y descargas

- **Resumen:** extremos reales, tendencias, cobertura e indicadores del tiempo evaluable; botón de interpretación con IA.
- **Eventos:** excursiones breves y persistentes, selección de intervalo, CSV y anotaciones.
- **Modelo térmico:** pronóstico a cinco minutos, comparación con la última lectura, ventanas inusuales y CSV de predicciones.
- **Análisis con IA:** vista previa de evidencia, clave protegida, modelo configurable e informe real. El informe se conserva solo durante la sesión y queda ligado a los datos, reglas y anotaciones con que fue generado.
- **Datos y validación:** intervalos observados, problemas de importación, catálogo de batches y registros originales.
- Descargas: informe Markdown y evidencia JSON con reglas, cobertura y huella SHA-256. Los archivos no contienen claves. Las anotaciones se guardan en `local/anotaciones` y se incluyen al exportar; los informes de IA no se guardan automáticamente al disco.

## Verificación

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe -m pytest -q
```

Las pruebas verifican umbrales, duración estricta, integración por tiempo, huecos, apagados, feedback, lectura de archivos, lotes reales, navegación y contrato de la API con un cliente simulado. Una prueba simulada no verifica saldo, permisos ni una respuesta real de OpenAI. La llamada real queda pendiente hasta configurar la clave del usuario.

Estructura: `app.py` (interfaz), `termico/data.py` (importación), `termico/analysis.py` (cálculos), `termico/charts.py` (gráficos), `termico/ai.py` (OpenAI e informes), `termico/notes.py` (anotaciones), `tests` (verificación).

## Modelo predictivo y validación

El modelo aprende a pronosticar la temperatura del grano a cinco minutos mediante regresión Ridge. Usa la temperatura disponible al emitir el pronóstico y sus cambios en el último minuto y los últimos cinco. Cada ventana usa lecturas anteriores o iguales a su hora de referencia y se descarta si cruza un hueco largo. La consigna queda disponible para el análisis determinista de tolerancia.

El modelo se entrena con el primer 75 % de las ventanas de lotes cerrados anteriores. El tramo restante calibra el percentil 99 del error absoluto con separación temporal entre ambos tramos. El lote seleccionado se reserva para evaluación. El batch 26310 produjo 1.211 ventanas evaluables. El error absoluto medio fue 0,232 °C con el modelo y 0,222 °C con la última lectura como predicción. Se detectaron 31 ventanas con error superior al umbral calibrado. Son candidatos para revisión del histórico. La sensibilidad se comprueba inyectando +2 °C en la lectura objetivo de las ventanas que el modelo no había señalado. Sin etiquetas de fallas reales, esa prueba solo mide respuesta a la perturbación artificial.

Ejecuta `./.venv/Scripts/python.exe verificar.py` para reproducir las pruebas y los resultados guardados en `evidencia/verificacion.json`.

## Medición de la optimización mediante OpenAI

La aplicación envía un resumen con métricas, eventos y resultados del modelo. Los números del informe salen de los cálculos de la aplicación. OpenAI interpreta los hallazgos en términos cualitativos. El flujo de comparación usa el batch 26310 y solicita dos informes al mismo modelo con las mismas instrucciones. La referencia añade todas las muestras de las señales al mismo resumen. La variante optimizada envía solo el resumen. La evidencia consigna los tokens reportados por la API y la latencia de cada solicitud.

Con una clave válida en `.env` o en el entorno, ejecuta:

```powershell
./.venv/Scripts/python.exe medir_openai.py --comparar
```

El comando realiza dos llamadas a OpenAI con tu cuenta. Guarda `comparacion_openai_26310.json` e `informe_openai_26310.md` en `evidencia/`. Cada latencia es una observación puntual.

La comparación inicial registró 156.614 tokens de entrada con las muestras y 2.163 con el resumen, una reducción del 98,62 %. Los tiempos fueron 19,38 s y 14,46 s, respectivamente. Al revisar el contenido se encontraron errores al interpretar los denominadores. Por eso, la aplicación ahora escribe las cifras desde sus propios cálculos. El informe guardado corresponde a una nueva solicitud real con ese formato.
