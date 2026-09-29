from flask import Flask, render_template



app = Flask(__name__)

NOMBRE_PROYECTO = "Calidad del agua lluvia"
DIMENSIONES = {
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


@app.context_processor
def contexto_global():
    return {"nombre_proyecto": NOMBRE_PROYECTO, "dimensiones": DIMENSIONES}

@app.route('/')
def inicio():
    return render_template("PaginaPrincipal.html")


@app.route("/Analisis/poblacional")
def dimension_poblacional():
    return render_template("Dimensiones.html", dim=DIMENSIONES["poblacional"])


@app.route("/Analisis/territorial")
def dimension_territorial():
    return render_template("Dimensiones.html", dim=DIMENSIONES["territorial"])


@app.route("/Analisis/temporal")
def dimension_temporal():
    return render_template("Dimensiones.html", dim=DIMENSIONES["temporal"])

@app.route("/Analisis/relacional")
def dimension_relacional():
    return render_template("Dimensiones.html", dim=DIMENSIONES["relacional"])

if __name__ == "__main__":
    app.run(debug=True)
