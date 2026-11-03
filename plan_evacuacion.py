"""
Plan de evacuación del campus completo.

Asigna a los ocupantes de cada edificio un punto de reunión abierto sin rebasar
su capacidad, minimizando el riesgo total = Σ personas × costo de su ruta.

- Costo de cada ruta: A* desde la puerta del edificio hasta UN punto de reunión,
  con el mismo escenario de humo y zonas críticas del módulo 2.
- Capacidad de cada punto: área (celdas × METROS_POR_CELDA² = 16 m²) ÷ m² por persona. Es una estimación
  que se ajusta con el parámetro m2_por_persona.
- Voraz: los edificios van en el orden de evacuación (Merge Sort) y cada uno se manda al
  punto más barato que todavía tenga lugar. Rápido, pero puede dejar sin lugar barato
  a los edificios que van después.
- Óptimo: flujo de costo mínimo (Bellman-Ford) sobre la red
  Ocupantes -> Edificios -> Puntos de reunión -> Zona segura.
"""
import busqueda as bq
from base_conocimiento import PUNTOS_REUNION, SITUACIONES, ZONAS
from flujo import OCUPACION_TOTAL, flujo_costo_minimo
from plano import METROS_POR_CELDA
from prioridad import merge_sort, priorizar


def capacidades(abiertos, m2_por_persona):
    m2_por_celda = METROS_POR_CELDA ** 2
    return {p: int(len(PUNTOS_REUNION[p]["celdas"]) * m2_por_celda / m2_por_persona) for p in abiertos}


def rutas_por_punto(esc):
    """A* de cada edificio a cada punto abierto por separado: {(edificio, punto): resultado}."""
    rutas = {}
    for p in esc["abiertos"]:
        esc_p = dict(esc, metas={c: p for c in PUNTOS_REUNION[p]["celdas"]})  # solo este punto es meta
        for e, z in ZONAS.items():
            r = bq.a_estrella(esc_p, z["puerta"])
            if r["encontrado"]:
                rutas[(e, p)] = r
    return rutas


def plan_voraz(codigo, incidente, rutas, cap):
    """Cada edificio, en orden de prioridad, toma el punto más barato con lugar (y si no cabe, el siguiente)."""
    libre = dict(cap)
    asignacion = []
    for fila in priorizar(codigo, incidente):
        e, resto = fila["Edificio"], ZONAS[fila["Edificio"]]["ocupacion"]
        opciones = [p for p in cap if (e, p) in rutas]
        opciones = merge_sort(opciones, lambda p: -rutas[(e, p)]["costo"])  # del más barato al más caro
        for p in opciones:
            n = min(resto, libre[p])
            if n > 0:
                asignacion.append((e, p, n))
                libre[p] -= n
                resto -= n
            if resto == 0:
                break
    return asignacion


def plan_optimo(codigo, incidente, rutas, cap):
    """
    Flujo de costo mínimo: manda a cada persona al punto que da el menor riesgo total.

    Si no caben todos, las personas que sobran pasan por la arista "Sin lugar". Esa arista
    cuesta más que cualquier ruta y cuesta más entre más prioritario es el edificio, así que
    los que se quedan sin lugar siempre son los de menor prioridad (nunca el del incidente).
    """
    orden = {f["Edificio"]: f["Orden"] for f in priorizar(codigo, incidente)}
    escalon = max(r["costo"] for r in rutas.values()) + 1
    aristas = [("Ocupantes", e, z["ocupacion"], 0) for e, z in ZONAS.items()]
    aristas += [(e, p, OCUPACION_TOTAL, r["costo"]) for (e, p), r in rutas.items()]
    aristas += [(e, "Sin lugar", OCUPACION_TOTAL, escalon * (len(ZONAS) + 1 - orden[e])) for e in ZONAS]
    aristas += [(p, "Zona segura", c, 0) for p, c in cap.items()]
    aristas.append(("Sin lugar", "Zona segura", OCUPACION_TOTAL, 0))
    _, _, por_arista = flujo_costo_minimo(aristas, "Ocupantes", "Zona segura")
    return [(e, p, por_arista[(e, p)]) for (e, p) in rutas if por_arista[(e, p)] > 0]


