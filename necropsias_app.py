"""Aplicación de escritorio para registrar necropsias médico-legales.

Tecnología elegida: Python + Tkinter + SQLite.
Está pensada para Windows porque no requiere servidor y guarda todo en archivos locales.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, Y, filedialog, messagebox
import tkinter as tk
from tkinter import ttk

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:  # se informa al usuario solo cuando intente exportar
    colors = None
    A4 = None
    getSampleStyleSheet = None
    cm = None
    Image = None
    PageBreak = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None

APP_DIR = Path.home() / "NecropsiasMedicoLegales"
DB_PATH = APP_DIR / "necropsias.db"
FOTOS_DIR = APP_DIR / "fotografias"
INFORMES_DIR = APP_DIR / "informes"


@dataclass
class Caso:
    id: int | None
    expediente: str
    fecha: str
    nombre_fallecido: str
    edad: str
    sexo: str
    lugar_hallazgo: str
    medico_forense: str
    datos_caso: str
    hallazgos: str
    causa_muerte: str
    observaciones: str


class RepositorioNecropsias:
    """Gestiona la base de datos local SQLite y las fotografías copiadas."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        FOTOS_DIR.mkdir(parents=True, exist_ok=True)
        INFORMES_DIR.mkdir(parents=True, exist_ok=True)
        self.conexion = sqlite3.connect(db_path)
        self.conexion.row_factory = sqlite3.Row
        self.crear_tablas()

    def crear_tablas(self) -> None:
        self.conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS casos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente TEXT NOT NULL UNIQUE,
                fecha TEXT NOT NULL,
                nombre_fallecido TEXT,
                edad TEXT,
                sexo TEXT,
                lugar_hallazgo TEXT,
                medico_forense TEXT,
                datos_caso TEXT,
                hallazgos TEXT,
                causa_muerte TEXT,
                observaciones TEXT,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fotografias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caso_id INTEGER NOT NULL,
                ruta TEXT NOT NULL,
                nombre_original TEXT NOT NULL,
                descripcion TEXT,
                FOREIGN KEY (caso_id) REFERENCES casos(id) ON DELETE CASCADE
            );
            """
        )
        self.conexion.commit()

    def listar_casos(self) -> list[sqlite3.Row]:
        return self.conexion.execute(
            "SELECT id, expediente, fecha, nombre_fallecido, causa_muerte FROM casos ORDER BY fecha DESC, id DESC"
        ).fetchall()

    def obtener_caso(self, caso_id: int) -> sqlite3.Row:
        return self.conexion.execute("SELECT * FROM casos WHERE id = ?", (caso_id,)).fetchone()

    def guardar_caso(self, caso: Caso) -> int:
        ahora = datetime.now().isoformat(timespec="seconds")
        if caso.id is None:
            cursor = self.conexion.execute(
                """
                INSERT INTO casos (
                    expediente, fecha, nombre_fallecido, edad, sexo, lugar_hallazgo,
                    medico_forense, datos_caso, hallazgos, causa_muerte, observaciones,
                    creado_en, actualizado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    caso.expediente,
                    caso.fecha,
                    caso.nombre_fallecido,
                    caso.edad,
                    caso.sexo,
                    caso.lugar_hallazgo,
                    caso.medico_forense,
                    caso.datos_caso,
                    caso.hallazgos,
                    caso.causa_muerte,
                    caso.observaciones,
                    ahora,
                    ahora,
                ),
            )
            self.conexion.commit()
            return int(cursor.lastrowid)

        self.conexion.execute(
            """
            UPDATE casos
               SET expediente = ?, fecha = ?, nombre_fallecido = ?, edad = ?, sexo = ?,
                   lugar_hallazgo = ?, medico_forense = ?, datos_caso = ?, hallazgos = ?,
                   causa_muerte = ?, observaciones = ?, actualizado_en = ?
             WHERE id = ?
            """,
            (
                caso.expediente,
                caso.fecha,
                caso.nombre_fallecido,
                caso.edad,
                caso.sexo,
                caso.lugar_hallazgo,
                caso.medico_forense,
                caso.datos_caso,
                caso.hallazgos,
                caso.causa_muerte,
                caso.observaciones,
                ahora,
                caso.id,
            ),
        )
        self.conexion.commit()
        return caso.id

    def eliminar_caso(self, caso_id: int) -> None:
        fotos = self.listar_fotografias(caso_id)
        self.conexion.execute("DELETE FROM fotografias WHERE caso_id = ?", (caso_id,))
        self.conexion.execute("DELETE FROM casos WHERE id = ?", (caso_id,))
        self.conexion.commit()
        for foto in fotos:
            Path(foto["ruta"]).unlink(missing_ok=True)

    def agregar_fotografia(self, caso_id: int, archivo: Path, descripcion: str = "") -> None:
        carpeta_caso = FOTOS_DIR / str(caso_id)
        carpeta_caso.mkdir(parents=True, exist_ok=True)
        destino = carpeta_caso / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
        shutil.copy2(archivo, destino)
        self.conexion.execute(
            "INSERT INTO fotografias (caso_id, ruta, nombre_original, descripcion) VALUES (?, ?, ?, ?)",
            (caso_id, str(destino), archivo.name, descripcion),
        )
        self.conexion.commit()

    def listar_fotografias(self, caso_id: int) -> list[sqlite3.Row]:
        return self.conexion.execute(
            "SELECT id, ruta, nombre_original, descripcion FROM fotografias WHERE caso_id = ? ORDER BY id",
            (caso_id,),
        ).fetchall()

    def eliminar_fotografia(self, foto_id: int) -> None:
        foto = self.conexion.execute("SELECT ruta FROM fotografias WHERE id = ?", (foto_id,)).fetchone()
        if foto:
            Path(foto["ruta"]).unlink(missing_ok=True)
        self.conexion.execute("DELETE FROM fotografias WHERE id = ?", (foto_id,))
        self.conexion.commit()


