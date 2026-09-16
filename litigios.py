"""
Created on 10/06/2024
Provision litigios comerciales, hipotecarios y laborales
@author: frposada
"""
#%%-------------------------------- Librerias ----------------------------------
print("Importando librerías...")
# librerias de control
import sys
import os
import re
import time
import logging
from traceback import format_exc
import tkinter as tk
from tkinter import messagebox

# librerias especificas
import numpy as np
import pandas as pd
import unidecode
import datetime
import calendar
import numpy_financial as npf
import ctypes
import tkinter.font as tkFont
import warnings
from ImpalaHelper.Impala_Helper import Helper
import getpass

# mis librerias
from Fpack import funcionesPD

#%%---------------------------- Variables globales -----------------------------
print("Preparando el sistema...")
start_time = time.time()
path_dir = "\\".join(os.path.dirname(__file__).split("\\")[: len(os.path.dirname(__file__).split("\\")) - 1]) # Ruta del directorio padre

if not os.path.exists(path_dir + "/LOG"):
  os.mkdir(path_dir + "/LOG")
if os.path.isfile(path_dir + "/LOG/Error.json"):
  os.remove(path_dir + "/LOG/Error.json")
logging.basicConfig(level=20, format="[%(asctime)s] %(levelname)s: %(message)s",handlers=[logging.FileHandler(path_dir +"/LOG/Record.log", mode='w'),logging.StreamHandler(sys.stdout)])
logging.info("Iniciando...")

# reading parameters ...........................................................
logging.info('Leyendo parametros...')
df_contabilidad = pd.read_excel(path_dir + '/Parametros/Contabilidad.xlsx', sheet_name = None)
sociedades = df_contabilidad['SOCIEDADES']
cuentas = df_contabilidad['CUENTAS']
cuentas.columns = cuentas.iloc[0]
cuentas = cuentas.drop(cuentas.index[0])
transaccion = df_contabilidad['TRANSACCIONES']
fecha = pd.read_excel(f'{path_dir}/Parametros/Fecha corte.xlsx')

# Variables ....................................................................
dict_fields = {                                                                 # diccionario con los campos y sus tipos de datos
  'LLAVE': str,
  'LITIGIO': str,
  'SOCIEDAD': str,
  'NUMERO_SOCIEDAD' : int,
  'NUMERO_DE_PROCESO': str,
  'SUJETO_PRINCIPAL': str,
  'RESUMEN_PROCESO': str,
  'CENTRO_DE_COSTOS': str,
  'CUANTIA_INICIAL': float,
  'CUANTIA_MES_ANTERIOR': float,
  'CUANTIA_ACTUAL': float,
  'PROVISION_TOTAL_ANOS_ANTERIORES': float,
  'PROVISION_TOTAL_ANO_ACTUAL': float,
  'PROVISION_TOTAL_MES_ANTERIOR': float,
  'PROVISION_MES_ACTUAL': float,
  'PROVISION_TOTAL': float,
  'CALIFICACION_CONTINGENCIA_MES_ANTERIOR': str,
  'CALIFICACION_CONTINGENCIA': str,
  'PROCESO_NUEVO_EXISTIA': str,
  'PROCESO_VIGENTE_TERMINADO': str,
  'PAGOS_PARCIALES': float,
  'FECHA_INICIO_LITIGIO_MES_ANTERIOR': 'date',
  'FECHA_INICIO_LITIGIO': 'date',
  'FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR': 'date',
  'FECHA_PROBABLE_GASTO_PROVISION': 'date',
  'CLASIFICACION_CP_LP_MES_ANTERIOR': str,
  'CLASIFICACION_CP_LP': str,
  'VALORAR_IFRS': bool,
  'PROVISION_IFRS_ACTUAL': float,
  'DIAS_A_VALORAR': int,
  'TASA_DESCUENTO': float,
  'VALOR_PRESENTE_PROVISION_MES_ANTERIOR': float,
  'VALOR_PRESENTE_PROVISION_MES_ANTERIOR_NUEVA_TASA': float,
  'VALOR_PRESENTE_PROVISION_MES_ACTUAL': float,
  'AJUSTE_GASTO_FINANCIERO': float,
  'VALORACION_MES_ANTERIOR_MAS_GASTO_FINANCIERO': float,
  'AJUSTE_PROVISION_NIIF': float,
  'RECUPERACION': float,
  'SALDO_FINAL': float,
  'AJUSTE_61': float,
  'CUENTA_CONTINGENTE_1': str,
  'CUENTA_CONTINGENTE_2': str,
  'CUENTA_PROVISION_GASTO_FINANCIERO': str,
  'CUENTA_GASTO_FINANCIERO': str,
  'CUENTA_PROVISION_GASTO_PROVISION': str,
  'CUENTA_GASTO_PROVISION': str,
  'CUENTA_PROVISION_INGRESO_PROVISION': str,
  'CUENTA_INGRESO_PROVISION': str,
  'FECHA_CORTE': 'date'
}

fields = list(dict_fields.keys())                                               # Lista con los campos, extraídas de las llaves del diccionario

valid_values = {
    fields[1]: ['COMERCIALES', 'HIPOTECARIOS', 'LABORALES'],                    # LITIGIO
    fields[2]: sociedades['SOCIEDAD'].dropna().unique().tolist(),                # SOCIEDAD - tomado de Contabilidad.xlsx > SOCIEDADES
    fields[17]: ['REMOTA', 'EVENTUAL', 'PROBABLE', 'EVENTUAL CON PROVISION'],   # CALIFICACION_CONTINGENCIA
    fields[18]: ['NUEVO', 'EXISTIA'],                                           # PROCESO_NUEVO_EXISTIA
    fields[19]: ['VIGENTE', 'TERMINADO']                                        # PROCESO_VIGENTE_TERMINADO
}

# Definiendo la fecha de corte
today = datetime.date.today()
if fecha.loc[0]['Automatico?'] == 'si':
  logging.info('Fecha de corte automatica...')
  if today.month == 1:
    fecha_corte = datetime.date(today.year - 1, 12, calendar.monthrange(today.year - 1, 12)[1])
  else:
    fecha_corte = datetime.date(today.year, today.month - 1, calendar.monthrange(today.year, today.month -1)[1])
else:
  logging.info('Fecha de corte manual...')
  fecha['Fecha corte'] = fecha['Fecha corte'].dt.date
  fecha_corte = fecha.loc[0]['Fecha corte']
logging.info(f'Fecha de corte: {fecha_corte}')
fecha_corte = pd.to_datetime(fecha_corte)

# Definiendo la fecha de corte mes anterior
if fecha_corte.month == 1:
  fc_mes_ant = datetime.date(fecha_corte.year - 1, 12, calendar.monthrange(fecha_corte.year - 1, 12)[1])
else:
  fc_mes_ant = datetime.date(fecha_corte.year, fecha_corte.month - 1, calendar.monthrange(fecha_corte.year, fecha_corte.month -1)[1])

def resolve_input_file(input_dir, base_name, fecha_ref):
  """
  Resuelve el archivo de insumo para el mes de corte.
  Prioriza nombre con YYYY-MM; si no existe, toma YYYY-MM-DD del mismo mes.
  """
  ym = fecha_ref.strftime('%Y-%m')
  file_ym = f"{base_name}_{ym}.xlsx"
  path_ym = os.path.join(input_dir, file_ym)

  if os.path.isfile(path_ym):
    return file_ym

  pattern = re.compile(rf"^{re.escape(base_name)}_{ym}-\d{{2}}\.xlsx$", re.IGNORECASE)
  candidates = sorted([f for f in os.listdir(input_dir) if pattern.match(f)], reverse=True)

  if candidates:
    if len(candidates) > 1:
      logging.warning(f"Se encontraron varios insumos para {base_name} y {ym}. Se usara el mas reciente: {candidates[0]}")
    return candidates[0]

  raise FileNotFoundError(f"No se encontro insumo para {base_name} con periodo {ym}. Se esperaba {base_name}_{ym}.xlsx o {base_name}_{ym}-DD.xlsx")