def resumen(asignacion, rutas):
    personas = sum(n for _, _, n in asignacion)
    return {
        "Personas asignadas": personas,
        "Sin lugar": OCUPACION_TOTAL - personas,
        "Riesgo total": sum(n * rutas[(e, p)]["costo"] for e, p, n in asignacion),
        "Distancia promedio (m)": round(sum(n * rutas[(e, p)]["metros"] for e, p, n in asignacion)
                                        / personas) if personas else 0,
        "Caminata más larga (s)": max((rutas[(e, p)]["segundos"] for e, p, _ in asignacion), default=0),
    }


def ocupacion_por_punto(asignacion, cap):
    llegan = {p: 0 for p in cap}
    for _, p, n in asignacion:
        llegan[p] += n
    return llegan


def plan(codigo, incidente=None, m2_por_persona=1.0):
    esc = bq.construir_escenario(codigo, incidente)
    cap = capacidades(esc["abiertos"], m2_por_persona)
    rutas = rutas_por_punto(esc)
    return {"esc": esc, "cap": cap, "rutas": rutas,
            "voraz": plan_voraz(codigo, incidente, rutas, cap),
            "optimo": plan_optimo(codigo, incidente, rutas, cap)}


def sin_lugar_por_edificio(asignacion):
    asignados = {e: 0 for e in ZONAS}
    for e, _, n in asignacion:
        asignados[e] += n
    return {e: ZONAS[e]["ocupacion"] - n for e, n in asignados.items()}


if __name__ == "__main__":
    # Autoverificación en todos los escenarios: el óptimo nunca es peor que el voraz,
    # ningún punto se rebasa y ambos acomodan a la misma cantidad de personas.
    mejoras = []
    for codigo, s in SITUACIONES.items():
        if not s["evacuar"]:
            continue
        for incidente in (ZONAS if s["zona"] else [None]):
            for m2 in (1.0, 1.5, 2.0):
                pl = plan(codigo, incidente, m2)
                rv, ro = resumen(pl["voraz"], pl["rutas"]), resumen(pl["optimo"], pl["rutas"])
                assert ro["Riesgo total"] <= rv["Riesgo total"], (codigo, incidente, m2)
                assert ro["Personas asignadas"] == rv["Personas asignadas"], (codigo, incidente, m2)
                # Los que se quedan sin lugar son los de menor prioridad: si a un edificio le falta
                # gente, todos los que van después de él en el orden quedan completamente fuera
                orden = [f["Edificio"] for f in priorizar(codigo, incidente)]
                faltan = sin_lugar_por_edificio(pl["optimo"])
                for i, e in enumerate(orden):
                    if faltan[e]:
                        assert all(faltan[x] == ZONAS[x]["ocupacion"] for x in orden[i + 1:]), (codigo, incidente, e)
                for a in (pl["voraz"], pl["optimo"]):
                    for p, n in ocupacion_por_punto(a, pl["cap"]).items():
                        assert n <= pl["cap"][p], (codigo, incidente, p)
                mejoras.append(1 - ro["Riesgo total"] / rv["Riesgo total"])
    print(f"{len(mejoras)} escenarios OK. El óptimo reduce el riesgo del voraz en promedio "
          f"{sum(mejoras) / len(mejoras):.1%} (máximo {max(mejoras):.1%}).")
    pl = plan("E2", "Edificio 6", 1.5)
    print("Incendio en Edificio 6:", pl["cap"])
    print("  voraz: ", resumen(pl["voraz"], pl["rutas"]))
    print("  óptimo:", resumen(pl["optimo"], pl["rutas"]))
