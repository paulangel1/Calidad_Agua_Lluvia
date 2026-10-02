from pathlib import Path

import pandas as pd
from flask import render_template, request
from markupsafe import Markup

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "data"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

def _cargar():
    ruta = sorted(CARPETA_DATOS.glob("*.csv"))[0]
    try:
        df = pd.read_csv(ruta, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(ruta, encoding="latin-1")
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={
        "NOMBRE DEL PUNTO DE MONITOREO": "punto",
        "DEPARTAMENTO": "depto",
        "FECHA": "fecha",
        "PROPIEDAD OBSERVADA": "propiedad",
        "RESULTADO": "resultado",
        "UNIDAD DEL RESULTADO": "unidad",
        "CODIGO MUESTRA": "muestra",
    })
    df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["fecha"]).copy()
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    df["trimestre"] = df["anio"].astype(str) + "-T" + df["fecha"].dt.quarter.astype(str)
    df["mes_key"] = df["fecha"].dt.strftime("%Y-%m")

    df["valor"] = pd.to_numeric(df["resultado"], errors="coerce")

    df.loc[(df["propiedad"] == "pH") & ((df["valor"] < 0) | (df["valor"] > 14)), "valor"] = None
    return df

DF = _cargar()
ANIO_MIN, ANIO_MAX = int(DF["anio"].min()), int(DF["anio"].max())

def _num(x):
    return None if pd.isna(x) else round(float(x), 2)

def analizar():
    a = request.args
    try:
        desde, hasta = int(a.get("desde", ANIO_MIN)), int(a.get("hasta", ANIO_MAX))
    except ValueError:
        desde, hasta = ANIO_MIN, ANIO_MAX
    if desde > hasta:
        desde, hasta = hasta, desde
    depto, propiedad, gran = a.get("depto", ""), a.get("propiedad", ""), a.get("gran", "anio")
    if gran not in ("anio", "trimestre", "mes"):
        gran = "anio"

    f = DF[DF["anio"].between(desde, hasta)]
    if depto:
        f = f[f["depto"] == depto]
    if propiedad:
        f = f[f["propiedad"] == propiedad]

    ctx = {
        "anio_min": ANIO_MIN, "anio_max": ANIO_MAX,
        "deptos": sorted(DF["depto"].dropna().unique()),
        "propiedades": sorted(DF["propiedad"].dropna().unique()),
        "sel": {"desde": desde, "hasta": hasta, "depto": depto, "propiedad": propiedad, "gran": gran},
        "vacio": f.empty, "kpis": None, "datos": None,
    }
    if not f.empty:
        anios = list(range(desde, hasta + 1))

        por_anio = f.groupby("anio").size().reindex(anios, fill_value=0)
        mitad = len(anios) // 2
        variacion = None
        if mitad >= 1:
            ini, fin = por_anio.iloc[:mitad].mean(), por_anio.iloc[len(anios) - mitad:].mean()
            variacion = round((fin - ini) / ini * 100, 1) if ini else None
        ctx["kpis"] = {
            "total": int(len(f)), "muestras": int(f["muestra"].nunique()),
            "anio_pico": int(por_anio.idxmax()), "registros_pico": int(por_anio.max()),
            "variacion": variacion,
        }

        clave = {"anio": "anio", "trimestre": "trimestre", "mes": "mes_key"}[gran]
        g = f.groupby(clave).agg(registros=("muestra", "size"), puntos=("punto", "nunique"))
        if clave == "anio":
            g = g.reindex(anios, fill_value=0)

        piv = f.groupby(["anio", "mes"]).size().unstack(fill_value=0)
        piv = piv.reindex(index=anios, columns=range(1, 13), fill_value=0)

        prop = propiedad or "pH"
        sub = f[f["propiedad"] == prop].dropna(subset=["valor"])
        t = sub.groupby("anio")["valor"].agg(["median", "count"]).reindex(anios)

        ctx["datos"] = {
            "evolucion": {"x": [str(i) for i in g.index],
                          "registros": g["registros"].astype(int).tolist(),
                          "puntos": g["puntos"].astype(int).tolist()},
            "heatmap": {"x": MESES, "y": [str(y) for y in anios], "z": piv.values.tolist()},
            "tendencia": {"propiedad": prop,
                          "unidad": sub["unidad"].mode().iat[0] if not sub.empty else "",
                          "x": anios,
                          "mediana": [_num(v) for v in t["median"]],
                          "n": [0 if pd.isna(v) else int(v) for v in t["count"]]},
        }
    return {"html": Markup(render_template("temporal_tablero.html", **ctx))}