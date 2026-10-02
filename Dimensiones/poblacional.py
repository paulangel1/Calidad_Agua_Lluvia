import os
import re
import time
import pandas as pd
import matplotlib
matplotlib.use("Agg")  
import matplotlib.pyplot as plt
plt.rcParams.update({
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})
from flask import request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
IMG_DIR = os.path.join(BASE_DIR, "..", "static", "img")


def _cargar_datos():
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    ruta = os.path.join(DATA_DIR, csv_files[0])
    df = pd.read_csv(ruta)

    df["ELEVACION_NUM"] = df["ELEVACIÓN"].str.replace(",", "", regex=False).astype(float)

    def extraer_numero(valor):
        if pd.isna(valor):
            return None
        m = re.match(r"[<>]?\s*([\d.]+)", str(valor).strip())
        return float(m.group(1)) if m else None

    df["RESULTADO_NUM"] = df["RESULTADO"].apply(extraer_numero)
    df["RESULTADO_CENSURADO"] = df["RESULTADO"].astype(str).str.startswith(("<", ">"))
    return df


def analizar():
    df = _cargar_datos()

    # Filtros interactivos
    propiedad_sel = request.args.get("propiedad", "")
    punto_sel = request.args.get("punto", "")

    data = df.copy()
    if propiedad_sel:
        data = data[data["PROPIEDAD OBSERVADA"] == propiedad_sel]
    if punto_sel:
        data = data[data["NOMBRE DEL PUNTO DE MONITOREO"] == punto_sel]

    total_registros = len(data)
    sin_datos = total_registros == 0

    indicador_propiedad = {}
    indicador_puntos = {}
    indicador_censura = {}

    if not sin_datos:
        # Indicadores (sobre los datos filtrados)
        dist_propiedad_pct = data["PROPIEDAD OBSERVADA"].value_counts(normalize=True) * 100
        dist_puntos = data["NOMBRE DEL PUNTO DE MONITOREO"].value_counts()
        dist_censura = data["RESULTADO_CENSURADO"].value_counts(normalize=True) * 100

        indicador_propiedad = dist_propiedad_pct.round(2).to_dict()
        indicador_puntos = dist_puntos.head(10).to_dict()
        indicador_censura = {
            ("Censurado (< o >)" if k else "Directo"): round(v, 2)
            for k, v in dist_censura.items()
        }

        # Visualizaciones 
        os.makedirs(IMG_DIR, exist_ok=True)

        plt.figure(figsize=(8, 5))
        dist_propiedad_pct.sort_values().plot(kind="barh", color="#2f6f5e")
        plt.title("Distribución de muestras por propiedad observada (%)")
        plt.xlabel("Porcentaje de registros")
        plt.tight_layout()
        plt.savefig(os.path.join(IMG_DIR, "poblacional_propiedad.png"))
        plt.close()

        plt.figure(figsize=(8, 5))
        dist_puntos.head(10).sort_values().plot(kind="barh", color="#2f6f5e")
        plt.title("Top 10 puntos de monitoreo con más registros")
        plt.xlabel("Cantidad de registros")
        plt.tight_layout()
        plt.savefig(os.path.join(IMG_DIR, "poblacional_puntos.png"))
        plt.close()

        etiquetas = ["Censurado (< o >)" if i else "Resultado directo" for i in dist_censura.index]
        colores = ["#b45309" if i else "#2f6f5e" for i in dist_censura.index]
        plt.figure(figsize=(5, 5))
        dist_censura.plot(kind="pie", autopct="%1.1f%%", labels=etiquetas, colors=colores)
        plt.title("Proporción de resultados censurados")
        plt.ylabel("")
        plt.tight_layout()
        plt.savefig(os.path.join(IMG_DIR, "poblacional_censura.png"))
        plt.close()

    # Contenido fijo (hallazgos sobre la población completa)
    conocimientos_evidentes = [
        {
            "pregunta": "¿Qué propiedad del agua lluvia se monitorea con mayor frecuencia en Colombia?",
            "variables": "PROPIEDAD OBSERVADA",
            "procedimiento": "Conteo de frecuencia relativa sobre el total de 25.377 registros.",
            "evidencia": "Gráfico de barras horizontal de distribución por propiedad observada.",
            "hallazgo": "El pH (39.19%) y la Conductividad eléctrica (34.74%) concentran casi tres cuartas partes de las mediciones; Fósforo total y Demanda química de oxígeno son casi inexistentes (0.00%-0.01%).",
            "interpretacion": "El monitoreo histórico del IDEAM ha priorizado variables básicas y económicas de medir (pH, conductividad) sobre otras más específicas de contaminación.",
            "utilidad": "Permite identificar qué parámetros tienen series históricas robustas para análisis de tendencia y cuáles necesitarían más muestreo.",
            "limitacion": "No indica si esta priorización es igual en todos los puntos geográficos ni en todos los años.",
        },
        {
            "pregunta": "¿Los puntos de monitoreo están distribuidos uniformemente en el país?",
            "variables": "NOMBRE DEL PUNTO DE MONITOREO",
            "procedimiento": "Conteo de frecuencia por punto de monitoreo sobre el total de registros.",
            "evidencia": "Gráfico de barras horizontal del top 10 de puntos con más registros.",
            "hallazgo": "De 45 puntos de monitoreo, Bogotá-Puente Aranda concentra el 15.47% de las muestras, y los 2 primeros puntos juntos superan el 27%.",
            "interpretacion": "La vigilancia de calidad de agua lluvia está concentrada en pocas estaciones.",
            "utilidad": "Sugiere dónde priorizar comparaciones entre ciudades y qué zonas podrían necesitar más puntos de monitoreo.",
            "limitacion": "No se puede concluir sobre la calidad del agua en regiones sin puntos de monitoreo activos.",
        },
        {
            "pregunta": "¿Qué proporción de las mediciones son resultados censurados (por límite de detección)?",
            "variables": "RESULTADO",
            "procedimiento": "Identificación de valores con prefijo '<' o '>' y cálculo de su proporción sobre el total.",
            "evidencia": "Gráfico circular de resultados censurados vs. directos.",
            "hallazgo": "El 5.97% de los resultados (1.516 registros) son valores censurados; el 94.03% son valores directos.",
            "interpretacion": "Una fracción pequeña pero no despreciable de las mediciones no representa un valor exacto, sino un límite técnico del instrumento.",
            "utilidad": "Advierte que estos valores requieren un tratamiento específico antes de calcular promedios.",
            "limitacion": "No sabemos si los valores censurados se concentran en ciertos puntos o propiedades, lo que podría sesgar comparaciones simples.",
        },
    ]

    limitacion_general = (
        "El 5.97% de los registros son resultados censurados (< o >), por lo que no representan "
        "una concentración exacta sino un límite de detección del equipo; cualquier promedio o "
        "estadística calculada directamente sobre RESULTADO debe interpretarse con cautela."
    )

    decision_sustentada = (
        "Dado que solo 2 de los 7 parámetros (pH y conductividad) concentran cerca del 74% de las "
        "mediciones, se podría evaluar redistribuir parte del esfuerzo de monitoreo hacia parámetros "
        "subrepresentados como fósforo total o demanda química de oxígeno."
    )

        # Perfil general y síntesis (siempre sobre la población completa) 
    def _pct(v):
        return "menos de 0.01%" if v < 0.01 else f"{v:.2f}%"

    def _miles(n):
        return f"{n:,}".replace(",", ".")

    pct_prop = df["PROPIEDAD OBSERVADA"].value_counts(normalize=True) * 100
    cont_puntos = df["NOMBRE DEL PUNTO DE MONITOREO"].value_counts()
    pct_puntos = cont_puntos / len(df) * 100
    pct_cens = df["RESULTADO_CENSURADO"].mean() * 100

    perfil = {
        "registros": len(df),
        "propiedades": df["PROPIEDAD OBSERVADA"].nunique(),
        "puntos": df["NOMBRE DEL PUNTO DE MONITOREO"].nunique(),
        "departamentos": df["DEPARTAMENTO"].nunique(),
    }

    top2 = pct_prop.head(2)
    bajos = pct_prop.tail(2)

    sintesis = [
        {
            "punto": "Cantidad total de registros",
            "respuesta": (
                f"El conjunto tiene {_miles(len(df))} registros. Cada registro es una medición de una "
                f"propiedad del agua lluvia en una muestra, y provienen de {perfil['puntos']} puntos de "
                f"monitoreo ubicados en {perfil['departamentos']} departamentos."
            ),
        },
        {
            "punto": "Categorías principales",
            "respuesta": (
                f"La principal variable categórica es la propiedad observada, con {perfil['propiedades']} "
                f"categorías: " + ", ".join(pct_prop.index) + ". La segunda es el punto de monitoreo, "
                f"con {perfil['puntos']} categorías."
            ),
        },
        {
            "punto": "Porcentaje de participación por categoría",
            "respuesta": (
                "Por propiedad observada: " + "; ".join(f"{k} {_pct(v)}" for k, v in pct_prop.items())
                + ". Los tres puntos con más registros son: "
                + "; ".join(f"{k} ({_pct(v)})" for k, v in pct_puntos.head(3).items()) + "."
            ),
        },
        {
            "punto": "Grupos predominantes y minoritarios",
            "respuesta": (
                f"Predominan {top2.index[0]} ({_pct(top2.iloc[0])}) y {top2.index[1]} ({_pct(top2.iloc[1])}), "
                f"que juntas suman {_pct(top2.sum())}. Las propiedades minoritarias son {bajos.index[0]} y "
                f"{bajos.index[1]}, con {_pct(bajos.sum())} entre las dos. Entre los puntos, "
                f"{cont_puntos.index[0]} es el predominante, con {_miles(int(cont_puntos.iloc[0]))} registros "
                f"({_pct(pct_puntos.iloc[0])})."
            ),
        },
        {
            "punto": "Distribución de las variables principales",
            "respuesta": (
                f"Las mediciones se concentran en pocas propiedades (las dos primeras reúnen {_pct(top2.sum())}) "
                f"y en pocos puntos (los dos primeros reúnen {_pct(pct_puntos.head(2).sum())}). El "
                f"{_pct(100 - pct_cens)} de los resultados es un valor directo y el {_pct(pct_cens)} está "
                f"censurado por el límite de detección del equipo."
            ),
        },
        {
            "punto": "Características generales de la población",
            "respuesta": (
                f"Es una población de mediciones fisicoquímicas de agua lluvia hechas por el IDEAM. Está "
                f"dominada por {top2.index[0]} y {top2.index[1]}, tiene una cobertura desigual entre estaciones "
                f"y una pequeña fracción de resultados censurados ({_pct(pct_cens)})."
            ),
        },
    ]

    return {
        "total_registros": total_registros,
        "sin_datos": sin_datos,
        "indicador_propiedad": indicador_propiedad,
        "indicador_puntos": indicador_puntos,
        "indicador_censura": indicador_censura,
        "propiedades_disponibles": sorted(df["PROPIEDAD OBSERVADA"].unique().tolist()),
        "puntos_disponibles": sorted(df["NOMBRE DEL PUNTO DE MONITOREO"].unique().tolist()),
        "propiedad_seleccionada": propiedad_sel,
        "punto_seleccionada": punto_sel,
        "version": int(time.time()),
        "imagenes": {
            "propiedad": "img/poblacional_propiedad.png",
            "puntos": "img/poblacional_puntos.png",
            "censura": "img/poblacional_censura.png",
        },
        "conocimientos_evidentes": conocimientos_evidentes,
        "limitacion_general": limitacion_general,
        "decision_sustentada": decision_sustentada,
        "perfil": perfil,
        "sintesis": sintesis,
    }