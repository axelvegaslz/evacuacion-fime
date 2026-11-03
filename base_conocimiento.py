"""
Base de conocimiento del Sistema Experto de Rutas de Evacuación del campus FIME (UANL).

Contiene:
- Los edificios del campus, su ocupación, número de pisos, riesgo químico y los puntos de reunión.
- Los niveles de contingencia oficiales y el directorio de emergencias externo.
- Las situaciones de emergencia (soluciones que entrega el sistema), su protocolo y brigadas.
- Las preguntas que el sistema hace al usuario.
- El árbol de decisión.
- La base de reglas SI-ENTONCES con factor de certeza (CF).

Fuente oficial: Plan de Contingencia FIME 2023 (en adelante, "el Plan"). Los protocolos
resumen sus procedimientos; en un caso real se siguen el Plan y las indicaciones de la UIRI
y de Protección Civil.
"""

# ---------------------------------------------------------------------------
# Campus FIME: edificios, ocupación estimada y puntos de reunión
# La geometría está en plano.py. La ocupación es una estimación en hora pico
# y se puede ajustar con datos reales.
# apoyo = personas que requieren apoyo de un brigadista (movilidad reducida)
# pisos = Tabla 1 del Plan (Niveles de construcción). E5, E12, Cafetería y Dirección
#         no aparecen en la tabla: se suponen de 1 piso.
# ---------------------------------------------------------------------------
from plano import CELDAS_EDIFICIO, CELDAS_PUNTO, PUERTAS

_DATOS = {
    "Edificio 1": (400, 1, 2, "Sector oriente-sur", "Aulas 1, Subdirección Administrativa"),
    "Edificio 2": (500, 3, 2, "Sector oriente-sur", "Aulas 2, Subdirección Académica, Auditorio Jorge Urencio"),
    "Edificio 3": (400, 0, 2, "Sector centro", "Aulas 3"),
    "Edificio 4": (450, 1, 1, "Sector norte", "Aulas 4, Coordinación de Administración y Sistemas"),
    "Edificio 5": (250, 0, 1, "Sector centro", "Coordinación de la División de Mecánica"),
    "Edificio 6": (300, 1, 2, "Sector centro", "División de Ciencias Básicas, Auditorio René M. Montante"),
    "Edificio 7": (450, 2, 1, "Sector poniente", "Coordinación de la División de Ingeniería Eléctrica"),
    "Edificio 8": (200, 0, 1, "Sector norte", "Laboratorios de Ingeniería Térmica, Servicios Generales"),
    "Edificio 9": (150, 0, 2, "Sector oriente-sur", "CEDAI, Prefectura, Centro de Calidad"),
    "Edificio 11": (120, 2, 2, "Sector oriente-sur", "Desarrollo Estudiantil, Servicios Médicos"),
    "Edificio 12": (150, 0, 1, "Sector norte", "Edificio 12"),
    "CIDET": (200, 0, 3, "Sector poniente", "Centro de Investigación y Desarrollo Tecnológico"),
    "Biblioteca": (250, 2, 2, "Sector norte", "Biblioteca Ing. Guadalupe E. Cedillo Garza"),
    "Cafetería": (300, 1, 1, "Sector centro", "Cafetería & Snack FIME"),
    "Dirección": (120, 0, 1, "Sector oriente-sur", "Dirección, Escolar y Archivo, Tesorería"),
    "Centro de Competitividad": (80, 0, 2, "Sector oriente-sur", "Centro de Competitividad y Productividad (CCPI)"),
}

# Atlas de Riesgo Interno del Plan (6.1): edificios con riesgo químico.
# LIITE (químico) y el Centro Cultural (biológico) no están en el mapa del sistema.
RIESGO_QUIMICO = {"Edificio 5", "Edificio 7", "Edificio 8", "Edificio 9", "CIDET"}

ZONAS = {
    n: {"ocupacion": o, "apoyo": a, "pisos": p, "sector": s, "descripcion": d,
        "quimico": n in RIESGO_QUIMICO, "puerta": PUERTAS[n], "celdas": CELDAS_EDIFICIO[n]}
    for n, (o, a, p, s, d) in _DATOS.items()
}

PUNTOS_REUNION = {n: {"celdas": c} for n, c in CELDAS_PUNTO.items()}

