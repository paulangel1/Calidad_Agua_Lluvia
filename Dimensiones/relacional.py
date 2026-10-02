from pathlib import Path

import pandas as pd
from flask import render_template, request
from markupsafe import Markup

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "data"
PERIODOS = ["1999-2004", "2005-2009", "2010-2014", "2015-2019", "2020-2024"]
EXCLUIDAS = ["Demanda química de oxígeno", "Fósforo total"]


def _cargar():
    ruta = sorted(CARPETA_DATOS.glob("*.csv"))[0]
    try:
        df = pd.read_csv(ruta, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(ruta, encoding="latin-1")
    df.columns = [c.strip() for c in df.columns]
    df = df.drop_duplicates()
    df = df.rename(columns={
        "NOMBRE DEL PUNTO DE MONITOREO": "punto",
        "DEPARTAMENTO": "depto",
        "MUNICIPIO": "municipio",
        "FECHA": "fecha",
        "PROPIEDAD OBSERVADA": "propiedad",
        "RESULTADO": "resultado",
        "UNIDAD DEL RESULTADO": "unidad",
        "ELEVACIÓN": "elevacion",
    })
    for col in ("punto", "depto", "municipio", "propiedad", "unidad"):
        df[col] = df[col].astype(str).str.strip()
    df["valor"] = pd.to_numeric(df["resultado"], errors="coerce")       # "<2", "<3" -> NaN
    df = df.dropna(subset=["valor"])
    df = df[~df["propiedad"].isin(EXCLUIDAS)]                           # muy pocos registros
    df = df[~((df["propiedad"] == "pH") & ~df["valor"].between(0, 14))]  # pH imposible
    df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["fecha"]).copy()
    df["periodo"] = pd.cut(df["fecha"].dt.year, [1998, 2004, 2009, 2014, 2019, 2024],
                           labels=PERIODOS).astype(str)
    df["elevacion"] = pd.to_numeric(df["elevacion"].astype(str).str.replace(",", "", regex=False),
                                    errors="coerce")
    return df


DF = _cargar()


def _num(x):
    return None if pd.isna(x) else round(float(x), 2)


def analizar():
    a = request.args
    propiedad = a.get("propiedad", "pH")
    depto = a.get("depto", "")

    f = DF[DF["propiedad"] == propiedad]
    if depto:
        f = f[f["depto"] == depto]

    ctx = {
        "deptos": sorted(DF["depto"].unique()),
        "propiedades": sorted(DF["propiedad"].unique()),
        "sel": {"propiedad": propiedad, "depto": depto},
        "vacio": f.empty, "kpis": None, "datos": None,
    }
    if not f.empty:
        unidad = f["unidad"].mode().iat[0]

        # Indicador 1: combinación departamento-propiedad-periodo con más registros (todo el conjunto)
        combos = DF.groupby(["depto", "propiedad", "periodo"]).size().sort_values(ascending=False)
        (c_dep, c_prop, c_per), c_n = combos.index[0], int(combos.iloc[0])

        # Indicador 2: correlación entre elevación y valor promedio por punto
        por_punto = f.groupby("punto").agg(promedio=("valor", "mean"), elevacion=("elevacion", "first"),
                                           depto=("depto", "first"), registros=("valor", "size")).reset_index()
        corr = por_punto["promedio"].corr(por_punto["elevacion"]) if len(por_punto) > 2 else None

        # Indicador 3: casos inusuales con la regla IQR
        q1, q3 = f["valor"].quantile([0.25, 0.75])
        lim_inf, lim_sup = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        inusuales = int(((f["valor"] < lim_inf) | (f["valor"] > lim_sup)).sum())

        ctx["kpis"] = {
            "total": int(len(f)),
            "acida": round((f["valor"] < 5.6).mean() * 100, 1) if propiedad == "pH" else None,
            "combo": f"{c_dep} – {c_prop} – {c_per}", "combo_n": c_n,
            "corr": None if corr is None or pd.isna(corr) else round(float(corr), 2),
            "puntos": int(len(por_punto)),
            "inusuales_pct": round(inusuales / len(f) * 100, 1), "inusuales": inusuales,
            "lim_inf": round(float(lim_inf), 2), "lim_sup": round(float(lim_sup), 2),
        }

        # Visualización 1: promedio por departamento y periodo
        piv = f.pivot_table(index="depto", columns="periodo", values="valor", aggfunc="mean")
        piv = piv.reindex(columns=[p for p in PERIODOS if p in piv.columns])

        # Visualización 2: elevación vs. promedio por punto, agrupado por departamento
        dispersion = [
            {"depto": d, "x": [_num(v) for v in g["elevacion"]], "y": [_num(v) for v in g["promedio"]],
             "n": g["registros"].astype(int).tolist(), "punto": g["punto"].tolist()}
            for d, g in por_punto.groupby("depto")
        ]

        # Visualización 3: distribución por municipio y periodo
        cajas = [{"periodo": p, "x": g["municipio"].tolist(), "y": g["valor"].round(2).tolist()}
                 for p, g in f.groupby("periodo") if p in PERIODOS]
        cajas.sort(key=lambda c: PERIODOS.index(c["periodo"]))

        ctx["datos"] = {
            "propiedad": propiedad, "unidad": unidad,
            "heatmap": {"x": list(piv.columns), "y": list(piv.index),
                        "z": [[_num(v) for v in fila] for fila in piv.values]},
            "dispersion": dispersion,
            "max_n": int(por_punto["registros"].max()),
            "cajas": cajas,
        }
    return {"html": Markup(render_template("relacional_tablero.html", **ctx))}
