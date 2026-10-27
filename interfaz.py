import tkinter as tk
from tkinter import ttk

from run_v3 import escanear_completo

MAX_PARTIDAS_VISIBLES = 5
TAMANO_CELDA = 20
ARCHIVOS_IMAGEN = {
    "pasto": "imagenes/pasto.png",
    "muro": "imagenes/muro.png",
    "muro_dinamico": "imagenes/muro_dinamico.png",
    "manzana": "imagenes/manzana.png",
    "multiplicador": "imagenes/multiplicador.png",
    "mi_cabeza": "imagenes/mi_cabeza.png",
    "mi_cuerpo": "imagenes/mi_cuerpo.png",
    "su_cabeza": "imagenes/su_cabeza.png",
    "su_cuerpo": "imagenes/su_cuerpo.png",
}
MAPA_ESTATICO = {
    '|': "muro",
    '-': "muro",
    '#': "muro_dinamico",
    '*': "manzana",
    'X': "multiplicador",
}
TEXTOS_ESPECIALES = {'\u2b50', '\U0001F4A3', '\U0001F9E8', '\u24b6', '\u24b7'}


def cargar_imagenes():
    try:
        return {
            clave: tk.PhotoImage(file=ruta)
            for clave, ruta in ARCHIVOS_IMAGEN.items()
        }
    except Exception as error:
        print(f"[!] Error al cargar imagenes: {error}.")
        return None


def limpiar_pestanas_viejas(pestanas, juegos_visibles, notebook):
    for game_id in list(pestanas):
        if game_id not in juegos_visibles:
            frame = pestanas.pop(game_id)["frame"]
            notebook.forget(frame)
            frame.destroy()


def crear_pestana(notebook, game_id):
    frame = tk.Frame(notebook, bg="black")
    notebook.add(frame, text=f"Partida {game_id[:6]}...")
    etiqueta = tk.Label(
        frame, text="", font=("Courier", 11, "bold"), fg="yellow", bg="black"
    )
    etiqueta.pack(pady=5)
    canvas = tk.Canvas(
        frame, width=100, height=100, bg="black", highlightthickness=0
    )
    canvas.pack(padx=5, pady=5)
    return {"frame": frame, "canvas": canvas, "label": etiqueta}


def imagen_serpiente(pos, t):
    if pos == t.cabeza:
        return "mi_cabeza"
    if pos in t.cuerpo:
        return "mi_cuerpo"
    if pos in t.cab_en:
        return "su_cabeza"
    if pos in t.cuerp_en:
        return "su_cuerpo"
    return None


def dibujar_celda(canvas, x, y, char, imagenes, t):
    px, py = x * TAMANO_CELDA, y * TAMANO_CELDA
    canvas.create_image(px, py, image=imagenes["pasto"], anchor="nw")
    clave = MAPA_ESTATICO.get(char) or imagen_serpiente((x, y), t)
    if clave:
        canvas.create_image(px, py, image=imagenes[clave], anchor="nw")
    elif char.isdigit() or char in TEXTOS_ESPECIALES:
        canvas.create_text(
            px + 10, py + 10, text=char,
            fill="white", font=("Courier", 12, "bold"),
        )


def renderizar_tablero(tab_info, data, imagenes):
    tab_info["label"].config(text=data["marcador"])
    canvas = tab_info["canvas"]
    canvas.delete("all")
    filas = data["tablero"].strip('\n').split('\n')
    canvas.config(
        width=len(filas[0]) * TAMANO_CELDA,
        height=len(filas) * TAMANO_CELDA,
    )
    t = escanear_completo(filas, data["side"])
    for y, fila in enumerate(filas):
        for x, char in enumerate(fila):
            dibujar_celda(canvas, x, y, char, imagenes, t)


def iniciar_interfaz_multitab(get_games_func):
    ventana = tk.Tk()
    ventana.title("Monitor de Partidas - IA A* - Bot Snake")
    ventana.configure(bg="black")
    notebook = ttk.Notebook(ventana)
    notebook.pack(fill="both", expand=True, padx=5, pady=5)
    pestanas = {}
    imagenes = cargar_imagenes()
    if not imagenes:
        return

    def actualizar_tabs():
        juegos = dict(list(get_games_func().items())[-MAX_PARTIDAS_VISIBLES:])
        limpiar_pestanas_viejas(pestanas, juegos, notebook)
        for game_id, data in juegos.items():
            if game_id not in pestanas:
                pestanas[game_id] = crear_pestana(notebook, game_id)
            renderizar_tablero(pestanas[game_id], data, imagenes)
        ventana.after(100, actualizar_tabs)

    ventana.after(100, actualizar_tabs)
    ventana.mainloop()
