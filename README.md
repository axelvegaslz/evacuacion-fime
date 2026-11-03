# Sistema Experto de Rutas de Evacuación — Campus FIME (UANL)

Sistema orientado a la toma de decisiones que, ante una emergencia en el campus de FIME:

1. **Identifica la emergencia** (conato o incendio, explosión, sismo, fuga de gas, derrame químico, falla estructural, amenaza de bomba, robo con violencia, lluvia torrencial, alarma) con un árbol de decisión y una base de reglas con factor de certeza. Indica el **nivel de contingencia oficial** (1, 2 o 3), el protocolo, las brigadas de la UIRI que se activan y el directorio de emergencias. También detecta riesgos secundarios, como un incendio o una falla estructural después de un sismo.
2. **Calcula la ruta de evacuación más segura** desde la puerta de cualquier edificio hasta un punto de reunión abierto, evitando humo y zonas críticas. La ruta se dibuja sobre el mapa real del campus. Compara búsqueda exhaustiva (BFS, DFS, Costo uniforme) contra heurística (Voraz, A*).
3. **Ordena los edificios a evacuar** con Merge Sort según cercanía al peligro, ocupación y personas que requieren apoyo.
4. **Calcula la capacidad de evacuación del campus** con el teorema de flujo máximo (Edmonds-Karp): personas por minuto y tiempo total, incluso con puntos de reunión cerrados.
5. **Aprende**: ajusta la certeza de las reglas cuando la brigada confirma qué ocurrió realmente.

> **Fuente oficial:** el *Plan de Contingencia FIME 2023* (`../FIME%20mapa.pdf`) aporta los niveles de contingencia (sección 5), los protocolos (sección 8), los pisos de cada edificio (Tabla 1), el riesgo químico por edificio (Atlas de Riesgo Interno, 6.1), las brigadas de la UIRI (4.3) y el directorio externo (9.4.2).
>
> **Importante:** es un proyecto académico. Hay 6 puntos de reunión. La **Cancha de fútbol** y el **Campo de béisbol** son las canchas reales de FIME: aparecen en el Atlas de Riesgo Interno del Plan y su geometría viene de OpenStreetMap. Campo sintético, Plaza central, Estacionamiento y Jardín del Oso son propuestas del equipo. La ocupación de cada edificio y las capacidades de la red son estimaciones propuestas por el equipo. Conviene validarlos con los puntos de reunión oficiales de FIME / Protección Civil UANL. En una emergencia real se siguen los procedimientos oficiales.

## Cómo ejecutarlo (Mac)

