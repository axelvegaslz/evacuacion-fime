"""
Motor de inferencia del sistema experto de evacuación.

- recorrer_arbol: recorrido en profundidad (DFS) del árbol de decisión.
- encadenamiento_adelante: evalúa las reglas y combina factores de certeza (MYCIN).
- aprender: ajusta el CF de las reglas según la situación real confirmada
  por la brigada (simulación del aprendizaje).
"""
import copy
import json
import os

from base_conocimiento import ARBOL, PREGUNTAS, REGLAS_BASE, SITUACIONES, etiqueta_valor, regla_a_texto
from prioridad import merge_sort

RUTA_CF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reglas_aprendidas.json")


def cargar_reglas():
    reglas = copy.deepcopy(REGLAS_BASE)
    if os.path.exists(RUTA_CF):
        try:
            with open(RUTA_CF, encoding="utf-8") as f:
                cfs = json.load(f)
            for r in reglas:
                if r["id"] in cfs:
                    r["cf"] = cfs[r["id"]]
        except (OSError, json.JSONDecodeError):
            pass
    return reglas


def guardar_reglas(reglas):
    with open(RUTA_CF, "w", encoding="utf-8") as f:
        json.dump({r["id"]: r["cf"] for r in reglas}, f, indent=2)


def reiniciar_aprendizaje():
    if os.path.exists(RUTA_CF):
        os.remove(RUTA_CF)
    return copy.deepcopy(REGLAS_BASE)


def recorrer_arbol(respuestas):
    """Devuelve (camino, nodo_final) siguiendo las respuestas desde la raíz."""
    camino = []
    nodo = ARBOL
    while "pregunta" in nodo:
        camino.append(nodo)
        clave = nodo["pregunta"]
        if clave not in respuestas:
            return camino, nodo
        nodo = nodo["ramas"][respuestas[clave]]
    camino.append(nodo)
    return camino, nodo


def contar_nodos(nodo=ARBOL):
    """Recorrido completo del árbol (DFS) para contar preguntas y hojas."""
    if "situacion" in nodo:
        return 0, 1
    preguntas, hojas = 1, 0
    for hijo in nodo["ramas"].values():
        p, h = contar_nodos(hijo)
        preguntas += p
        hojas += h
    return preguntas, hojas


def encadenamiento_adelante(hechos, reglas, traza=None):
    """
    Dispara las reglas que se cumplen. Devuelve (ranking [(situación, cf)], disparadas).
    Si se pasa una lista en traza, se agrega (regla, cf_previo, cf_nuevo) por cada disparo.
    """
    disparadas = []
    certeza = {}
    for r in reglas:
        if all(k in hechos and hechos[k] == v for k, v in r["si"].items()):
            disparadas.append(r)
            s = r["entonces"]
            previo = certeza.get(s, 0.0)
            certeza[s] = previo + r["cf"] * (1 - previo)
            if traza is not None:
                traza.append((r, previo, certeza[s]))
    ranking = merge_sort(list(certeza.items()), lambda x: x[1])  # de mayor a menor certeza
    return ranking, disparadas


def explicar(hechos, reglas):
    """Traza legible: preguntas del árbol, reglas disparadas con su CF y por qué se elige la situación."""
    camino, hoja = recorrer_arbol(hechos)
    lineas = ["**1. Preguntas respondidas (recorrido del árbol de decisión)**"]
    for nodo in camino[:-1]:
        clave = nodo["pregunta"]
        lineas.append(f"- {nodo['id']} · {PREGUNTAS[clave]['texto']} → **{etiqueta_valor(clave, hechos[clave])}**")
    s = hoja["situacion"]
    lineas.append(f"- {hoja['id']} · Hoja del árbol: **{s} – {SITUACIONES[s]['nombre']}**")

    traza = []
    ranking, _ = encadenamiento_adelante(hechos, reglas, traza)
    lineas.append("\n**2. Reglas disparadas y combinación de certeza (MYCIN)**")
    for r, previo, nuevo in traza:
        lineas.append(f"- **{r['id']}** (CF {r['cf']:.2f}): {regla_a_texto(r)}")
        if previo == 0:
            lineas.append(f"    - certeza de {r['entonces']} = {nuevo:.2f}")
        else:
            lineas.append(f"    - certeza de {r['entonces']} = {previo:.2f} + {r['cf']:.2f} × (1 − {previo:.2f}) "
                          f"= {nuevo:.2f}")
    lineas.append(f"- {'Las otras' if traza else 'Las'} {len(reglas) - len(traza)} reglas no se dispararon: "
                  "al menos una de sus condiciones no se cumple con estas respuestas.")

    lineas.append("\n**3. Conclusión**")
    if not ranking:
        lineas.append(f"- Sin reglas aplicables, se toma la conclusión del árbol: **{s} – {SITUACIONES[s]['nombre']}**.")
        return lineas
    principal, cf = ranking[0]
    lineas.append(f"- Se elige **{principal} – {SITUACIONES[principal]['nombre']}** por tener la mayor "
                  f"certeza ({cf:.0%}).")
    if len(ranking) > 1:
        lineas.append("- Riesgos secundarios que también se vigilan: "
                      + ", ".join(f"{SITUACIONES[k]['nombre']} ({v:.0%})" for k, v in ranking[1:]) + ".")
    if principal != s:
        lineas.append(f"- El árbol llegó a {s}, pero por lo aprendido las reglas de {principal} "
                      "tienen ahora más certeza.")
    return lineas


def aprender(reglas, ids_disparadas, situacion_real, tasa=0.15):
    """
    acierto: cf = cf + tasa * (1 - cf)
    error:   cf = cf - tasa * cf
    """
    cambios = []
    for r in reglas:
        if r["id"] in ids_disparadas:
            antes = r["cf"]
            acierto = r["entonces"] == situacion_real
            nuevo = antes + tasa * (1 - antes) if acierto else antes - tasa * antes
            r["cf"] = round(min(max(nuevo, 0.05), 0.99), 3)
            cambios.append({"Regla": r["id"], "Concluye": r["entonces"],
                            "CF antes": round(antes, 3), "CF después": r["cf"],
                            "Resultado": "Acertó ↑" if acierto else "Falló ↓"})
    guardar_reglas(reglas)
    return cambios


def arbol_a_dot(ids_camino=()):
    ids_camino = set(ids_camino)
    lineas = ['digraph Arbol {', 'rankdir=LR; bgcolor="transparent";',
              'node [fontname="Helvetica", fontsize=10, style=filled];',
              'edge [fontname="Helvetica", fontsize=9];']

    def visitar(nodo):
        nid = nodo["id"]
        activo = nid in ids_camino
        if "pregunta" in nodo:
            etiqueta = PREGUNTAS[nodo["pregunta"]]["corta"]
            forma, relleno = "box", ("#FFCD11" if activo else "#E8EEF4")
        else:
            s = nodo["situacion"]
            etiqueta = f'{s}\\n{SITUACIONES[s]["nombre"]}'
            forma, relleno = "ellipse", ("#6CC24A" if activo else "#F4F4F4")
        lineas.append(f'{nid} [label="{etiqueta}", shape={forma}, fillcolor="{relleno}"];')
        for valor, hijo in nodo.get("ramas", {}).items():
            texto = etiqueta_valor(nodo["pregunta"], valor)
            estilo = ', penwidth=2.5, color="#C79A00"' if activo and hijo["id"] in ids_camino else ""
            lineas.append(f'{nid} -> {hijo["id"]} [label="{texto}"{estilo}];')
            visitar(hijo)

    visitar(ARBOL)
    lineas.append("}")
    return "\n".join(lineas)
