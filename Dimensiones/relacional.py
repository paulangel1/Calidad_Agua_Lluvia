"""Dimensión 4: relacional y multivariada.

Versión sin pandas ni numpy: solo usa la librería estándar de Python.
Las gráficas se dibujan en el navegador con Plotly.js (ver Templates/relacional.html).
Filtros (por URL): ?propiedad=pH&departamento=HUILA
"""
import csv
import glob
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime

from flask import request

PLANTILLA = "relacional.html"  # app.py usa esta plantilla en lugar de Dimensiones.html
PLOTLY_VERSION = "2.35.2"     # versión de Plotly.js que se carga desde el CDN

RUTA = os.path.join(os.path.dirname(__file__), "..", "data")
PERIODOS = ["1999-2004", "2005-2009", "2010-2014", "2015-2019", "2020-2024"]
TEAL = [[0, "rgb(209,238,234)"], [0.33, "rgb(133,196,201)"], [0.67, "rgb(79,144,166)"], [1, "rgb(42,86,116)"]]
EXCLUIDAS = {"Demanda química de oxígeno", "Fósforo total"}


def periodo(anio):
    for limite, nombre in [(2004, "1999-2004"), (2009, "2005-2009"), (2014, "2010-2014"), (2019, "2015-2019")]:
        if anio <= limite:
            return nombre
    return "2020-2024"


def numero(texto):
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None  # "<2", "<3", vacíos...


def cargar_datos():
    archivo = glob.glob(os.path.join(RUTA, "*.csv"))[0]
    filas, vistas = [], set()
    with open(archivo, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r = {k.strip(): (v or "").strip() for k, v in r.items()}
            clave = tuple(r.values())
            if clave in vistas:          # duplicados exactos
                continue
            vistas.add(clave)
            valor = numero(r["RESULTADO"])
            prop = r["PROPIEDAD OBSERVADA"]
            if valor is None or prop in EXCLUIDAS:
                continue
            if prop == "pH" and not 0 <= valor <= 14:   # pH imposible
                continue
            anio = datetime.strptime(r["FECHA"], "%d/%m/%Y").year
            filas.append({
                "punto": r["NOMBRE DEL PUNTO DE MONITOREO"],
                "departamento": r["DEPARTAMENTO"],
                "municipio": r["MUNICIPIO"],
                "propiedad": prop,
                "unidad": r["UNIDAD DEL RESULTADO"],
                "valor": valor,
                "periodo": periodo(anio),
                "elevacion": numero(r["ELEVACIÓN"].replace(",", "")),
            })
    return filas


DATOS = cargar_datos()  # se carga una sola vez al iniciar la app


def miles(n):
    return f"{n:,}".replace(",", ".")


def correlacion(xs, ys):
    pares = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pares) < 3:
        return float("nan")
    xs, ys = zip(*pares)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in pares)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else float("nan")


def layout(titulo, **extra):
    base = {"title": {"text": titulo}, "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
            "paper_bgcolor": "white", "plot_bgcolor": "white"}
    base.update(extra)
    for eje in ("xaxis", "yaxis"):
        base.setdefault(eje, {})["automargin"] = True
    return base


