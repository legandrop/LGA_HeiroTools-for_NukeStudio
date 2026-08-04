> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# LGA_NKS_Flow - Tipos de Task Definidos

## Descripción General

Este documento define los tipos de tasks estándar que pueden ser creadas automáticamente por el sistema LGA_NKS_Flow. Las tasks están organizadas en dos grupos principales: **2D** y **3D**, según el tipo de trabajo que representan.

## Grupo 2D

### Comp (Pipeline Step: Comp)
### Roto (Pipeline Step: Roto)
### CleanUp (Pipeline Step: Comp)
### DMP (Pipeline Step: DMP)


## Grupo 3D
### MatchMove (Match Moving)
### Model (Modelado)
### Retopo (Retopología)
### Rig (Rigging)
### Shaders (Shaders/Materials)
### Anim (Animación)
### FX (Efectos Especiales)
### Lighting (Iluminación)

## Configuración por Defecto

### Estados Iniciales
Todas las tasks se crean con:
- **Estado inicial:** `noread`
- **Reviewers:** Lega Pugliese, Sebas Romano, Juan Olivares, Javi Bravo (todos seleccionados por defecto)

### Asignación de Reviewers
Los reviewers se asignan automáticamente usando el campo `task_reviewers` de ShotGrid:
```python
"task_reviewers": [
    {"type": "HumanUser", "id": lega_id},
    {"type": "HumanUser", "id": sebas_id},
    {"type": "HumanUser", "id": juano_id},
    {"type": "HumanUser", "id": javi_id}
]
```

## Uso en el Sistema

### Creación Automática
- Las tasks se crean automáticamente al usar el script `LGA_NKS_Flow_CreateShot.py`
- Por defecto solo se crea la task "Comp"
- Futuras versiones podrán crear múltiples tasks según el proyecto

### Estados del Workflow
Las tasks siguen el workflow estándar:
1. `noread` → `ready` → `ip` → `rev` → `apr`
2. Estados de revisión: `rev_su` (supervisor), `revjua` (Juano), `revjav` (Javi), `rev_di` (director)

## Proyectos Analizados

Basado en el análisis de proyectos existentes:

### LC (Proyecto Pequeño)
- Enfoque: Composición básica
- Tasks típicas: Comp, Plate Online, Match Move
- Volumen: 17 tasks total

### PROJD (Proyecto Complejo)
- Enfoque: Pipeline completo
- Tasks identificadas: Plate Online, Comp, Matte, Roto, Clean, Matchmove, etc.
- Volumen: 332 tasks total

## Expansión Futura

El sistema está preparado para:
- Crear automáticamente múltiples tasks según el tipo de shot
- Adaptar la creación de tasks según el proyecto
- Integrar con diferentes pipelines de producción

## Referencias

- **Script principal:** `LGA_NKS_Flow_CreateShot.py`
- **Documentación técnica:** `LGA_NKS_Flow_CreateShot.MD`
- **Análisis de proyectos:** `LC_EHQALPV_Tasks_Comparison.md` (archivado)
