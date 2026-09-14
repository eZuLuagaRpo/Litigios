# -*- coding: utf-8 -*-
"""
Created on Mon Sep 26 17:16:01 2022
Funciones para el manejo de bases de datos con pandas
@author: frposada
"""
import os
import logging
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Protection


#%%--------------------- Definicion de funciones ------------------------------
""" parametro opcional - tiene un valor por default por lo que no es necesario que el usuario pase este parametro"""

def save_df(path_dir,name,df, extension): # Definicion de funcion (Guarda el df seleccionado con la extension que se especifique)
  nombre = name + "." + extension
  if extension == "xlsx":
    df.to_excel(path_dir + "/" + nombre, index = False)
  elif extension == "txt":
    df.to_csv(path_dir + "/" + nombre, index=False, sep='¡')

def read_some_files(path_dir, extension, separador = ",", in_supplied = [], encabezado = "infer", consolidation = False): # Definicion de funcion (Permite leer y consolidar diferentes archivos xlsx (excel) o csv (txt) que se encuentren en una carpeta)
  if in_supplied == []:
    in_supplied = os.listdir(path_dir)

  x = []
  if extension == "xlsx":
    for i in range(len(in_supplied)):
      x.append(pd.read_excel(path_dir + "/" + in_supplied[i], header = encabezado))
      logging.info("file " + in_supplied[i] + " read")
  elif extension == "txt":
    for i in range(len(in_supplied)):
      x.append(pd.read_csv(path_dir + "/" + in_supplied[i], sep = separador, header = encabezado, engine='python', encoding_errors='ignore'))
      logging.info("file " + in_supplied[i] + " read")
  if consolidation == True:
    consolidado = pd.concat(x,ignore_index = True)
    return consolidado
  else:
    return x

def inputs_identifying(path_dir_rec, path_dir): # Definicion de funcion (Identifica cuales de los archivos suministrados son reconocidos por el sistema)
  insumos_rec = pd.read_excel(path_dir_rec + "/Insumos reconocidos.xlsx")
  in_supplied = os.listdir(path_dir)
  x = []
  for i in range(insumos_rec.shape[0]):
    x.append(insumos_rec.iloc[i]["Insumo"] in in_supplied)
  insumos_rec = insumos_rec.assign(Encontrado = x)
  #insumos_rec = insumos_rec[insumos_rec["Encontrado"] == True]
  return(insumos_rec)

def df_to_list (df):                    # Definicion de funcion (transforma un dataframe en una lista - El resultado es una lista que contiene 1 elemento por cada registro del df)
  df = pd.DataFrame(df)
  lista = []
  for i in range(df.shape[0]):
    lista.append(df.iloc[i][0])
  return lista

def searchv(df,camposearch,search,campoload = "opcional"): # Definicion de funcion (identifica valores en un dataframe a partir de una llave)
  if campoload == "opcional":
    x = df[df[camposearch] == search]
  else:
    x = df[df[camposearch] == search][campoload]
    x = pd.DataFrame(x)

  if x.empty:
    logging.info("No se encontro " + str(search) + " en el campo " + camposearch)
  else:
    x = x.reset_index(drop = True)
  return x

def protect_excel(file_path: str, sheet_name: str = "Sheet1", password: str = "frank", unlock_columns: list = None, protect_all_sheets: bool = False):

  logging.info(f"Protegiendo archivo: {file_path}")                             # mensaje de control
  try:
    wb = load_workbook(file_path)                                               # cargar el archivo
  except Exception as e:                                                        # Manejo de excepciones
    logging.error(f"No se pudo abrir el archivo: {file_path}. Error: {e}")      # mensaje de error si no se pudo abrir el archivo
    return False                                                                # retorno de funcion

  try:
    sheets_to_protect = wb.worksheets if protect_all_sheets else [wb[sheet_name]] # seleccionar las hojas a proteger
    for ws in sheets_to_protect:                                                # iterar sobre las hojas
      # configuracion de proteccion (True = deshabilitar, False = habilitar)
      ws.protection.sheet = False                                               # habilitar proteccion de hoja
      ws.protection.formatCells = True                                          # deshabilitar formateo de celdas
      ws.protection.formatRows = False                                          # habilitar formateo de filas
      ws.protection.formatColumns = False                                       # habilitar formateo de columnas
      ws.protection.insertColumns = True                                        # deshabilitar insertar columnas
      ws.protection.insertRows = True                                           # deshabilitar insertar filas
      ws.protection.insertHyperlinks = True                                     # deshabilitar insertar hiperenlaces
      ws.protection.deleteColumns = True                                        # deshabilitar eliminar columnas
      ws.protection.deleteRows = True                                           # deshabilitar eliminar filas
      ws.protection.selectLockedCells = False                                   # habilitar seleccion de celdas bloqueadas
      ws.protection.selectUnlockedCells = False                                 # habilitar seleccion de celdas desbloqueadas
      ws.protection.sort = True                                                 # deshabilitar ordenamiento
      ws.protection.autoFilter=False                                            # habilitar autofiltro
      ws.protection.set_password(password)                                      # establecer la contraseña de la hoja

      # Desbloquear columnas específicas
      if unlock_columns:                                                        # si hay columnas a desbloquear
        header = [cell.value for cell in ws[1]]                                 # obtener el encabezado de la hoja
        for col_name in unlock_columns:                                         # iterar sobre las columnas a desbloquear
          if col_name not in header:                                            # si la columna no existe en el encabezado
            logging.warning(f"Columna '{col_name}' no encontrada en la hoja '{ws.title}'") # mensaje de advertencia
            continue                                                            # continuar con la siguiente columna
          col_index = header.index(col_name) + 1                                # obtener el indice de la columna
          for row in ws.iter_rows(min_col=col_index, max_col=col_index):        # iterar sobre las filas de la columna
            for cell in row:                                                    # iterar sobre las celdas de la fila
              cell.protection = Protection(locked=False)                        # desbloquear la celda

    wb.save(file_path)                                                          # guardar el archivo
    logging.info(f"Archivo Excel exportado y protegido: {file_path}")           # mensaje de control
  except Exception as e:                                                        # Manejo de excepciones
    logging.error(f"No se pudo proteger el archivo: {file_path}. Error: {e}")   # mensaje de error
