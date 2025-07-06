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

### 3. Funcionalidad Dual de Botones de Usuario
- **Click normal**: Asigna el usuario a la task comp en Flow Production Tracking
- **Shift+Click**: Crea/actualiza políticas IAM de Wasabi para el usuario seleccionado

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
Al hacer Shift+Click en un botón de usuario, el panel llama al script de Wasabi:
- **Función**: `create_wasabi_policy_for_user(wasabi_user)` 
- **Script llamado**: `Python/Startup/LGA_NKS_Wasabi/LGA_NKS_Wasabi_PolicyAssign.py`
- **Parámetro**: El `wasabi_user` configurado en el JSON para ese usuario
- **Interfaz**: El script de Wasabi maneja toda la interfaz (ventana de estado, hilos, etc.)

## Funciones Principales

### `create_wasabi_policy_for_user(wasabi_user)`
- Llama al script de políticas de Wasabi para usuario específico
- Pasa el parámetro `wasabi_user` al script
- El script se encarga de mostrar ventana de estado y procesamiento
- Ubicación: `Python/Startup/LGA_NKS_Flow_Assignee_Panel.py`

### `reload_config()`
- Recarga la configuración sin reiniciar Hiero
- Útil para desarrollo y pruebas

## Estructura del Panel

### Botones Fijos
1. **Reveal in Flow** - `Shift+F`
2. **Policy** - Crea política para usuario por defecto (TestPoli)
3. **Get Assignees**
4. **Clear Assignees**

### Botones Dinámicos (Usuarios)
- Se generan automáticamente basándose en el archivo de configuración
- Cada usuario tiene su propio botón con color personalizado
- **Click normal**: Asigna el usuario a la task comp en Flow Production Tracking
- **Shift+Click**: Crea/actualiza políticas IAM de Wasabi para el usuario

## Notas Técnicas
- El archivo de configuración se busca en la misma carpeta que el script del panel
- Si el archivo no existe, se crea automáticamente con la configuración por defecto
- Los errores se muestran en la consola de debug (activar DEBUG = True en el script)
- El sistema es compatible con caracteres Unicode (nombres con acentos, etc.)
- La funcionalidad de Wasabi requiere variables de entorno: `WASABI_ADMIN_KEY` y `WASABI_ADMIN_SECRET`
- Los botones de usuario utilizan `CustomButton` para manejar Shift+Click
- La ventana de estado es modal y se cierra automáticamente al completar la operación 