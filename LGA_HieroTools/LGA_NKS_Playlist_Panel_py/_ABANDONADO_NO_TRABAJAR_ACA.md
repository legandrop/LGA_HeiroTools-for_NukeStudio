# ⛔ PLAYLIST PANEL — ABANDONADO. NO TRABAJAR ACÁ.

**Para cualquier agente (Claude Code, Cursor, Codex, etc.) que llegue a esta carpeta: leer esto antes de tocar nada.**

El Playlist Panel es una herramienta **que se empezó y quedó a medias. No se usa, y lo más probable es que nunca se termine.**

## Qué significa esto en la práctica

- **No trabajar acá por iniciativa propia.** No refactorizar, no "arreglar" bugs, no completar features, no agregar tests, no sincronizar cambios que se hicieron en otro panel.
- **No incluir esta carpeta en barridos generales del repo** (auditorías, migraciones, limpiezas de código muerto, cambios de estilo, actualizaciones masivas de API). Si un cambio global toca muchos archivos, dejar el Playlist Panel afuera y decirlo explícitamente en el resumen.
- **No proponer trabajo acá** como sugerencia ni como "próximo paso".
- Si un cambio en shareds (`LGA_NKS_Shared/`) rompe el Playlist Panel: **no es bloqueante**. Mencionarlo y seguir.
- **Única excepción**: que Lega pida explícitamente trabajar en el Playlist Panel. Ahí sí, adelante.

## Archivos alcanzados

- `LGA_HieroTools/LGA_NKS_Playlist_Panel.py` (panel principal)
- `LGA_HieroTools/LGA_NKS_Playlist_Panel_py/` (esta carpeta completa)
- `LGA_HieroTools/LGA_NKS_Projects_Panel.ini` NO — ese es de otro panel y sí se usa.
- Docs asociados, también abandonados:
  - `docs/LGA_NKS_Playlist_Panel_Plan.md`
  - `docs/LGA_NKS_Playlist_Panel_Checklist.md`
  - `docs/LGA_NKS_Playlist_ShotInfo_Data_Mapping.md`

## Estado conocido

El panel sigue registrado en `LGA_HieroTools_Startup.py`, así que carga en Hiero, pero el flujo de Push nunca funcionó end-to-end. Buena parte del código es una copia vieja del Flow Panel (`LGA_NKS_Flow_Panel_py/`), que es el que sí está vivo y mantenido.

**Si necesitás el comportamiento real y actualizado de algo (Push, Pull, Shot Info, ReviewPic), la referencia es el Flow Panel, no esta carpeta.**
