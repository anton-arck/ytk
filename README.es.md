# ytk

**Español** · [English](README.md)

Busca videos de YouTube desde la terminal y míralos con mpv. Muestra las miniaturas en una cuadrícula con el
protocolo gráfico de kitty (también funciona dentro de zellij).

## Idioma

La interfaz está en español e inglés. Al abrir usa el idioma de tu sistema (`$LANG`); `espacio L` lo alterna al instante y
guarda la elección en `~/.local/state/ytk/lang`. `YTK_LANG=es` o `YTK_LANG=en` fuerza uno (tiene prioridad).

## Instalación

**Necesitas** [kitty](https://sw.kovidgoyal.net/kitty/) (o una terminal con su protocolo gráfico), `python3` (3.9 o más),
[`yt-dlp`](https://github.com/yt-dlp/yt-dlp) y [`mpv`](https://mpv.io/). Opcional: `python-pillow` (si falta, las
miniaturas se convierten con `ffmpeg`).

```sh
# Arch / Manjaro / Garuda
sudo pacman -S yt-dlp mpv kitty python-pillow

# Debian / Ubuntu
sudo apt install mpv kitty python3-pil ffmpeg && python3 -m pip install --user -U yt-dlp

# Fedora
sudo dnf install yt-dlp mpv kitty python3-pillow
```

**Instalar ytk** (no hay nada que compilar): clona el repo y enlaza el lanzador a una carpeta de tu `PATH`.

```sh
git clone https://github.com/anton-arck/ytk.git ~/.local/share/ytk
mkdir -p ~/.local/bin && ln -sf ~/.local/share/ytk/bin/ytk ~/.local/bin/ytk
ytk --version
```

(Asegúrate de que `~/.local/bin` esté en tu `PATH`.) Para quedarte en una versión concreta:
`git -C ~/.local/share/ytk checkout v0.3.0`; para actualizar: `git -C ~/.local/share/ytk pull`. También puedes
descargar el `.zip` de una versión desde *Releases*, descomprimirlo y ejecutar `bin/ytk` desde ahí.

> **Aviso:** ytk depende de `yt-dlp`, que lee YouTube sin API oficial. Cuando YouTube cambia algo puede dejar de
> funcionar hasta que salga un `yt-dlp` nuevo: actualízalo primero (`yt-dlp -U`, o el gestor de paquetes) antes de
> reportar un problema.

## Uso

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
| `espacio i` | información del video: canal y suscriptores, duración, vistas, likes, fecha, resolución y descripción |
| `espacio c` → `v` / `l` | abrir el canal del video: sus videos o sus listas de reproducción |
| `espacio L` | cambiar el idioma de la interfaz (español ⇄ English); se guarda |
| `espacio b` / `n` / `q` | volver / más resultados / salir |

Al buscar (`espacio f` o `/`) aparece un cuadro flotante, como el de LazyVim: escribes, `Enter` busca, `Esc` cancela y
`Tab` cambia el modo (el cuadro muestra cuál está activo).

En el panel de información: `c` videos del canal · `l` listas del canal · `Enter` reproducir · `Esc` cerrar. Dentro de un canal, `Tab` alterna entre sus videos y sus listas, y `b` vuelve.

`Esc` cancela el menú y `Backspace` sube un nivel. Los atajos directos de abajo siguen funcionando.

Teclas: flechas o `h j k l` mover · `Enter` reproducir (una lista se reproduce completa) · `o` abrir una lista, o el
**Mix** que YouTube genera a partir de un video · `i` información · `c` canal · `P` reproducir de corrido lo que estás viendo (lista o mix) ·
`Tab` cambia el modo de búsqueda · `b` volver · `/` buscar · `n` más resultados · `g`/`G` inicio/fin · `q` salir.

Modos de búsqueda (`Tab`): **mixto** (videos con listas intercaladas, como la web; es el de inicio), **videos** y **listas**.

Variables: `YTK_HEIGHT` (calidad máxima, 720 por defecto), `YTK_MPV_ARGS` (opciones extra para mpv), `YTK_DOWNLOADS` (carpeta de descargas) y `YTK_LANG` (`es` o `en`).
Las miniaturas se guardan en `~/.cache/ytk`; el registro de mpv, en `~/.cache/ytk/mpv.log`.

## Estructura del código

```
bin/ytk            lanzador (sirve también como enlace simbólico en ~/.local/bin)
ytk/
  cli.py           punto de entrada: argumentos, --help, --version
  i18n.py          idiomas de la interfaz (es/en): detección, preferencia y textos
  app.py           la clase App: estado, bucle principal y carga en segundo plano
  keys.py          menú de la tecla líder y manejo de teclas
  view.py          dibujo: cuadrícula, panel de información, menú y cuadro de búsqueda
  navigation.py    cargar fuentes, abrir listas/canales/información, volver, cambiar de modo
  playback.py      reproducción con mpv y control del mpv que suena
  downloads.py     descargas de audio y video
  youtube.py       consultas a yt-dlp (búsqueda, listas, canales, info de un video)
  sources.py       de dónde salen los elementos (búsqueda, lista, mix, canal, historial)
  storage.py       historial, posición guardada y archivos descargados
  thumbs.py        descarga y conversión de miniaturas
  terminal.py      tamaño de la terminal, protocolo gráfico de kitty y lectura de teclas
  text.py          anchos, recortes y saneado de texto externo
  config.py        constantes y rutas
```

Se puede lanzar con `bin/ytk` o con `python3 -m ytk` desde la raíz del repo.

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

## Versiones y licencia

`ytk --version` muestra la versión. Los cambios de cada una están en `CHANGELOG.md`; cada versión es una etiqueta de
git (`v0.3.0`…) y una página de descarga en *Releases*. Licencia MIT.
