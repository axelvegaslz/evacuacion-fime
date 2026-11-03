"""
Orden de evacuación por edificios usando Merge Sort (implementación propia).

Con incidente localizado:
    El edificio donde ocurre el incidente siempre sale primero (puntaje 100).
    Puntaje = 100 * (0.5 * cercanía al peligro + 0.2 * ocupación + 0.1 * requiere apoyo
                     + 0.1 * pisos + 0.1 * riesgo químico)
Sin incidente localizado (sismo, alarma):
    Puntaje = 100 * (0.4 * ocupación + 0.3 * requiere apoyo + 0.15 * pisos + 0.15 * riesgo químico)

Pisos (Tabla 1 del Plan de Contingencia): más pisos = más tiempo para bajar, conviene empezar antes.
Riesgo químico (Atlas de Riesgo Interno): un incendio o sismo puede liberar sustancias peligrosas.
"""
from base_conocimiento import SITUACIONES, ZONAS
from busqueda import distancia_a_edificio
from plano import METROS_POR_CELDA


def merge_sort(lista, clave):
    """Ordena de mayor a menor según clave(elemento)."""
    if len(lista) <= 1:
        return list(lista)
    medio = len(lista) // 2
    izq = merge_sort(lista[:medio], clave)
    der = merge_sort(lista[medio:], clave)
    res, i, j = [], 0, 0
    while i < len(izq) and j < len(der):
        if clave(izq[i]) >= clave(der[j]):
            res.append(izq[i])
            i += 1
        else:
            res.append(der[j])
            j += 1
    res.extend(izq[i:])
    res.extend(der[j:])
    return res


def priorizar(codigo, zona_incidente=None):
    localizado = SITUACIONES[codigo]["zona"] and zona_incidente
    max_ocup = max(z["ocupacion"] for z in ZONAS.values())
    max_pisos = max(z["pisos"] for z in ZONAS.values())
    if localizado:
        distancias = {n: (0 if n == zona_incidente else distancia_a_edificio(z["puerta"], zona_incidente))
                      for n, z in ZONAS.items()}
        max_d = max(distancias.values()) or 1
    evaluadas = []
    for nombre, z in ZONAS.items():
        ocup = z["ocupacion"] / max_ocup
        apoyo = 1 if z["apoyo"] > 0 else 0
        pisos = (z["pisos"] - 1) / (max_pisos - 1)
        quimico = 1 if z["quimico"] else 0
        if localizado:
            cercania = 1 - distancias[nombre] / max_d
            if nombre == zona_incidente:
                puntaje = 100
            else:
                puntaje = 100 * (0.5 * cercania + 0.2 * ocup + 0.1 * apoyo + 0.1 * pisos + 0.1 * quimico)
            dist_txt = str(distancias[nombre] * METROS_POR_CELDA)
        else:
            puntaje = 100 * (0.4 * ocup + 0.3 * apoyo + 0.15 * pisos + 0.15 * quimico)
            dist_txt = "—"
        evaluadas.append({"Edificio": nombre, "Sector": z["sector"], "Ocupantes": z["ocupacion"],
                          "Requieren apoyo": z["apoyo"], "Pisos": z["pisos"],
                          "Riesgo químico": "Sí" if z["quimico"] else "No",
                          "Distancia al peligro (m)": dist_txt, "Puntaje": round(puntaje, 1)})
    ordenadas = merge_sort(evaluadas, lambda x: x["Puntaje"])
    for i, e in enumerate(ordenadas, start=1):
        e["Orden"] = i
    return ordenadas
