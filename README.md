# ytk

Busca videos de YouTube desde la terminal y míralos con mpv. Muestra las miniaturas en una cuadrícula con el
protocolo gráfico de kitty (también funciona dentro de zellij).

Necesita `yt-dlp`, `mpv` y kitty. Pillow es opcional (si falta, usa `ffmpeg` para convertir las miniaturas).

```
ytk                      # abre y pulsa / para buscar
ytk big buck bunny       # busca directo
```

**Tecla líder (como LazyVim):** `espacio` abre un menú que muestra las opciones, y cada letra es una acción:

| Teclas | Acción |
|---|---|
| `espacio f` | buscar |
| `espacio m` → `m` / `v` / `l` | modo de búsqueda: mixto, solo videos, solo listas (repite la búsqueda actual) |
| `espacio o` | abrir una lista, o el Mix de un video |
| `espacio p` | reproducir todo lo que estás viendo (lista o mix) |
| `espacio b` / `n` / `q` | volver / más resultados / salir |

Al buscar (`espacio f` o `/`) aparece un cuadro flotante, como el de LazyVim: escribes, `Enter` busca, `Esc` cancela y
`Tab` cambia el modo (el cuadro muestra cuál está activo).

`Esc` cancela el menú y `Backspace` sube un nivel. Los atajos directos de abajo siguen funcionando.

Teclas: flechas o `h j k l` mover · `Enter` reproducir (una lista se reproduce completa) · `o` abrir una lista, o el
**Mix** que YouTube genera a partir de un video · `P` reproducir de corrido lo que estás viendo (lista o mix) ·
`Tab` cambia el modo de búsqueda · `b` volver · `/` buscar · `n` más resultados · `g`/`G` inicio/fin · `q` salir.

Modos de búsqueda (`Tab`): **mixto** (videos con listas intercaladas, como la web; es el de inicio), **videos** y **listas**.

Variables: `YTK_HEIGHT` (calidad máxima, 720 por defecto) y `YTK_MPV_ARGS` (opciones extra para mpv).
Las miniaturas se guardan en `~/.cache/ytk`; el registro de mpv, en `~/.cache/ytk/mpv.log`.

`probe/` tiene dos pruebas pequeñas del protocolo de imágenes de kitty.

## Continuar viendo

- Al salir de mpv con `q` se guarda el segundo donde ibas (`--save-position-on-quit`, carpeta `~/.local/state/mpv/watch_later`); al volver a abrir el video continúa ahí.
- En la cuadrícula, los videos con posición guardada muestran `▶ 12:30/45:10` y una barra de progreso.
- `H` o `espacio h` abre el historial (lo último que reproduciste, hasta 200), guardado en `~/.local/state/ytk/history.json`.

## Descargas

- `espacio a` baja el audio (opus, en `~/Videos/ytk/audio/`) y `espacio d` baja el video (mkv, en `~/Videos/ytk/`) del video seleccionado. Se hace en segundo plano; la barra de estado avisa al terminar. Registro en `~/.cache/ytk/dl.log`.
- Los videos bajados se marcan con `⬇` y Enter reproduce el archivo local (sin red, y también recuerda dónde te quedaste).
- `YTK_DOWNLOADS` cambia la carpeta.

## Cambiar de canción en una lista

**Desde ytk** (sin enfocar mpv; ytk le habla por un socket en `$XDG_RUNTIME_DIR`):
- `]` siguiente canción y `[` anterior (también `espacio ]` y `espacio [`).
- Con una lista o un Mix sonando, ábrela en ytk (`o`), elige una canción y pulsa Enter: salta a esa canción en el mismo mpv, sin abrir otro.

**Dentro de mpv** (con su ventana enfocada): `>` siguiente, `<` anterior, y `g` luego `p` abre un selector de la lista con filtro (escribes para buscar, flechas y Enter para elegir).