# ---------------------------------------------------------------------------
# Niveles de contingencia del Plan (sección 5)
# ---------------------------------------------------------------------------
CONTINGENCIA = {
    0: {"nombre": "Sin contingencia", "descripcion": "No hay una situación de riesgo identificada."},
    1: {"nombre": "Nivel 1",
        "descripcion": "No pone en riesgo a las personas ni a las instalaciones y se controla fácilmente. "
                       "El Secretario Ejecutivo decide si llama a alguna brigada."},
    2: {"nombre": "Nivel 2",
        "descripcion": "Afecta un área específica y la controlan las brigadas de FIME. Se avisa a toda la "
                       "comunidad que esté preparada para evacuar si se requiere."},
    3: {"nombre": "Nivel 3",
        "descripcion": "Pone en riesgo la vida de las personas y las instalaciones. Se activan todas las "
                       "brigadas, se pide apoyo externo, se instala un Puesto de Mando y se evacúa parcial "
                       "o totalmente."},
}

# Directorio de emergencias externo del Plan (9.4.2)
DIRECTORIO = [
    ("Centro Federal de Emergencias", "911"),
    ("Protección Civil de San Nicolás", "81-8383-9568 / 81-2556-9360"),
    ("Bomberos", "81-2556-9360"),
    ("Cruz Roja de San Nicolás", "81-1477-1450"),
    ("Protección Civil del Estado de NL", "81-8343-5634"),
    ("Policía y Tránsito de San Nicolás", "81-8158-1313"),
    ("Conmutador FIME", "81-8329-4020"),
]

# Brigadas de la Unidad Interna de Respuesta Inmediata (UIRI)
EVAC, PA, INC, BR = "Evacuación", "Primeros auxilios", "Combate contra incendio", "Búsqueda y rescate"

