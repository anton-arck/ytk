# ytk: ideas y decisiones pendientes

## Decisión actual (2026-11-15)

Seguimos con **Python + yt-dlp + mpv**. El prototipo (`ytk.py`, un solo archivo, solo biblioteca estándar) ya
funciona: cuadrícula de miniaturas, búsqueda mixta/videos/listas, Mix de YouTube y reproducción con mpv.

## Opción para más adelante: reescribir la interfaz en Rust

**Qué sería:** un binario `ytk` en Rust que hace lo mismo que `ytk.py`, y **sigue llamando a yt-dlp y a mpv** como
programas aparte. No se reemplaza yt-dlp.

**Qué ganaría**
- Arranque más rápido y un solo binario, sin depender de Python.
- Mejor manejo de teclado, de redibujado y de las imágenes (menos parpadeo).
- Más fácil de repartir o instalar en otra máquina.

**Qué no arregla:** el tiempo de apertura de un video (unos 30 s con red móvil: ~7 s de extracción de yt-dlp más la
descarga). Eso depende de la red y de yt-dlp, no del lenguaje de la interfaz.

**Cuándo tiene sentido hacerlo:** cuando el uso diario nos convenza de que `ytk` se queda, o cuando Python estorbe
(arranque, dependencias, repartirlo). Mientras tanto no es necesario.

**Piezas posibles** (a confirmar al empezar)
- Terminal y teclas: `crossterm`; interfaz: `ratatui` (o dibujo a mano como ahora).
- Imágenes: protocolo gráfico de kitty escrito directamente (como `ytk.py`), o `ratatui-image`.
- Red e imágenes: `ureq` o `reqwest` para las miniaturas; `image` para convertir a PNG y reducir.
- Procesos: `std::process::Command` para yt-dlp (`--flat-playlist -j`) y mpv; hilos o `tokio` para no bloquear.

## Lo que aprendimos y hay que conservar en cualquier versión

- **No limpiar la pantalla con `ESC[2J`** (ED 2): kitty descarta las imágenes ya enviadas. Borrar línea a línea.
- **Las imágenes sirven igual dentro de zellij** (0.45): se probó con el protocolo de kitty.
- **YouTube a veces responde sin canal ni vistas** (1 de 8 búsquedas con yt-dlp). Reintentar si faltan en más de la mitad.
- **Texto externo = no confiable:** quitar caracteres de control y de formato de títulos, canales y errores antes de
  dibujarlos; validar el `id` antes de usarlo en rutas; construir la URL a partir del id; pasar `--` a mpv; bajar
  miniaturas solo de `i.ytimg.com`, `i9.ytimg.com` y `yt3.ggpht.com`.
- **Reproducción ligera:** 720p por defecto, sin AV1 ni audio 5.1 (`YTK_HEIGHT` cambia la calidad máxima).
- **El Mix de YouTube** de un video es la lista `RD` + id: `watch?v=ID&list=RDID`. No sale en las búsquedas.
- **Recoger los procesos de mpv terminados** para no dejar zombis.

## Otras ideas, sin prioridad

- **Búsqueda sin yt-dlp** (consultando la API interna de YouTube) para ahorrar los ~3 s por búsqueda. Es frágil porque
  YouTube la cambia; dejar yt-dlp como plan B.
- Historial de búsquedas y favoritos; abrir el canal de un video; reproducir solo audio.
- Probar: cambiar el tamaño de la ventana, `n` (más resultados) en listas largas y la reproducción de una lista con audio.

## Lo que NO vamos a hacer

- **Un clon de yt-dlp propio (en Rust o en otro lenguaje).** Lo difícil es mantener el paso con los cambios de YouTube
  (desafíos de JavaScript, tokens), que el equipo de yt-dlp arregla casi cada semana. Un clon se rompería cada vez.
- **Licencia:** yt-dlp es Unlicense (dominio público) y `ytk` lo ejecuta como programa aparte, así que no obliga a nada.
  `ytk` no tiene archivo `LICENSE` todavía; se decide si algún día se abre el repo (hoy es privado).
