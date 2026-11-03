"""
Teorema de flujo máximo (Edmonds-Karp) aplicado a la capacidad de evacuación
del campus FIME.

Los sectores del campus envían personas a los andadores, los andadores a los
puntos de reunión y estos a la zona segura. Cada arista es la capacidad en
personas por minuto (valores estimados para el proyecto). Si un punto de
reunión se cierra, se recalcula el flujo máximo y el tiempo de evacuación.
"""
from collections import defaultdict, deque

from base_conocimiento import ZONAS

FUENTE = "Ocupantes"
SUMIDERO = "Zona segura"

RED = [
    ("Ocupantes", "Sector norte", 500),
    ("Ocupantes", "Sector centro", 550),
    ("Ocupantes", "Sector poniente", 350),
    ("Ocupantes", "Sector oriente-sur", 600),
    ("Sector norte", "Andador norte", 400),
    ("Sector norte", "Andador central", 150),
    ("Sector centro", "Andador central", 400),
    ("Sector centro", "Andador norte", 150),
    ("Sector centro", "Andador poniente", 100),
    ("Sector poniente", "Andador poniente", 300),
    ("Sector poniente", "Andador sur", 100),
    ("Sector oriente-sur", "Andador sur", 450),
    ("Sector oriente-sur", "Andador central", 150),
    ("Andador norte", "Campo sintético", 450),
    ("Andador norte", "Cancha de fútbol", 300),
    ("Andador norte", "Campo de béisbol", 250),
    ("Andador poniente", "Cancha de fútbol", 150),
    ("Andador central", "Plaza central", 300),
    ("Andador central", "Campo sintético", 150),
    ("Andador central", "Jardín del Oso", 150),
    ("Andador poniente", "Estacionamiento", 350),
    ("Andador sur", "Jardín del Oso", 500),
    ("Campo sintético", "Zona segura", 500),
    ("Cancha de fútbol", "Zona segura", 450),
    ("Campo de béisbol", "Zona segura", 300),
    ("Plaza central", "Zona segura", 250),
    ("Estacionamiento", "Zona segura", 350),
    ("Jardín del Oso", "Zona segura", 550),
]

NODOS = ["Ocupantes", "Sector norte", "Sector centro", "Sector poniente", "Sector oriente-sur",
         "Andador norte", "Andador central", "Andador poniente", "Andador sur",
         "Cancha de fútbol", "Campo de béisbol", "Campo sintético", "Plaza central", "Estacionamiento",
         "Jardín del Oso", "Zona segura"]

PUNTOS = ["Cancha de fútbol", "Campo de béisbol", "Campo sintético", "Plaza central", "Estacionamiento",
          "Jardín del Oso"]

OCUPACION_TOTAL = sum(z["ocupacion"] for z in ZONAS.values())


def flujo_maximo(cerrados=()):
    """Devuelve (flujo máximo en personas/min, {(u, v): flujo})."""
    cerrados = set(cerrados)
    aristas = [(u, v, c) for u, v, c in RED if u not in cerrados and v not in cerrados]
    capacidad = defaultdict(lambda: defaultdict(int))
    for u, v, c in aristas:
        capacidad[u][v] += c
        capacidad[v][u] += 0
    flujo = defaultdict(lambda: defaultdict(int))
    total = 0
    while True:
        padre = {FUENTE: None}
        cola = deque([FUENTE])
        while cola and SUMIDERO not in padre:
            u = cola.popleft()
            for v in list(capacidad[u]):
                if v not in padre and capacidad[u][v] - flujo[u][v] > 0:
                    padre[v] = u
                    cola.append(v)
        if SUMIDERO not in padre:
            break
        cuello, v = float("inf"), SUMIDERO
        while padre[v] is not None:
            u = padre[v]
            cuello = min(cuello, capacidad[u][v] - flujo[u][v])
            v = u
        v = SUMIDERO
        while padre[v] is not None:
            u = padre[v]
            flujo[u][v] += cuello
            flujo[v][u] -= cuello
            v = u
        total += cuello
    return total, {(u, v): max(flujo[u][v], 0) for u, v, _ in aristas}


def tiempo_evacuacion(cerrados=()):
    total, _ = flujo_maximo(cerrados)
    return round(OCUPACION_TOTAL / total, 1) if total else float("inf")


def flujo_a_dot(por_arista, cerrados=()):
    cerrados = set(cerrados)
    lineas = ['digraph Red {', 'rankdir=LR; bgcolor="transparent";',
              'node [fontname="Helvetica", fontsize=10, style=filled, shape=box];',
              'edge [fontname="Helvetica", fontsize=9];']
    for nodo in NODOS:
        if nodo in cerrados:
            color = "#E06666"
        elif nodo in (FUENTE, SUMIDERO):
            color = "#CFE2F3"
        elif nodo in PUNTOS:
            color = "#D9EAD3"
        else:
            color = "#FFF2CC"
        lineas.append(f'"{nodo}" [fillcolor="{color}"];')
    for u, v, c in RED:
        if u in cerrados or v in cerrados:
            lineas.append(f'"{u}" -> "{v}" [label="0/{c}", style=dashed, color="#E06666"];')
        else:
            f = por_arista.get((u, v), 0)
            lineas.append(f'"{u}" -> "{v}" [label="{f}/{c}", penwidth={1 + 3 * f / 500:.1f}];')
    lineas.append("}")
    return "\n".join(lineas)


def flujo_costo_minimo(aristas, fuente, sumidero):
    """
    Flujo máximo de costo mínimo (caminos sucesivos más baratos).

    Igual que Edmonds-Karp, se repite: buscar un camino aumentante y empujar flujo
    por él. La diferencia es que aquí el camino no es el más corto en aristas (BFS),
    sino el MÁS BARATO, y se busca con Bellman-Ford porque las aristas residuales
    tienen costo negativo (devolver flujo "reembolsa" su costo).

    aristas: [(u, v, capacidad, costo por unidad)]
    Devuelve (flujo total, costo total, {(u, v): flujo}).
    """
    # ponytail: una sola arista por par (u, v); basta para la red edificios -> puntos
    capacidad = defaultdict(lambda: defaultdict(int))
    costo = defaultdict(dict)
    for u, v, c, w in aristas:
        capacidad[u][v] += c
        capacidad[v][u] += 0  # arista residual
        costo[u][v], costo[v][u] = w, -w
    flujo = defaultdict(lambda: defaultdict(int))
    nodos = list(capacidad)
    total = costo_total = 0

    while True:
        # Bellman-Ford: camino aumentante de menor costo en la red residual
        dist = {n: float("inf") for n in nodos}
        dist[fuente], padre = 0, {fuente: None}
        for _ in range(len(nodos) - 1):
            hubo_cambio = False
            for u in nodos:
                if dist[u] == float("inf"):
                    continue
                for v in capacidad[u]:
                    if capacidad[u][v] - flujo[u][v] > 0 and dist[u] + costo[u][v] < dist[v]:
                        dist[v], padre[v] = dist[u] + costo[u][v], u
                        hubo_cambio = True
            if not hubo_cambio:
                break
        if dist[sumidero] == float("inf"):
            break

        cuello, v = float("inf"), sumidero
        while padre[v] is not None:
            u = padre[v]
            cuello = min(cuello, capacidad[u][v] - flujo[u][v])
            v = u
        v = sumidero
        while padre[v] is not None:
            u = padre[v]
            flujo[u][v] += cuello
            flujo[v][u] -= cuello
            v = u
        total += cuello
        costo_total += cuello * dist[sumidero]

    return total, costo_total, {(u, v): max(flujo[u][v], 0) for u, v, _, _ in aristas}