in1_dir = f"{path_dir}/Insumos/Litigios_comerciales_hip"
in2_dir = f"{path_dir}/Insumos/Litigios_laborales"
in3_dir = f"{path_dir}/Insumos/Curva_TES"

# Cada insumo se resuelve dentro de su funcion (preprocessing/provision) para poder prevalidar uno aunque falten los demas

# reading inputs ...............................................................
logging.info("Leyendo resultados mes anterior...")
mes_ant = pd.read_excel(f"{path_dir}/Resultados/Provision litigios {fc_mes_ant.strftime('%Y%m%d')}.xlsx")
mes_ant = mes_ant.loc[mes_ant['PROCESO_VIGENTE_TERMINADO'] == 'VIGENTE']

#%%-------------------------- funciones y clases -------------------------------
try:
  def errores(e):
    "Indica como actuar en caso de que se presente un error en el programa"
    logging.error(e)
    traceback = format_exc()
    file = open(path_dir + "/LOG/Error.json", "w")
    file.write(traceback)
    file.close()
    root = tk.Tk()
    tk.messagebox.showerror(message=e, title="Error!")
    root.destroy()
    sys.exit()

  def preprocessing(laborales=True):
    """
    Organiza los df de los litigios laborales y los de comerciales e hipotecarios (Litisoft)
    identificando los campos necesarios, renombrando los campos, filtrando los registros y creando nuevos campos
    """
    #...........................................................................
    def clean_column_names(df):
      """
      Limpia los nombres de las columnas de un DataFrame de pandas.
      - Reemplaza espacios por guiones bajos.
      - Reemplaza diagonales por guiones bajos.
      - Elimina tildes y caracteres especiales.
      - Convierte los nombres a mayusculas.
      :param df: DataFrame de pandas.
      :return: DataFrame con nombres de columnas limpios.
      """
      def remove_multiple_underscores(input_str):
        "remueve los multiples guiones bajos"
        while '__' in input_str:
          input_str = input_str.replace('__', '_')
        return input_str

      new_columns = []
      for col in df.columns:
        col = col.upper()
        col = col.replace(' ', '_')
        col = col.replace('/', '_')
        col = remove_multiple_underscores(col)
        col = unidecode.unidecode(col)
        new_columns.append(col)

      df.columns = new_columns
      return df

    def validar_conversion(valor, tipo):
      """
      Intenta convertir un valor al tipo especificado.
      Si la conversión tiene éxito, devuelve True.
      Si lanza una excepción, devuelve False.
      """
      try:
        if tipo == 'date':
          pd.to_datetime(valor, errors='raise').date()
        else:
          tipo(valor)
        return True
      except Exception:
        return False

    def validar_fecha(x, y):
      """
      Valida que la fecha del parametro 1 sea mayor a la fecha del parametro 2,
      en caso de que no sea posible la conversion de los parametros a formato fecha, retorna False
      """
      try:
        x = pd.to_datetime(x, errors='raise').date()
        y = pd.to_datetime(y, errors='raise').date()
        return x > y
      except:
        return False

    def observacion(df, condicion, mensaje):
      "Agrega un mensaje de observación a los registros que cumplan con la condición"
      df.loc[condicion, 'OBSERVACION'] = df.loc[condicion, 'OBSERVACION'].fillna('') + mensaje
    #...........................................................................
    if laborales == False:
      in_dir, in_file = in1_dir, resolve_input_file(in1_dir, "Litigios_comerciales_e_hipotecarios", fecha_corte)
    else:
      in_dir, in_file = in2_dir, resolve_input_file(in2_dir, "Litigios_laborales", fecha_corte)
    logging.info(f"Preprocesando insumo {in_file}...")
    # reading inputs
    logging.info("Leyendo Insumo...")
    if laborales == False:
      df = pd.read_excel(f"{in_dir}/{in_file}", skiprows=1)
    else:
      df = pd.read_excel(f"{in_dir}/{in_file}")

    # Campos
    positions = [0,1,2,3,4,5,6,7,8,10,14,17,18,19,20,24]
    campos = [fields[pos] for pos in positions]
    campos_dict = {key: dict_fields[key] for key in campos}

    campos_litisoft = ['LINEA_DE_NEGOCIO','PRETENSION','VALOR_DEL_PAGO_1','FECHA_DEL_PAGO_1','VALOR_DEL_PAGO_2','FECHA_DEL_PAGO_2','VALOR_DEL_PAGO_3','FECHA_DEL_PAGO_3','VALOR_DEL_PAGO_4','FECHA_DEL_PAGO_4']
    campos.extend(campos_litisoft)

    if df.empty == True:
      raise ValueError('Insumo vacío')

    df = clean_column_names(df)
    df = df.apply(lambda col: col.map(lambda x: x.upper() if isinstance(x, str) else x))

    if laborales == False:                                                      # condicion para identificar si se trata de los litigios comerciales e hipotecarios
      line_comer = ['BANCOLOMBIA', 'FACTORING', 'FONDO INMOBILIARIO','LEASING','SUFI','TITULARIZADORA','NEQUI','VALORES','BANCA DE INVERSION','FIDUCIARIA']
      df.rename(columns={'CENTRO_COSTO': campos[7],'PROVISION':campos[10], 'CALIFICACION_CONTIGENCIA': campos[11], 'TIPO_ESTADO':campos[13], 'FECHA_PROBABLE_DE_GASTO_PROVISION':campos[15]}, inplace=True)
      df = df.reindex(columns = campos)
      df = df.loc[df['LINEA_DE_NEGOCIO'].isin(line_comer)]

      # LITIGIO
      df['LITIGIO'] = df['LITIGIO'].astype('object')
      df.loc[df['PRETENSION'] == 'REVISION CONTRATO DE MUTUO', 'LITIGIO'] = 'HIPOTECARIOS'
      df.loc[(df['PRETENSION'] != 'REVISION CONTRATO DE MUTUO') & (df['LINEA_DE_NEGOCIO'].isin(line_comer)), 'LITIGIO'] = 'COMERCIALES'

      # SOCIEDAD
      df['SOCIEDAD'] = df['SOCIEDAD'].astype('object')
      df.loc[df['LINEA_DE_NEGOCIO'].isin(line_comer[0:6]), 'SOCIEDAD'] = 'BANCOLOMBIA'
      df.loc[df['LINEA_DE_NEGOCIO'] == 'BANCA DE INVERSION', 'SOCIEDAD'] = 'BANCA DE INVERSION'
      df.loc[df['LINEA_DE_NEGOCIO'] == 'FIDUCIARIA', 'SOCIEDAD'] = 'FIDUCIARIA'
      df.loc[df['LINEA_DE_NEGOCIO'] == 'VALORES', 'SOCIEDAD'] = 'VALORES'
      df.loc[df['LINEA_DE_NEGOCIO'] == 'NEQUI', 'SOCIEDAD'] = 'NEQUI'

      # PROCESO_VIGENTE_TERMINADO
      df.loc[(df['PROCESO_VIGENTE_TERMINADO'] == 'INACTIVO') | (df['PROCESO_VIGENTE_TERMINADO'] == 'SUSPENDIDO'), 'PROCESO_VIGENTE_TERMINADO'] = 'VIGENTE'

      # PAGOS_PARCIALES
      mask = (df['FECHA_DEL_PAGO_1'].dt.year == fecha_corte.year) & (df['FECHA_DEL_PAGO_1'].dt.month == fecha_corte.month)
      df.loc[mask, 'PAGOS_PARCIALES'] = df.loc[mask, 'VALOR_DEL_PAGO_1']
      mask = (df['FECHA_DEL_PAGO_2'].dt.year == fecha_corte.year) & (df['FECHA_DEL_PAGO_2'].dt.month == fecha_corte.month)
      df.loc[mask, 'PAGOS_PARCIALES'] = df.loc[mask, 'VALOR_DEL_PAGO_2']
      mask = (df['FECHA_DEL_PAGO_3'].dt.year == fecha_corte.year) & (df['FECHA_DEL_PAGO_3'].dt.month == fecha_corte.month)
      df.loc[mask, 'PAGOS_PARCIALES'] = df.loc[mask, 'VALOR_DEL_PAGO_3']
      mask = (df['FECHA_DEL_PAGO_4'].dt.year == fecha_corte.year) & (df['FECHA_DEL_PAGO_4'].dt.month == fecha_corte.month)
      df.loc[mask, 'PAGOS_PARCIALES'] = df.loc[mask, 'VALOR_DEL_PAGO_4']

    df['PAGOS_PARCIALES'] = df['PAGOS_PARCIALES'].fillna(0)

    # NUMERO_SOCIEDAD
    df.loc[df['SOCIEDAD'] == 'BANCOLOMBIA', 'NUMERO_SOCIEDAD'] = int(funcionesPD.searchv(sociedades,'SOCIEDAD','BANCOLOMBIA','NUMERO_SOCIEDAD').iloc[0, 0])
    df.loc[df['SOCIEDAD'] == 'BANCA DE INVERSION', 'NUMERO_SOCIEDAD'] = int(funcionesPD.searchv(sociedades,'SOCIEDAD','BANCA DE INVERSION','NUMERO_SOCIEDAD').iloc[0, 0])
    df.loc[df['SOCIEDAD'] == 'FIDUCIARIA', 'NUMERO_SOCIEDAD'] = int(funcionesPD.searchv(sociedades,'SOCIEDAD','FIDUCIARIA','NUMERO_SOCIEDAD').iloc[0, 0])
    df.loc[df['SOCIEDAD'] == 'VALORES', 'NUMERO_SOCIEDAD'] = int(funcionesPD.searchv(sociedades,'SOCIEDAD','VALORES','NUMERO_SOCIEDAD').iloc[0, 0])
    df.loc[df['SOCIEDAD'] == 'NEQUI', 'NUMERO_SOCIEDAD'] = int(funcionesPD.searchv(sociedades,'SOCIEDAD','NEQUI','NUMERO_SOCIEDAD').iloc[0, 0])

    # llave
    df['LLAVE'] = df['LITIGIO'] + df['SOCIEDAD'] + df['NUMERO_DE_PROCESO'].astype(str)

    df = df.reindex(columns = campos[0:16])
    df = df[(df['PROCESO_NUEVO_EXISTIA'] == 'NUEVO') | (df['LLAVE'].isin(mes_ant['LLAVE']))] # filtro de registros, se conservan los registros cuyo 'PROCESO_NUEVO_EXISTIA' sea 'NUEVO' o cuya 'LLAVE' este en la sabana del mes anterior
    #---------------------------------------------------------------------------
    # controles
    df['OBSERVACION'] = None
    for campo, tipo in campos_dict.items():
      if campo == campos[15]:                                                   # condicion para identificar el campo 'FECHA_PROBABLE_GASTO_PROVISION'
        df1 = df.loc[df[campos[11]].isin(['PROBABLE', 'EVENTUAL CON PROVISION'])].copy() # filtro del df, se conservan los registros cuyo 'CALIFICACION_CONTIGENCIA' sea 'PROBLABLE' o 'EVENTUAL CON PROVISION'
        df1 = df1.loc[df1[campos[13]] == 'VIGENTE']                             # filtro del df, se conservan los registros cuyo 'PROCESO_VIGENTE_TERMINADO' sea 'VIGENTE'
        validos = df1[campo].apply(lambda x: validar_fecha(x, fecha_corte))
        nulos = df1[campo].isnull()
        observacion(df1, ~validos & ~nulos, f'{campo} ERRADO; ')
        observacion(df1, nulos, f'{campo} NULO; ')
        df.update(df1)
      else:
        validos = df[campo].apply(lambda x: validar_conversion(x, tipo))
        nulos = df[campo].isnull()
        if campo in valid_values:
          val_validos = df[campo].isin(valid_values.get(campo, []))
          observacion(df, (~validos | ~val_validos) & ~nulos, f'{campo} ERRADO; ')
          observacion(df, nulos, f'{campo} NULO; ')
        elif campo == campos[7]:                                                # condicion para identificar el campo 'CENTRO_DE_COSTOS'
          df1 = df.loc[df[campos[11]].isin(['PROBABLE', 'EVENTUAL CON PROVISION'])].copy() # filtro del df, se conservan los registros cuyo 'CALIFICACION_CONTIGENCIA' sea 'PROBLABLE' o 'EVENTUAL CON PROVISION'
          val_validos = df1[campo].apply(lambda x: isinstance(x, str) and len(x) == 10 and x.startswith('C')) # Validar que el valor sea un string, que tenga 10 caracteres y que empiece con 'C'
          nulos = df1[campo].isnull()
          observacion(df1, (~validos | ~val_validos) & ~nulos, f'{campo} ERRADO; ')
          observacion(df1, nulos, f'{campo} NULO; ')
          df.update(df1)
        else:
          observacion(df, ~validos & ~nulos, f'{campo} ERRADO; ')
          observacion(df, nulos, f'{campo} NULO; ')

    # transformaciones
    if df['OBSERVACION'].isnull().all():
      logging.info('Preprocesamiento: insumo correcto')
      df = df.drop(columns = 'OBSERVACION')
      # tranformacion al tipo de dato especificado
      for campo, tipo in campos_dict.items():
        if tipo == 'date':
          df[campo] = pd.to_datetime(df[campo], errors='coerce')
        else:
          df[campo] = df[campo].astype(tipo, errors='raise')
    else:
      file_name = in_file.replace('.xlsx', '')
      funcionesPD.save_df(f"{path_dir}/Resultados" , f"Preprocesamiento {file_name}", df, "xlsx")
      raise ValueError('Preprocesamiento: insumo incorrecto')
    df[campos[7]] = df[campos[7]].replace('nan', pd.NA)                         # Reemplazar valores 'nan' por NaN en la columna 'CENTRO_DE_COSTOS'
    return (df)

  def organized_output_last_month(df):
    """
    Organiza el df del output del mes anterior y lo consolida con el consolidado del mes de cierre
    identificando los campos necesarios, renombrandolos y filtrando por los registros
    a tener en cuenta para el calculo de la provision del cierre. Adicionalmente,
    consolida la informacion con el consolidado del mes de cierre.
    """
    logging.info("Organizando output del mes anterior...")
    # Diccionario con mapeo de columnas actuales a columnas deseadas
    column_mapping = {
      fields[0]: fields[0],                                                     # LLAVE por LLAVE
      fields[10]: fields[9],                                                    # CANTIA_ACTUAL por CUANTIA_MES_ANTERIOR
      fields[11]: fields[11],                                                   # PROVISION_TOTAL_ANOS_ANTERIORES por PROVISION_TOTAL_ANOS_ANTERIORES
      fields[12]: fields[12],                                                   # PROVISION_TOTAL_ANO_ACTUAL por PROVISION_TOTAL_ANO_ACTUAL
      fields[15]: fields[13],                                                   # PROVISION_TOTAL por PROVISION_TOTAL_MES_ANTERIOR
      fields[17]: fields[16],                                                   # CALIFICACION_CONTINGENCIA por CALIFICACION_CONTINGENCIA_MES_ANTERIOR
      fields[33]: fields[31],                                                   # VALOR_PRESENTE_PROVISION_MES_ACTUAL por VALOR_PRESENTE_PROVISION_MES_ANTERIOR
      fields[22]: fields[21],                                                   # FECHA_INICIO_LITIGIO por FECHA_INICIO_LITIGIO_MES_ANTERIOR
      fields[24]: fields[23]                                                    # FECHA_PROBABLE_GASTO_PROVISION por FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR
    }
    desired_columns = list(column_mapping.keys())
    df1 = mes_ant.reindex(columns=desired_columns).copy()
    df1.rename(columns=column_mapping, inplace=True)

    # consolidando
    logging.info("Consolidando output del mes anterior...")
    desired_columns = list(column_mapping.values())
    df = df.merge(df1[desired_columns], on='LLAVE', how='left')

    # organizando campos
    df[fields[23]] = pd.to_datetime(df[fields[23]], errors='coerce')            # FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR - convierte las fechas al formato adecuado
    df[fields[21]] = pd.to_datetime(df[fields[21]], errors='coerce')            # FECHA_INICIO_LITIGIO_MES_ANTERIOR - convierte las fechas al formato adecuado

    desired_columns = [desired_columns[idx] for idx in [1, 2, 3, 4, 6]]         # Lista de columnas deseadas, extraídas de los valores del diccionario
    for column in desired_columns:
      df[column] = df[column].fillna(0.0)

    return df

  def processing_data(df, tasa):
    """
    Porcesa la informacion del consolidado de litigios, calculando la provision
    Genera todos los demas campos necesarios para el calculo de la provision,
    y el movimiento de cuentas por cada litigio
    """
    logging.info("Procesando datos...")

    # Cambio de "EVENTUAL CON PROVISION" a "PROBABLE"
    mask = df['CALIFICACION_CONTINGENCIA'] == 'EVENTUAL CON PROVISION'          # Crear una máscara para filtrar los registros que cumplen la condición
    df_mask = df[mask]                                                          # Filtrar los registros que cumplen la condición

    if not df_mask.empty:                                                       # Verificar si el DataFrame filtrado no está vacío
      logging.info(f"Se cambiarán a 'PROBABLE' {len(df_mask)} litigios 'EVENTUAL CON PROVISION':")
      for _, row in df_mask.iterrows():                                         # Iterar sobre los registros filtrados
        logging.info(f'  - LLAVE: {row["LLAVE"]}, SUJETO_PRINCIPAL: {row["SUJETO_PRINCIPAL"]}, {row["CALIFICACION_CONTINGENCIA"]} -> PROBABLE')
      df.loc[mask, 'CALIFICACION_CONTINGENCIA'] = 'PROBABLE'                    # Actualizar la columna 'CALIFICACION_CONTINGENCIA' a 'PROBABLE' para los registros filtrados
    else:
      logging.info("No hay litigios 'EVENTUAL CON PROVISION' para cambiar")

    # PROVISION_MES_ACTUAL
    df.loc[(df['LITIGIO'] != 'LABORALES') & (df['PROCESO_NUEVO_EXISTIA'] == 'EXISTIA'), 'PROVISION_MES_ACTUAL'] =  df['PROVISION_MES_ACTUAL'] - df['PROVISION_TOTAL_MES_ANTERIOR']
    df.loc[df['PROCESO_VIGENTE_TERMINADO'] == 'TERMINADO', 'PROVISION_MES_ACTUAL'] = 0.0

    # PROVISION_TOTAL_ANO_ACTUAL y PROVISION_TOTAL_ANOS_ANTERIORES
    if fecha_corte.month == 1:
      df['PROVISION_TOTAL_ANOS_ANTERIORES'] = df['PROVISION_TOTAL_ANO_ACTUAL']
      df['PROVISION_TOTAL_ANO_ACTUAL'] = df['PROVISION_MES_ACTUAL']
    else:
      df['PROVISION_TOTAL_ANO_ACTUAL'] = df['PROVISION_TOTAL_ANO_ACTUAL'] + df['PROVISION_MES_ACTUAL']

    # PROVISION_TOTAL
    df['PROVISION_TOTAL'] = df['PROVISION_TOTAL_MES_ANTERIOR'] + df['PROVISION_MES_ACTUAL']

    # FECHA_INICIO_LITIGIO
    df.loc[df['CALIFICACION_CONTINGENCIA'] != 'PROBABLE','FECHA_INICIO_LITIGIO'] = pd.NaT
    df.loc[(df['CALIFICACION_CONTINGENCIA'] == 'PROBABLE') & (df['CALIFICACION_CONTINGENCIA_MES_ANTERIOR'] == 'PROBABLE'),'FECHA_INICIO_LITIGIO'] = df['FECHA_INICIO_LITIGIO_MES_ANTERIOR']
    df.loc[(df['CALIFICACION_CONTINGENCIA'] == 'PROBABLE') & (df['CALIFICACION_CONTINGENCIA_MES_ANTERIOR'] != 'PROBABLE'), 'FECHA_INICIO_LITIGIO'] = pd.to_datetime(fc_mes_ant)

    # CLASIFICACION_CP_LP_MES_ANTERIOR
    difference = (df['FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR'] - df['FECHA_INICIO_LITIGIO']).dt.days
    df.loc[difference < 360, 'CLASIFICACION_CP_LP_MES_ANTERIOR'] = 'CP'
    df.loc[difference >= 360, 'CLASIFICACION_CP_LP_MES_ANTERIOR'] = 'LP'
    df.loc[(df['FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR'].isna()) | (df['FECHA_INICIO_LITIGIO'].isna()), 'CLASIFICACION_CP_LP_MES_ANTERIOR'] = None

    # CLASIFICACION_CP_LP
    difference = (df['FECHA_PROBABLE_GASTO_PROVISION'] - df['FECHA_INICIO_LITIGIO']).dt.days
    df.loc[difference < 360, 'CLASIFICACION_CP_LP'] = 'CP'
    df.loc[difference >= 360, 'CLASIFICACION_CP_LP'] = 'LP'
    df.loc[(df['FECHA_PROBABLE_GASTO_PROVISION'].isna()) | (df['FECHA_INICIO_LITIGIO'].isna()) | (df['PROCESO_VIGENTE_TERMINADO'] == 'TERMINADO'), 'CLASIFICACION_CP_LP'] = None

    # VALORAR_IFRS
    df['VALORAR_IFRS'] = False
    df.loc[(df['CLASIFICACION_CP_LP'] == 'LP') & ((df['CALIFICACION_CONTINGENCIA'] == 'PROBABLE') | (df['CALIFICACION_CONTINGENCIA_MES_ANTERIOR'] == 'PROBABLE')), 'VALORAR_IFRS'] = True

    # PROVISION_IFRS_ACTUAL
    df['PROVISION_IFRS_ACTUAL'] = 0.0
    df.loc[df['PROCESO_VIGENTE_TERMINADO'] == 'VIGENTE', 'PROVISION_IFRS_ACTUAL'] = -df['PROVISION_TOTAL']

    # DIAS_A_VALORAR
    df['DIAS_A_VALORAR'] = 0
    df.loc[df['VALORAR_IFRS'] == True, 'DIAS_A_VALORAR'] = (df['FECHA_PROBABLE_GASTO_PROVISION'] - fecha_corte).dt.days

    # TASA_DESCUENTO
    df['TASA_DESCUENTO'] = df['DIAS_A_VALORAR'].apply(lambda x: 0.0 if x == 0 else funcionesPD.searchv(tasa, 'DiasVenc.', x, 'CurvaSpotDiscreta').iloc[0, 0])

    # VALOR_PRESENTE_PROVISION_MES_ACTUAL
    warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in divide") # Ignorar advertencias por división inválida
    df['VALOR_PRESENTE_PROVISION_MES_ACTUAL'] = npf.pv(rate=df['TASA_DESCUENTO'], nper = df['DIAS_A_VALORAR']/365, pmt=0, fv=-df['PROVISION_IFRS_ACTUAL'])

    # VALOR_PRESENTE_PROVISION_MES_ANTERIOR_NUEVA_TASA
    df['VALOR_PRESENTE_PROVISION_MES_ANTERIOR_NUEVA_TASA'] = npf.pv(rate=df['TASA_DESCUENTO'], nper = df['DIAS_A_VALORAR']/365, pmt=0, fv=df['PROVISION_TOTAL_MES_ANTERIOR'])
    df.loc[df['VALORAR_IFRS'] == False, 'VALOR_PRESENTE_PROVISION_MES_ANTERIOR_NUEVA_TASA'] = 0.0
    warnings.filterwarnings("default", category=RuntimeWarning, message="invalid value encountered in divide") # Volver a activar la advertencia específica

    # AJUSTE_GASTO_FINANCIERO
    df['AJUSTE_GASTO_FINANCIERO'] = 0.0
    mask = df['VALORAR_IFRS'] == True                                           # Crear una máscara para filtrar los registros que cumplen la condición
    cond1 = (df['PROVISION_IFRS_ACTUAL'] == -df['PROVISION_TOTAL_MES_ANTERIOR'] + df['PAGOS_PARCIALES']) # Crear una condición para filtrar los registros que cumplen la condición
    cond2 = (df['PROVISION_IFRS_ACTUAL'] != -df['PROVISION_TOTAL_MES_ANTERIOR'] + df['PAGOS_PARCIALES']) # Crear una condición para filtrar los registros que cumplen la condición
    df.loc[mask & cond1, 'AJUSTE_GASTO_FINANCIERO'] = df['VALOR_PRESENTE_PROVISION_MES_ACTUAL'] - df['VALOR_PRESENTE_PROVISION_MES_ANTERIOR'] - df['PAGOS_PARCIALES'] # Asignar un valor a la columna 'AJUSTE_GASTO_FINANCIERO' donde la máscara y la condición son True
    df.loc[mask & cond2, 'AJUSTE_GASTO_FINANCIERO'] = df['VALOR_PRESENTE_PROVISION_MES_ANTERIOR_NUEVA_TASA'] - df['VALOR_PRESENTE_PROVISION_MES_ANTERIOR'] # Asignar un valor a la columna 'AJUSTE_GASTO_FINANCIERO' donde la máscara y la condición son True


    # VALORACION_MES_ANTERIOR_MAS_GASTO_FINANCIERO
    df['VALORACION_MES_ANTERIOR_MAS_GASTO_FINANCIERO'] = df['VALOR_PRESENTE_PROVISION_MES_ANTERIOR'] + df['AJUSTE_GASTO_FINANCIERO']

    # AJUSTE_PROVISION_NIIF
    def calcular_niif(row):
      "Calcula el ajuste de provision NIIF"

      if row['PROCESO_VIGENTE_TERMINADO'] == 'TERMINADO':
        if (row['PROVISION_TOTAL_MES_ANTERIOR'] == row['PROVISION_MES_ACTUAL']) & (row['PAGOS_PARCIALES'] == 0):
          return 0
        else:
          return row['VALOR_PRESENTE_PROVISION_MES_ACTUAL'] - row['VALORACION_MES_ANTERIOR_MAS_GASTO_FINANCIERO'] - row['PAGOS_PARCIALES']
      else:
        if (row['PROVISION_TOTAL_MES_ANTERIOR'] == row['PROVISION_TOTAL']) & (row['PAGOS_PARCIALES'] == 0):
          return 0
        elif abs(row['PAGOS_PARCIALES']) > abs(row['VALORACION_MES_ANTERIOR_MAS_GASTO_FINANCIERO']):
          return -row['PROVISION_TOTAL_MES_ANTERIOR'] - row['PAGOS_PARCIALES']
        else:
          return row['VALOR_PRESENTE_PROVISION_MES_ACTUAL'] - row['VALORACION_MES_ANTERIOR_MAS_GASTO_FINANCIERO'] - row['PAGOS_PARCIALES']
    df['AJUSTE_PROVISION_NIIF'] = df.apply(calcular_niif, axis=1)

    # RECUPERACION
    def calcular_recuperacion(row):
      "calcula la recuperacion"
      x = 0
      if row['PROVISION_TOTAL_ANO_ACTUAL'] >= 0:
        x = row['PROVISION_TOTAL_ANO_ACTUAL']

      y = 0
      if row['PROVISION_MES_ACTUAL'] != row['PROVISION_TOTAL_ANO_ACTUAL']:
        y = row['PROVISION_TOTAL_ANO_ACTUAL'] - row['PROVISION_MES_ACTUAL'] + row['PAGOS_PARCIALES']

      if row['PROVISION_TOTAL_ANOS_ANTERIORES'] > 0:
        if row['PROCESO_VIGENTE_TERMINADO'] == 'TERMINADO':
          if -row['VALOR_PRESENTE_PROVISION_MES_ANTERIOR'] - row['PAGOS_PARCIALES'] - x < 0:
            return 0
          else:
            return -row['VALOR_PRESENTE_PROVISION_MES_ANTERIOR'] - row['PAGOS_PARCIALES'] - x
        else:
          if row['PROVISION_TOTAL_ANO_ACTUAL'] < 0 and row['PROVISION_MES_ACTUAL'] + row['PAGOS_PARCIALES'] < 0:
            return (row['PROVISION_MES_ACTUAL'] + row['PAGOS_PARCIALES'] + y) * -1
          else:
            return 0
      else:
          return 0
    df['RECUPERACION'] = df.apply(calcular_recuperacion, axis=1)

    # SALDO_FINAL
    df['SALDO_FINAL'] = 0.0
    df.loc[df['PROCESO_VIGENTE_TERMINADO'] == 'VIGENTE', 'SALDO_FINAL'] = df['VALOR_PRESENTE_PROVISION_MES_ACTUAL']

    # AJUSTE_61
    df.loc[df['PROCESO_VIGENTE_TERMINADO'] == 'TERMINADO', 'AJUSTE_61'] = -df['CUANTIA_ACTUAL']
    df.loc[df['PROCESO_VIGENTE_TERMINADO'] != 'TERMINADO', 'AJUSTE_61'] = df['CUANTIA_ACTUAL'] - df['CUANTIA_MES_ANTERIOR']

    # CUENTA_CONTINGENTE_1
    df['CUENTA_CONTINGENTE_1'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_CONTINGENTE_1').iloc[0,0])

    # CUENTA_CONTINGENTE_2
    df['CUENTA_CONTINGENTE_2'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_CONTINGENTE_2').iloc[0,0])

    # CUENTA_PROVISION_GASTO_FINANCIERO
    df['CUENTA_PROVISION_GASTO_FINANCIERO'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_PROVISION_GASTO_FINANCIERO').iloc[0,0])

    # CUENTA_GASTO_FINANCIERO
    df['CUENTA_GASTO_FINANCIERO'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_GASTO_FINANCIERO').iloc[0,0])

    # CUENTA_PROVISION_GASTO_PROVISION
    df['CUENTA_PROVISION_GASTO_PROVISION'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_PROVISION_GASTO_PROVISION').iloc[0,0])

    # CUENTA_GASTO_PROVISION
    df['CUENTA_GASTO_PROVISION'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_GASTO_PROVISION').iloc[0,0])

    # CUENTA_PROVISION_INGRESO_PROVISION
    df['CUENTA_PROVISION_INGRESO_PROVISION'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_PROVISION_INGRESO_PROVISION').iloc[0,0])

    # CUENTA_INGRESO_PROVISION
    df['CUENTA_INGRESO_PROVISION'] = df['LITIGIO'].apply(lambda x: funcionesPD.searchv(cuentas, 'LITIGIO', x, 'CUENTA_INGRESO_PROVISION').iloc[0,0])

    # FECHA_CORTE
    df['FECHA_CORTE'] = fecha_corte

    # organizando df
    df['FECHA_INICIO_LITIGIO_MES_ANTERIOR'] = pd.to_datetime(df['FECHA_INICIO_LITIGIO_MES_ANTERIOR'], errors='coerce').dt.date
    df['FECHA_INICIO_LITIGIO'] = pd.to_datetime(df['FECHA_INICIO_LITIGIO'], errors='coerce').dt.date
    df['FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR'] = pd.to_datetime(df['FECHA_PROBABLE_GASTO_PROVISION_MES_ANTERIOR'], errors='coerce').dt.date
    df['FECHA_PROBABLE_GASTO_PROVISION'] = pd.to_datetime(df['FECHA_PROBABLE_GASTO_PROVISION'], errors='coerce').dt.date
    df['FECHA_CORTE'] = pd.to_datetime(df['FECHA_CORTE'], errors='coerce').dt.date
    df = df.reindex(columns = fields)
    return df

  def accounting_colgaap(df1):
    "Totaliza la contabilidad bajo COLGAAP solo las cuentas contingentes"

    # creacion df plantilla
    df = pd.DataFrame(columns=['CUENTA', 'DESCRIPCION', 'LITIGIO', 'SOCIEDAD'])
    descripcion = ['CUENTA_CONTINGENTE_1', 'CUENTA_CONTINGENTE_2']
    litigios  = valid_values['LITIGIO']
    sociedades = valid_values['SOCIEDAD']

    # Generación de las combinaciones de cuentas, litigios y sociedades
    for lit in litigios:
      for desc in descripcion:
        for soc in sociedades:
          cuenta = funcionesPD.searchv(cuentas, 'LITIGIO', lit, desc).iloc[0, 0]
          df.loc[len(df)] = [cuenta, desc, lit, soc]
    df['LLAVE'] = df['LITIGIO'] + df['SOCIEDAD'] + df['CUENTA'].astype(str)

    # Identificando ajustes del cierre .........................................
    # Agrupación y suma de los valores por tipo de cuenta, litigio y sociedad
    con_1 = df1.groupby(['CUENTA_CONTINGENTE_1', 'LITIGIO', 'SOCIEDAD'])['AJUSTE_61'].sum().rename('AJUSTE').reset_index()
    con_2 = (df1.groupby(['CUENTA_CONTINGENTE_2', 'LITIGIO', 'SOCIEDAD'])['AJUSTE_61'].sum() * -1).rename('AJUSTE').reset_index()

    # Ajustar el nombre de la columna de agrupación para unificación
    con_1 = con_1.rename(columns={'CUENTA_CONTINGENTE_1': 'CUENTA'})
    con_2 = con_2.rename(columns={'CUENTA_CONTINGENTE_2': 'CUENTA'})

    # Concatenación de los DataFrames
    ajuste = pd.concat([con_1, con_2]).reset_index(drop=True)
    ajuste['LLAVE'] = ajuste['LITIGIO'] + ajuste['SOCIEDAD'] + ajuste['CUENTA'].astype(str)

    # Fusion de los DF .........................................................
    df = pd.merge(df, ajuste[['LLAVE', 'AJUSTE']], on='LLAVE', how='left')
    df['AJUSTE'] = df['AJUSTE'].fillna(0)
    df.drop(columns=['LLAVE'], inplace=True)
    return df

  def accounting_ifrs(df1):
    "Totaliza la contabilidad bajo IFRS"
    logging.info("Totalizando contabilidad bajo IFRS...")
    # creacion df plantilla
    df = pd.DataFrame(columns=['CUENTA', 'DESCRIPCION', 'LITIGIO', 'SOCIEDAD'])
    descripcion = ['CUENTA_PROVISION_GASTO_FINANCIERO', 'CUENTA_GASTO_FINANCIERO', 'CUENTA_PROVISION_GASTO_PROVISION', 'CUENTA_GASTO_PROVISION', 'CUENTA_PROVISION_INGRESO_PROVISION', 'CUENTA_INGRESO_PROVISION']
    litigios  = valid_values['LITIGIO']
    sociedades = valid_values['SOCIEDAD']

    # Generación de las combinaciones de cuentas, litigios y sociedades
    for lit in litigios:
      for desc in descripcion:
        for soc in sociedades:
          cuenta = funcionesPD.searchv(cuentas, 'LITIGIO', lit, desc).iloc[0, 0]
          df.loc[len(df)] = [cuenta, desc, lit, soc]
    df['LLAVE'] = df['CUENTA'].astype(str) + df['DESCRIPCION'] + df['LITIGIO'] + df['SOCIEDAD']

    # Identificando ajustes del cierre .........................................
    # Agrupación y suma de los valores por tipo de cuenta, litigio y sociedad
    pgf = df1.groupby([descripcion[0], 'LITIGIO', 'SOCIEDAD'])['AJUSTE_GASTO_FINANCIERO'].sum().rename('AJUSTE').reset_index()

    pgp = df1.groupby([descripcion[2], 'LITIGIO', 'SOCIEDAD'])['AJUSTE_PROVISION_NIIF'].sum().rename('AJUSTE').reset_index()
    pgp2 = df1.groupby([descripcion[2], 'LITIGIO', 'SOCIEDAD'])['RECUPERACION'].sum().rename('AJUSTE').reset_index()
    pgp = pd.merge(pgp, pgp2, on=[descripcion[2], 'LITIGIO', 'SOCIEDAD'], suffixes=('_pgp', '_pgp2'))
    pgp['AJUSTE'] = pgp['AJUSTE_pgp'] - pgp['AJUSTE_pgp2']
    pgp.drop(columns=['AJUSTE_pgp', 'AJUSTE_pgp2'], inplace=True)

    pip = df1.groupby([descripcion[4], 'LITIGIO', 'SOCIEDAD'])['RECUPERACION'].sum().rename('AJUSTE').reset_index()

    # Ajustar el nombre de la columna de agrupación para unificación
    pgf = pgf.rename(columns={descripcion[0]:'CUENTA'})
    pgp = pgp.rename(columns={descripcion[2]:'CUENTA'})
    pip = pip.rename(columns={descripcion[4]:'CUENTA'})

    # organizando las demas cuentas
    gf = pgf.copy()
    gf['AJUSTE'] = gf['AJUSTE'] * -1
    gp = pgp.copy()
    gp['AJUSTE'] = gp['AJUSTE'] * -1
    ip = pip.copy()
    ip['AJUSTE'] = pip['AJUSTE'] * -1

    gf['CUENTA'] = gf['CUENTA'].apply(lambda x: funcionesPD.searchv(cuentas, descripcion[0], x, descripcion[1]).iloc[0, 0])
    gp['CUENTA'] = gp['CUENTA'].apply(lambda x: funcionesPD.searchv(cuentas, descripcion[2], x, descripcion[3]).iloc[0, 0])
    ip['CUENTA'] = ip['CUENTA'].apply(lambda x: funcionesPD.searchv(cuentas,descripcion[4], x, descripcion[5]).iloc[0, 0])

    # descripcion
    pgf['DESCRIPCION'] = descripcion[0]
    gf['DESCRIPCION'] = descripcion[1]
    pgp['DESCRIPCION'] = descripcion[2]
    gp['DESCRIPCION'] = descripcion[3]
    pip['DESCRIPCION'] = descripcion[4]
    ip['DESCRIPCION'] = descripcion[5]

    # Concatenación de los DataFrames
    ajuste = pd.concat([pgf, gf, pgp, gp, pip, ip]).reset_index(drop=True)
    ajuste['LLAVE'] = ajuste['CUENTA'].astype(str) + ajuste['DESCRIPCION'] + ajuste['LITIGIO'] + ajuste['SOCIEDAD']

    # Fusion de los DF .........................................................
    df = pd.merge(df, ajuste[['LLAVE', 'AJUSTE']], on='LLAVE', how='left')
    df['AJUSTE'] = df['AJUSTE'].fillna(0)

    df.drop(columns=['LLAVE'], inplace=True)
    return df

  def template(df1):
    "Genera la plantilla SAP para montar la contabilidad al sistema de transacciones agiles"
    #...........................................................................
    def get_cc_cb(lista, tipo):
        if tipo == 'ajuste_61':                                                 # COOLGAP - cuentas contingentes
          c_costo = 'x'
          c_beneficio = 'x'
        else:
          c_costo = funcionesPD.searchv(sociedades, 'NUMERO_SOCIEDAD', soc, f'{lit}_CENTRO_COSTO').iloc[0, 0]
          if c_costo == 'TODOS':
            c_costo = df1.loc[i][fields[7]]                                     # tomando el centro de costo de la sabana
          c_beneficio = funcionesPD.searchv(sociedades, 'NUMERO_SOCIEDAD', soc, f'{lit}_CENTRO_BENEFICIO').iloc[0, 0]
          if c_beneficio == 'TODOS':
            c_beneficio = df1.loc[i][fields[7]]                                 # tomando el centro de costo de la sabana
            c_beneficio = 'I100100' + c_beneficio[7:]                           # construyendo el centro de beneficio a partir del centro de costo
        lista.append([tipo, lit, soc, c_costo, c_beneficio, ajuste])
        return lista

    def get_accounts(tipo):
      """
      Identifica las cuentas a debitar y acreditar basado en el ajuste."
      parametros: tipo -> indica el tipo de ajuste a trabajar, mediante el cual se determina las cuentas a debitar y acreditar.
      """
      if tipo == 'ajuste_61':                                                   # COOLGAP - cuentas contingentes
        count1,count2 = fields[40], fields[41]
      elif tipo == 'pgf':                                                       # IFRS - provision gasto financiero
        count1,count2 = fields[42], fields[43]
      elif tipo == 'pgp':                                                       # IFRS - provision gasto provision
        count1,count2 = fields[44], fields[45]
      elif tipo == 'pip':                                                       # IFRS - provision ingreso provision
        count1,count2 = fields[46], fields[47]

      if ajuste > 0:
        c_debitar = funcionesPD.searchv(cuentas, 'LITIGIO', lit, count1).iloc[0, 0]
        c_acreditar = funcionesPD.searchv(cuentas, 'LITIGIO', lit, count2).iloc[0, 0]
      else:
        c_debitar = funcionesPD.searchv(cuentas, 'LITIGIO', lit, count2).iloc[0, 0]
        c_acreditar = funcionesPD.searchv(cuentas, 'LITIGIO', lit, count1).iloc[0, 0]
      return c_debitar, c_acreditar

    def generate_register(df, c_debitar, c_acreditar):
      "Genera un registro en la plantilla SAP"
      # identificando transaccion
      transaccion2 = transaccion.loc[transaccion['LITIGIO'] == lit].copy()
      transaccion2 = transaccion2.loc[transaccion2['NUMERO_SOCIEDAD'] == soc]
      transaccion2 = transaccion2.loc[(transaccion2['CUENTA_A_DEBITAR'] == c_debitar) & (transaccion2['CUENTA_A_ACREDITAR'] == c_acreditar)].reset_index(drop=True)
      texto = transaccion2.loc[0]['DESCRIPCION']

      # identificando si la transaccion agil lleva centro de costo
      c_costo = transaccion2.loc[0]['CENTRO_COSTO']
      if c_costo == 'APLICA':
        c_costo = df_totales.loc[i]['c_costo']
      else:
        c_costo = np.nan

      # identificando si la transaccion agil lleva centro de beneficio
      c_beneficio = transaccion2.loc[0]['CENTRO_BENEFICIO']
      if c_beneficio == 'APLICA':
        c_beneficio = df_totales.loc[i]['c_beneficio']
      else:
        c_beneficio = np.nan

      # creacion registro en la plantilla SAP
      diccionario = {
        campos[0]: transaccion2.loc[0]['CODIGO_TRANSACCION'],                   # identificacion de codigo de transaccion
        campos[1]: str_today,                                                   # identificacion de Fecha Documento
        campos[2]: str_fecha_corte,                                             # identificacion de Fecha Contabilización
        campos[3]: transaccion2.loc[0]['MONEDA'],                               # identificacion de Moneda
        campos[4]: f'{lit}{soc}',                                               # identificacion de referencia
        campos[6]: [abs(round(float(ajuste), 2))],                              # identificacion de ajuste (necesario redondear a 2 decimales y trabajarlo en valor absoluto)
        campos[7]: c_costo,                                                     # identificacion de centro de costo
        campos[8]: texto,                                                       # identificacion de texto
        campos[9]: c_beneficio,                                                 # identificacion de centro de beneficio
        campos[10]: transaccion2.loc[0]['SEGMENTO_DEBITO'],                     # identificacion de segmento debito
        campos[11]: transaccion2.loc[0]['SEGMENTO_CREDITO'],                    # identificacion de segmento credito
        campos[13]: 1                                                           # identificacion de moneda doc
      }

      df0 = pd.DataFrame(diccionario)
      df0 = df0.reindex(columns=campos)
      if df.empty:
          df = df0
      else:
          df = pd.concat([df, df0], ignore_index=True)
      return df
  #.............................................................................
    logging.info('Definiendo plantilla SAP...')
    campos = ['Código Transacción', 'Fecha Documento', 'Fecha Contabilización', 'Moneda', 'Referencia', 'Texto Cabecera Documento', 'Importe en Moneda de Trx.',
    'Centro de Coste', 'Texto', 'Centro de Beneficio', 'Segmento del Débito', 'Segmento del Crédito', 'Moneda Doc', 'Tasa de Cambio', 'Fecha Valor',
    'Cálculo Impuestos', 'Indicador Impuestos', 'Importe Moneda Local', 'Sociedad GL Asociada', 'NIT de Tercero', 'Dígito Verificación', 'Detalle 1',
    'Detalle 2', 'Detalle 3', 'Detalle 4', 'Detalle 5', 'Detalle 6', 'Detalle 7', 'Detalle 8', 'Orden', 'Centro Gestor', 'Posición Presupuestal', 'Material']
    df = pd.DataFrame(columns=campos)

    lista = []
    for i in range (df1.shape[0]):
      lit = df1.loc[i][fields[1]]                                               # identificacion del litigio
      soc = df1.loc[i][fields[3]]                                               # identificacion del numero de sociedad

      # COOLGAP - cuentas contingentes
      ajuste = df1.loc[i][fields[39]]                                           # obtencion del ajuste para las cuentas contingentes (AJUSTE_61)
      if ajuste != 0:
        lista = get_cc_cb(lista, 'ajuste_61')

      # IFRS - provision gasto financiero
      ajuste = df1.loc[i][fields[34]]                                           # obtencion del ajuste para la provision gasto financiero (AJUSTE_GASTO_FINANCIERO)
      if ajuste != 0:
        lista = get_cc_cb(lista, 'pgf')

      # IFRS - provision gasto provision
      ajuste = df1.loc[i][fields[36]] - df1.loc[i][fields[37]]                  # obtencion del ajuste para la provision gasto provision (AJUSTE_PROVISION_NIIF - RECUPERACION)
      if ajuste != 0:
        lista = get_cc_cb(lista, 'pgp')

      # IFRS - provision ingreso provision
      ajuste = df1.loc[i][fields[37]]                                           # obtencion del ajuste para la provision ingreso provision (RECUPERACION)
      if ajuste != 0:
        lista = get_cc_cb(lista, 'pip')

    # totalizar ajustes
    df_totales = pd.DataFrame(lista, columns=['tipo','lit', 'soc', 'c_costo', 'c_beneficio', 'ajuste'])
    df_totales = df_totales.groupby(['tipo', 'lit', 'soc', 'c_costo', 'c_beneficio'], as_index=False).agg({'ajuste': 'sum'}) # Agrupar por los campos 'tipo', 'lit', 'soc', 'c_costo' y 'c_beneficio' y sumar el campo 'ajuste'

    # ...................... creacion plantilla SAP ............................
    str_today = today.strftime('%Y%m%d')
    str_fecha_corte = fecha_corte.strftime('%Y%m%d')

    for i in range (df_totales.shape[0]):
      lit = df_totales.loc[i]['lit']
      soc = df_totales.loc[i]['soc']
      ajuste = df_totales.loc[i]['ajuste']
      if ajuste != 0:
        c_debitar, c_acreditar = get_accounts(df_totales.loc[i]['tipo'])
        df = generate_register(df, c_debitar, c_acreditar)
    return df

  class InterfazGrafica:
    """Clase que permite la creación de una interfaz gráfica con botones dinámicos."""
    def __init__(self, title, buttons):

      color = ["black", "white", "gray", "red", "blue", "yellow", "green", "purple", "orange", "cyan", "#C1C1C1"]
      metricas = self.metrics(1, 1)
      self.border = 10
      self.px = 10
      self.py = 10
      f_family = ['Arial','Calibri','Calibri Light','Times New Roman','System','Terminal','Modern','Roman','Script','Courier']
      f_size = int(metricas[0])
      f_weight = ["normal","bold"]
      f_slant = ["roman", "italic"]
      self.root = tk.Tk()
      self.root.title('Bancolombia')
      self.root.resizable(False, False)
      self.font1 = tkFont.Font(family=f_family[3],size=f_size,weight=f_weight[1],slant=f_slant[1])
      self.font2 = tkFont.Font(family=f_family[3],size=f_size,weight=f_weight[1],slant=f_slant[0])
      self.frame = tk.Frame(self.root, bg=color[0])
      self.frame.pack(side="top")
      self.frame.config(bd=self.border, relief="groove")
      self.message = tk.Label(self.frame, text=title, bg=color[0], fg=color[8], font=self.font1)
      self.message.grid(row=0, column=0, columnspan=len(buttons), padx=self.px, pady=self.py)
      self.create_buttons(buttons)
      self.center_window()
      self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
      self.root.mainloop()

    def metrics (self, porcent_x,porcent_y):
      """
      Permite obtener la resolución del monitor.
      Retorna un porcentaje de la resolución del monitor según se especifique.
      """
      user32 = ctypes.windll.user32
      user32.SetProcessDPIAware()
      width = user32.GetSystemMetrics(0)
      height = user32.GetSystemMetrics(1)
      return(porcent_x * width / 100, porcent_y * height / 100)

    def create_buttons(self, buttons):
      """Crea botones dinámicamente basados en la lista proporcionada."""
      for idx, boton in enumerate(buttons):
        b = tk.Button(self.frame, text=boton['texto'], command=lambda b=boton: self.metodos(b['texto'], b['comando']), cursor="hand2", width=15)
        b.config(justify="center", font=self.font2, bd=self.border, relief="raised")
        b.grid(row=1, column=idx, padx=self.px, pady=self.py)

    def center_window(self):
      """Centra la ventana en la pantalla."""
      self.root.update_idletasks()
      root_width = self.root.winfo_width()
      root_height = self.root.winfo_height()
      screen_width = self.root.winfo_screenwidth()
      screen_height = self.root.winfo_screenheight()
      x = int((screen_width / 2) - (root_width / 2))
      y = int((screen_height / 2) - (root_height / 2))
      self.root.geometry("+{}+{}".format(x, y))

    def on_exit(self):
      "Funcion de seguridad para no cerrar la ventana por accidente"
      if tk.messagebox.askyesno("Salir", "Esta acción terminará la ejecución. ¿Desea continuar?"):
        self.root.destroy()
        sys.exit()

    def metodos(self, texto, comando):
      "Ejecuta el comando asociado al botón presionado"
      try:
        self.root.withdraw()
        logging.info(f'{texto}...')
        comando()
        self.root.destroy()
      except Exception as e:
        self.root.destroy()
        errores(e)

  def provision():
    logging.info("Calculo de provisión iniciado...")
    # reading inputs
    in3_file = resolve_input_file(in3_dir, "Curva_TES", fecha_corte)
    logging.info(f"Leyendo {in3_file}...")
    tasa = pd.read_excel(f'{in3_dir}/{in3_file}', skiprows=7)
    tasa.columns = tasa.iloc[0]
    tasa = tasa.drop(tasa.index[0])
    tasa = tasa.iloc[:,[0, 3]]
    tasa['CurvaSpotDiscreta'] = tasa['CurvaSpotDiscreta'] / 100

    insumo1_ = preprocessing(False)
    insumo2_ = preprocessing()
    logging.info("Consolidando insumos...")
    consolidado = pd.concat([insumo1_,insumo2_],ignore_index = True)
    consolidado = organized_output_last_month(consolidado)
    consolidado = processing_data(consolidado, tasa)
    colgaap = accounting_colgaap(consolidado)
    ifrs = accounting_ifrs(consolidado)
    sap = template(consolidado)
    logging.info("Guardando resultados...")
    writer = pd.ExcelWriter(f"{path_dir}/Resultados/Provision litigios {fecha_corte.strftime('%Y%m%d')}.xlsx", engine='xlsxwriter')
    consolidado.to_excel(writer, sheet_name='Provision', index = False)
    colgaap.to_excel(writer, sheet_name='Contabilidad COLGAAP', index = False)
    ifrs.to_excel(writer, sheet_name='Contabilidad IFRS', index = False)
    sap.to_excel(writer, sheet_name='Plantilla SAP', index = False)
    writer.close()
    funcionesPD.protect_excel(f"{path_dir}/Resultados/Provision litigios {fecha_corte.strftime('%Y%m%d')}.xlsx", password = 'Bancolombia2025', protect_all_sheets=True)

#---------------------------- Main Function ------------------------------------
  def main():                           # Definicion de funcion principal
    logging.info("Seleccione tarea a realizar...")
    botones = [
      {'texto': 'Preproc Com e Hipot', 'comando':  lambda: preprocessing(False)},
      {'texto': 'Preproc Lab', 'comando':lambda: preprocessing()},
      {'texto': 'Provision', 'comando': provision}
    ]
    app = InterfazGrafica('¿Qué tarea desea realizar?', botones)

    end_time = time.time()
    ejecution_time = end_time - start_time
    logging.info("Tiempo de ejecucion: " + str(ejecution_time) + " Seg")
    logging.info("Feliz dia!!")

  #----------------------------- Run program -----------------------------------
  if __name__ == "__main__":
    main()

except Exception as e:
  errores(e)
