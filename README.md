# Modelo_ML_waymo

[![Powered by Kedro](https://img.shields.io/badge/powered_by-kedro-ffc900?logo=kedro)](https://kedro.org)

## 🚀 Guía de Inicio Rápido (Git Bash)

Sigue estos pasos desde la terminal de **Git Bash** para levantar y ejecutar el proyecto en cualquier computadora desde cero:

### 1. Clonar el repositorio y entrar al proyecto
git clone <https://github.com/donMixho/Modelo_ML_waymo.git>
cd Modelo_ML_waymo

### 2. Crear y activar el entorno virtual
python -m venv .venv
source .venv/Scripts/activate

*(Nota: Al activarse correctamente verás (.venv) al inicio de tu línea de comandos).*

### 3. Instalar dependencias
pip install -r requirements.txt

### 4. Ejecutar los pipelines de Kedro
Para ejecutar todos los pipelines del proyecto a la vez:
kedro run

O si prefieres ejecutar un pipeline individual:
kedro run --pipeline=data_inventory
kedro run --pipeline=eda

---

## Overview

Proyecto Kedro (`kedro 1.3.1`) para el análisis exploratorio y la verificación de señal
predictiva sobre un dataset sintético de detecciones estilo Waymo:
[data/01_raw/detecciones_waymo_like.csv](data/01_raw/detecciones_waymo_like.csv).

**Importante:** este CSV no es el Waymo Open Dataset real. Es una tabla plana de
detecciones (153 segmentos, ~40,680 filas) con cajas delimitadoras 3D, sin imágenes,
cámaras ni tfrecords. Todo el trabajo hecho hasta ahora es de **diagnóstico**: inventario,
perfilado, auditoría de calidad y verificación de señal. No se ha limpiado, imputado ni
transformado ningún dato de forma persistente.

## Pipelines

### `data_inventory`

Inventario de solo lectura de `data/01_raw`, sin asumir ningún formato previo.

| Nodo | Qué hace |
| --- | --- |
| `scan_raw_files` | Recorre `data/01_raw` y genera un índice de archivos (ruta, formato, tamaño). |
| `profile_sample` | Abre una muestra pequeña y detecta el esquema disponible (columnas, tipos de anotación, metadata). |
| `build_inventory_report` | Consolida ambos en una tabla resumen y un reporte Markdown. |

Salidas: `data/02_intermediate/data_inventory_*.parquet` y
[data/08_reporting/data_inventory_report.md](data/08_reporting/data_inventory_report.md).

### `eda`

Análisis exploratorio completo + verificación de señal predictiva.

| Nodo | Qué hace |
| --- | --- |
| `load_and_profile` | Perfil por columna: dtype, nulos, cardinalidad, estadísticos o top-10 de valores. |
| `audit_categorical_consistency` | Lista los valores crudos de las columnas categóricas y **propone** (sin aplicar) una normalización canónica. |
| `audit_data_quality` | Duplicados, valores físicamente imposibles, sentinels no numéricos, outliers (IQR/z-score), co-ocurrencia de nulos y consistencia temporal por segmento. |
| `target_candidates_analysis` | Balance de clases, tablas cruzadas y asociación (Cramér's V) de `detection_difficulty` y `object_type` contra weather/time_of_day/object_type. |
| `generate_plots` | Histogramas, boxplots, barplots, matriz de correlación y heatmap de nulos (PNG). |
| `build_eda_report` | Consolida todo en un reporte Markdown en español. |
| `signal_check` | Para cada candidato a target: normalización en memoria, información mutua (con ruido de referencia), test de separabilidad (Kruskal-Wallis) y un baseline honesto (dummy vs. árbol de decisión) con split estratificado y deduplicado. Veredicto: SEÑAL / SEÑAL DÉBIL / SIN SEÑAL. |

Salidas: `data/02_intermediate/eda_*.parquet` y `data/02_intermediate/signal_*.parquet`,
figuras en `data/08_reporting/figures/`, y dos reportes:
[data/08_reporting/eda_report.md](data/08_reporting/eda_report.md) y
[data/08_reporting/signal_check_report.md](data/08_reporting/signal_check_report.md).

Todos los nodos son de solo lectura sobre `data/01_raw`: ninguno imputa, elimina filas ni
normaliza datos de forma persistente. Las normalizaciones y coerciones numéricas que se ven
en el código (p. ej. `object_type` en `signal_check`, o el sentinel `"N/D"` en
`timestamp_micros`) existen solo en memoria, dentro de la función que las necesita.

## Estructura del proyecto

```
modelo-ml-waymo/
├── conf/
│   ├── base/
│   │   ├── catalog.yml                  # datasets de ambos pipelines
│   │   ├── parameters.yml
│   │   ├── parameters_data_inventory.yml
│   │   └── parameters_eda.yml           # incluye parámetros de signal_check
│   └── local/                           # credenciales/config local (no se versiona)
├── data/
│   ├── 01_raw/
│   │   └── detecciones_waymo_like.csv   # dataset fuente (no versionado, ver .gitignore)
│   ├── 02_intermediate/                 # salidas parquet de ambos pipelines
│   └── 08_reporting/
│       ├── data_inventory_report.md
│       ├── eda_report.md
│       ├── signal_check_report.md
│       └── figures/                     # PNG generados por generate_plots
├── src/modelo_ml_waymo/
│   ├── pipelines/
│   │   ├── data_inventory/
│   │   │   ├── nodes.py
│   │   │   └── pipeline.py
│   │   └── eda/
│   │       ├── nodes.py                 # incluye signal_check
│   │       └── pipeline.py
│   ├── pipeline_registry.py             # autodescubre los pipelines de arriba
│   └── settings.py
├── tests/pipelines/                     # boilerplate de test por pipeline
├── pyproject.toml / requirements.txt / uv.lock
└── README.md
```
##