class AppNecropsias(tk.Tk):
    """Interfaz gráfica simple en español para capturar casos y exportar informes."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Registro de necropsias médico-legales")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.repo = RepositorioNecropsias()
        self.caso_actual_id: int | None = None
        self.foto_seleccionada_id: int | None = None
        self.campos: dict[str, tk.Entry | ttk.Combobox] = {}
        self.textos: dict[str, tk.Text] = {}
        self.crear_interfaz()
        self.cargar_lista_casos()
        self.nuevo_caso()

    def crear_interfaz(self) -> None:
        contenedor = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        contenedor.pack(fill=BOTH, expand=True, padx=10, pady=10)

        panel_lista = ttk.Frame(contenedor, width=360)
        panel_formulario = ttk.Frame(contenedor)
        contenedor.add(panel_lista, weight=1)
        contenedor.add(panel_formulario, weight=3)

        ttk.Label(panel_lista, text="Casos registrados", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.tabla_casos = ttk.Treeview(
            panel_lista,
            columns=("expediente", "fecha", "fallecido"),
            show="headings",
            height=22,
        )
        self.tabla_casos.heading("expediente", text="Expediente")
        self.tabla_casos.heading("fecha", text="Fecha")
        self.tabla_casos.heading("fallecido", text="Fallecido")
        self.tabla_casos.column("expediente", width=110)
        self.tabla_casos.column("fecha", width=90)
        self.tabla_casos.column("fallecido", width=140)
        self.tabla_casos.pack(fill=BOTH, expand=True, pady=8)
        self.tabla_casos.bind("<<TreeviewSelect>>", self.seleccionar_caso)

        botones_lista = ttk.Frame(panel_lista)
        botones_lista.pack(fill="x")
        ttk.Button(botones_lista, text="Nuevo", command=self.nuevo_caso).pack(side=LEFT, padx=(0, 5))
        ttk.Button(botones_lista, text="Eliminar", command=self.eliminar_caso).pack(side=LEFT)

        encabezado = ttk.Frame(panel_formulario)
        encabezado.pack(fill="x")
        ttk.Label(encabezado, text="Datos de necropsia", font=("Segoe UI", 15, "bold")).pack(side=LEFT)
        ttk.Button(encabezado, text="Guardar caso", command=self.guardar_caso).pack(side=RIGHT, padx=4)
        ttk.Button(encabezado, text="Exportar informe PDF", command=self.exportar_pdf).pack(side=RIGHT, padx=4)

        notebook = ttk.Notebook(panel_formulario)
        notebook.pack(fill=BOTH, expand=True, pady=(10, 0))

        pestaña_datos = ttk.Frame(notebook)
        pestaña_descripcion = ttk.Frame(notebook)
        pestaña_fotos = ttk.Frame(notebook)
        notebook.add(pestaña_datos, text="Identificación")
        notebook.add(pestaña_descripcion, text="Descripción médico-legal")
        notebook.add(pestaña_fotos, text="Fotografías")

        self.crear_pestaña_datos(pestaña_datos)
        self.crear_pestaña_descripcion(pestaña_descripcion)
        self.crear_pestaña_fotos(pestaña_fotos)

    def crear_pestaña_datos(self, padre: ttk.Frame) -> None:
        formulario = ttk.Frame(padre, padding=12)
        formulario.pack(fill=BOTH, expand=True)
        definiciones = [
            ("expediente", "Expediente *"),
            ("fecha", "Fecha * (AAAA-MM-DD)"),
            ("nombre_fallecido", "Nombre de la persona fallecida"),
            ("edad", "Edad"),
            ("sexo", "Sexo"),
            ("lugar_hallazgo", "Lugar del hallazgo"),
            ("medico_forense", "Médico/a forense"),
        ]
        for fila, (clave, etiqueta) in enumerate(definiciones):
            ttk.Label(formulario, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=5)
            if clave == "sexo":
                campo = ttk.Combobox(formulario, values=["", "Femenino", "Masculino", "No identificado"], state="readonly")
            else:
                campo = ttk.Entry(formulario)
            campo.grid(row=fila, column=1, sticky="ew", pady=5, padx=(12, 0))
            self.campos[clave] = campo
        formulario.columnconfigure(1, weight=1)

    def crear_pestaña_descripcion(self, padre: ttk.Frame) -> None:
        formulario = ttk.Frame(padre, padding=12)
        formulario.pack(fill=BOTH, expand=True)
        definiciones = [
            ("datos_caso", "Datos del caso"),
            ("hallazgos", "Hallazgos de necropsia"),
            ("causa_muerte", "Causa de muerte *"),
            ("observaciones", "Observaciones"),
        ]
        for fila, (clave, etiqueta) in enumerate(definiciones):
            ttk.Label(formulario, text=etiqueta).grid(row=fila * 2, column=0, sticky="w", pady=(8, 2))
            texto = tk.Text(formulario, height=5, wrap="word")
            texto.grid(row=fila * 2 + 1, column=0, sticky="nsew")
            self.textos[clave] = texto
            formulario.rowconfigure(fila * 2 + 1, weight=1)
        formulario.columnconfigure(0, weight=1)

    def crear_pestaña_fotos(self, padre: ttk.Frame) -> None:
        contenedor = ttk.Frame(padre, padding=12)
        contenedor.pack(fill=BOTH, expand=True)
        ttk.Label(
            contenedor,
            text="Guarde el caso antes de agregar fotografías. Se copiarán a una carpeta local del expediente.",
        ).pack(anchor="w")

        cuerpo = ttk.Frame(contenedor)
        cuerpo.pack(fill=BOTH, expand=True, pady=8)
        self.lista_fotos = ttk.Treeview(cuerpo, columns=("archivo", "descripcion"), show="headings")
        self.lista_fotos.heading("archivo", text="Archivo")
        self.lista_fotos.heading("descripcion", text="Descripción")
        self.lista_fotos.column("archivo", width=320)
        self.lista_fotos.column("descripcion", width=360)
        self.lista_fotos.pack(side=LEFT, fill=BOTH, expand=True)
        self.lista_fotos.bind("<<TreeviewSelect>>", self.seleccionar_fotografia)

        barra = ttk.Scrollbar(cuerpo, orient=tk.VERTICAL, command=self.lista_fotos.yview)
        barra.pack(side=RIGHT, fill=Y)
        self.lista_fotos.configure(yscrollcommand=barra.set)

        fila_descripcion = ttk.Frame(contenedor)
        fila_descripcion.pack(fill="x", pady=4)
        ttk.Label(fila_descripcion, text="Descripción de foto").pack(side=LEFT)
        self.descripcion_foto = ttk.Entry(fila_descripcion)
        self.descripcion_foto.pack(side=LEFT, fill="x", expand=True, padx=8)

        botones = ttk.Frame(contenedor)
        botones.pack(fill="x", pady=4)
        ttk.Button(botones, text="Agregar fotografías", command=self.agregar_fotografias).pack(side=LEFT, padx=(0, 5))
        ttk.Button(botones, text="Abrir fotografía", command=self.abrir_fotografia).pack(side=LEFT, padx=5)
        ttk.Button(botones, text="Eliminar fotografía", command=self.eliminar_fotografia).pack(side=LEFT, padx=5)

    def asignar_campo(self, clave: str, valor: str) -> None:
        campo = self.campos[clave]
        if isinstance(campo, ttk.Combobox):
            campo.set(valor)
            return
        campo.delete(0, END)
        campo.insert(0, valor)

    def nuevo_caso(self) -> None:
        self.caso_actual_id = None
        self.foto_seleccionada_id = None
        for clave in self.campos:
            self.asignar_campo(clave, "")
        self.asignar_campo("fecha", date.today().isoformat())
        for texto in self.textos.values():
            texto.delete("1.0", END)
        self.limpiar_fotografias()
        self.tabla_casos.selection_remove(self.tabla_casos.selection())

    def caso_desde_formulario(self) -> Caso:
        return Caso(
            id=self.caso_actual_id,
            expediente=self.campos["expediente"].get().strip(),
            fecha=self.campos["fecha"].get().strip(),
            nombre_fallecido=self.campos["nombre_fallecido"].get().strip(),
            edad=self.campos["edad"].get().strip(),
            sexo=self.campos["sexo"].get().strip(),
            lugar_hallazgo=self.campos["lugar_hallazgo"].get().strip(),
            medico_forense=self.campos["medico_forense"].get().strip(),
            datos_caso=self.textos["datos_caso"].get("1.0", END).strip(),
            hallazgos=self.textos["hallazgos"].get("1.0", END).strip(),
            causa_muerte=self.textos["causa_muerte"].get("1.0", END).strip(),
            observaciones=self.textos["observaciones"].get("1.0", END).strip(),
        )

    def validar_caso(self, caso: Caso) -> bool:
        if not caso.expediente:
            messagebox.showwarning("Dato requerido", "Capture el expediente.")
            return False
        try:
            datetime.strptime(caso.fecha, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Fecha inválida", "Use el formato AAAA-MM-DD para la fecha.")
            return False
        if not caso.causa_muerte:
            messagebox.showwarning("Dato requerido", "Capture la causa de muerte.")
            return False
        return True

    def guardar_caso(self, mostrar_confirmacion: bool = True) -> bool:
        caso = self.caso_desde_formulario()
        if not self.validar_caso(caso):
            return False
        try:
            self.caso_actual_id = self.repo.guardar_caso(caso)
        except sqlite3.IntegrityError:
            messagebox.showerror("Expediente duplicado", "Ya existe un caso con ese número de expediente.")
            return False
        self.cargar_lista_casos()
        self.cargar_fotografias()
        if mostrar_confirmacion:
            messagebox.showinfo("Guardado", "El caso fue guardado correctamente.")
        return True

    def cargar_lista_casos(self) -> None:
        for item in self.tabla_casos.get_children():
            self.tabla_casos.delete(item)
        for caso in self.repo.listar_casos():
            self.tabla_casos.insert(
                "",
                END,
                iid=str(caso["id"]),
                values=(caso["expediente"], caso["fecha"], caso["nombre_fallecido"] or "Sin nombre"),
            )

    def seleccionar_caso(self, _evento: object | None = None) -> None:
        seleccion = self.tabla_casos.selection()
        if not seleccion:
            return
        caso_id = int(seleccion[0])
        caso = self.repo.obtener_caso(caso_id)
        self.caso_actual_id = caso_id
        for clave in self.campos:
            self.asignar_campo(clave, caso[clave] or "")
        for clave in self.textos:
            self.textos[clave].delete("1.0", END)
            self.textos[clave].insert("1.0", caso[clave] or "")
        self.cargar_fotografias()

    def eliminar_caso(self) -> None:
        if self.caso_actual_id is None:
            messagebox.showwarning("Sin selección", "Seleccione un caso para eliminar.")
            return
        if not messagebox.askyesno("Confirmar eliminación", "¿Desea eliminar el caso y sus fotografías locales?"):
            return
        self.repo.eliminar_caso(self.caso_actual_id)
        self.cargar_lista_casos()
        self.nuevo_caso()

    def limpiar_fotografias(self) -> None:
        for item in self.lista_fotos.get_children():
            self.lista_fotos.delete(item)

    def cargar_fotografias(self) -> None:
        self.limpiar_fotografias()
        self.foto_seleccionada_id = None
        if self.caso_actual_id is None:
            return
        for foto in self.repo.listar_fotografias(self.caso_actual_id):
            self.lista_fotos.insert(
                "",
                END,
                iid=str(foto["id"]),
                values=(foto["nombre_original"], foto["descripcion"] or ""),
            )

    def seleccionar_fotografia(self, _evento: object | None = None) -> None:
        seleccion = self.lista_fotos.selection()
        self.foto_seleccionada_id = int(seleccion[0]) if seleccion else None

    def agregar_fotografias(self) -> None:
        if self.caso_actual_id is None:
            messagebox.showwarning("Guarde primero", "Debe guardar el caso antes de agregar fotografías.")
            return
        archivos = filedialog.askopenfilenames(
            title="Seleccione fotografías",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.gif"), ("Todos los archivos", "*.*")],
        )
        if not archivos:
            return
        descripcion = self.descripcion_foto.get().strip()
        for archivo in archivos:
            self.repo.agregar_fotografia(self.caso_actual_id, Path(archivo), descripcion)
        self.descripcion_foto.delete(0, END)
        self.cargar_fotografias()

    def abrir_fotografia(self) -> None:
        if self.foto_seleccionada_id is None:
            messagebox.showwarning("Sin selección", "Seleccione una fotografía para abrir.")
            return
        foto = self.repo.conexion.execute(
            "SELECT ruta FROM fotografias WHERE id = ?", (self.foto_seleccionada_id,)
        ).fetchone()
        if not foto:
            return
        ruta = foto["ruta"]
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", ruta], check=False)
        else:
            subprocess.run(["xdg-open", ruta], check=False)

    def eliminar_fotografia(self) -> None:
        if self.foto_seleccionada_id is None:
            messagebox.showwarning("Sin selección", "Seleccione una fotografía para eliminar.")
            return
        if not messagebox.askyesno("Confirmar eliminación", "¿Desea eliminar la fotografía local seleccionada?"):
            return
        self.repo.eliminar_fotografia(self.foto_seleccionada_id)
        self.cargar_fotografias()

    def exportar_pdf(self) -> None:
        if SimpleDocTemplate is None:
            messagebox.showerror(
                "Falta dependencia",
                "Instale la dependencia con: python -m pip install -r requirements.txt",
            )
            return
        if self.caso_actual_id is None:
            messagebox.showwarning("Guarde primero", "Guarde el caso antes de exportar el informe PDF.")
            return
        if not self.guardar_caso(mostrar_confirmacion=False):
            return
        caso = self.repo.obtener_caso(self.caso_actual_id)
        fotos = self.repo.listar_fotografias(self.caso_actual_id)
        ruta_predeterminada = INFORMES_DIR / f"informe_{caso['expediente'].replace('/', '-')}.pdf"
        ruta_pdf = filedialog.asksaveasfilename(
            title="Guardar informe PDF",
            defaultextension=".pdf",
            initialfile=ruta_predeterminada.name,
            initialdir=str(INFORMES_DIR),
            filetypes=[("PDF", "*.pdf")],
        )
        if not ruta_pdf:
            return
        generar_informe_pdf(caso, fotos, Path(ruta_pdf))
        messagebox.showinfo("PDF exportado", f"Informe guardado en:\n{ruta_pdf}")


def generar_informe_pdf(caso: sqlite3.Row, fotos: list[sqlite3.Row], ruta_pdf: Path) -> None:
    """Genera un informe PDF con datos del caso y fotografías."""
    if SimpleDocTemplate is None:
        raise RuntimeError("La dependencia reportlab no está instalada.")

    estilos = getSampleStyleSheet()
    documento = SimpleDocTemplate(str(ruta_pdf), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm)
    elementos: list[object] = []

    elementos.append(Paragraph("Informe de necropsia médico-legal", estilos["Title"]))
    elementos.append(Spacer(1, 0.4 * cm))

    datos = [
        ["Expediente", caso["expediente"]],
        ["Fecha", caso["fecha"]],
        ["Persona fallecida", caso["nombre_fallecido"] or "Sin dato"],
        ["Edad", caso["edad"] or "Sin dato"],
        ["Sexo", caso["sexo"] or "Sin dato"],
        ["Lugar del hallazgo", caso["lugar_hallazgo"] or "Sin dato"],
        ["Médico/a forense", caso["medico_forense"] or "Sin dato"],
    ]
    tabla = Table(datos, colWidths=[4.5 * cm, 11 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.5 * cm))

    secciones = [
        ("Datos del caso", caso["datos_caso"]),
        ("Hallazgos de necropsia", caso["hallazgos"]),
        ("Causa de muerte", caso["causa_muerte"]),
        ("Observaciones", caso["observaciones"]),
    ]
    for titulo, contenido in secciones:
        elementos.append(Paragraph(titulo, estilos["Heading2"]))
        elementos.append(Paragraph((contenido or "Sin dato").replace("\n", "<br/>"), estilos["BodyText"]))
        elementos.append(Spacer(1, 0.35 * cm))

    if fotos:
        elementos.append(PageBreak())
        elementos.append(Paragraph("Anexo fotográfico", estilos["Title"]))
        for foto in fotos:
            ruta = Path(foto["ruta"])
            if not ruta.exists():
                continue
            elementos.append(Spacer(1, 0.3 * cm))
            elementos.append(Paragraph(foto["descripcion"] or foto["nombre_original"], estilos["Heading3"]))
            elementos.append(Image(str(ruta), width=15 * cm, height=10 * cm, kind="proportional"))

    documento.build(elementos)


def main() -> None:
    app = AppNecropsias()
    app.mainloop()


if __name__ == "__main__":
    main()
