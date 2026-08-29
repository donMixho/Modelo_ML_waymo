# Verificación de señal predictiva

Diagnóstico de si `detection_difficulty` y `object_type` tienen señal predictiva aprovechable con las variables numéricas disponibles (box_center_x, box_center_y, box_center_z, box_length, box_width, box_height, speed_mps, num_lidar_points). Ningún dato transformado se persiste: la normalización de categorías es solo en memoria, y las filas con nulos en las variables usadas (únicamente `speed_mps` los tiene) se excluyen por caso completo, nunca se imputan.

## Normalización aplicada (solo en memoria)

#### Mapeo aplicado a `detection_difficulty` (solo en memoria, exclusivo de este análisis)

| valor_crudo | valor_normalizado | frecuencia |
| --- | --- | --- |
| LEVEL_1 | LEVEL_1 | 36165 |
| LEVEL_2 | LEVEL_2 | 4515 |

#### Mapeo aplicado a `object_type` (solo en memoria, exclusivo de este análisis)

| valor_crudo | valor_normalizado | frecuencia |
| --- | --- | --- |
| VEHICLE | VEHICLE | 25111 |
| PEDESTRIAN | PEDESTRIAN | 9134 |
| SIGN | SIGN | 3303 |
| Pedestrian | PEDESTRIAN | 1069 |
| PEATON | PEDESTRIAN | 811 |
| CYCLIST | CYCLIST | 789 |
| Ped | PEDESTRIAN | 463 |

## Resumen final

| candidato | mi_maxima | mi_ruido_base | n_features_p_lt_alpha | n_features_totales | macro_f1_arbol | macro_f1_dummy | n_filas_tras_dedup | n_duplicados_removidos | veredicto |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| detection_difficulty | 0.068045 | 0.001864 | 2 | 8 | 0.6904 | 0.4745 | 39425 | 468 | SEÑAL |
| object_type | 0.914615 | 0.0 | 4 | 8 | 0.9963 | 0.1909 | 39425 | 468 | SEÑAL |

**SEÑAL**: mejora de macro-F1 (árbol vs. dummy) ≥ 0.05, Y MI máxima > 2.0x el ruido de referencia, Y al menos 1 feature con p < 0.05. **SEÑAL DÉBIL**: cumple al menos una de esas tres condiciones de forma más modesta (mejora ≥ 0.01, o MI por sobre el ruido, o algún p < 0.05). **SIN SEÑAL**: no cumple ninguna.

## detection_difficulty

### Información mutua (mayor a menor; incluye ruido aleatorio de referencia)

| rank | feature | mi_score | es_ruido_base |
| --- | --- | --- | --- |
| 1 | num_lidar_points | 0.06804465903964085 | False |
| 2 | box_center_x | 0.044881010402602284 | False |
| 3 | box_center_y | 0.0025876893086815844 | False |
| 4 | ruido_aleatorio_referencia | 0.0018637500945009045 | True |
| 5 | speed_mps | 0.0018165925336002253 | False |
| 6 | box_width | 0.0005450916194116306 | False |
| 7 | box_center_z | 0.0004924534987105211 | False |
| 8 | box_length | 0.0 | False |
| 9 | box_height | 0.0 | False |

### Separabilidad (Kruskal-Wallis)

| feature | test | estadistico | p_valor |
| --- | --- | --- | --- |
| num_lidar_points | kruskal_wallis | 917.9961000850856 | 1.2015102978383123e-201 |
| box_center_x | kruskal_wallis | 890.4757211371976 | 1.1542415178946014e-195 |
| speed_mps | kruskal_wallis | 3.411564926598695 | 0.06474102293752705 |
| box_height | kruskal_wallis | 0.18833302993365733 | 0.6643076585723502 |
| box_width | kruskal_wallis | 0.1431006490957699 | 0.7052177995588228 |
| box_length | kruskal_wallis | 0.015988258490924976 | 0.8993799320687332 |
| box_center_z | kruskal_wallis | 0.009601529848531307 | 0.9219423014377108 |
| box_center_y | kruskal_wallis | 0.0021934328597210785 | 0.9626454515095904 |

### Baseline honesto (dummy vs. árbol de decisión)

| modelo | accuracy | macro_f1 | n_train | n_test |
| --- | --- | --- | --- | --- |
| dummy_mas_frecuente | 0.9029421711193778 | 0.47449795628221075 | 27597 | 11828 |
| arbol_decision | 0.9280520798106189 | 0.69038187390485 | 27597 | 11828 |

## object_type

### Información mutua (mayor a menor; incluye ruido aleatorio de referencia)

| rank | feature | mi_score | es_ruido_base |
| --- | --- | --- | --- |
| 1 | box_length | 0.9146152510675889 | False |
| 2 | box_width | 0.83927256418811 | False |
| 3 | speed_mps | 0.7385142923631733 | False |
| 4 | box_height | 0.21285304665154992 | False |
| 5 | box_center_y | 0.00885869101657466 | False |
| 6 | box_center_x | 0.006811614456082804 | False |
| 7 | num_lidar_points | 0.005467930419749578 | False |
| 8 | box_center_z | 0.0 | False |
| 9 | ruido_aleatorio_referencia | 0.0 | True |

### Separabilidad (Kruskal-Wallis)

| feature | test | estadistico | p_valor |
| --- | --- | --- | --- |
| box_length | kruskal_wallis | 29917.112454350507 | 0.0 |
| box_width | kruskal_wallis | 29966.42242095941 | 0.0 |
| box_height | kruskal_wallis | 5931.208883199387 | 0.0 |
| speed_mps | kruskal_wallis | 25836.562118852926 | 0.0 |
| box_center_x | kruskal_wallis | 6.75685586208152 | 0.08006492795636996 |
| num_lidar_points | kruskal_wallis | 5.361796960016019 | 0.14714236842043435 |
| box_center_y | kruskal_wallis | 4.144017660664081 | 0.24632688734042496 |
| box_center_z | kruskal_wallis | 0.5577178655311166 | 0.9060399025511283 |

### Baseline honesto (dummy vs. árbol de decisión)

| modelo | accuracy | macro_f1 | n_train | n_test |
| --- | --- | --- | --- | --- |
| dummy_mas_frecuente | 0.6176868447751099 | 0.19091669279816034 | 27597 | 11828 |
| arbol_decision | 0.9994081839702401 | 0.9963461739747655 | 27597 | 11828 |