def analizar():
    # ---- Filtros interactivos
    propiedad = request.args.get("propiedad", "pH")
    departamento = request.args.get("departamento", "Todos")

    resultado = {
        "propiedad": propiedad,
        "departamento": departamento,
        "propiedades": sorted({f["propiedad"] for f in DATOS}),
        "departamentos": ["Todos"] + sorted({f["departamento"] for f in DATOS}),
        "plotly_version": PLOTLY_VERSION,
        "variables": [
            ("PROPIEDAD OBSERVADA", "Categórica", "Qué parámetro se mide (filtro 1)"),
            ("RESULTADO", "Numérica", "Valor medido"),
            ("DEPARTAMENTO / MUNICIPIO", "Territorial", "Dónde se tomó la muestra (filtro 2)"),
            ("FECHA → PERIODO", "Temporal", "Agrupada en periodos de cinco años"),
            ("ELEVACIÓN", "Numérica", "Altitud del punto de monitoreo"),
            ("NOMBRE DEL PUNTO DE MONITOREO", "Categórica", "Estación donde se tomó la muestra"),
        ],
    }

    df = [f for f in DATOS if f["propiedad"] == propiedad
          and (departamento == "Todos" or f["departamento"] == departamento)]
    if not df:
        resultado["aviso"] = "No hay datos para esta combinación de filtros."
        return resultado
    valores = [f["valor"] for f in df]
    unidad = Counter(f["unidad"] for f in df).most_common(1)[0][0]

    # ---- Indicador 1: combinación con más registros
    (c_dep, c_prop, c_per), c_n = Counter(
        (f["departamento"], f["propiedad"], f["periodo"]) for f in DATOS).most_common(1)[0]

    # ---- Indicador 2: correlación elevación vs. promedio por punto
    puntos = defaultdict(list)
    for f in df:
        puntos[f["punto"]].append(f)
    por_punto = [{"punto": p, "promedio": statistics.fmean(x["valor"] for x in fs),
                  "elevacion": fs[0]["elevacion"], "departamento": fs[0]["departamento"],
                  "registros": len(fs)} for p, fs in puntos.items()]
    corr = correlacion([p["elevacion"] for p in por_punto], [p["promedio"] for p in por_punto])

    # ---- Indicador 3: casos inusuales (regla IQR)
    if len(valores) >= 2:
        q1, _, q3 = statistics.quantiles(valores, n=4, method="inclusive")
    else:
        q1 = q3 = valores[0]
    lim_inf, lim_sup = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    inusuales = sum(1 for v in valores if v < lim_inf or v > lim_sup)

    registros = f"{miles(len(df))} mediciones de {propiedad} ({departamento})."
    if propiedad == "pH":
        acida = sum(1 for v in valores if v < 5.6) / len(valores) * 100
        registros += f" El {acida:.1f} % es lluvia ácida (pH < 5,6)."

    # ---- Visualización 1: mapa de calor departamento x periodo
    celdas = defaultdict(list)
    for f in df:
        celdas[(f["departamento"], f["periodo"])].append(f["valor"])
    deptos = sorted({f["departamento"] for f in df})
    pers = [p for p in PERIODOS if any(f["periodo"] == p for f in df)]
    z = [[round(statistics.fmean(celdas[(d, p)]), 2) if celdas.get((d, p)) else None for p in pers] for d in deptos]
    fig1 = {"data": [{"type": "heatmap", "x": pers, "y": deptos, "z": z, "colorscale": TEAL,
                      "texttemplate": "%{z}", "hoverongaps": False}],
            "layout": layout(f"{propiedad} promedio por departamento y periodo ({unidad})",
                             yaxis={"autorange": "reversed", "automargin": True},
                             xaxis={"title": {"text": "PERIODO"}}, height=max(350, 28 * len(deptos)))}

    # ---- Visualización 2: elevación vs. promedio por punto
    max_reg = max(p["registros"] for p in por_punto)
    trazas2 = []
    for d in sorted({p["departamento"] for p in por_punto}):
        ps = [p for p in por_punto if p["departamento"] == d]
        trazas2.append({"type": "scatter", "mode": "markers", "name": d,
                        "x": [p["elevacion"] for p in ps], "y": [round(p["promedio"], 2) for p in ps],
                        "text": [p["punto"] for p in ps],
                        "marker": {"size": [p["registros"] for p in ps], "sizemode": "area",
                                   "sizeref": 2 * max_reg / 40 ** 2, "sizemin": 3},
                        "hovertemplate": "%{text}<br>Elevación: %{x} m<br>Promedio: %{y}<extra></extra>"})
    fig2 = {"data": trazas2,
            "layout": layout(f"Elevación vs. {propiedad} promedio por punto de monitoreo",
                             xaxis={"title": {"text": "Elevación (m s. n. m.)"}},
                             yaxis={"title": {"text": f"{propiedad} promedio"}})}

    # ---- Visualización 3: distribución por municipio y periodo
    trazas3 = []
    for p in PERIODOS:
        fs = [f for f in df if f["periodo"] == p]
        if fs:
            trazas3.append({"type": "box", "name": p, "x": [f["municipio"] for f in fs],
                            "y": [f["valor"] for f in fs]})
    fig3 = {"data": trazas3,
            "layout": layout(f"Distribución de {propiedad} por municipio y periodo (puntos = casos inusuales)",
                             boxmode="group", xaxis={"title": {"text": "MUNICIPIO"}},
                             yaxis={"title": {"text": f"{propiedad} ({unidad})"}})}

    resultado.update({
        "registros": registros,
        "indicadores": [
            ("Combinación con más registros", f"{c_dep} – {c_prop} – {c_per}", f"{miles(c_n)} registros"),
            ("Correlación elevación vs. valor promedio", "N/D (pocos puntos)" if math.isnan(corr) else f"{corr:.2f}", f"{len(por_punto)} puntos (entre -1 y 1)"),
            ("Casos inusuales (regla IQR)", f"{inusuales / len(valores) * 100:.1f} %",
             f"{inusuales} fuera de [{lim_inf:.2f}; {lim_sup:.2f}]"),
        ],
        "graficas": [
            {"id": "grafica1", "json": json.dumps(fig1),
             "interpretacion": "Muestra cómo cambia el valor promedio de la propiedad en cada departamento según el "
                               "periodo; las celdas vacías indican que no hubo mediciones."},
            {"id": "grafica2", "json": json.dumps(fig2),
             "interpretacion": "Relaciona la altitud de cada punto con su valor promedio; el tamaño indica cuántas "
                               "mediciones tiene. Con la temperatura la relación es fuerte y negativa."},
            {"id": "grafica3", "json": json.dumps(fig3),
             "interpretacion": "Compara la distribución por municipio y periodo; los puntos aislados son casos "
                               "inusuales que pueden ser eventos reales o errores de registro."},
        ],
        "conocimientos": [
            "Cerca de la mitad de las mediciones de pH (48,3 %) corresponde a lluvia ácida, y en Boyacá y Meta "
            "llega a cerca del 69 %.",
            "En el periodo 2020-2024 el pH promedio baja a 4,91 y el 79,6 % de las mediciones es ácida, "
            "aunque ese periodo solo tiene 398 mediciones.",
            "Hay valores imposibles de pH (2.070 en Cali y 21,8 en Bogotá), que se excluyen del análisis; "
            "la conductividad y el nitrato tienen más del 6 % de casos inusuales.",
        ],
        "limitacion": "La cantidad de mediciones cambia mucho entre departamentos y periodos, y una correlación "
                      "no implica causalidad.",
        "decision": "Priorizar el seguimiento de la lluvia ácida en Boyacá, Meta y Huila y retomar la frecuencia "
                    "de muestreo en los últimos años para confirmar la tendencia.",
    })
    return resultado