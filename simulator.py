import tkinter as tk
from tkinter import ttk

def iniciar_interfaz_multitab(get_games_func):
    """
    Crea una única ventana principal con un sistema de pestañas (Notebook) 
    para monitorear múltiples partidas simultáneas y congelarlas al terminar.
    """
    ventana = tk.Tk()
    ventana.title("Monitor de Partidas - IA A* - Bot Snake")
    ventana.configure(bg="black")
    
    notebook = ttk.Notebook(ventana)
    notebook.pack(fill="both", expand=True, padx=5, pady=5)
    
    pestanas = {}
    TAMAÑO_CELDA = 20

    try:
        imagenes = {
            "pasto": tk.PhotoImage(file="imagenes/pasto.png"),
            "muro": tk.PhotoImage(file="imagenes/muro.png"),
            "manzana": tk.PhotoImage(file="imagenes/manzana.png"),
            "mi_cabeza": tk.PhotoImage(file="imagenes/mi_cabeza.png"),
            "mi_cuerpo": tk.PhotoImage(file="imagenes/mi_cuerpo.png"),
            "su_cabeza": tk.PhotoImage(file="imagenes/su_cabeza.png"),
            "su_cuerpo": tk.PhotoImage(file="imagenes/su_cuerpo.png")
        }
    except Exception as e:
        print(f"[!] Error al cargar imágenes: {e}. Asegurate de tener los .png en la carpeta.")
        return 

    def actualizar_tabs():
        juegos_actuales = get_games_func()
        
        for game_id, data in juegos_actuales.items():
            if game_id not in pestanas:
                frame = tk.Frame(notebook, bg="black")
                notebook.add(frame, text=f"Partida {game_id[:6]}...")
                
                etiqueta_marcador = tk.Label(
                    frame, 
                    text="", 
                    font=("Courier", 11, "bold"), 
                    fg="yellow", 
                    bg="black"
                )
                etiqueta_marcador.pack(pady=5)
                
                canvas = tk.Canvas(frame, width=100, height=100, bg="black", highlightthickness=0)
                canvas.pack(padx=5, pady=5)
                
                pestanas[game_id] = {
                    "frame": frame,
                    "canvas": canvas,
                    "label": etiqueta_marcador,
                    "dibujado_final": False 
                }
            
            tab_info = pestanas[game_id]
            tab_info["label"].config(text=data["marcador"])
            
            if data.get("game_over") and tab_info["dibujado_final"]:
                continue 

            canvas = tab_info["canvas"]
            canvas.delete("all")
            
            tablero_actual_str = data["tablero"]
            mi_lado_str = data["side"]
            
            filas = tablero_actual_str.strip('\n').split('\n')
            
            ancho_tablero = len(filas[0]) * TAMAÑO_CELDA
            alto_tablero = len(filas) * TAMAÑO_CELDA
            canvas.config(width=ancho_tablero, height=alto_tablero)
            
            char_mi_cabeza = mi_lado_str
            char_mi_cuerpo = mi_lado_str.lower()
            
            for y, fila in enumerate(filas):
                for x, char in enumerate(fila):
                    pos_x = x * TAMAÑO_CELDA
                    pos_y = y * TAMAÑO_CELDA
                    
                    canvas.create_image(pos_x, pos_y, image=imagenes["pasto"], anchor="nw")
                    
                    if char in ['|', '-']:
                        canvas.create_image(pos_x, pos_y, image=imagenes["muro"], anchor="nw")
                    elif char == '*':
                        canvas.create_image(pos_x, pos_y, image=imagenes["manzana"], anchor="nw")
                    elif char == char_mi_cabeza:
                        canvas.create_image(pos_x, pos_y, image=imagenes["mi_cabeza"], anchor="nw")
                    elif char == char_mi_cuerpo:
                        canvas.create_image(pos_x, pos_y, image=imagenes["mi_cuerpo"], anchor="nw")
                    elif char in ['A', 'B'] and char != char_mi_cabeza:
                        canvas.create_image(pos_x, pos_y, image=imagenes["su_cabeza"], anchor="nw")
                    elif char in ['a', 'b'] and char != char_mi_cuerpo:
                        canvas.create_image(pos_x, pos_y, image=imagenes["su_cuerpo"], anchor="nw")

            if data.get("game_over"):
                tab_info["dibujado_final"] = True
                tab_info["label"].config(fg="red")

        ventana.after(100, actualizar_tabs)

    ventana.after(100, actualizar_tabs)
    ventana.mainloop()
