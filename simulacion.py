"""
Simulación en el tiempo de un plan de evacuación (módulo 7).

Modelo:
- Las personas de cada edificio salen por su puerta en fila, a TASA_PUERTA personas por segundo.
- La ocupación se reparte igual entre los pisos (Tabla 1 del Plan de Contingencia); quien está en
  el piso k no llega a la puerta antes de bajar k pisos (SEGUNDOS_POR_PISO cada uno).
- Ya afuera caminan por su ruta A* hasta el punto de reunión asignado a VELOCIDAD_M_S.
- Para dibujar, cada punto en el mapa representa un grupo de PERSONAS_POR_PUNTO personas.

Con esto se obtiene el tiempo total de evacuación (lo que tarda en llegar el último grupo),
que ya incluye la fila en la puerta y la caminata, no solo la capacidad de los andadores.
"""
from base_conocimiento import ZONAS
from busqueda import VELOCIDAD_M_S
from plano import METROS_POR_CELDA

# ponytail: estimaciones fijas; calibrar con los tiempos de un simulacro real
TASA_PUERTA = 1.3        # personas por segundo que cruzan una puerta
PERSONAS_POR_PUNTO = 10  # personas que representa cada punto de la animación
SEGUNDOS_POR_PISO = 30   # bajar un piso por escalera, sin elevadores


def grupos(asignacion, rutas):
    """Divide el plan en grupos con su ruta, hora de salida y hora de llegada (segundos)."""
    por_edificio = {}
    for e, p, n in asignacion:
        por_edificio.setdefault(e, []).append((p, n))
    lista = []
    for e, destinos in por_edificio.items():
        sale = 0.0  # la puerta es una fila: cada grupo sale cuando terminó de salir el anterior
        total, pisos, ya = sum(n for _, n in destinos), ZONAS[e]["pisos"], 0
        for p, n in destinos:
            camino = rutas[(e, p)]["camino"]
            caminata = (len(camino) - 1) * METROS_POR_CELDA / VELOCIDAD_M_S
            while n > 0:
                k = min(PERSONAS_POR_PUNTO, n)
                piso = ya * pisos // total  # 0 = planta baja
                sale = max(sale, piso * SEGUNDOS_POR_PISO) + k / TASA_PUERTA
                ya += k
                lista.append({"edificio": e, "punto": p, "camino": camino, "personas": k,
                              "sale": sale, "llega": sale + caminata})
                n -= k
    return lista


def tiempo_total(lista):
    return max((g["llega"] for g in lista), default=0)


def posicion(g, t):
    """Posición (fila, columna) del grupo en el segundo t, interpolando entre celdas; None si sigue adentro."""
    if t < g["sale"]:
        return None
    avance = (t - g["sale"]) * VELOCIDAD_M_S / METROS_POR_CELDA  # celdas recorridas
    camino = g["camino"]
    if avance >= len(camino) - 1 - 1e-9:  # tolerancia: llega/sale se calcularon con decimales
        return camino[-1]
    i, f = int(avance), avance - int(avance)
    (r0, c0), (r1, c1) = camino[i], camino[i + 1]
    return (r0 + (r1 - r0) * f, c0 + (c1 - c0) * f)


def conteo(lista, t):
    """Personas dentro de los edificios, caminando y ya en el punto de reunión en el segundo t."""
    dentro = sum(g["personas"] for g in lista if t < g["sale"])
    llegaron = sum(g["personas"] for g in lista if t >= g["llega"])
    return dentro, sum(g["personas"] for g in lista) - dentro - llegaron, llegaron


def curva_llegadas(lista, puntos, pasos=60):
    """Personas acumuladas en cada punto de reunión a lo largo del tiempo (para la gráfica)."""
    total = tiempo_total(lista)
    filas = []
    for k in range(pasos + 1):
        t = total * k / pasos
        fila = {"Minuto": round(t / 60, 2)}
        for p in puntos:
            fila[p] = sum(g["personas"] for g in lista if g["punto"] == p and t >= g["llega"])
        filas.append(fila)
    return filas


if __name__ == "__main__":
    import plan_evacuacion as pe

    pl = pe.plan("E2", "Biblioteca", 1.5)
    lista = grupos(pl["optimo"], pl["rutas"])
    total = sum(n for _, _, n in pl["optimo"])
    T = tiempo_total(lista)
    # Autoverificación: nadie se pierde, todos llegan después de salir y al final todos están en su punto
    assert sum(g["personas"] for g in lista) == total
    assert all(g["llega"] >= g["sale"] > 0 for g in lista)
    assert conteo(lista, 0) == (total, 0, 0)
    assert conteo(lista, T) == (0, 0, total)
    assert all(posicion(g, T) == g["camino"][-1] for g in lista)
    print(f"{len(lista)} grupos, {total:,} personas. Tiempo total de evacuación: {T / 60:.1f} min")
