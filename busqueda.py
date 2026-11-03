"""
Búsqueda de la ruta de evacuación más segura desde un edificio de FIME hacia
cualquier punto de reunión abierto.

Cada celda del campus tiene un costo:
  1                 andador / área libre
  1 + penal         zona con humo o peligro
  1 + 3 * penal     zona crítica junto al incidente (solo se cruza si no hay otra opción)

Exhaustivos: BFS (anchura), DFS (profundidad), Costo uniforme (Dijkstra)
Heurísticos: Búsqueda voraz y A* (h = distancia Manhattan al rectángulo del punto
de reunión abierto más cercano; es admisible porque ninguna celda cuesta menos de 1)
"""
import heapq
import time
from collections import Counter, deque

from base_conocimiento import PUNTOS_REUNION, SITUACIONES, ZONAS
from plano import COLUMNAS, FILAS, METROS_POR_CELDA, OCUPADAS, TRANSITABLE

VELOCIDAD_M_S = 1.2  # caminata rápida en evacuación
EXTRA_QUIMICO = 2    # celdas extra de riesgo y de cierre si el edificio tiene riesgo químico


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def distancia_a_edificio(celda, edificio):
    """Distancia (en celdas, tipo Chebyshev) de una celda al edificio más cercano."""
    r, c = celda
    return min(max(abs(r - er), abs(c - ec)) for er, ec in ZONAS[edificio]["celdas"])


def distancia_punto_edificio(punto, edificio):
    return min(distancia_a_edificio(c, edificio) for c in PUNTOS_REUNION[punto]["celdas"])


def construir_escenario(codigo, edificio_incidente=None):
    s = SITUACIONES[codigo]
    costo = [[1 if TRANSITABLE[r][c] else None for c in range(COLUMNAS)] for r in range(FILAS)]
    criticas, riesgo, cerrados = set(), set(), []
    # Atlas de Riesgo Interno: con materiales químicos el humo o la nube tóxica llegan más lejos
    agravado = bool(s["quimico"] and edificio_incidente and ZONAS[edificio_incidente]["quimico"])
    radio_riesgo = s["riesgo"] + (EXTRA_QUIMICO if agravado else 0)
    cierre = s["cierre"] + (EXTRA_QUIMICO if agravado else 0)

    if codigo == "E4":  # después de un sismo: alejarse de fachadas
        for r in range(FILAS):
            for c in range(COLUMNAS):
                if costo[r][c] is None:
                    continue
                cerca = any((r + dr, c + dc) in OCUPADAS for dr in (-1, 0, 1) for dc in (-1, 0, 1))
                if cerca:
                    costo[r][c] = 4
                    riesgo.add((r, c))
        cerrados.append("Plaza central")
    elif s["zona"] and edificio_incidente:
        for r in range(FILAS):
            for c in range(COLUMNAS):
                if costo[r][c] is None:
                    continue
                d = distancia_a_edificio((r, c), edificio_incidente)
                if d <= s["bloqueo"]:
                    costo[r][c] = 1 + 3 * s["penal"]
                    criticas.add((r, c))
                elif d <= radio_riesgo:
                    costo[r][c] = 1 + s["penal"]
                    riesgo.add((r, c))
        for p in PUNTOS_REUNION:
            if distancia_punto_edificio(p, edificio_incidente) <= cierre:
                cerrados.append(p)

    abiertos = [p for p in PUNTOS_REUNION if p not in cerrados]
    if not abiertos:  # nunca dejar el campus sin punto de reunión
        lejano = max(PUNTOS_REUNION, key=lambda p: distancia_punto_edificio(p, edificio_incidente))
        cerrados.remove(lejano)
        abiertos = [lejano]

    meta_a_punto = {c: p for p in abiertos for c in PUNTOS_REUNION[p]["celdas"]}
    return {"costo": costo, "criticas": criticas, "riesgo": riesgo, "cerrados": cerrados,
            "abiertos": abiertos, "metas": meta_a_punto, "cierre": cierre, "agravado": agravado}


def vecinos(costo, pos):
    r, c = pos
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < FILAS and 0 <= nc < COLUMNAS and costo[nr][nc] is not None:
            yield (nr, nc)


def _caja(celdas):
    """Rectángulo (fila_min, fila_max, col_min, col_max) que contiene a las celdas."""
    filas, cols = [r for r, _ in celdas], [c for _, c in celdas]
    return min(filas), max(filas), min(cols), max(cols)


CAJAS_PUNTO = {n: _caja(p["celdas"]) for n, p in PUNTOS_REUNION.items()}


def _heuristica(metas):
    """
    h(n) = distancia Manhattan al rectángulo del punto de reunión abierto más cercano.
    Se mide contra el rectángulo (4 cuentas por punto) y no contra cada celda meta
    (~190 cuentas): da el mismo número de nodos explorados y es ~9 veces más rápido.
    Sigue siendo admisible: la distancia al rectángulo nunca es mayor que a cualquiera de sus celdas.
    """
    cajas = [CAJAS_PUNTO[p] for p in set(metas.values())]
    return lambda p: min(max(0, r0 - p[0], p[0] - r1) + max(0, c0 - p[1], p[1] - c1)
                         for r0, r1, c0, c1 in cajas)


