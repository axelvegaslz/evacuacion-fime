"""
Demostración en consola (sin interfaz) de todos los módulos.
Uso:  python demo_consola.py
"""
from base_conocimiento import SITUACIONES, regla_a_texto
import busqueda as bq
import flujo as fl
import motor_inferencia as mi
import prioridad as pr


def linea(titulo):
    print("\n" + "=" * 72 + f"\n{titulo}\n" + "=" * 72)


linea("1. IDENTIFICACIÓN DE LA EMERGENCIA (árbol + reglas)")
reglas = mi.cargar_reglas()
casos = {
    "Humo, fuego no controlable": {"humo": True, "explosion": False, "controlable": False},
    "Terminó el sismo": {"humo": False, "movimiento": True, "sigue": False},
    "Olor a gas": {"humo": False, "movimiento": False, "instalacion": True, "gas": True},
    "Explosión": {"humo": True, "explosion": True},
}
for nombre, hechos in casos.items():
    camino, hoja = mi.recorrer_arbol(hechos)
    ranking, disparadas = mi.encadenamiento_adelante(hechos, reglas)
    print(f"\nCaso: {nombre}")
    print("  Camino:", " -> ".join(n["id"] for n in camino))
    for r in disparadas:
        print("  Regla:", regla_a_texto(r), f"[CF={r['cf']}]")
    for s, cf in ranking:
        print(f"  -> {s} {SITUACIONES[s]['nombre']}: certeza {cf:.2f}")
p, h = mi.contar_nodos()
print(f"\nEl árbol tiene {p} preguntas y {h} hojas.")

linea("2. RUTA DE EVACUACIÓN — Incendio en Edificio 6, salen del Edificio 7")
esc, res = bq.comparar("E2", "Edificio 6", "Edificio 7")
print("Puntos de reunión cerrados:", ", ".join(esc["cerrados"]) or "ninguno")
for r in res:
    print(f"  {r['algoritmo']:15} explorados={r['nodos_explorados']:4}  pasos={r['pasos']:3}  "
          f"costo={r['costo']:4}  celdas de riesgo={r['celdas_riesgo']:2}  "
          f"punto={r['punto']:16} óptima={r['optima']}")

linea("3. CAPACIDAD DE EVACUACIÓN (flujo máximo)")
print(f"Ocupantes estimados: {fl.OCUPACION_TOTAL}")
for cerradas in ([], ["Plaza central"], ["Plaza central", "Estacionamiento"]):
    f, _ = fl.flujo_maximo(cerradas)
    print(f"  Cerradas: {', '.join(cerradas) or 'ninguna':35}  flujo={f} personas/min  "
          f"tiempo={fl.tiempo_evacuacion(cerradas)} min")

linea("4. ORDEN DE EVACUACIÓN (Merge Sort) — Incendio en Edificio 6")
for e in pr.priorizar("E2", "Edificio 6")[:6]:
    print(f"  #{e['Orden']:2} {e['Edificio']:25} ocupantes={e['Ocupantes']:3} "
          f"distancia={e['Distancia al peligro (m)']} m  puntaje={e['Puntaje']}")
