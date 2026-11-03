"""
Benchmark de los algoritmos de búsqueda de rutas de evacuación.

Corre BFS, DFS, Costo uniforme, Voraz y A* en TODAS las combinaciones:
    situación que requiere evacuar x edificio del incidente (si aplica) x edificio de origen
y resume por algoritmo: nodos explorados promedio, % de rutas más seguras
(costo mínimo), costo promedio, sobrecosto contra la óptima y tiempo de cómputo.
"""
import busqueda as bq
from base_conocimiento import SITUACIONES, ZONAS


def correr():
    """Devuelve una fila por (escenario, algoritmo)."""
    filas = []
    for codigo, s in SITUACIONES.items():
        if not s["evacuar"]:
            continue
        for incidente in (ZONAS if s["zona"] else [None]):
            esc = bq.construir_escenario(codigo, incidente)  # se construye una vez por escenario
            for origen, z in ZONAS.items():
                resultados = bq.correr_algoritmos(esc, z["puerta"])
                optimo = min(r["costo"] for r in resultados if r["encontrado"])
                for r in resultados:
                    filas.append({
                        "Situación": f"{codigo} - {s['nombre']}",
                        "Incidente": incidente or "—", "Origen": origen,
                        "Algoritmo": r["algoritmo"],
                        "Nodos explorados": r["nodos_explorados"],
                        "Costo": r["costo"],
                        "Celdas de riesgo": r["celdas_riesgo"],
                        "Óptima": r["optima"],
                        # Si el origen ya está en un punto de reunión el costo óptimo es 0
                        "Sobrecosto (%)": 100 * (r["costo"] - optimo) / optimo if optimo else 0.0,
                        "Cómputo (ms)": r["tiempo_ms"],
                    })
    return filas


def resumen(filas):
    """Promedios por algoritmo (en el orden en que aparecen)."""
    grupos = {}
    for f in filas:
        grupos.setdefault(f["Algoritmo"], []).append(f)
    tabla = []
    for alg, fs in grupos.items():
        n = len(fs)
        tabla.append({
            "Algoritmo": alg,
            "Corridas": n,
            "Nodos explorados (prom.)": round(sum(f["Nodos explorados"] for f in fs) / n, 1),
            "Rutas más seguras (%)": round(100 * sum(f["Óptima"] for f in fs) / n, 1),
            "Costo de riesgo (prom.)": round(sum(f["Costo"] for f in fs) / n, 1),
            "Celdas de riesgo (prom.)": round(sum(f["Celdas de riesgo"] for f in fs) / n, 1),
            "Sobrecosto vs. óptima (%)": round(sum(f["Sobrecosto (%)"] for f in fs) / n, 1),
            "Cómputo (ms prom.)": round(sum(f["Cómputo (ms)"] for f in fs) / n, 3),
        })
    return tabla


if __name__ == "__main__":
    filas = correr()
    tabla = {t["Algoritmo"]: t for t in resumen(filas)}
    # Autoverificación: Costo uniforme y A* siempre dan la ruta de menor costo,
    # y A* explora menos que Costo uniforme
    assert tabla["Costo uniforme"]["Rutas más seguras (%)"] == 100
    assert tabla["A*"]["Rutas más seguras (%)"] == 100
    assert tabla["A*"]["Nodos explorados (prom.)"] < tabla["Costo uniforme"]["Nodos explorados (prom.)"]
    for t in tabla.values():
        print(t)