# ---------------------------------------------------------------------------
# Situaciones de emergencia (soluciones del sistema)
#   contingencia: nivel oficial del Plan (1, 2 o 3)
#   bloqueo:   radio (celdas) alrededor del incidente que no se puede cruzar
#   riesgo:    radio con humo / peligro (se puede cruzar, pero cuesta más)
#   penal:     costo extra por cada celda de riesgo
#   cierre:    se cierran las salidas a esta distancia o menos del incidente
#   zona:      True si hay que indicar dónde ocurre
#   quimico:   True si el riesgo crece cuando ocurre en un edificio con riesgo químico
#   fuente:    sección del Plan de donde sale el protocolo
# ---------------------------------------------------------------------------
SITUACIONES = {
    "E1": {"nombre": "Conato de incendio", "evacuar": True, "nivel": "Parcial (zona afectada y contiguas)",
           "contingencia": 2, "zona": True, "bloqueo": 0, "riesgo": 3, "penal": 4, "cierre": 3, "gravedad": 2,
           "quimico": True, "brigadas": [INC, EVAC], "fuente": "8.5 Procedimiento contra incendio",
           "acciones": ["Dar la voz de alarma y avisar al brigadista del piso",
                        "Solo si está capacitado, descargar el extintor a 3 m en forma de vaivén",
                        "Si el fuego es eléctrico, no usar agua",
                        "El brigadista activa la alarma y avisa al Secretario Ejecutivo",
                        "Si el fuego no se controla, pasar a evacuación total"]},
    "E2": {"nombre": "Incendio declarado", "evacuar": True, "nivel": "Total",
           "contingencia": 3, "zona": True, "bloqueo": 2, "riesgo": 6, "penal": 8, "cierre": 6, "gravedad": 3,
           "quimico": True, "brigadas": [INC, EVAC, PA, BR], "fuente": "8.5 Procedimiento contra incendio",
           "acciones": ["Activar la alarma y llamar a Bomberos / 911",
                        "Salir por la puerta más alejada del fuego; no usar elevadores",
                        "Con humo, avanzar a rastras y taparse nariz y boca con un trapo húmedo",
                        "Tocar la manija antes de abrir: si está caliente, no abrir",
                        "Informar a Bomberos si hay personas atrapadas y no regresar"]},
    "E3": {"nombre": "Sismo en curso", "evacuar": False, "nivel": "Repliegue",
           "contingencia": 3, "zona": False, "bloqueo": 0, "riesgo": 0, "penal": 0, "cierre": 0, "gravedad": 3,
           "quimico": False, "brigadas": [EVAC, BR],
           "fuente": "8.7 Procedimiento para terremotos o fallas estructurales",
           "acciones": ["Protegerse de inmediato; no intentar salir durante el temblor",
                        "Replegarse lejos de ventanas, junto a columnas o muros de carga",
                        "Cuando el temblor se detenga, evacuar de inmediato"]},
    "E4": {"nombre": "Después de un sismo", "evacuar": True, "nivel": "Total",
           "contingencia": 3, "zona": False, "bloqueo": 0, "riesgo": 0, "penal": 0, "cierre": 0, "gravedad": 2,
           "quimico": False, "brigadas": [EVAC, BR, PA],
           "fuente": "8.7 Procedimiento para terremotos o fallas estructurales",
           "acciones": ["Evacuar de inmediato siguiendo el Plan General de Evacuación",
                        "Alejarse de fachadas, vidrios y cables; no usar la Plaza central",
                        "Dar de baja los servicios del edificio dañado",
                        "No entrar hasta que el Secretario Ejecutivo libere el edificio"]},
    "E5": {"nombre": "Fuga de gas", "evacuar": True, "nivel": "Total",
           "contingencia": 3, "zona": True, "bloqueo": 2, "riesgo": 6, "penal": 8, "cierre": 6, "gravedad": 3,
           "quimico": False, "brigadas": [EVAC, INC], "fuente": "8.5 y 8.10 (riesgo de explosión)",
           "acciones": ["No accionar interruptores ni usar flamas o aparatos eléctricos",
                        "Cortar el suministro de gas solo si es seguro",
                        "Evacuar sin correr; no usar elevadores",
                        "Llamar al 911 desde fuera del edificio"]},
    "E6": {"nombre": "Amenaza de bomba o paquete sospechoso", "evacuar": True, "nivel": "Total",
           "contingencia": 3, "zona": True, "bloqueo": 2, "riesgo": 8, "penal": 6, "cierre": 9, "gravedad": 3,
           "quimico": False, "brigadas": [EVAC, BR],
           "fuente": "8.8 Amenaza de bomba y 8.9 Protocolo de artefacto explosivo",
           "acciones": ["No tocar ni mover el objeto sospechoso",
                        "Avisar al supervisor; el Secretario Ejecutivo de la UIRI avisa a las autoridades (911)",
                        "Si la amenaza es válida, el Coordinador de Emergencias ordena evacuar",
                        "Regresar solo cuando las autoridades y la UIRI liberen el edificio"]},
    "E7": {"nombre": "Alarma sin causa identificada", "evacuar": True, "nivel": "Preventiva",
           "contingencia": 2, "zona": False, "bloqueo": 0, "riesgo": 0, "penal": 0, "cierre": 0, "gravedad": 1,
           "quimico": False, "brigadas": [EVAC], "fuente": "8.10 Procedimiento de evacuación",
           "acciones": ["Apagar el equipo y dirigirse a la salida más cercana",
                        "Esperar la señal del brigadista; no usar elevadores",
                        "Pasar lista en el punto de reunión",
                        "Regresar solo cuando se autorice"]},
    "E8": {"nombre": "Explosión", "evacuar": True, "nivel": "Total",
           "contingencia": 3, "zona": True, "bloqueo": 3, "riesgo": 8, "penal": 8, "cierre": 8, "gravedad": 3,
           "quimico": True, "brigadas": [INC, BR, PA, EVAC],
           "fuente": "8.9 Protocolo de artefacto explosivo",
           "acciones": ["Tirarse al piso junto a una pared y no asomarse por ventanas",
                        "Los heridos esperan en su lugar y hacen ruido para ser localizados",
                        "Evacuar cuando lo indique la brigada; no acercarse al sitio de la explosión",
                        "Llamar al 911 y respetar el cerco de las autoridades"]},
    "E9": {"nombre": "Falla estructural", "evacuar": True, "nivel": "Parcial (edificio afectado y contiguos)",
           "contingencia": 3, "zona": True, "bloqueo": 2, "riesgo": 4, "penal": 6, "cierre": 4, "gravedad": 3,
           "quimico": True, "brigadas": [EVAC, BR, PA],
           "fuente": "8.7 Procedimiento para terremotos o fallas estructurales",
           "acciones": ["Evacuar el edificio de inmediato: el daño puede provocar un derrumbe",
                        "Alejarse de fachadas y vidrios del edificio dañado",
                        "Dar de baja los servicios (luz, gas, agua) del edificio",
                        "No entrar hasta que el Secretario Ejecutivo libere el edificio"]},
    "E10": {"nombre": "Derrame de sustancia química", "evacuar": True, "nivel": "Parcial (edificio afectado)",
            "contingencia": 2, "zona": True, "bloqueo": 1, "riesgo": 4, "penal": 6, "cierre": 4, "gravedad": 2,
            "quimico": True, "brigadas": [EVAC, PA],
            "fuente": "8.12 Respuesta ante derrame de sustancias químicas",
            "acciones": ["Alertar a las personas cercanas y aislar el área",
                         "Acordonar con la cinta del kit antiderrames",
                         "Solo personal capacitado usa el kit antiderrames con EPP",
                         "Notificar a la Subdirección de Desarrollo Sostenible (Edificio 1, ext. 1621)"]},
    "E11": {"nombre": "Lluvia torrencial o vientos fuertes", "evacuar": False,
            "nivel": "Resguardo dentro del edificio", "contingencia": 2,
            "zona": False, "bloqueo": 0, "riesgo": 0, "penal": 0, "cierre": 0, "gravedad": 2,
            "quimico": False, "brigadas": [EVAC, PA],
            "fuente": "8.11 Respuesta ante riesgos hidrometeorológicos",
            "acciones": ["Permanecer dentro del edificio, lejos de ventanas",
                         "Desconectar luz y gas si hay agua en el área",
                         "No cruzar zonas inundadas ni acercarse a árboles, postes o cables",
                         "Evacuar solo si lo indican las autoridades"]},
    "E12": {"nombre": "Robo con violencia", "evacuar": False, "nivel": "Resguardo (no evacuar)",
            "contingencia": 2, "zona": False, "bloqueo": 0, "riesgo": 0, "penal": 0, "cierre": 0, "gravedad": 2,
            "quimico": False, "brigadas": [PA],
            "fuente": "8.4 Procedimiento ante robo con violencia",
            "acciones": ["Mantener la calma y obedecer al asaltante; no oponer resistencia",
                         "Avisar a Seguridad y Vigilancia solo cuando el asaltante se haya retirado",
                         "Revisar si hay heridos",
                         "Asegurar el área y no comentar detalles hasta que llegue la policía"]},
    "E0": {"nombre": "Sin emergencia confirmada", "evacuar": False, "nivel": "Ninguna",
           "contingencia": 0, "zona": False, "bloqueo": 0, "riesgo": 0, "penal": 0, "cierre": 0, "gravedad": 0,
           "quimico": False, "brigadas": [], "fuente": "—",
           "acciones": ["Mantener la calma",
                        "Reportar a seguridad cualquier anomalía"]},
}

