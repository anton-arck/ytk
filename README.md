# ytk

Busca videos de YouTube desde la terminal y míralos con mpv. Muestra las miniaturas en una cuadrícula con el
protocolo gráfico de kitty (también funciona dentro de zellij).

Necesita `yt-dlp`, `mpv` y kitty. Pillow es opcional (si falta, usa `ffmpeg` para convertir las miniaturas).

```
ytk                      # abre y pulsa / para buscar
ytk big buck bunny       # busca directo
```

Teclas: flechas o `h j k l` mover · `Enter` reproducir (una lista se reproduce completa) · `o` abrir una lista, o el
**Mix** que YouTube genera a partir de un video · `P` reproducir de corrido lo que estás viendo (lista o mix) ·
`Tab` cambia el modo de búsqueda · `b` volver · `/` buscar · `n` más resultados · `g`/`G` inicio/fin · `q` salir.

Modos de búsqueda (`Tab`): **mixto** (videos con listas intercaladas, como la web; es el de inicio), **videos** y **listas**.

Variables: `YTK_HEIGHT` (calidad máxima, 720 por defecto) y `YTK_MPV_ARGS` (opciones extra para mpv).
Las miniaturas se guardan en `~/.cache/ytk`; el registro de mpv, en `~/.cache/ytk/mpv.log`.

`probe/` tiene dos pruebas pequeñas del protocolo de imágenes de kitty.
