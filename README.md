# ytk

Busca videos de YouTube desde la terminal y míralos con mpv. Muestra las miniaturas en una cuadrícula con el
protocolo gráfico de kitty (también funciona dentro de zellij).

Necesita `yt-dlp`, `mpv` y kitty. Pillow es opcional (si falta, usa `ffmpeg` para convertir las miniaturas).

```
ytk                      # abre y pulsa / para buscar
ytk big buck bunny       # busca directo
```

Teclas: flechas o `h j k l` mover · `Enter` reproducir · `/` buscar · `n` más resultados · `g`/`G` inicio/fin · `q` salir.

Variables: `YTK_HEIGHT` (calidad máxima, 720 por defecto) y `YTK_MPV_ARGS` (opciones extra para mpv).
Las miniaturas se guardan en `~/.cache/ytk`; el registro de mpv, en `~/.cache/ytk/mpv.log`.

`probe/` tiene dos pruebas pequeñas del protocolo de imágenes de kitty.
