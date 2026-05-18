# Registro de necropsias médico-legales

Aplicación de escritorio en español para Windows, creada con **Python + Tkinter + SQLite**. La elección busca una instalación sencilla, una interfaz local sin servidor y una base de datos guardada en el equipo.

## Funciones incluidas

- Registro de datos del caso: expediente, fecha, persona fallecida, edad, sexo, lugar del hallazgo y médico/a forense.
- Captura de datos médico-legales: datos del caso, hallazgos, causa de muerte y observaciones.
- Base de datos local SQLite en la carpeta del usuario: `NecropsiasMedicoLegales/necropsias.db`.
- Copia local de fotografías por expediente en `NecropsiasMedicoLegales/fotografias/`.
- Exportación de informe PDF con datos del caso y anexo fotográfico.

## Instalación en Windows

1. Instale Python 3.11 o superior desde <https://www.python.org/downloads/> y marque la opción **Add python.exe to PATH**.
2. Abra PowerShell en la carpeta del proyecto.
3. Instale la dependencia para generar PDF:

```powershell
python -m pip install -r requirements.txt
```

4. Ejecute la aplicación:

```powershell
python necropsias_app.py
```

## Uso básico

1. Presione **Nuevo**.
2. Capture el expediente, la fecha y la causa de muerte. Esos campos son obligatorios.
3. Presione **Guardar caso**.
4. Abra la pestaña **Fotografías** y agregue imágenes del caso.
5. Presione **Exportar informe PDF** para generar el informe.

## Nota de alcance

Esta herramienta organiza información médico-legal de forma local. No sustituye los protocolos oficiales, la revisión institucional ni los requisitos legales aplicables en cada jurisdicción.
