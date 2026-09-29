from flask import Flask, render_template
from Dimensiones import poblacional, relacional, temporal, territorial



app = Flask(__name__)

NOMBRE_PROYECTO = "Calidad del agua lluvia"
DESCRIPCION = {
    "poblacional": {
        "nombre": "Dimensión poblacional",
        "clase": "poblacional",
        "endpoint": "dimension_poblacional",
        "pregunta": "¿Qué se está midiendo en las muestras?",
        "descripcion": "Cantidad total de registros. "
                      "Categorías principales. "
                      "Porcentaje de participación por categoría. "
                      "Grupos predominantes y minoritarios. "
                      "Distribución de las variables principales. "
                      "Características generales de la población.",
    },
    "territorial": {
        "nombre": "Dimensión territorial",
        "clase": "territorial",
        "endpoint": "dimension_territorial",
        "pregunta": "¿Cómo se distribuye la población y sus principales características entre los territorios disponibles?",
        "descripcion": "Distribución por departamento, municipio, localidad o zona. "
                       "Territorios con mayor y menor cantidad de registros. "
                       "Participación porcentual de cada territorio. "
                       "Concentraciones territoriales. "
                       "Diferencias entre territorios. "
                       "Comportamientos particulares de algunas zonas.",
    },
    "temporal": {
        "nombre": "Dimensión temporal",
        "clase": "temporal",
        "endpoint": "dimension_temporal",
        "pregunta": "¿Cómo ha cambiado el comportamiento de la población durante el periodo disponible?",
        "descripcion": "Evolución por año, trimestre, mes o fecha. "
                       "Periodos con mayor y menor cantidad de registros. "
                       "Aumentos y disminuciones. "
                       "Cambios importantes. "
                       "Posibles comportamientos repetitivos o estacionales. "
                       "Comparación entre periodos.",
    },
    "relacional": {
        "nombre": "Dimensión relacional y multivariada",
        "clase": "relacional",
        "endpoint": "dimension_relacional",
        "pregunta": "¿Qué diferencias o relaciones evidentes pueden identificarse al analizar conjuntamente tres o más variables?",
        "descripcion": "Relaciones entre variables.Diferencias entre grupos. "
                       "Cruce de tres o más variables. "
                       "Combinaciones con mayor cantidad de registros. "
                       "Comportamientos particulares por categoría, territorio o periodo. "
                       "Posibles casos inusuales. ",
    },
}

DIMENSIONES = {
    "poblacional": poblacional,
    "territorial": territorial,
    "temporal": temporal,
    "relacional": relacional,
}


@app.context_processor
def contexto_global():
    return {"nombre_proyecto": NOMBRE_PROYECTO, "dimensiones": DESCRIPCION}


def mostrar_dimension(clave):
    modulo = DIMENSIONES[clave]
    analizar = getattr(modulo, "analizar", None)
    resultados = analizar() if callable(analizar) else None
    return render_template(
        "Dimensiones.html",
        dim=DESCRIPCION[clave],
        resultados=resultados,
    )

@app.route('/')
def inicio():
    return render_template("PaginaPrincipal.html")


@app.route("/Analisis/poblacional")
def dimension_poblacional():
    return mostrar_dimension("poblacional")


@app.route("/Analisis/territorial")
def dimension_territorial():
    return mostrar_dimension("territorial")


@app.route("/Analisis/temporal")
def dimension_temporal():
    return mostrar_dimension("temporal")

@app.route("/Analisis/relacional")
def dimension_relacional():
    return mostrar_dimension("relacional")

if __name__ == "__main__":
    app.run(debug=True)