```bash
cd sistema_experto_evacuacion_fime
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

En Windows: `python -m venv .venv` y `.venv\Scripts\activate`.

Demostración en consola, sin interfaz: `python3 demo_consola.py`

## Archivos

| Archivo | Contenido |
|---|---|
| `app.py` | Interfaz en Streamlit con los 7 módulos |
| `plano.py` | Conversión del mapa de FIME a una cuadrícula de 60 × 72 celdas (≈ 4 m cada una, medida con el Plan de Contingencia y OpenStreetMap): edificios, puertas y puntos de reunión |
| `assets/mapa_fime.png` | Mapa del campus sobre el que se dibujan las rutas: el mapa original (`mapa_fime_original.png`) con una franja norte de 345 px dibujada con datos de © OpenStreetMap contributors (cancha de fútbol, Polideportivo, campo de béisbol) |
| `base_conocimiento.py` | Edificios (ocupación, pisos, riesgo químico), niveles de contingencia, directorio, situaciones, protocolos, árbol y reglas |
| `motor_inferencia.py` | Recorrido del árbol, encadenamiento hacia adelante, factores de certeza, aprendizaje y explicación del razonamiento (`explicar`) |
| `busqueda.py` | Escenario de la emergencia (humo, zona crítica, puntos cerrados) y algoritmos BFS, DFS, Costo uniforme, Voraz y A* |
| `flujo.py` | Red sectores → andadores → puntos de reunión, flujo máximo (Edmonds-Karp) y flujo de costo mínimo (Bellman-Ford) |
| `benchmark.py` | Corre los 5 algoritmos en todas las combinaciones de escenarios (`python3 benchmark.py` se autoverifica) |
| `simulacion.py` | Simulación en el tiempo del plan: fila en cada puerta y caminata por la ruta A* (`python3 simulacion.py` se autoverifica); la animación está en el módulo 7 |
| `plan_evacuacion.py` | Plan del campus completo: asigna cada edificio a un punto de reunión sin rebasar su capacidad; voraz vs. óptimo (`python3 plan_evacuacion.py` se autoverifica) |
| `prioridad.py` | Puntaje de prioridad por edificio y Merge Sort |
| `demo_consola.py` | Demostración de todos los módulos en consola |

## Cómo ajustarlo

- **Mover un edificio, puerta o punto de reunión:** editar los rectángulos en píxeles en `plano.py` (la imagen mide 900 × 1081).
- **Cambiar ocupación, personas que requieren apoyo o pisos:** editar `_DATOS` en `base_conocimiento.py`. El riesgo químico está en `RIESGO_QUIMICO`.
- **Cambiar capacidades de evacuación:** editar `RED` en `flujo.py`.
- **Cambiar la capacidad de los puntos de reunión:** ajustar los m² por persona en el módulo 7 (capacidad = área ÷ m² por persona).

## Relación con lo que pide el PIA

| Requisito | Dónde está |
|---|---|
| Problema detectado | Evacuación segura del campus FIME ante distintas emergencias |
| Análisis de estados / árbol de decisión | `ARBOL` en `base_conocimiento.py`, módulos 1 y 5 |
| Reglas o condiciones de las soluciones | `REGLAS_BASE` (R1–R16) con factor de certeza |
| Soluciones a presentarse | `SITUACIONES` (E0–E12) con nivel de contingencia oficial, nivel de evacuación, protocolo, brigadas y sección del Plan |
| Búsqueda exhaustiva | BFS, DFS y Costo uniforme en `busqueda.py` |
| Búsqueda heurística | Voraz y A* con distancia Manhattan al punto de reunión más cercano |
| Recorridos de árbol | DFS guiado del árbol de decisión y `contar_nodos` |
| Ordenamiento | Merge Sort propio en `prioridad.py` |
| Teoremas de flujo | Flujo máximo Edmonds-Karp y flujo de costo mínimo en `flujo.py` (módulos 4 y 7) |
| Optimización de la búsqueda | Comparativa de nodos explorados, costo de riesgo y seguridad de la ruta (módulo 2), benchmark de 1,824 corridas (módulo 6) y plan voraz vs. óptimo (módulo 7) |
| Simulación del aprendizaje | `aprender()` en `motor_inferencia.py` |

## Casos sugeridos para el video

- **Identificar:** humo Sí → explosión No → fuego controlable No → Incendio declarado (Nivel 3) en el Edificio 6. Después: sin humo → movimiento Sí → sigue No → Después de un sismo, con falla estructural e incendio como riesgos secundarios. Otro: humo Sí → explosión Sí → Explosión con incendio secundario al 60 %.
- **Riesgo químico:** incendio en el Edificio 8 (Atlas de Riesgo Interno): la zona de humo y el radio de cierre crecen 8 m.
- **Ruta:** incendio en el Edificio 6, salen del Edificio 7. Se cierran la Plaza central y el Estacionamiento. BFS va a la Cancha de fútbol cruzando 24 celdas de riesgo junto al incendio; A* va al Jardín del Oso sin cruzar ninguna (140 m) y explora 43 nodos contra 283 de Costo uniforme.
- **Sismo en curso:** el sistema indica repliegue y no calcula ruta.
- **Capacidad:** 4,320 personas salen en 2.3 min; con el incendio en el Edificio 6 (Plaza central y Estacionamiento cerrados) sube a 3.1 min.
- **Plan del campus (módulo 7):** con el incendio en el Edificio 6 caben las 4,320 personas gracias a la Cancha de fútbol y el Campo de béisbol. Con una amenaza de bomba en la Biblioteca se cierran 4 de los 6 puntos y faltan lugares: hay que usar los puntos alternos fuera de FIME (Plan, Ilustración 10).
- **Orden:** incendio en el Edificio 6. Primero el Edificio 6, luego la Biblioteca y el Edificio 7.
