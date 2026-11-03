"""
Plano del campus FIME (UANL) convertido en una cuadrícula para las búsquedas.

Las coordenadas están en píxeles de la imagen assets/mapa_fime.png (900 x 1081).
La imagen es el mapa original (assets/mapa_fime_original.png, 900 x 736) con una franja de
345 px arriba dibujada con datos de OpenStreetMap (cancha de fútbol, Polideportivo, campo de
béisbol); por eso todas las coordenadas y del mapa original están desplazadas 345 px.
Cada celda mide CELDA x CELDA píxeles. Una celda es transitable si su centro
no cae dentro de ningún edificio.

Escala: 1 celda ≈ 4 m (≈ 0.27 m por píxel). Se obtuvo de dos fuentes que coinciden:
- Plan de Contingencia FIME 2023 (1.8): el conjunto mide 213 x 225 m; de E7 a E3 hay 755 px → 0.28 m/px.
- OpenStreetMap: ajustando los centros de 10 edificios de FIME contra su posición en el mapa → 0.26 m/px.
"""
IMG_ANCHO, IMG_ALTO = 900, 1081
CELDA = 15
COLUMNAS = IMG_ANCHO // CELDA          # 60
FILAS = IMG_ALTO // CELDA              # 72
METROS_POR_CELDA = 4

# ---------------------------------------------------------------------------
# Edificios de FIME: lista de rectángulos (x0, y0, x1, y1) y puerta (x, y)
# ---------------------------------------------------------------------------
EDIFICIOS_PLANO = {
    "Edificio 1": {"rects": [(580, 888, 748, 927)], "puerta": (660, 937)},
    "Edificio 2": {"rects": [(490, 775, 840, 815)], "puerta": (700, 765)},
    "Edificio 3": {"rects": [(585, 610, 840, 655)], "puerta": (660, 667)},
    "Edificio 4": {"rects": [(555, 423, 690, 557)], "puerta": (620, 570)},
    "Edificio 5": {"rects": [(285, 697, 407, 895)], "puerta": (420, 795)},
    "Edificio 6": {"rects": [(310, 575, 425, 675)], "puerta": (370, 688)},
    "Edificio 7": {"rects": [(92, 687, 272, 893), (205, 890, 250, 917), (85, 915, 250, 995)],
                   "puerta": (278, 795)},
    "Edificio 8": {"rects": [(140, 423, 180, 625), (180, 500, 260, 590)], "puerta": (272, 555)},
    "Edificio 9": {"rects": [(735, 685, 790, 730), (785, 647, 840, 775)], "puerta": (722, 710)},
    "Edificio 11": {"rects": [(715, 823, 822, 885)], "puerta": (702, 855)},
    "Edificio 12": {"rects": [(190, 423, 340, 493)], "puerta": (300, 505)},
    "CIDET": {"rects": [(285, 895, 475, 997)], "puerta": (380, 1010)},
    "Biblioteca": {"rects": [(385, 423, 520, 530)], "puerta": (452, 543)},
    "Cafetería": {"rects": [(425, 728, 605, 775)], "puerta": (515, 717)},
    "Dirección": {"rects": [(475, 885, 560, 1010)], "puerta": (572, 945)},
    "Centro de Competitividad": {"rects": [(750, 890, 840, 1005)], "puerta": (738, 945)},
}

# Otras construcciones que bloquean el paso (no se evacuan en el sistema)
OBSTACULOS = [
    (40, 385, 140, 480),     # Laboratorios de investigación
    (0, 480, 70, 625),      # CFM
    (310, 515, 380, 545),   # construcciones junto a la biblioteca
    (378, 194, 560, 395),   # Polideportivo FIME (OpenStreetMap)
    (360, 0, 725, 180),     # Estadio Gaspar Mass: recinto cercado, no es de FIME (OpenStreetMap)
    (745, 0, 900, 105),     # edificios al noreste, fuera de FIME (OpenStreetMap)
]

# Puntos de reunión (áreas abiertas). Los dos primeros son las canchas reales de FIME
# (Atlas de Riesgo Interno del Plan de Contingencia, geometría de OpenStreetMap);
# los otros cuatro son propuestos por el equipo.
PUNTOS_PLANO = {
    "Cancha de fútbol": (165, 20, 345, 395),
    "Campo de béisbol": (640, 195, 815, 375),
    "Campo sintético": (715, 415, 830, 540),
    "Plaza central": (450, 560, 540, 635),
    "Estacionamiento": (95, 633, 300, 680),
    "Jardín del Oso": (590, 945, 740, 1030),
}


def a_celda(x, y):
    return (int(y // CELDA), int(x // CELDA))


def centro_px(celda):
    r, c = celda
    return (c * CELDA + CELDA / 2, r * CELDA + CELDA / 2)


def _dentro(px, rect):
    x, y = px
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def _celdas_de(rects):
    celdas = set()
    for r in range(FILAS):
        for c in range(COLUMNAS):
            if any(_dentro(centro_px((r, c)), rc) for rc in rects):
                celdas.add((r, c))
    return celdas


CELDAS_EDIFICIO = {n: _celdas_de(e["rects"]) for n, e in EDIFICIOS_PLANO.items()}
CELDAS_OBSTACULO = _celdas_de(OBSTACULOS)
OCUPADAS = set().union(*CELDAS_EDIFICIO.values(), CELDAS_OBSTACULO)

# Matriz base: True = transitable
TRANSITABLE = [[(r, c) not in OCUPADAS for c in range(COLUMNAS)] for r in range(FILAS)]


def _mas_cercana_libre(celda):
    if TRANSITABLE[celda[0]][celda[1]]:
        return celda
    mejor, dmin = None, 10 ** 9
    for r in range(FILAS):
        for c in range(COLUMNAS):
            if TRANSITABLE[r][c]:
                d = abs(r - celda[0]) + abs(c - celda[1])
                if d < dmin:
                    mejor, dmin = (r, c), d
    return mejor


PUERTAS = {n: _mas_cercana_libre(a_celda(*e["puerta"])) for n, e in EDIFICIOS_PLANO.items()}
CELDAS_PUNTO = {n: {c for c in _celdas_de([rect]) if c not in OCUPADAS}
                for n, rect in PUNTOS_PLANO.items()}