# ---------------------------------------------------------------------------
# Preguntas
# ---------------------------------------------------------------------------
SI_NO = [("Sí", True), ("No", False)]

PREGUNTAS = {
    "humo": {"texto": "¿Hay humo o fuego visible?", "corta": "¿Humo o fuego?"},
    "explosion": {"texto": "¿Hubo una explosión?", "corta": "¿Explosión?"},
    "controlable": {"texto": "¿El fuego es pequeño y se puede controlar con un extintor?",
                    "corta": "¿Fuego pequeño y\\ncontrolable?"},
    "movimiento": {"texto": "¿Se siente movimiento o vibración fuerte del edificio?",
                   "corta": "¿Movimiento del\\nedificio?"},
    "sigue": {"texto": "¿El movimiento continúa en este momento?", "corta": "¿Sigue el\\nmovimiento?"},
    "instalacion": {"texto": "¿Hay un problema en las instalaciones: olor a gas, derrame químico o daño "
                             "en la estructura?", "corta": "¿Gas, químico o\\ndaño estructural?"},
    "gas": {"texto": "¿Hay olor a gas?", "corta": "¿Olor a gas?"},
    "quimico": {"texto": "¿Se derramó una sustancia química? (No = grietas o daño en la estructura)",
                "corta": "¿Derrame\\nquímico?"},
    "seguridad": {"texto": "¿Hay un problema de seguridad: amenaza de bomba, paquete sospechoso o robo?",
                  "corta": "¿Amenaza\\no robo?"},
    "amenaza": {"texto": "¿Es una amenaza de bomba o un paquete sospechoso? (No = robo con violencia)",
                "corta": "¿Amenaza o paquete\\nsospechoso?"},
    "clima": {"texto": "¿Hay lluvia torrencial, inundación o vientos fuertes (más de 60 km/h)?",
              "corta": "¿Lluvia torrencial\\no vientos?"},
    "alarma": {"texto": "¿Está sonando la alarma del edificio?", "corta": "¿Suena la alarma?"},
}
for _p in PREGUNTAS.values():
    _p["opciones"] = SI_NO


