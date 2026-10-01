"""Visualización de la distribución y las características territoriales."""

from pathlib import Path
import re

import pandas as pd


def _normalizar(nombre):
	return re.sub(r"[^a-z0-9]", "", str(nombre).lower())


def _encontrar_columna(columnas, nombres):
	"""Busca una columna aunque use mayúsculas, espacios o tildes diferentes."""
	mapa = {_normalizar(columna): columna for columna in columnas}
	for nombre in nombres:
		if _normalizar(nombre) in mapa:
			return mapa[_normalizar(nombre)]
	for columna in columnas:
		if any(_normalizar(nombre) in _normalizar(columna) for nombre in nombres):
			return columna
	return None


def _cargar_data():
	"""Carga el primer conjunto tabular encontrado bajo la carpeta data del proyecto."""
	carpeta = Path(__file__).resolve().parent.parent / "data"
	if not carpeta.is_dir():
		return None

	for patron in ("*.csv", "*.xlsx", "*.xls", "*.parquet"):
		archivos = sorted(carpeta.rglob(patron))
		if not archivos:
			continue
		marcos = []
		for archivo in archivos:
			try:
				if archivo.suffix.lower() == ".csv":
					marco = pd.read_csv(archivo, sep=None, engine="python")
				elif archivo.suffix.lower() in (".xlsx", ".xls"):
					marco = pd.read_excel(archivo)
				else:
					marco = pd.read_parquet(archivo)
				marcos.append(marco)
			except (OSError, ValueError, ImportError):
				continue
		if marcos:
			return pd.concat(marcos, ignore_index=True, sort=False)
	return None