def _resultado(nombre, tipo, padre, meta, explorados, t0, esc):
    tiempo_ms = (time.perf_counter() - t0) * 1000
    camino = []
    if meta is not None:
        nodo = meta
        while nodo is not None:
            camino.append(nodo)
            nodo = padre[nodo]
        camino.reverse()
    pasos = max(len(camino) - 1, 0)
    return {
        "algoritmo": nombre, "tipo": tipo, "camino": camino, "explorados": explorados,
        "nodos_explorados": len(explorados), "pasos": pasos,
        "costo": sum(esc["costo"][r][c] for r, c in camino[1:]),
        "celdas_riesgo": sum(1 for p in camino if p in esc["riesgo"] or p in esc["criticas"]),
        "metros": pasos * METROS_POR_CELDA,
        "segundos": round(pasos * METROS_POR_CELDA / VELOCIDAD_M_S),
        "punto": esc["metas"].get(meta, "—"), "tiempo_ms": round(tiempo_ms, 3),
        "encontrado": bool(camino),
    }


def bfs(esc, inicio):
    """Anchura: minimiza pasos, ignora el humo (todas las celdas valen 1)."""
    t0 = time.perf_counter()
    metas = esc["metas"]
    frontera, padre, explorados, meta = deque([inicio]), {inicio: None}, [], None
    while frontera:
        actual = frontera.popleft()
        explorados.append(actual)
        if actual in metas:
            meta = actual
            break
        for v in vecinos(esc["costo"], actual):
            if v not in padre:
                padre[v] = actual
                frontera.append(v)
    return _resultado("BFS", "Exhaustiva", padre, meta, explorados, t0, esc)


def dfs(esc, inicio):
    """Profundidad: encuentra un punto de reunión, sin garantía de ruta corta ni segura."""
    t0 = time.perf_counter()
    metas = esc["metas"]
    pila, padre, explorados, meta = [(inicio, None)], {}, [], None
    while pila:
        actual, p = pila.pop()
        if actual in padre:
            continue
        padre[actual] = p
        explorados.append(actual)
        if actual in metas:
            meta = actual
            break
        for v in vecinos(esc["costo"], actual):
            if v not in padre:
                pila.append((v, actual))
    return _resultado("DFS", "Exhaustiva", padre, meta, explorados, t0, esc)


def costo_uniforme(esc, inicio):
    """Dijkstra: exhaustiva y óptima en costo (evita el humo), pero explora mucho."""
    t0 = time.perf_counter()
    metas = esc["metas"]
    cola, g, padre, cerrados, explorados, meta, n = [(0, 0, inicio)], {inicio: 0}, {inicio: None}, set(), [], None, 0
    while cola:
        gc, _, actual = heapq.heappop(cola)
        if actual in cerrados:
            continue
        cerrados.add(actual)
        explorados.append(actual)
        if actual in metas:
            meta = actual
            break
        for v in vecinos(esc["costo"], actual):
            ng = gc + esc["costo"][v[0]][v[1]]
            if ng < g.get(v, float("inf")):
                g[v], padre[v] = ng, actual
                n += 1
                heapq.heappush(cola, (ng, n, v))
    return _resultado("Costo uniforme", "Exhaustiva", padre, meta, explorados, t0, esc)


def voraz(esc, inicio):
    """Voraz: va directo al punto más cercano según h(n); rápida, no siempre segura."""
    t0 = time.perf_counter()
    metas, h = esc["metas"], _heuristica(esc["metas"])
    cola, padre, cerrados, explorados, meta, n = [(h(inicio), 0, inicio)], {inicio: None}, set(), [], None, 0
    while cola:
        _, _, actual = heapq.heappop(cola)
        if actual in cerrados:
            continue
        cerrados.add(actual)
        explorados.append(actual)
        if actual in metas:
            meta = actual
            break
        for v in vecinos(esc["costo"], actual):
            if v not in padre:
                padre[v] = actual
                n += 1
                heapq.heappush(cola, (h(v), n, v))
    return _resultado("Voraz", "Heurística", padre, meta, explorados, t0, esc)


def a_estrella(esc, inicio):
    """A*: f(n) = g(n) + h(n). Óptima en costo y explora menos que Dijkstra."""
    t0 = time.perf_counter()
    metas, h = esc["metas"], _heuristica(esc["metas"])
    h0 = h(inicio)
    cola, g, padre, cerrados, explorados, meta, n = [(h0, h0, 0, 0, inicio)], {inicio: 0}, {inicio: None}, set(), [], None, 0
    while cola:
        _, _, _, gc, actual = heapq.heappop(cola)
        if actual in cerrados:
            continue
        cerrados.add(actual)
        explorados.append(actual)
        if actual in metas:
            meta = actual
            break
        for v in vecinos(esc["costo"], actual):
            ng = gc + esc["costo"][v[0]][v[1]]
            if ng < g.get(v, float("inf")):
                g[v], padre[v] = ng, actual
                n += 1
                hv = h(v)
                heapq.heappush(cola, (ng + hv, hv, n, ng, v))
    return _resultado("A*", "Heurística", padre, meta, explorados, t0, esc)


