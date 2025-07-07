# LGA_NKS_Flow_Assignee_Panel - Configuración Dinámica de Usuarios

## Descripción
El panel LGA_NKS_Flow_Assignee_Panel carga dinámicamente la lista de usuarios desde el archivo `LGA_NKS_Flow_Users.json`, permitiendo agregar, modificar o eliminar usuarios sin necesidad de editar el código fuente.

## Funcionalidades Principales

### 1. Shortcut para "Reveal in Flow"
- **Shortcut**: `Shift+F`
- **Función**: Abre la task comp del clip seleccionado en Chrome
- **Tooltip**: Se muestra el shortcut al hacer hover sobre el botón

### 2. Configuración Dinámica de Usuarios
- Los usuarios se cargan desde `Python/Startup/LGA_NKS_Flow_Users.json`
- Cada usuario tiene nombre, color y usuario de Wasabi configurables
- El sistema crea automáticamente el archivo de configuración si no existe

### 3. Funcionalidad Triple de Botones de Usuario
- **Click normal**: Asigna el usuario a la task comp en Flow Production Tracking
- **Shift+Click**: Crea/actualiza políticas IAM de Wasabi para el usuario seleccionado
- **Ctrl+Shift+Click**: Abre ventana de gestión de shots asignados en policy de Wasabi

## Archivo de Configuración: LGA_NKS_Flow_Users.json

```json
{
    "users": [
        {
            "name": "Lega Pugliese",
            "color": "#69135e",
            "wasabi_user": "lega"
        },
        {
            "name": "Sebas Romano", 
            "color": "#a3557e",
            "wasabi_user": "Sebastian_Romano"
        },
        {
            "name": "Patricio Barreiro",
            "color": "#19335D",
            "wasabi_user": "Pato_Barreiro"
        },
        {
            "name": "Mariel Falco",
            "color": "#665621",
            "wasabi_user": "mariel"
        }
    ]
}
```

## Cómo Agregar un Nuevo Usuario

1. Abrir el archivo `Python/Startup/LGA_NKS_Flow_Users.json`
2. Agregar un nuevo objeto al array `users`:
   ```json
   {
       "name": "Nuevo Usuario",
       "color": "#ff6600",
       "wasabi_user": "nuevo_usuario"
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

## Formato de Campos
- **Colores**: Formato hexadecimal (`#69135e`, `#ff6600`, `#19335D`)
- **wasabi_user**: Nombre exacto del usuario en Wasabi (case-sensitive)

## Integración con Wasabi

### Asignación de Políticas (Shift+Click)
Al hacer Shift+Click en un botón de usuario, el panel llama al script de asignación:
- **Función**: `create_wasabi_policy_for_user(wasabi_user)` 
- **Script llamado**: `Python/Startup/LGA_NKS_Wasabi/LGA_NKS_Wasabi_PolicyAssign.py`
- **Parámetro**: El `wasabi_user` configurado en el JSON para ese usuario
- **Interfaz**: El script maneja toda la interfaz (ventana de estado, hilos, etc.)

### Gestión de Shots (Ctrl+Shift+Click)
Al hacer Ctrl+Shift+Click en un botón de usuario, el panel llama al script de gestión:
- **Función**: `unassign_wasabi_policy_for_user(wasabi_user)`
- **Script llamado**: `Python/Startup/LGA_NKS_Wasabi/LGA_NKS_Wasabi_PolicyUnassign.py`
- **Funcionalidad**: Muestra ventana con shots asignados y permite eliminarlos individualmente
- **Interfaz**: Ventana scrolleable con botones de shots y botón "✕" para eliminar

## Funciones Principales

### `create_wasabi_policy_for_user(wasabi_user)`
- Llama al script de asignación de políticas de Wasabi para usuario específico
- Pasa el parámetro `wasabi_user` al script
- El script se encarga de mostrar ventana de estado y procesamiento
- Ubicación: `Python/Startup/LGA_NKS_Flow_Assignee_Panel.py`

### `unassign_wasabi_policy_for_user(wasabi_user)`
- Llama al script de gestión de shots de Wasabi para usuario específico
- Abre ventana con lista de shots asignados en la policy del usuario
- Permite eliminar shots individuales con interfaz visual
- Ubicación: `Python/Startup/LGA_NKS_Flow_Assignee_Panel.py`

### `reload_config()`
- Recarga la configuración sin reiniciar Hiero
- Útil para desarrollo y pruebas

## Estructura del Panel

### Botones Fijos
1. **Reveal in Flow** - `Shift+F`
2. **Get Assignees**
3. **Clear Assignees**

### Botones Dinámicos (Usuarios)
- Se generan automáticamente basándose en el archivo de configuración
- Cada usuario tiene su propio botón con color personalizado
- **Click normal**: Asigna el usuario a la task comp en Flow Production Tracking
- **Shift+Click**: Crea/actualiza políticas IAM de Wasabi para el usuario
- **Ctrl+Shift+Click**: Abre ventana de gestión de shots asignados en policy de Wasabi

## Notas Técnicas
- El archivo de configuración se busca en la misma carpeta que el script del panel
- Si el archivo no existe, se crea automáticamente con la configuración por defecto
- Los errores se muestran en la consola de debug (activar DEBUG = True en el script)
- El sistema es compatible con caracteres Unicode (nombres con acentos, etc.)
- Las funcionalidades de Flow y Wasabi utilizan credenciales seguras desde PipeSync (SecureConfig_Reader)
- Los botones de usuario utilizan `CustomButton` para manejar Shift+Click y Ctrl+Shift+Click
- Las ventanas de Wasabi son no-modales y se cierran manualmente con botón Close 