def analizar(nivel=None, territorio=None, indicador=None, pagina=1):
	"""Prepara métricas y comparaciones territoriales para la página de Flask."""
	datos = _cargar_data()
	if not isinstance(datos, pd.DataFrame) or datos.empty:
		return {"sin_datos": True}

	columna_departamento = _encontrar_columna(datos.columns, ("departamento", "depto"))
	columna_municipio = _encontrar_columna(datos.columns, ("municipio",))
	columna_punto = _encontrar_columna(
		datos.columns, ("nombre del punto de monitoreo", "punto de monitoreo", "estación")
	)
	columna_indicador = _encontrar_columna(
		datos.columns, ("propiedad observada", "indicador", "parámetro", "parametro")
	)
	columna_valor = _encontrar_columna(datos.columns, ("resultado", "valor"))
	columna_unidad = _encontrar_columna(datos.columns, ("unidad del resultado", "unidad"))
	columna_muestra = _encontrar_columna(datos.columns, ("código muestra", "codigo muestra"))

	def texto(valor):
		if pd.isna(valor) or not str(valor).strip():
			return "Sin dato"
		return str(valor).strip()

	columnas_nivel = {
		"Departamento": columna_departamento,
		"Municipio": columna_municipio,
		"Punto de monitoreo": columna_punto,
	}
	for nombre in ("Localidad", "Zona"):
		columna = _encontrar_columna(datos.columns, (nombre.lower(),))
		if columna:
			columnas_nivel[nombre] = columna
	columnas_nivel = {
		nombre: columna for nombre, columna in columnas_nivel.items() if columna
	}
	if not columnas_nivel or not columna_indicador:
		return {"sin_datos": True}

	niveles = list(columnas_nivel)
	nivel = nivel if nivel in columnas_nivel else niveles[0]
	columna_territorio = columnas_nivel[nivel]
	trabajo = datos.copy()
	trabajo["_territorio"] = trabajo[columna_territorio].map(texto)
	trabajo["_indicador"] = trabajo[columna_indicador].map(texto)

	indicadores = sorted(trabajo["_indicador"].unique())
	indicador = indicador if indicador in indicadores else ""
	seleccion = trabajo
	if indicador:
		seleccion = seleccion[seleccion["_indicador"] == indicador]
	territorios = sorted(seleccion["_territorio"].unique())

	if seleccion.empty:
		return {"sin_datos": True}

	resumen = (
		seleccion.groupby("_territorio", sort=False)
		.size()
		.rename("registros")
		.to_frame()
	)
	if columna_muestra:
		resumen["muestras"] = seleccion.groupby("_territorio")[columna_muestra].nunique()
	else:
		resumen["muestras"] = resumen["registros"]

	por_indicador = (
		trabajo.groupby(["_territorio", "_indicador"], sort=False)
		.size()
		.rename("cantidad")
		.reset_index()
		.sort_values(["cantidad", "_indicador"], ascending=[False, True])
		.drop_duplicates("_territorio")
		.set_index("_territorio")["_indicador"]
	)
	resumen["indicador_principal"] = por_indicador
	total_registros = int(resumen["registros"].sum())
	resumen["participacion"] = resumen["registros"] / total_registros * 100
	resumen = resumen.sort_values("registros", ascending=False)

	resultados_numericos = pd.Series(dtype="float64")
	unidades = []
	if columna_valor:
		resultados_numericos = pd.to_numeric(
			seleccion[columna_valor]
			.astype("string")
			.str.strip()
			.str.replace(",", ".", regex=False),
			errors="coerce",
		)
		if columna_unidad:
			unidades = sorted(
				unidad for unidad in seleccion[columna_unidad].map(texto).unique()
				if unidad != "Sin dato"
			)

	if resultados_numericos.notna().any() and len(unidades) <= 1:
		medidas = resultados_numericos.groupby(seleccion["_territorio"]).agg(
			promedio="mean",
			mediana="median",
			minimo="min",
			maximo="max",
			resultados_validos="count",
		)
		resumen = resumen.join(medidas)
	else:
		resumen["promedio"] = float("nan")
		resumen["mediana"] = float("nan")
		resumen["minimo"] = float("nan")
		resumen["maximo"] = float("nan")
		resumen["resultados_validos"] = 0

	territorio = territorio if territorio in territorios else ""
	territorio_destacado = territorio or str(resumen.index[0])

	maximo = resumen.iloc[0]
	minimo = resumen.iloc[-1]
	top_cinco = resumen.head(min(5, len(resumen)))
	comparacion = resumen.reset_index().rename(columns={"_territorio": "territorio"})
	comparacion["posicion"] = range(1, len(comparacion) + 1)
	comparacion["barra"] = (
		comparacion["registros"] / maximo["registros"] * 100
	)
	for columna in ("promedio", "mediana", "minimo", "maximo"):
		comparacion[columna] = comparacion[columna].astype(object).map(
			lambda valor: float(valor) if pd.notna(valor) else None
		)

	detalle = resumen.loc[territorio_destacado]
	participacion_top = float(top_cinco["participacion"].sum())
	promedios_validos = resumen["promedio"].dropna()
	mayor_promedio = (
		{"territorio": str(promedios_validos.idxmax()), "valor": float(promedios_validos.max())}
		if not promedios_validos.empty else None
	)
	menor_promedio = (
		{"territorio": str(promedios_validos.idxmin()), "valor": float(promedios_validos.min())}
		if not promedios_validos.empty else None
	)

	registros_territorio = seleccion
	if territorio:
		registros_territorio = registros_territorio[
			registros_territorio["_territorio"] == territorio
		]
	total_consulta = len(registros_territorio)
	tamano_pagina = 100
	try:
		pagina = max(1, int(pagina))
	except (TypeError, ValueError):
		pagina = 1
	total_paginas = max(1, (total_consulta + tamano_pagina - 1) // tamano_pagina)
	pagina = min(pagina, total_paginas)
	inicio = (pagina - 1) * tamano_pagina
	columna_fecha = _encontrar_columna(datos.columns, ("fecha", "periodo", "período"))
	registros_consulta = []
	for _, fila in registros_territorio.iloc[inicio:inicio + tamano_pagina].iterrows():
		registros_consulta.append({
			"territorio": fila["_territorio"],
			"indicador": fila["_indicador"],
			"valor": texto(fila[columna_valor]) if columna_valor else "—",
			"unidad": texto(fila[columna_unidad]) if columna_unidad else "—",
			"periodo": texto(fila[columna_fecha]) if columna_fecha else "—",
			"muestra": texto(fila[columna_muestra]) if columna_muestra else "—",
		})

	datos_graficos = trabajo
	if territorio:
		datos_graficos = datos_graficos[datos_graficos["_territorio"] == territorio]
	conteo_indicadores = (
		datos_graficos["_indicador"].value_counts().sort_values(ascending=False)
	)
	principales_indicadores = conteo_indicadores.head(7)
	etiquetas_indicadores = principales_indicadores.index.tolist()
	valores_indicadores = [int(valor) for valor in principales_indicadores.tolist()]
	otros_indicadores = int(conteo_indicadores.iloc[7:].sum())
	if otros_indicadores:
		etiquetas_indicadores.append("Otros")
		valores_indicadores.append(otros_indicadores)

	indicador_histograma = indicador or (
		str(conteo_indicadores.index[0]) if not conteo_indicadores.empty else ""
	)
	datos_histograma = datos_graficos[
		datos_graficos["_indicador"] == indicador_histograma
	]
	if territorio:
		datos_histograma = datos_histograma[
			datos_histograma["_territorio"] == territorio
		]
	valores_histograma = pd.Series(dtype="float64")
	if columna_valor:
		valores_histograma = pd.to_numeric(
			datos_histograma[columna_valor]
			.astype("string")
			.str.strip()
			.str.replace(",", ".", regex=False),
			errors="coerce",
		).dropna()
	unidades_histograma = []
	if columna_unidad:
		unidades_histograma = sorted(
			unidad for unidad in datos_histograma[columna_unidad].map(texto).unique()
			if unidad != "Sin dato"
		)

	histograma_etiquetas = []
	histograma_conteos = []
	if not valores_histograma.empty and len(unidades_histograma) <= 1:
		minimo_valor = float(valores_histograma.min())
		maximo_valor = float(valores_histograma.max())
		if minimo_valor == maximo_valor:
			margen = max(abs(minimo_valor) * 0.05, 0.5)
			inicio_bin, fin_bin = minimo_valor - margen, maximo_valor + margen
		else:
			inicio_bin, fin_bin = minimo_valor, maximo_valor
		limites = [
			inicio_bin + (fin_bin - inicio_bin) * indice / 10
			for indice in range(11)
		]
		categorias = pd.cut(valores_histograma, bins=limites, include_lowest=True)
		conteo_bins = categorias.value_counts(sort=False)
		for intervalo, cantidad in conteo_bins.items():
			histograma_etiquetas.append(
				f"{intervalo.left:.2f}–{intervalo.right:.2f}"
			)
			histograma_conteos.append(int(cantidad))

	columna_fecha = _encontrar_columna(datos.columns, ("fecha", "periodo", "período"))
	registros_filtro = []
	for indice in datos.index:
		fila = datos.loc[indice]
		registros_filtro.append([
			texto(fila[columna_departamento]) if columna_departamento else "Sin dato",
			texto(fila[columna_municipio]) if columna_municipio else "Sin dato",
			texto(fila[columna_punto]) if columna_punto else "Sin dato",
			texto(fila[columna_indicador]),
			texto(fila[columna_valor]) if columna_valor else "Sin dato",
			texto(fila[columna_unidad]) if columna_unidad else "Sin dato",
			texto(fila[columna_fecha]) if columna_fecha else "Sin dato",
			texto(fila[columna_muestra]) if columna_muestra else "Sin dato",
		])

	return {
		"sin_datos": False,
		"niveles": niveles,
		"nivel_seleccionado": nivel,
		"territorios": territorios,
		"territorio_seleccionado": territorio,
		"territorio_destacado": territorio_destacado,
		"indicadores": indicadores,
		"indicador_seleccionado": indicador,
		"total_registros": total_registros,
		"total_muestras": int(seleccion[columna_muestra].nunique()) if columna_muestra else total_registros,
		"total_territorios": len(resumen),
		"mayor": {
			"territorio": str(resumen.index[0]),
			"registros": int(maximo["registros"]),
			"participacion": float(maximo["participacion"]),
		},
		"menor": {
			"territorio": str(resumen.index[-1]),
			"registros": int(minimo["registros"]),
			"participacion": float(minimo["participacion"]),
		},
		"diferencia": int(maximo["registros"] - minimo["registros"]),
		"concentracion_top": participacion_top,
		"concentracion_cantidad": len(top_cinco),
		"unidad": unidades[0] if len(unidades) == 1 else "",
		"comparacion_unidades_compatible": len(unidades) <= 1,
		"comparacion_resultados": {
			"mayor": mayor_promedio,
			"menor": menor_promedio,
		},
		"detalle": {
			"territorio": territorio_destacado,
			"registros": int(detalle["registros"]),
			"muestras": int(detalle["muestras"]),
			"participacion": float(detalle["participacion"]),
			"indicador_principal": str(detalle["indicador_principal"]),
			"promedio": float(detalle["promedio"]) if pd.notna(detalle["promedio"]) else None,
			"mediana": float(detalle["mediana"]) if pd.notna(detalle["mediana"]) else None,
			"resultados_validos": int(detalle["resultados_validos"]),
		},
		"resultados": comparacion.to_dict(orient="records"),
		"registros_consulta": registros_consulta,
		"total_registros_consulta": total_consulta,
		"pagina": pagina,
		"total_paginas": total_paginas,
		"tamano_pagina": tamano_pagina,
		"graficos_indicadores": {
			"etiquetas": etiquetas_indicadores,
			"valores": valores_indicadores,
		},
		"histograma": {
			"etiquetas": histograma_etiquetas,
			"valores": histograma_conteos,
			"total": int(len(valores_histograma)),
			"unidad": unidades_histograma[0] if len(unidades_histograma) == 1 else "",
			"unidades_compatibles": len(unidades_histograma) <= 1,
			"indicador": indicador_histograma,
		},
		"registros_filtro": registros_filtro,
		"territorio_grafico": territorio or "Todos los territorios",
		"aviso_niveles": (
			"El conjunto no incluye campos explícitos de localidad o zona; "
			"se muestran los niveles territoriales disponibles."
			if "Localidad" not in niveles or "Zona" not in niveles else ""
		),
	}


def mostrar_analisis_territorial(datos=None):
	"""Muestra un análisis territorial con Streamlit.

	Pasa ``datos`` desde app.py si allí ya se cargó el conjunto de datos;
	si no, la función lo busca en la carpeta ``data`` del proyecto.
	"""
	import streamlit as st

	if datos is None:
		datos = _cargar_data()
	if not isinstance(datos, pd.DataFrame) or datos.empty:
		st.warning("No hay datos disponibles para realizar el análisis territorial.")
		return

	st.title("Distribución territorial de la población y los registros")
	st.caption(
		"El conteo representa registros del conjunto de datos; solo debe interpretarse "
		"como población si cada fila corresponde a una persona."
	)

	aliases = {
		"Departamento": ("departamento", "depto"),
		"Municipio": ("municipio",),
		"Localidad": ("localidad",),
		"Zona": ("zona", "region", "territorio"),
	}
	columnas = {
		nivel: _encontrar_columna(datos.columns, nombres)
		for nivel, nombres in aliases.items()
	}
	disponibles = [nivel for nivel, columna in columnas.items() if columna]
	if not disponibles:
		st.error("No se encontraron columnas de departamento, municipio, localidad o zona.")
		st.write("Columnas disponibles:", list(datos.columns))
		return

	preferencia = ("Localidad", "Zona", "Municipio", "Departamento")
	nivel_inicial = next(nivel for nivel in preferencia if nivel in disponibles)
	nivel = st.selectbox(
		"Nivel territorial para comparar",
		disponibles,
		index=disponibles.index(nivel_inicial),
	)
	columna = columnas[nivel]
	trabajo = datos.copy()
	trabajo[columna] = trabajo[columna].fillna("Sin dato").astype(str).str.strip()
	trabajo.loc[trabajo[columna].eq(""), columna] = "Sin dato"

	resumen = trabajo.groupby(columna, dropna=False).size().to_frame("Registros")
	resumen["Participación (%)"] = resumen["Registros"] / len(trabajo) * 100
	resumen = resumen.sort_values("Registros", ascending=False)
	mayor, menor = resumen.iloc[0], resumen.iloc[-1]

	a, b, c = st.columns(3)
	a.metric("Total de registros", f"{len(trabajo):,}")
	b.metric("Territorios", f"{len(resumen):,}")
	c.metric("Participación del territorio principal", f"{mayor['Participación (%)']:.1f}%")

	st.subheader(f"Registros por {nivel.lower()}")
	st.bar_chart(resumen["Registros"])
	st.dataframe(
		resumen.style.format({"Participación (%)": "{:.2f}%"}),
		use_container_width=True,
	)

	st.markdown(
		f"**Mayor cantidad:** {resumen.index[0]} — {int(mayor['Registros']):,} registros "
		f"({mayor['Participación (%)']:.2f}%).  \n"
		f"**Menor cantidad:** {resumen.index[-1]} — {int(menor['Registros']):,} registros "
		f"({menor['Participación (%)']:.2f}%)."
	)
	top_n = min(5, len(resumen))
	concentracion = resumen.head(top_n)["Participación (%)"].sum()
	diferencia = int(mayor["Registros"] - menor["Registros"])
	st.write(
		f"Los {top_n} territorios con más registros concentran el **{concentracion:.2f}%** "
		f"del total. La diferencia entre el mayor y el menor es de **{diferencia:,} registros**."
	)

	# Comparar las variables numéricas permite identificar particularidades por zona.
	columnas_territoriales = {col for col in columnas.values() if col is not None}
	numericas = [
		col for col in trabajo.select_dtypes(include="number").columns
		if col not in columnas_territoriales
	]
	if numericas:
		st.subheader("Características y diferencias entre territorios")
		variable = st.selectbox("Variable numérica", numericas)
		valores = pd.to_numeric(trabajo[variable], errors="coerce")
		comparacion = valores.groupby(trabajo[columna]).agg(
			Promedio="mean", Mediana="median", Registros_validos="count"
		).sort_values("Promedio", ascending=False)
		st.dataframe(comparacion, use_container_width=True)
		validos = comparacion["Promedio"].dropna()
		if not validos.empty:
			territorio_alto, territorio_bajo = validos.index[0], validos.index[-1]
			st.write(
				f"El mayor promedio de **{variable}** se registra en **{territorio_alto}** "
				f"({validos.iloc[0]:.2f}) y el menor en **{territorio_bajo}** "
				f"({validos.iloc[-1]:.2f})."
			)