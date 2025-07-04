# LGA_NKS_Flow_Assignee_Panel - Configuración Dinámica de Usuarios

## Descripción
El panel LGA_NKS_Flow_Assignee_Panel ahora carga dinámicamente la lista de usuarios desde el archivo `LGA_NKS_Flow_Users.json`, permitiendo agregar, modificar o eliminar usuarios sin necesidad de editar el código fuente.

## Cambios Implementados

### 1. Shortcut para "Show in Flow"
- **Shortcut**: `Ctrl+Shift+E`
- **Función**: Abre la task comp del clip seleccionado en Chrome
- **Tooltip**: Se muestra el shortcut al hacer hover sobre el botón

### 2. Configuración Dinámica de Usuarios
- Los usuarios se cargan desde `LGA_NKS_Flow_Users.json`
- Cada usuario tiene un nombre y color personalizable
- El sistema crea automáticamente el archivo de configuración si no existe

## Archivo de Configuración: LGA_NKS_Flow_Users.json

```json
{
    "users": [
        {
            "name": "Lega Pugliese",
            "color": "#69135e"
        },
        {
            "name": "Sebas Romano", 
            "color": "#a3557e"
        },
        {
            "name": "Patricio Barreiro",
            "color": "#19335D"
        },
        {
            "name": "Mariel Falco",
            "color": "#665621"
        }
    ]
}
```

## Cómo Agregar un Nuevo Usuario

1. Abrir el archivo `LGA_NKS_Flow_Users.json`
2. Agregar un nuevo objeto al array `users`:
   ```json
   {
       "name": "Nuevo Usuario",
       "color": "#ff6600"
   }
   ```
3. Guardar el archivo
4. Reiniciar Hiero o recargar el panel

## Cómo Modificar un Usuario Existente

1. Abrir el archivo `LGA_NKS_Flow_Users.json`
2. Modificar el `name` o `color` del usuario deseado
3. Guardar el archivo
4. Reiniciar Hiero o recargar el panel

## Cómo Eliminar un Usuario

1. Abrir el archivo `LGA_NKS_Flow_Users.json`
2. Eliminar el objeto correspondiente al usuario del array `users`
3. Guardar el archivo
4. Reiniciar Hiero o recargar el panel

## Formato de Colores
- Los colores deben estar en formato hexadecimal
- Ejemplos: `#69135e`, `#ff6600`, `#19335D`

## Funciones Adicionales

### reload_config()
- Función para recargar la configuración sin reiniciar Hiero
- Útil para desarrollo y pruebas

### create_default_config()
- Crea automáticamente el archivo de configuración con usuarios por defecto
- Se ejecuta si no se encuentra el archivo de configuración

## Estructura del Panel

### Botones Fijos
1. **Show in Flow** - `Ctrl+Shift+E`
2. **Get Assignees**
3. **Clear Assignees**

### Botones Dinámicos
- Se generan automáticamente basándose en el archivo de configuración
- Cada usuario tiene su propio botón con color personalizado
- Función: Asignar el usuario a la task comp del clip seleccionado

## Notas Técnicas
- El archivo de configuración se busca en la misma carpeta que el script del panel
- Si el archivo no existe, se crea automáticamente con la configuración por defecto
- Los errores se muestran en la consola de debug (activar DEBUG = True en el script)
- El sistema es compatible con caracteres Unicode (nombres con acentos, etc.) 