def etiqueta_valor(clave, valor):
    for etiqueta, v in PREGUNTAS[clave]["opciones"]:
        if v == valor:
            return etiqueta
    return str(valor)


# ---------------------------------------------------------------------------
# Árbol de decisión
# ---------------------------------------------------------------------------
def _si_no(nid, pregunta, si, no):
    return {"id": nid, "pregunta": pregunta, "ramas": {True: si, False: no}}


ARBOL = _si_no(
    "N1", "humo",
    _si_no("N2", "explosion",
           {"id": "H1", "situacion": "E8"},
           _si_no("N3", "controlable", {"id": "H2", "situacion": "E1"}, {"id": "H3", "situacion": "E2"})),
    _si_no("N4", "movimiento",
           _si_no("N5", "sigue", {"id": "H4", "situacion": "E3"}, {"id": "H5", "situacion": "E4"}),
           _si_no("N6", "instalacion",
                  _si_no("N7", "gas", {"id": "H6", "situacion": "E5"},
                         _si_no("N8", "quimico", {"id": "H7", "situacion": "E10"}, {"id": "H8", "situacion": "E9"})),
                  _si_no("N9", "seguridad",
                         _si_no("N10", "amenaza", {"id": "H9", "situacion": "E6"}, {"id": "H10", "situacion": "E12"}),
                         _si_no("N11", "clima", {"id": "H11", "situacion": "E11"},
                                _si_no("N12", "alarma", {"id": "H12", "situacion": "E7"},
                                       {"id": "H13", "situacion": "E0"}))))),
)

# ---------------------------------------------------------------------------
# Base de reglas con factor de certeza
# Algunas reglas concluyen riesgos secundarios (p. ej. incendio tras un sismo).
# ---------------------------------------------------------------------------
_SIN = {"humo": False, "movimiento": False}  # rama sin humo ni sismo
_INST = {**_SIN, "instalacion": True}
_OTRO = {**_SIN, "instalacion": False}

REGLAS_BASE = [
    {"id": "R1", "si": {"humo": True, "controlable": True}, "entonces": "E1", "cf": 0.85},
    {"id": "R2", "si": {"humo": True, "controlable": False}, "entonces": "E2", "cf": 0.90},
    {"id": "R3", "si": {"humo": False, "movimiento": True, "sigue": True}, "entonces": "E3", "cf": 0.90},
    {"id": "R4", "si": {"humo": False, "movimiento": True, "sigue": False}, "entonces": "E4", "cf": 0.85},
    {"id": "R5", "si": {"movimiento": True, "sigue": False}, "entonces": "E2", "cf": 0.20},
    {"id": "R6", "si": {**_INST, "gas": True}, "entonces": "E5", "cf": 0.90},
    {"id": "R7", "si": {"gas": True}, "entonces": "E2", "cf": 0.25},
    {"id": "R8", "si": {**_OTRO, "seguridad": True, "amenaza": True}, "entonces": "E6", "cf": 0.85},
    {"id": "R9", "si": {**_OTRO, "seguridad": False, "clima": False, "alarma": True}, "entonces": "E7", "cf": 0.70},
    {"id": "R10", "si": {"humo": True, "explosion": True}, "entonces": "E8", "cf": 0.90},
    {"id": "R11", "si": {"explosion": True}, "entonces": "E2", "cf": 0.60},
    {"id": "R12", "si": {"movimiento": True, "sigue": False}, "entonces": "E9", "cf": 0.30},
    {"id": "R13", "si": {**_INST, "gas": False, "quimico": True}, "entonces": "E10", "cf": 0.85},
    {"id": "R14", "si": {**_INST, "gas": False, "quimico": False}, "entonces": "E9", "cf": 0.80},
    {"id": "R15", "si": {**_OTRO, "seguridad": True, "amenaza": False}, "entonces": "E12", "cf": 0.80},
    {"id": "R16", "si": {**_OTRO, "seguridad": False, "clima": True}, "entonces": "E11", "cf": 0.80},
]


def regla_a_texto(regla):
    condiciones = " Y ".join(
        f"{PREGUNTAS[k]['corta'].replace(chr(92) + 'n', ' ')} = {etiqueta_valor(k, v)}"
        for k, v in regla["si"].items()
    )
    s = SITUACIONES[regla["entonces"]]["nombre"]
    return f"SI {condiciones} ENTONCES {regla['entonces']} ({s})"