ALGORITMOS = [bfs, dfs, costo_uniforme, voraz, a_estrella]


def correr_algoritmos(esc, origen):
    """Corre todos los algoritmos en un escenario y marca cuáles encontraron la ruta de menor costo."""
    resultados = [alg(esc, origen) for alg in ALGORITMOS]
    mejor = min(r["costo"] for r in resultados if r["encontrado"])
    for r in resultados:
        r["optima"] = r["encontrado"] and r["costo"] == mejor
    return resultados


def comparar(codigo, edificio_incidente, edificio_origen):
    esc = construir_escenario(codigo, edificio_incidente)
    return esc, correr_algoritmos(esc, ZONAS[edificio_origen]["puerta"])


def explicar_ruta(esc, resultados, codigo, incidente=None):
    """Traza legible de por qué A* eligió esta ruta y este punto de reunión."""
    s = SITUACIONES[codigo]
    d = {r["algoritmo"]: r for r in resultados}
    a, b, uc = d["A*"], d["BFS"], d["Costo uniforme"]
    m = METROS_POR_CELDA

    lineas = ["**1. Puntos de reunión disponibles**"]
    if esc["agravado"]:
        lineas.append(f"- ⚠ {incidente} tiene riesgo químico (Atlas de Riesgo Interno del Plan de Contingencia): "
                      f"la zona de riesgo y el radio de cierre crecen {EXTRA_QUIMICO * m} m.")
    for p in PUNTOS_REUNION:
        if p in esc["cerrados"]:
            if codigo == "E4":
                motivo = "está rodeado de edificios y después de un sismo pueden caer fachadas o vidrios"
            else:
                motivo = (f"está a {distancia_punto_edificio(p, incidente) * m} m del incidente "
                          f"(se cierran los que estén a {esc['cierre'] * m} m o menos)")
            lineas.append(f"- ✕ {p}: cerrado, {motivo}.")
        elif incidente and s["zona"] and distancia_punto_edificio(p, incidente) <= esc["cierre"]:
            lineas.append(f"- ✓ {p}: abierto aunque está cerca del incidente, porque es el más lejano "
                          "y el campus no puede quedar sin punto de reunión.")
        else:
            lineas.append(f"- ✓ {p}: abierto.")

    h0 = _heuristica(esc["metas"])(a["camino"][0])
    lineas += [
        "\n**2. Cómo eligió A\\* la ruta**",
        "- A\\* ordena la frontera por f(n) = g(n) + h(n): g = costo de riesgo acumulado y "
        "h = distancia Manhattan al punto de reunión abierto más cercano.",
        f"- Al salir, h = {h0} y el costo real de la ruta es {a['costo']}. h nunca supera el costo real "
        "(cada celda cuesta al menos 1), por eso A\\* garantiza la ruta de menor riesgo.",
        f"- Busca hacia todos los puntos abiertos a la vez, así que llega al de menor costo: **{a['punto']}**.",
        f"- Exploró {a['nodos_explorados']} nodos contra {uc['nodos_explorados']} de Costo uniforme, "
        "que da la misma ruta pero sin heurística.",
    ]

    riesgo_txt = "junto a fachadas" if codigo == "E4" else "con humo o peligro"
    conteo = Counter()
    for r, c in a["camino"][1:]:
        tipo = ("en zona crítica" if (r, c) in esc["criticas"]
                else riesgo_txt if (r, c) in esc["riesgo"] else "de andador libre")
        conteo[(tipo, esc["costo"][r][c])] += 1
    partes = [f"{n} {'celda' if n == 1 else 'celdas'} {tipo} × {costo}" for (tipo, costo), n in conteo.items()]
    lineas += ["\n**3. Costo de la ruta elegida**",
               f"- {' + '.join(partes)} = **{a['costo']}** ({a['metros']} m, unos {a['segundos']} s caminando)."]
    if a["camino"][0] in esc["riesgo"] or a["camino"][0] in esc["criticas"]:
        lineas.append("- La puerta de salida ya está dentro de la zona de riesgo: cuenta como celda de riesgo "
                      "cruzada, pero no suma costo porque ahí empieza la ruta.")

    lineas.append("\n**4. ¿Por qué no la ruta más corta?**")
    if b["costo"] > a["costo"]:
        extra = (a["pasos"] - b["pasos"]) * m
        lineas.append(f"- BFS encuentra la ruta con menos pasos ({b['pasos']} contra {a['pasos']}), pero cruza "
                      f"{b['celdas_riesgo']} celdas de riesgo (costo {b['costo']}). A\\* "
                      + (f"camina {extra} m más" if extra > 0 else "recorre la misma distancia")
                      + f" y solo cruza {a['celdas_riesgo']}.")
    else:
        lineas.append("- En este caso la ruta más corta (BFS) también es la más segura.")
    return lineas
