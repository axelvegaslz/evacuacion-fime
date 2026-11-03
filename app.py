"""
Sistema Experto de Rutas de Evacuación — Campus FIME (UANL).
Interfaz en Streamlit.

Ejecutar:  streamlit run app.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.animation import FuncAnimation

from base_conocimiento import (ARBOL, CONTINGENCIA, DIRECTORIO, PREGUNTAS, PUNTOS_REUNION, SITUACIONES, ZONAS,
                                regla_a_texto)
import benchmark as bm
import busqueda as bq
import flujo as fl
import motor_inferencia as mi
import plan_evacuacion as pe
import plano
import prioridad as pr
import simulacion as sim

st.set_page_config(page_title="Evacuación FIME", page_icon="🚨", layout="wide")

LISTA_EDIF = list(ZONAS)
LISTA_SIT = list(SITUACIONES)
LISTA_PUNTOS = list(PUNTOS_REUNION)
RUTA_MAPA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "mapa_fime.png")


@st.cache_resource
def imagen_mapa():
    return plt.imread(RUTA_MAPA)


def celda_rect(ax, celda, color, alpha):
    r, c = celda
    C = plano.CELDA
    ax.add_patch(patches.Rectangle((c * C, r * C), C, C, color=color, alpha=alpha, lw=0))


COLORES_PUNTO = dict(zip(LISTA_PUNTOS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8e44ad", "#d81b60"]))


def mapa_base_plan(ax, cap, zona_inc, textos):
    """Mapa en gris (para que resalten los colores), puntos de reunión, incidente y etiquetas de los puntos."""
    ax.imshow(imagen_mapa()[..., :3].mean(axis=2), cmap="gray", vmin=-0.6, vmax=1)
    for nombre, punto in PUNTOS_REUNION.items():
        for celda in punto["celdas"]:
            celda_rect(ax, celda, COLORES_PUNTO[nombre] if nombre in cap else "#9E9E9E", 0.35)
        xs = [plano.centro_px(c)[0] for c in punto["celdas"]]
        ys = [plano.centro_px(c)[1] for c in punto["celdas"]]
        ax.text(sum(xs) / len(xs), sum(ys) / len(ys), textos[nombre] if nombre in cap else f"✕ {nombre}\ncerrado",
                ha="center", va="center", fontsize=7, fontweight="bold", color="#1F1F1F", zorder=5,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.85, lw=0))
    if zona_inc:
        for (x1, y1, x2, y2) in plano.EDIFICIOS_PLANO[zona_inc]["rects"]:
            ax.add_patch(patches.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec="#CC0000", lw=2.5, ls="--"))
    ax.set_xlim(0, plano.IMG_ANCHO)
    ax.set_ylim(plano.IMG_ALTO, 0)
    ax.axis("off")


@st.cache_data(show_spinner="Generando la animación…")
def animacion_cache(codigo, incidente, m2_por_persona, optimo):
    """Animación (HTML con controles de reproducción) de las personas caminando a su punto de reunión."""
    pl = plan_cache(codigo, incidente, m2_por_persona)
    lista = sim.grupos(pl["optimo"] if optimo else pl["voraz"], pl["rutas"])
    total = sim.tiempo_total(lista)
    fig, ax = plt.subplots(figsize=(5.0, 6.0), dpi=80)
    mapa_base_plan(ax, pl["cap"], incidente, {p: p for p in PUNTOS_REUNION})
    puntos = ax.scatter([], [], s=16, edgecolors="white", linewidths=0.4, zorder=4)
    reloj = ax.text(10, 12, "", ha="left", va="top", fontsize=8, fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9, lw=0))
    celdas_punto = {p: list(v["celdas"]) for p, v in PUNTOS_REUNION.items()}
    tiempos = np.linspace(0, total, 80)

    def cuadro(k):
        t = tiempos[k]
        xy, col = [], []
        for i, g in enumerate(lista):
            pos = sim.posicion(g, t)
            if pos is None:
                continue
            if t >= g["llega"]:  # ya llegó: se acomoda dentro del área del punto de reunión
                celdas = celdas_punto[g["punto"]]
                pos = celdas[i % len(celdas)]
            xy.append((pos[1] * plano.CELDA + plano.CELDA / 2, pos[0] * plano.CELDA + plano.CELDA / 2))
            col.append(COLORES_PUNTO[g["punto"]])
        puntos.set_offsets(np.array(xy) if xy else np.empty((0, 2)))
        puntos.set_facecolors(col)
        dentro, caminando, llegaron = sim.conteo(lista, t)
        reloj.set_text(f"Tiempo {int(t // 60)}:{int(t % 60):02d}   En edificios: {dentro:,}   "
                       f"Caminando: {caminando:,}   En punto de reunión: {llegaron:,}")
        return puntos, reloj

    fig.tight_layout()
    anim = FuncAnimation(fig, cuadro, frames=len(tiempos), interval=150)
    with matplotlib.rc_context({"animation.frame_format": "jpeg"}):  # JPEG pesa ~4 veces menos que PNG
        html = anim.to_jshtml(default_mode="once")
    plt.close(fig)
    html = ('<style>img{max-width:100%;height:auto} input[type=range].anim-slider{width:100%}'
            '.anim-buttons button{width:30px}</style>'  # que quepa en pantalla de celular
            f'<div style="background:white;padding:6px;font-family:sans-serif">{html}</div>')  # controles legibles
    return html, sim.curva_llegadas(lista, list(pl["cap"])), total


@st.cache_data(show_spinner="Asignando edificios a puntos de reunión…")
def plan_cache(codigo, incidente, m2_por_persona):
    return pe.plan(codigo, incidente, m2_por_persona)


@st.cache_data(show_spinner="Corriendo todas las combinaciones de escenarios…")
def benchmark_cache():
    return bm.correr()


@st.cache_data(show_spinner="Calculando rutas…")
def comparar_cache(codigo, incidente, origen):
    return bq.comparar(codigo, incidente, origen)


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
for clave, valor in {"reglas": None, "emergencia": None, "intento": 0, "cambios": None}.items():
    if clave not in st.session_state:
        st.session_state[clave] = valor
if st.session_state.reglas is None:
    st.session_state.reglas = mi.cargar_reglas()


def nombre_sit(s):
    return f"{s} - {SITUACIONES[s]['nombre']}"


def mostrar_directorio(expandido=False):
    with st.expander("📞 Directorio de emergencias (Plan de Contingencia FIME, 9.4.2)", expanded=expandido):
        st.dataframe(pd.DataFrame(DIRECTORIO, columns=["Entidad", "Teléfono"]), hide_index=True, width="stretch")


def selector_emergencia(col_sit, col_zona, clave):
    em = st.session_state.emergencia
    sit_def = em["codigo"] if em else "E2"
    zona_def = em["zona"] if em and em["zona"] else "Edificio 6"
    codigo = col_sit.selectbox("Situación de emergencia", LISTA_SIT, index=LISTA_SIT.index(sit_def),
                               format_func=nombre_sit, key=f"sit_{clave}")
    zona = None
    if SITUACIONES[codigo]["zona"]:
        zona = col_zona.selectbox("¿En qué edificio ocurre?", LISTA_EDIF, index=LISTA_EDIF.index(zona_def),
                                  key=f"zona_{clave}")
    else:
        col_zona.caption("Esta situación afecta a todo el campus; no requiere edificio.")
    return codigo, zona


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
# Vista de celular: sin barra de Deploy, márgenes chicos y títulos más compactos.
st.markdown("""<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {display: none !important;}
.block-container {padding: 3rem 1rem 2rem !important;}
h1 {font-size: 1.6rem !important;} h2 {font-size: 1.35rem !important;} h3 {font-size: 1.15rem !important;}
[data-testid="stMetricValue"] {font-size: 1.4rem !important;}
[data-testid="stHorizontalBlock"]:has(> div [data-testid="stMetric"]) > div {min-width: calc(50% - 1rem) !important;}
[data-testid="stGraphVizChart"] {overflow-x: auto; background: white; border-radius: 8px;}  /* legible, se desliza de lado */
[data-testid="stGraphVizChart"] svg {max-width: none !important;}
</style>""", unsafe_allow_html=True)

st.sidebar.title("🚨 Evacuación FIME")
st.sidebar.caption("Sistema experto de rutas de evacuación del campus")
pagina = st.selectbox("🚨 Evacuación FIME — Módulo", [
    "1. Identificar emergencia",
    "2. Ruta de evacuación",
    "3. Orden de evacuación",
    "4. Capacidad de evacuación",
    "5. Base de conocimiento",
    "6. Benchmark de algoritmos",
    "7. Plan de evacuación del campus",
])
st.sidebar.divider()
st.sidebar.markdown(
    "**Técnicas aplicadas**\n"
    "- Árbol de decisión (recorrido DFS)\n"
    "- Reglas SI–ENTONCES con factor de certeza\n"
    "- BFS, DFS y Costo uniforme (exhaustiva)\n"
    "- Voraz y A* (heurística)\n"
    "- Merge Sort (ordenamiento)\n"
    "- Flujo máximo (Edmonds-Karp)\n"
    "- Flujo de costo mínimo (Bellman-Ford)\n"
    "- Aprendizaje por ajuste de certeza"
)
if st.session_state.emergencia:
    em = st.session_state.emergencia
    s_act = SITUACIONES[em["codigo"]]
    st.sidebar.error(f"**Emergencia activa:** {s_act['nombre']}"
                     + (f" en {em['zona']}" if em["zona"] else "")
                     + f"  \n**Contingencia:** {CONTINGENCIA[s_act['contingencia']]['nombre']}"
                     + ("  \nLlamar al **911**" if s_act["contingencia"] == 3 else ""))
st.sidebar.caption("Proyecto académico. Niveles de contingencia, protocolos, pisos, riesgo químico y directorio "
                   "vienen del Plan de Contingencia FIME 2023. Puntos de reunión, ocupación y capacidades son "
                   "estimaciones; en una emergencia real se sigue el Plan y las indicaciones de la UIRI.")


# ===========================================================================
# 1. IDENTIFICAR EMERGENCIA
# ===========================================================================
if pagina.startswith("1"):
    st.header("1. Identificar la emergencia")
    st.write("El sistema hace solo las preguntas necesarias siguiendo el árbol de decisión, y "
             "después aplica la base de reglas para calcular la certeza de cada situación, "
             "incluyendo riesgos secundarios.")

    col_preg, col_arbol = st.columns([1, 1.4])
    with col_preg:
        if st.button("🔄 Nueva evaluación"):
            st.session_state.intento += 1
            st.session_state.cambios = None
            st.rerun()
        st.subheader("Preguntas")
        respuestas, nodo, camino = {}, ARBOL, []
        while "pregunta" in nodo:
            camino.append(nodo["id"])
            p = PREGUNTAS[nodo["pregunta"]]
            eleccion = st.radio(p["texto"], [o[0] for o in p["opciones"]], index=None, horizontal=True,
                                key=f"{st.session_state.intento}_{nodo['id']}")
            if eleccion is None:
                break
            valor = dict(p["opciones"])[eleccion]
            respuestas[nodo["pregunta"]] = valor
            nodo = nodo["ramas"][valor]
        terminado = "situacion" in nodo
        if terminado:
            camino.append(nodo["id"])

    with col_arbol:
        st.subheader("Árbol de decisión")
        st.caption("En amarillo, el camino recorrido; en verde, la conclusión.")
        st.graphviz_chart(mi.arbol_a_dot(camino), width="content")

    if terminado:
        st.divider()
        ranking, disparadas = mi.encadenamiento_adelante(respuestas, st.session_state.reglas)
        principal = ranking[0][0] if ranking else nodo["situacion"]
        certeza = ranking[0][1] if ranking else 1.0
        s = SITUACIONES[principal]

        st.subheader("Resultado")
        caja = st.error if s["evacuar"] else st.warning
        cont = CONTINGENCIA[s["contingencia"]]
        caja(f"**Situación:** {nombre_sit(principal)}  ·  **Certeza:** {certeza:.0%}  \n"
             f"**Contingencia:** {cont['nombre']} · **Evacuación:** {s['nivel']}")
        st.caption(cont["descripcion"])
        st.markdown("**Protocolo:**\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(s["acciones"], 1)))
        if s["brigadas"]:
            st.markdown("**Brigadas de la UIRI que se activan:** " + ", ".join(s["brigadas"]))
        st.caption(f"Fuente: Plan de Contingencia FIME 2023, sección {s['fuente']}.")
        if s["contingencia"] >= 2:
            mostrar_directorio(expandido=s["contingencia"] == 3)
        if len(ranking) > 1:
            st.info("**Riesgo secundario a vigilar:** " +
                    ", ".join(f"{SITUACIONES[k]['nombre']} ({v:.0%})" for k, v in ranking[1:]))

        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**Situaciones posibles (encadenamiento hacia adelante)**")
            if ranking:
                st.dataframe(pd.DataFrame([{"Situación": nombre_sit(k), "Certeza": f"{v:.0%}"}
                                           for k, v in ranking]), hide_index=True, width="stretch")
            else:
                st.write("Ninguna regla aplica.")
        with r2:
            st.markdown("**Reglas disparadas**")
            for r in disparadas:
                st.markdown(f"- **{r['id']}** (CF {r['cf']:.2f}): {regla_a_texto(r)}")

        with st.expander("🔎 ¿Por qué? Explicación del razonamiento"):
            st.markdown("\n".join(mi.explicar(respuestas, st.session_state.reglas)))

        zona = None
        if s["zona"]:
            zona = st.selectbox("¿En qué edificio ocurre?", LISTA_EDIF, index=LISTA_EDIF.index("Edificio 6"))
        if st.button("🚨 Activar emergencia", type="primary"):
            st.session_state.emergencia = {"codigo": principal, "zona": zona}
            st.toast("Emergencia activada. Consulta la ruta en el módulo 2.")
            st.rerun()

        with st.expander("🧠 Confirmar la situación real (aprendizaje del sistema)"):
            st.write("Después del evento, la brigada confirma qué ocurrió realmente. "
                     "Las reglas que acertaron suben su certeza y las que fallaron la bajan.")
            real = st.selectbox("Situación real confirmada", LISTA_SIT,
                                index=LISTA_SIT.index(principal), format_func=nombre_sit)
            if st.button("Confirmar y aprender"):
                st.session_state.cambios = mi.aprender(st.session_state.reglas,
                                                       [r["id"] for r in disparadas], real)
                st.rerun()
            if st.session_state.cambios is not None:
                if st.session_state.cambios:
                    st.dataframe(pd.DataFrame(st.session_state.cambios), hide_index=True, width="stretch")
                else:
                    st.write("No había reglas disparadas que ajustar.")


# ===========================================================================
# 2. RUTA DE EVACUACIÓN
# ===========================================================================
elif pagina.startswith("2"):
    st.header("2. Ruta de evacuación hacia el punto de reunión")
    c1, c2, c3 = st.columns(3)
    codigo, zona_inc = selector_emergencia(c1, c2, "ruta")
    origen = c3.selectbox("¿Desde qué edificio salen?", LISTA_EDIF, index=LISTA_EDIF.index("Edificio 7"))
    st.caption(f"**{origen}:** {ZONAS[origen]['descripcion']} · ocupación estimada {ZONAS[origen]['ocupacion']} personas")

    s = SITUACIONES[codigo]
    if not s["evacuar"]:
        st.warning(f"**{s['nombre']}:** no se evacua en este momento ({s['nivel']}).\n\n"
                   + "\n".join(f"- {a}" for a in s["acciones"]))
        st.stop()

    esc, resultados = comparar_cache(codigo, zona_inc, origen)
    st.caption(f"Puntos de reunión cerrados: **{', '.join(esc['cerrados']) or 'ninguno'}**. "
               f"Cada celda ≈ {plano.METROS_POR_CELDA} m. Una celda libre cuesta 1, una con humo o peligro "
               f"{1 + s['penal'] if s['penal'] else 4}"
               + (f" y una crítica junto al incidente {1 + 3 * s['penal']}." if s["penal"] else "."))

    st.dataframe(pd.DataFrame([{
        "Algoritmo": r["algoritmo"], "Tipo": r["tipo"],
        "Nodos explorados": r["nodos_explorados"], "Distancia (m)": r["metros"],
        "Celdas de riesgo cruzadas": r["celdas_riesgo"], "Costo de riesgo": r["costo"],
        "Punto de reunión": r["punto"], "Tiempo caminando (s)": r["segundos"],
        "Cómputo (ms)": r["tiempo_ms"], "¿Ruta más segura?": "✅" if r["optima"] else "❌",
    } for r in resultados]), hide_index=True, width="stretch")

    d = {r["algoritmo"]: r for r in resultados}
    bfs_r, uc_r, ast_r = d["BFS"], d["Costo uniforme"], d["A*"]
    texto = (f"**A*** lleva a las personas del **{origen}** por la ruta más segura hacia el "
             f"**{ast_r['punto']}** (costo {ast_r['costo']}, {ast_r['metros']} m), explorando "
             f"**{ast_r['nodos_explorados']}** nodos contra **{uc_r['nodos_explorados']}** de Costo uniforme.")
    if bfs_r["celdas_riesgo"] > ast_r["celdas_riesgo"]:
        texto += (f" BFS encuentra el camino con menos pasos, pero cruza **{bfs_r['celdas_riesgo']}** "
                  f"celdas de riesgo porque no toma en cuenta el humo.")
    st.info(texto)
    with st.expander("🔎 ¿Por qué esta ruta? Explicación paso a paso"):
        st.markdown("\n".join(bq.explicar_ruta(esc, resultados, codigo, zona_inc)))

    fondo = imagen_mapa()

    def dibujar(r):
        fig, ax = plt.subplots(figsize=(5.4, 6.5))
        ax.imshow(fondo)
        for celda in r["explorados"]:
            celda_rect(ax, celda, "#3D85C6", 0.22)
        for celda in esc["riesgo"]:
            celda_rect(ax, celda, "#FF9900", 0.35)
        for celda in esc["criticas"]:
            celda_rect(ax, celda, "#CC0000", 0.45)
        for nombre, punto in PUNTOS_REUNION.items():
            cerrado = nombre in esc["cerrados"]
            for celda in punto["celdas"]:
                celda_rect(ax, celda, "#CC0000" if cerrado else "#00B050", 0.30)
            xs = [plano.centro_px(c)[0] for c in punto["celdas"]]
            ys = [plano.centro_px(c)[1] for c in punto["celdas"]]
            ax.text(sum(xs) / len(xs), sum(ys) / len(ys), ("✕ " if cerrado else "") + nombre,
                    ha="center", va="center", fontsize=6.5, fontweight="bold",
                    color="#7F0000" if cerrado else "#0B5D1E",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8, lw=0))
        if r["camino"]:
            xs = [plano.centro_px(c)[0] for c in r["camino"]]
            ys = [plano.centro_px(c)[1] for c in r["camino"]]
            ax.plot(xs, ys, color="white", lw=6, solid_capstyle="round")
            ax.plot(xs, ys, color="#FFD400", lw=3.5, solid_capstyle="round")
            ax.plot(xs[-1], ys[-1], marker="o", ms=9, color="#00B050", mec="white", mew=1.5)
        x0, y0 = plano.centro_px(ZONAS[origen]["puerta"])
        ax.plot(x0, y0, marker="o", ms=10, color="#1F3B57", mec="white", mew=1.5)
        if zona_inc:
            for (x1, y1, x2, y2) in plano.EDIFICIOS_PLANO[zona_inc]["rects"]:
                ax.add_patch(patches.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False,
                                               ec="#CC0000", lw=2.5, ls="--"))
        ax.set_xlim(0, plano.IMG_ANCHO)
        ax.set_ylim(plano.IMG_ALTO, 0)
        ax.axis("off")
        ax.set_title(f"{r['algoritmo']} · {r['nodos_explorados']} explorados · costo {r['costo']} · "
                     f"{r['celdas_riesgo']} celdas de riesgo", fontsize=9)
        fig.tight_layout()
        return fig

    vista = st.radio("Mostrar", ["A* vs BFS", "Todos los algoritmos"], horizontal=True)
    mostrar = [bfs_r, ast_r] if vista == "A* vs BFS" else resultados
    columnas = st.columns(2)
    for idx, r in enumerate(mostrar):
        with columnas[idx % 2]:
            fig = dibujar(r)
            st.pyplot(fig)
            plt.close(fig)
    st.caption("Amarillo: ruta · Azul: nodos explorados · Naranja: humo o peligro · Rojo: zona crítica · "
               "Verde: punto de reunión abierto · Rojo con ✕: punto cerrado · Contorno rojo punteado: "
               "edificio del incidente · Círculo azul: puerta de salida del edificio.")


# ===========================================================================
# 3. ORDEN DE EVACUACIÓN
# ===========================================================================
elif pagina.startswith("3"):
    st.header("3. Orden de evacuación por edificios")
    st.write("Los edificios se ordenan con **Merge Sort** para decidir a cuál acude primero la brigada.")
    c1, c2 = st.columns(2)
    codigo, zona_inc = selector_emergencia(c1, c2, "orden")
    if SITUACIONES[codigo]["zona"]:
        st.latex(r"Puntaje = 100 \times (0.5 \cdot Cercanía + 0.2 \cdot Ocupación + 0.1 \cdot Apoyo"
                 r" + 0.1 \cdot Pisos + 0.1 \cdot Químico)")
        st.caption("El edificio del incidente siempre sale primero. Cercanía = 1 − distancia ÷ distancia máxima. "
                   "Ocupación = ocupantes ÷ el edificio más lleno. Apoyo = 1 si hay personas que requieren "
                   "apoyo de un brigadista. Pisos = (pisos − 1) ÷ (máximo − 1), según la Tabla 1 del Plan de "
                   "Contingencia. Químico = 1 si el Atlas de Riesgo Interno marca riesgo químico.")
    else:
        st.latex(r"Puntaje = 100 \times (0.4 \cdot Ocupación + 0.3 \cdot Apoyo + 0.15 \cdot Pisos"
                 r" + 0.15 \cdot Químico)")
        st.caption("Sin incidente localizado, se priorizan los edificios más llenos, los que requieren apoyo, "
                   "los de más pisos y los que tienen riesgo químico.")

    if not SITUACIONES[codigo]["evacuar"]:
        st.warning(f"{SITUACIONES[codigo]['nombre']}: no se evacua en este momento.")
    else:
        orden = pr.priorizar(codigo, zona_inc)
        df = pd.DataFrame(orden)[["Orden", "Edificio", "Sector", "Ocupantes", "Requieren apoyo", "Pisos",
                                  "Riesgo químico", "Distancia al peligro (m)", "Puntaje"]]
        st.dataframe(df, hide_index=True, width="stretch", height=600)


# ===========================================================================
# 4. CAPACIDAD DE EVACUACIÓN
# ===========================================================================
elif pagina.startswith("4"):
    st.header("4. Capacidad de evacuación del campus (teorema de flujo máximo)")
    st.write("El campus se modela como una red de sectores, andadores y puntos de reunión. Cada flecha es "
             "la capacidad en personas por minuto. **Edmonds-Karp** calcula cuántas personas por minuto "
             "pueden llegar a zona segura y cuánto tarda la evacuación total.")

    em = st.session_state.emergencia
    cerr_def = []
    if em and SITUACIONES[em["codigo"]]["evacuar"]:
        cerr_def = bq.construir_escenario(em["codigo"], em["zona"])["cerrados"]
    cerrados = st.multiselect("Puntos de reunión cerrados", LISTA_PUNTOS, default=cerr_def)

    normal, _ = fl.flujo_maximo()
    total, por_arista = fl.flujo_maximo(cerrados)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ocupantes del campus (estimado)", f"{fl.OCUPACION_TOTAL:,}")
    m2.metric("Flujo máximo", f"{total:,} pers/min", delta=f"{total - normal:,} pers/min" if cerrados else None)
    m3.metric("Tiempo de evacuación", f"{fl.tiempo_evacuacion(cerrados)} min",
              delta=f"{fl.tiempo_evacuacion(cerrados) - fl.tiempo_evacuacion():+.1f} min" if cerrados else None,
              delta_color="inverse")
    m4.metric("Capacidad perdida", f"{(normal - total) / normal:.0%}")

    st.graphviz_chart(fl.flujo_a_dot(por_arista, cerrados), width="content")
    st.caption("Cada flecha muestra flujo/capacidad. Las flechas rojas punteadas están cerradas.")

    st.subheader("¿Qué punto de reunión es más crítico? (ordenado con Merge Sort)")
    filas = [{"Punto cerrado": n, "Flujo (pers/min)": fl.flujo_maximo([n])[0],
              "Tiempo de evacuación (min)": fl.tiempo_evacuacion([n]),
              "Minutos extra": round(fl.tiempo_evacuacion([n]) - fl.tiempo_evacuacion(), 1)}
             for n in LISTA_PUNTOS]
    st.dataframe(pd.DataFrame(pr.merge_sort(filas, lambda x: x["Minutos extra"])),
                 hide_index=True, width="stretch")


# ===========================================================================
# 6. BENCHMARK DE ALGORITMOS
# ===========================================================================
elif pagina.startswith("6"):
    st.header("6. Benchmark: búsqueda exhaustiva vs. heurística")
    st.write("Se corren los 5 algoritmos en **todas** las combinaciones: cada situación que requiere evacuar "
             "× cada edificio donde puede ocurrir el incidente × cada edificio de origen. Así la comparación "
             "no depende de un solo caso elegido a mano.")

    filas = benchmark_cache()
    resumen = pd.DataFrame(bm.resumen(filas))
    st.caption(f"{len(filas) // len(resumen):,} escenarios × {len(resumen)} algoritmos = {len(filas):,} búsquedas. "
               "Ruta más segura = la de menor costo de riesgo (humo y zona crítica cuestan más que un andador libre).")
    st.dataframe(resumen, hide_index=True, width="stretch")

    g1, g2 = st.columns(2)
    for col, metrica, nota in [
        (g1, "Nodos explorados (prom.)", "Menos es mejor: mide cuánto trabajo hace la búsqueda."),
        (g2, "Rutas más seguras (%)", "Porcentaje de escenarios donde encontró la ruta de menor costo."),
        (g1, "Celdas de riesgo (prom.)", "Celdas con humo o peligro que cruzan las personas, en promedio."),
        (g2, "Cómputo (ms prom.)", "Tiempo de cálculo; depende de la computadora."),
    ]:
        col.markdown(f"**{metrica}**")
        col.bar_chart(resumen, x="Algoritmo", y=metrica, horizontal=True, sort=False,
                      x_label="", y_label="", height=240)
        col.caption(nota)

    a = resumen.set_index("Algoritmo")
    ahorro = 1 - a.loc["A*", "Nodos explorados (prom.)"] / a.loc["Costo uniforme", "Nodos explorados (prom.)"]
    st.info(f"**Conclusión:** A* y Costo uniforme encuentran siempre la ruta más segura, pero A* explora "
            f"**{ahorro:.0%} menos nodos** gracias a la heurística. BFS minimiza pasos, no riesgo: solo da la ruta "
            f"más segura en el {a.loc['BFS', 'Rutas más seguras (%)']:.0f}% de los casos. La búsqueda voraz es la que "
            f"menos explora, pero acierta en el {a.loc['Voraz', 'Rutas más seguras (%)']:.0f}%, y DFS cruza en "
            f"promedio **{a.loc['DFS', 'Celdas de riesgo (prom.)']:.0f}** celdas de riesgo.")

    st.subheader("Nodos explorados promedio por situación")
    st.dataframe(pd.DataFrame(filas).pivot_table(index="Algoritmo", columns="Situación",
                                                 values="Nodos explorados", sort=False).round(1),
                 width="stretch")
    st.subheader("Rutas más seguras (%) por situación")
    st.dataframe((100 * pd.DataFrame(filas).pivot_table(index="Algoritmo", columns="Situación",
                                                        values="Óptima", sort=False)).round(1),
                 width="stretch")
    with st.expander("Ver las búsquedas una por una"):
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")


# ===========================================================================
# 7. PLAN DE EVACUACIÓN DEL CAMPUS
# ===========================================================================
elif pagina.startswith("7"):
    st.header("7. Plan de evacuación del campus completo")
    st.write("Asigna a los ocupantes de los 16 edificios un punto de reunión **sin rebasar la capacidad** de "
             "ninguno y minimizando el **riesgo total = Σ personas × costo de su ruta** (el mismo costo de humo y "
             "zona crítica del módulo 2, calculado con A* desde cada edificio hasta cada punto).")
    c1, c2, c3 = st.columns(3)
    codigo, zona_inc = selector_emergencia(c1, c2, "plan")
    m2 = c3.slider("m² por persona en el punto de reunión", 0.5, 3.0, 1.5, 0.25,
                   help="Capacidad del punto = área ÷ m² por persona. Es una estimación: ajústala con el criterio "
                        "de Protección Civil.")
    s = SITUACIONES[codigo]
    if not s["evacuar"]:
        st.warning(f"**{s['nombre']}:** no se evacua en este momento ({s['nivel']}).")
        st.stop()

    pl = plan_cache(codigo, zona_inc, m2)
    rv, ro = pe.resumen(pl["voraz"], pl["rutas"]), pe.resumen(pl["optimo"], pl["rutas"])
    metodo = st.radio("Plan a mostrar", ["Óptimo (flujo de costo mínimo)", "Voraz (por orden de prioridad)"],
                      horizontal=True)
    optimo = metodo.startswith("Óptimo")
    asig, res, otro = (pl["optimo"], ro, rv) if optimo else (pl["voraz"], rv, ro)

    m1, m2c, m3, m4 = st.columns(4)
    m1.metric("Riesgo total", f"{res['Riesgo total']:,}",
              delta=f"{res['Riesgo total'] - otro['Riesgo total']:+,} vs. el otro plan", delta_color="inverse")
    m2c.metric("Personas con lugar", f"{res['Personas asignadas']:,} de {fl.OCUPACION_TOTAL:,}")
    m3.metric("Distancia promedio", f"{res['Distancia promedio (m)']} m")
    m4.metric("Caminata más larga", f"{res['Caminata más larga (s)']} s")

    mejora = 1 - ro["Riesgo total"] / rv["Riesgo total"] if rv["Riesgo total"] else 0
    if mejora > 0:
        st.info(f"El plan **óptimo** reduce el riesgo total del plan voraz en **{mejora:.0%}** "
                f"({rv['Riesgo total']:,} → {ro['Riesgo total']:,}). El voraz manda a cada edificio al punto más "
                "barato que quede libre, en orden de prioridad, y los últimos edificios terminan en puntos lejanos o "
                "con humo; el flujo de costo mínimo reparte a todos al mismo tiempo.")
    else:
        st.info("En este escenario el plan voraz ya es óptimo: hay suficiente lugar en los puntos más baratos.")
    faltan = pe.sin_lugar_por_edificio(asig)
    if res["Sin lugar"]:
        st.error(f"**Faltan {res['Sin lugar']:,} lugares** en los puntos de reunión abiertos. Se quedan fuera los "
                 "edificios de menor prioridad: " + ", ".join(f"{e} ({n})" for e, n in faltan.items() if n)
                 + ". Hay que habilitar un punto alterno o evacuar de forma escalonada.")

    llegan = pe.ocupacion_por_punto(asig, pl["cap"])
    fig, ax = plt.subplots(figsize=(6.6, 7.9))
    mapa_base_plan(ax, pl["cap"], zona_inc,
                   {p: f"{p}\n{llegan[p]:,} / {pl['cap'][p]:,}" for p in pl["cap"]})
    for e, p, n in asig:
        xs = [plano.centro_px(c)[0] for c in pl["rutas"][(e, p)]["camino"]]
        ys = [plano.centro_px(c)[1] for c in pl["rutas"][(e, p)]["camino"]]
        ancho = 1.5 + n / 120
        ax.plot(xs, ys, color="white", lw=ancho + 2, solid_capstyle="round")
        ax.plot(xs, ys, color=COLORES_PUNTO[p], lw=ancho, solid_capstyle="round")
    for e, z in ZONAS.items():
        x, y = plano.centro_px(z["puerta"])
        sin = faltan[e] > 0
        ax.plot(x, y, marker="X" if sin else "o", ms=8, color="#CC0000" if sin else "#1F3B57",
                mec="white", mew=1.2)
    fig.tight_layout()

    col_mapa, col_puntos = st.columns([1.6, 1])
    with col_mapa:
        st.pyplot(fig)
        plt.close(fig)
        st.caption("Cada línea es la ruta A* de un edificio a su punto; el color es el punto de reunión y el grosor, "
                   "cuántas personas van. Etiqueta del punto: personas que llegan / capacidad. Círculo: puerta del "
                   "edificio · ✕ roja: edificio con personas sin lugar · gris: punto cerrado · contorno rojo: incidente.")
    with col_puntos:
        st.markdown("**Ocupación de los puntos de reunión**")
        st.dataframe(pd.DataFrame([{
            "Punto": p,
            "Estado": "Abierto" if p in pl["cap"] else "Cerrado",
            "Capacidad": pl["cap"].get(p, 0),
            "Llegan": llegan.get(p, 0),
            "Ocupación": f"{llegan[p] / pl['cap'][p]:.0%}" if pl["cap"].get(p) else "—",
        } for p in LISTA_PUNTOS]), hide_index=True, width="stretch")
        st.caption(f"Capacidad estimada = área del punto ÷ {m2} m² por persona (celdas de 4 m × 4 m). La Cancha de "
                   "fútbol y el Campo de béisbol son las canchas reales de FIME (Atlas de Riesgo del Plan, "
                   "geometría de OpenStreetMap); los demás puntos y la ocupación son estimaciones del proyecto.")

    st.subheader("Simulación de la evacuación en el tiempo")
    st.write(f"Las personas salen por la puerta de su edificio en fila ({sim.TASA_PUERTA} personas/s) y caminan por "
             f"su ruta A* a {bq.VELOCIDAD_M_S} m/s. Cada punto del mapa es un grupo de {sim.PERSONAS_POR_PUNTO} "
             "personas y tiene el color de su punto de reunión.")
    if st.toggle("▶ Mostrar simulación animada", key="sim_evac"):
        html, curva, total = animacion_cache(codigo, zona_inc, m2, optimo)
        s1, s2 = st.columns(2)
        s1.metric("Tiempo total de evacuación (simulado)", f"{total / 60:.1f} min")
        cerrados = [p for p in LISTA_PUNTOS if p not in pl["cap"]]
        s2.metric("Estimación del módulo 4 (solo capacidad de andadores)", f"{fl.tiempo_evacuacion(cerrados)} min")
        col_anim, col_curva = st.columns([1.15, 1])
        with col_anim:
            st.iframe(html, height=540)  # HTML generado por matplotlib (confiable)
            st.caption("Usa ▶ para reproducir; la barra permite moverse a cualquier segundo. Solo se simulan las "
                       "personas que tienen lugar en algún punto de reunión.")
        with col_curva:
            st.markdown("**Personas que ya llegaron a cada punto de reunión**")
            df_curva = pd.DataFrame(curva).set_index("Minuto")
            st.line_chart(df_curva, color=[COLORES_PUNTO[p] for p in df_curva.columns],
                          x_label="Minuto", y_label="Personas", height=360)
            st.caption("La simulación tarda más que el módulo 4 porque incluye la fila en la puerta de cada edificio "
                       "y la caminata; los edificios grandes son el cuello de botella.")

    st.subheader("Asignación por edificio (en orden de prioridad)")
    filas = []
    for f in pr.priorizar(codigo, zona_inc):
        e = f["Edificio"]
        suyas = [(p, n) for x, p, n in asig if x == e]
        filas.append({
            "Orden": f["Orden"], "Edificio": e, "Ocupantes": ZONAS[e]["ocupacion"],
            "Punto(s) de reunión": " · ".join(f"{p}: {n}" for p, n in suyas) or "—",
            "Sin lugar": faltan[e],
            "Riesgo de la ruta": " · ".join(str(pl["rutas"][(e, p)]["costo"]) for p, _ in suyas) or "—",
            "Caminata (s)": max((pl["rutas"][(e, p)]["segundos"] for p, _ in suyas), default=0),
        })
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")

    with st.expander("🔎 ¿Cómo se calcula el plan?"):
        st.markdown(
            "**Voraz:** recorre los edificios en el orden de evacuación (Merge Sort del módulo 3); a cada uno le asigna "
            "el punto de reunión más barato que todavía tenga lugar y, si no cabe completo, manda al resto al "
            "siguiente punto. Es rápido, pero no puede corregir decisiones: si un edificio de alta prioridad ocupa el "
            "punto más barato de otro, ese otro termina lejos.\n\n"
            "**Óptimo (flujo de costo mínimo):** se arma la red *Ocupantes → Edificios → Puntos de reunión → Zona "
            "segura*. Las aristas edificio → punto cuestan el riesgo de la ruta A* y las aristas punto → zona segura "
            "tienen la capacidad del punto. Igual que Edmonds-Karp, se repite: buscar un camino aumentante y empujar "
            "flujo; la diferencia es que el camino es el **más barato** y se busca con **Bellman-Ford**, porque "
            "devolver flujo por una arista residual tiene costo negativo (así el algoritmo puede \"arrepentirse\" "
            "de una asignación anterior, cosa que el voraz no hace).\n\n"
            "**Si no caben todos:** cada edificio tiene además una arista a *Sin lugar* que cuesta más que cualquier "
            "ruta y más entre más prioritario sea el edificio; así los que se quedan fuera son siempre los de menor "
            "prioridad, nunca el edificio del incidente.")


# ===========================================================================
# 5. BASE DE CONOCIMIENTO
# ===========================================================================
else:
    st.header("5. Base de conocimiento y aprendizaje")
    preguntas, hojas = mi.contar_nodos()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Reglas", len(st.session_state.reglas))
    k2.metric("Situaciones", len(SITUACIONES))
    k3.metric("Preguntas en el árbol", preguntas)
    k4.metric("Edificios", len(ZONAS))

    st.subheader("Reglas y factor de certeza actual")
    originales = {r["id"]: r["cf"] for r in mi.REGLAS_BASE}
    st.dataframe(pd.DataFrame([{
        "Regla": r["id"], "Descripción": regla_a_texto(r),
        "CF original": originales[r["id"]], "CF actual": r["cf"],
        "Cambio": round(r["cf"] - originales[r["id"]], 3),
    } for r in st.session_state.reglas]), hide_index=True, width="stretch")
    if st.button("Reiniciar aprendizaje (volver a los CF originales)"):
        st.session_state.reglas = mi.reiniciar_aprendizaje()
        st.session_state.cambios = None
        st.rerun()

    st.subheader("Niveles de contingencia (Plan de Contingencia FIME, sección 5)")
    st.dataframe(pd.DataFrame([{"Nivel": v["nombre"], "Descripción": v["descripcion"],
                                "Situaciones": ", ".join(k for k, s in SITUACIONES.items() if s["contingencia"] == n)}
                               for n, v in CONTINGENCIA.items() if n]), hide_index=True, width="stretch")

    st.subheader("Situaciones y protocolos")
    st.dataframe(pd.DataFrame([{
        "Código": k, "Situación": v["nombre"], "Contingencia": CONTINGENCIA[v["contingencia"]]["nombre"],
        "Evacuación": v["nivel"], "Brigadas": ", ".join(v["brigadas"]) or "—",
        "Protocolo": " / ".join(v["acciones"]), "Fuente (Plan)": v["fuente"],
    } for k, v in SITUACIONES.items()]), hide_index=True, width="stretch")

    st.subheader("Edificios del campus")
    st.dataframe(pd.DataFrame([{"Edificio": n, "Contenido": z["descripcion"], "Sector": z["sector"],
                                "Pisos": z["pisos"], "Riesgo químico": "Sí" if z["quimico"] else "No",
                                "Ocupación estimada": z["ocupacion"], "Requieren apoyo": z["apoyo"]}
                               for n, z in ZONAS.items()]), hide_index=True, width="stretch")
    st.caption("Pisos: Tabla 1 del Plan (E5, E12, Cafetería y Dirección no aparecen; se suponen de 1 piso). "
               "Riesgo químico: Atlas de Riesgo Interno del Plan.")
    mostrar_directorio()

    st.subheader("Árbol de decisión completo")
    st.graphviz_chart(mi.arbol_a_dot(), width="content")
