# Inventario de datos crudos (data/01_raw)

## Archivos

| ruta_relativa | formato | tamano_mb | segmento_contexto |
| --- | --- | --- | --- |
| detecciones_waymo_like.csv | csv | 4.6373 | None |

## Archivos

- **total_archivos**: 1
- **tamano_total_mb**: 4.6373

## Archivos por formato

- **csv**: 1

## Muestra

- **archivos_inspeccionados**: 1
- **archivo**: detecciones_waymo_like.csv
- **filas_leidas**: 20

## Esquema

- **columnas**: segment_id, timestamp_micros, id_interno, object_type, box_center_x, box_center_y, box_center_z, box_length, box_width, box_height, speed_mps, num_lidar_points, weather, time_of_day, detection_difficulty, sensor_version

## Anotaciones

- **bounding_box_3d**: si
- **bounding_box_2d**: no

## Camaras

- **campos_camara_presentes**: no presentes en este dataset

## Metadata

- **time_of_day**: Day, Night, Dawn/Dusk
- **weather**: sunny, soleado, SUNNY, Sunny, RAIN , fog, rain
- **location**: campo no presente
- **detection_difficulty**: LEVEL_1, LEVEL_2
- **sensor_version**: v2.0.1

## Conteo objetos

- **VEHICLE**: 13
- **PEDESTRIAN**: 4
- **SIGN**: 1
- **Ped**: 1
- **Pedestrian**: 1

## Segmentos

- **segmentos_distintos_en_muestra**: 20
