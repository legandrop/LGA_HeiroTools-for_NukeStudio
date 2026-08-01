> **Regla de documentacion**: este archivo describe el estado actual del codigo. No es un historial de cambios, changelog ni bitacora temporal.
> **Regla de documentacion**: este archivo debe incluir una seccion de referencias tecnicas con rutas completas a los archivos mas importantes relacionados, y para cada archivo nombrar las funciones, clases o metodos clave vinculados a este tema.

# Reorganizacion de Paneles Hiero

## Objetivo

Documentar:

- La ubicacion actual de los paneles y scripts relacionados.
- Que scripts son privados de un panel y cuales son compartidos.
- Una propuesta de reorganizacion basada en ownership real.

El criterio usado es:

- Si un script/tool lo usa un solo panel, debe vivir en la carpeta privada de ese panel.
- Si lo usan tools de varios paneles, debe vivir en una carpeta compartida.
- Los renombres y movimientos futuros deberian hacerse con `git mv`.

## Estructura actual

### Paneles raiz

- `LGA_NKS_Flow_Panel.py`
- `LGA_NKS_Assignee_Panel.py`
- `LGA_NKS_Coordination_Panel.py`
- `LGA_NKS_ViewerTL_Panel.py`
- `LGA_NKS_Edit_Panel.py`
- `LGA_NKS_Review_Panel.py`
- `LGA_NKS_Projects_Panel.py`
- `LGA_NKS_ClipColor_Panel.py`

### Mapa de nombres canonicos de panel

| Panel | Archivo canonico | Archivo legacy | Criterio |
| --- | --- | --- | --- |
| Flow | `LGA_NKS_Flow_Panel.py` | `LGA_NKS_Flow_Panel.py` | Ya representaba bien al panel. |
| Assignees | `LGA_NKS_Assignee_Panel.py` | `LGA_NKS_Flow_Assignee_Panel.py` | El panel opera sobre Flow y Wasabi, no solo sobre Flow. |
| Coordination | `LGA_NKS_Coordination_Panel.py` | `LGA_NKS_Flow_FlowProd_Panel.py` | Se alinea con el nombre real visible en UI: `Coordination`. |
| ViewerTL | `LGA_NKS_ViewerTL_Panel.py` | `LGA_NKS_ViewerPanel.py` | Se alinea con el nombre real visible en UI: `ViewerTL`. |
| Edit | `LGA_NKS_Edit_Panel.py` | `LGA_NKS_EditTools_Panel.py` | `EditTools` era mas largo de lo necesario frente al nombre visible `Edit`. |
| Review | `LGA_NKS_Review_Panel.py` | `LGA_NKS_Review_Panel.py` | Ya representaba bien al panel. |
| Projects | `LGA_NKS_Projects_Panel.py` | `LGA_NKS_Projects_Panel.py` | Se mantiene estable porque ya tiene dependencias externas. |
| ClipColor | `LGA_NKS_ClipColor_Panel.py` | `LGA_NKS_Color_Panel.py` | Se alinea con el nombre real visible en UI: `ClipColor`. |
| NoFPT | `LGA_NKS_NoFPT_Panel.py` | `LGA_NKS_FlowNo_Panel.py` | `NoFPT` describe mejor el panel actual que `FlowNo`. |

### Carpetas actuales relacionadas

- `LGA_NKS/`
- `LGA_NKS_Edit/`
- `LGA_NKS_Flow/`
- `LGA_NKS_Shared/`
- `LGA_NKS_Coordination_Panel_py/`
- `LGA_NKS_ViewerTL_Panel_py/`
- `LGA_NKS_Wasabi/`
- `LGA_NKS_Projects_Panel_py/`

Nota: `LGA_NKS_Wasabi/` ya no se considera runtime del panel `Assignees`. El runtime operativo de Wasabi queda dentro de `LGA_NKS_Assignee_Panel_py/`, y `LGA_NKS_Wasabi/` queda como carpeta legacy de documentacion y verificaciones.

### Shareds actuales sueltos en raiz

- `LGA_QtAdapter_HieroTools.py`
- `LGA_NKS_Flow_Task_Config.py`
- `LGA_NKS_Flow_Users.json`
- `LGA_NKS_Projects_Panel.ini`
- `LGA_NKS_Shortcuts.py`

## Mapa actual por panel

### 1. Flow Panel

Panel:

- `LGA_NKS_Flow_Panel.py`

Hoy carga scripts desde:

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py`
- `LGA_NKS_Shared/LGA_NKS_Delete_ClipTags.py`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
- `LGA_NKS_Shared/LGA_NKS_GetClip.py`

### 2. Assignees Panel

Panel:

- `LGA_NKS_Assignee_Panel.py`

Hoy carga scripts desde:

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py`

Y sus dependencias runtime de Wasabi tambien viven ahi:

- `LGA_NKS_Assignee_Panel_py/wasabi_policy_utils.py`
- `LGA_NKS_Assignee_Panel_py/boto3/`
- `LGA_NKS_Assignee_Panel_py/botocore/`
- `LGA_NKS_Assignee_Panel_py/dateutil/`
- `LGA_NKS_Assignee_Panel_py/jmespath/`
- `LGA_NKS_Assignee_Panel_py/s3transfer/`
- `LGA_NKS_Assignee_Panel_py/urllib3/`
- `LGA_NKS_Assignee_Panel_py/six.py`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`
- `LGA_NKS_Shared/LGA_NKS_GetClip.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
- `LGA_NKS_Flow_Users.json`
- `LGA_NKS_Flow_Task_Config.py`

### 3. Coordination Panel

Panel:

- `LGA_NKS_Coordination_Panel.py`

Hoy carga scripts desde:

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
- `LGA_NKS_Flow_Task_Config.py` indirectamente via `LGA_NKS_Flow_CreateShot.py`

### 4. ViewerTL Panel

Panel:

- `LGA_NKS_ViewerTL_Panel.py`

Hoy carga scripts desde:

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Viewer_Mask.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py`
- `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_InOut_Editref.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_SnapShot.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber.py`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_Timeline_PreCleanup.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
- `LGA_NKS_Shared/SecureConfig_Reader.py`

### 5. Edit Panel

Panel:

- `LGA_NKS_Edit_Panel.py`

Hoy carga scripts desde:

- `LGA_NKS_Edit_Panel_py/LGA_NKS_ColorTransforms.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_FixColorspaces.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateNewTrack.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_OrganizeProject.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_SetShotName.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_Trim_In.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_Trim_Out.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_Reconnect.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CleanProject.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_mediaMissingFrames.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CompareEXR_to_aPlate.py`

Tambien carga shareds fuera de esa carpeta:

- `LGA_NKS_Shared/LGA_NKS_Delete_ClipTags.py`
- `LGA_NKS_Shared/LGA_NKS_SelfReplaceClip.py`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`

### 6. Review Panel

Panel:

- `LGA_NKS_Review_Panel.py`

Hoy carga scripts desde:

- `LGA_NKS_Review_Panel_py/LGA_NKS_ON_Clips_OFF_v00-Clips.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_EXRTrack_Difference.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions_OFF.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealInExplorer.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealNKS_Project.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealNK_Script.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_OpenInNukeX.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py`

Tambien carga:

- `LGA_NKS_Shared/LGA_NKS_SelfReplaceClip.py`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`

### 7. Projects Panel

Panel:

- `LGA_NKS_Projects_Panel.py`

Hoy carga scripts y recursos desde:

- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py`
- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectItem.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_Workers.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_UIManager.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ScanManager.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectHandler.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_Projects_Panel_Smart_Reload.py`
- `LGA_NKS_Projects_Panel_py/*.svg`

Tambien usa shareds:

- `LGA_NKS_Shared/LGA_NKS_Timeline_PreCleanup.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
- `LGA_NKS_Projects_Panel.ini`

### 8. ClipColor Panel

Panel:

- `LGA_NKS_ClipColor_Panel.py`

Hoy usa shareds:

- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`

No depende de una carpeta privada propia.

### 9. NoFPT Panel

Estado actual:

- Archivado en `+Building_Blocks/LGA_NKS_NoFPT_Panel.py`
- Ya no forma parte del startup operativo

Problema actual:

- Intenta cargar `LGA_FPT-Hiero/LGA_FPT-Hiero_Push.py`
- Intenta cargar `LGA_FPT-Hiero/LGA_H-DeleteClipTags.py`

Esa carpeta no existe actualmente en el repo.

Conclusion:

- Queda archivado como panel legacy no operativo.

## Scripts compartidos detectados

### Shared generales

- `LGA_QtAdapter_HieroTools.py`
- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
- `LGA_NKS_Shared/LGA_NKS_GetClip.py`

### Shared de dominio Flow

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`
- `LGA_NKS_Flow_Task_Config.py`
- `LGA_NKS_Flow_Users.json`
- `LGA_NKS_Shared/SecureConfig_Reader.py`

### Shared de acciones

- `LGA_NKS_Shared/LGA_NKS_Delete_ClipTags.py`
- `LGA_NKS_Shared/LGA_NKS_Delete_ClipTags.py`
  - Usado por `Flow Panel`
  - Usado por `Edit Panel`
  - `NoFPT Panel` intenta usar su variante legacy

- `LGA_NKS_Shared/LGA_NKS_SelfReplaceClip.py`
  - Usado por `Edit Panel`
  - Usado por `Review Panel`

- `LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py`
  - Usado por `ViewerTL Panel`
  - Usado por `Projects Panel`

- `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py`
  - Usado por `ViewerTL Panel`
  - Usado por `Projects Panel`

## Scripts privados de un solo panel

### Flow Panel

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push_connector.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py`
- `LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py`

### Assignees Panel

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py`
- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py`

### Coordination Panel

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`
- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`

### ViewerTL Panel

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Viewer_Mask.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_InOut_Editref.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_SnapShot.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber.py`
- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber_Create.py`

### Edit Panel

- `LGA_NKS_Edit_Panel_py/LGA_NKS_ColorTransforms.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_FixColorspaces.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateNewTrack.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_OrganizeProject.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_SetShotName.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_Trim_In.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_Trim_Out.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_Reconnect.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CleanProject.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_mediaMissingFrames.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py`
- `LGA_NKS_Edit_Panel_py/LGA_NKS_CompareEXR_to_aPlate.py`

### Review Panel

- `LGA_NKS_Review_Panel_py/LGA_NKS_ON_Clips_OFF_v00-Clips.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_EXRTrack_Difference.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions_OFF.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealInExplorer.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealNKS_Project.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealNK_Script.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_OpenInNukeX.py`
- `LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py`

### Projects Panel

- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py`
- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectItem.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_Workers.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_UIManager.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ScanManager.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectHandler.py`
- `LGA_NKS_Projects_Panel_py/LGA_NKS_Projects_Panel_Smart_Reload.py`
- `LGA_NKS_Projects_Panel_py/*.svg`

## Problemas detectados

### Naming inconsistente entre panel y carpeta

- `LGA_NKS_Projects_Panel.py` usa carpeta `LGA_NKS_Projects_Panel_py/`
- `LGA_NKS_ViewerTL_Panel.py` usa carpeta `LGA_NKS_ViewerTL_Panel_py/`
- `LGA_NKS_Coordination_Panel.py` usa carpeta `LGA_NKS_Coordination_Panel_py/`
- `LGA_NKS_Review_Panel.py` usa carpeta `LGA_NKS_Review_Panel_py/`

### Carpetas que parecen privadas pero no lo son

- `LGA_NKS_Shared/` concentra todos los modulos compartidos usados por multiples paneles.
- `LGA_NKS/` ya no contiene shareds activos; ahora conserva solo scripts legacy/no migrados.

### Legacy roto

- `LGA_NKS_NoFPT_Panel.py` referencia una carpeta inexistente: `LGA_FPT-Hiero/`

### Helpers internos que tambien hay que contemplar

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push_connector.py`
  - No lo llama un panel directo.
  - Lo usa `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py` del `Flow Panel`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`
  - No lo llama un panel directo.
  - Lo usan:
    - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` del `Coordination Panel`
    - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py` del `Coordination Panel`

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh.py`
  - No lo llama un panel directo.
  - Lo usa `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py` del `ViewerTL Panel`.

- `LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py`
  - No lo llama un panel directo.
  - Lo usan:
    - `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py` del `ViewerTL Panel`
    - `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py` del `Projects Panel`

## Propuesta de reorganizacion

## Criterio de destino

- Carpeta privada del panel si lo usa un solo panel.
- Carpeta shared si lo usan varios paneles.
- Mantener paneles raiz visibles en `Startup/`.

### Estructura propuesta

```text
Startup/
  LGA_NKS_Flow_Panel.py
  LGA_NKS_Assignee_Panel.py
  LGA_NKS_Coordination_Panel.py
  LGA_NKS_ViewerTL_Panel.py
  LGA_NKS_Edit_Panel.py
  LGA_NKS_Review_Panel.py
  LGA_NKS_Projects_Panel.py
  LGA_NKS_ClipColor_Panel.py
  LGA_NKS_NoFPT_Panel.py

  LGA_NKS_Shared/
    LGA_QtAdapter_HieroTools.py
    LGA_NKS_StyleUtils.py
    LGA_NKS_GetClip.py
    LGA_NKS_Reduce_SeqWin.py

  LGA_NKS_Shared/
    LGA_NKS_Flow_NamingUtils.py
    LGA_NKS_Flow_Task_Config.py
    LGA_NKS_Flow_Users.json
    SecureConfig_Reader.py

  LGA_NKS_Flow_Panel_py/
    LGA_NKS_Flow_Pull.py
    LGA_NKS_Flow_Push.py
    LGA_NKS_Flow_Push_connector.py
    LGA_NKS_Flow_Shot_info.py
    LGA_NKS_ReviewPic.py

  LGA_NKS_Assignee_Panel_py/
    LGA_NKS_Flow_Assignee.py
    LGA_NKS_Flow_Assign_Assignee.py
    LGA_NKS_Flow_Clear_Assignees.py
    LGA_NKS_Wasabi_PolicyAssign.py
    LGA_NKS_Wasabi_PolicyUnassign.py
    LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py
    wasabi_policy_utils.py
    boto3/
    botocore/
    dateutil/
    jmespath/
    s3transfer/
    urllib3/
    six.py

  LGA_NKS_Coordination_Panel_py/
    LGA_NKS_Flow_ShowInFlow.py
    LGA_NKS_Flow_Thumbs.py
    LGA_NKS_Flow_CreateShot.py
    LGA_NKS_Flow_ModifyShot.py
    LGA_NKS_Flow_ShotPriority.py
    LGA_NKS_FileManagerS3_OpenPath.py
    LGA_NKS_FileManagerS3_Download.py
    LGA_NKS_FileManagerS3_Upload.py
    LGA_NKS_Flow_CheckTimelineShots.py
    LGA_NKS_PipeSync_OpenPath.py
    LGA_NKS_PipeSync_CreatePsync.py
    LGA_NKS_Flow_CreateShot_Folders.py

  LGA_NKS_ViewerTL_Panel_py/
    LGA_NKS_Viewer_Mask.py
    LGA_NKS_Timeline_Refresh_Wrap.py
    LGA_NKS_Timeline_Refresh.py
    LGA_NKS_InOut_Editref.py
    LGA_NKS_PrevNext_Rev.py
    LGA_NKS_SnapShot.py
    LGA_NKS_FrameNumber.py
    LGA_NKS_FrameNumber_Create.py

  LGA_NKS_Edit_Panel_py/
    LGA_NKS_ColorTransforms.py
    LGA_NKS_FixColorspaces.py
    LGA_NKS_CreateNewTrack.py
    LGA_NKS_OrganizeProject.py
    LGA_NKS_SetShotName.py
    LGA_NKS_Trim_In.py
    LGA_NKS_Trim_Out.py
    LGA_NKS_Reconnect.py
    LGA_NKS_CleanProject.py
    LGA_NKS_mediaMissingFrames.py
    LGA_NKS_MatchVerToEXR.py
    LGA_NKS_CompareVerToEditref.py
    LGA_NKS_CompareEXR_to_aPlate.py

  LGA_NKS_Review_Panel_py/
    LGA_NKS_ON_Clips_OFF_v00-Clips.py
    LGA_NKS_EXRTrack_Difference.py
    LGA_NKS_Compare_Versions.py
    LGA_NKS_Compare_Versions_OFF.py
    LGA_NKS_RevealInExplorer.py
    LGA_NKS_RevealNKS_Project.py
    LGA_NKS_RevealNK_Script.py
    LGA_NKS_OpenInNukeX.py
    LGA_NKS_Clip_DisableEXR.py

  LGA_NKS_Shared/
    LGA_NKS_Delete_ClipTags.py
    LGA_NKS_SelfReplaceClip.py
    LGA_NKS_ScrollTo_TopTrack.py

  LGA_NKS_Projects_Panel_py/
    LGA_Projects_Panel_ScanProjects.py
    LGA_Projects_Panel_SwitchSequence.py
    LGA_NKS_ProjectItem.py
    LGA_NKS_Workers.py
    LGA_NKS_UIManager.py
    LGA_NKS_ScanManager.py
    LGA_NKS_ProjectHandler.py
    LGA_NKS_Projects_Panel_Smart_Reload.py
    *.svg
```

## Notas de criterio

### Por que `LGA_NKS_Flow_Task_Config.py` va a shared

Porque no pertenece solo al Flow Panel:

- Lo usan tools del Assignees Panel.
- Lo usan tools del Coordination Panel.

No deberia quedar en la carpeta privada de `Flow Panel`.

### Por que `LGA_NKS_Flow_Pull.py` y `LGA_NKS_Flow_Push.py` van a `LGA_NKS_Flow_Panel_py/`

Porque hoy los invoca directamente solo `LGA_NKS_Flow_Panel.py`.

### Por que `LGA_NKS_Delete_ClipTags.py` no deberia quedar dentro de `LGA_NKS_Flow/`

Porque ya no es privado de Flow:

- Lo usa `Flow Panel`
- Lo usa `Edit Panel`
- `NoFPT Panel` intenta usar su equivalente legacy

### Por que `LGA_NKS_SelfReplaceClip.py` no deberia quedar dentro de `LGA_NKS_Edit/`

Porque hoy ya no es privado de Edit:

- Lo usa `Edit Panel`
- Lo usa `Review Panel`

Ambos deberian vivir en `LGA_NKS_Shared/`.

### Por que `LGA_NKS_Reduce_SeqWin.py` va a `LGA_NKS_Shared/`

Porque no es privado del `ViewerTL Panel`:

- Lo usa `ViewerTL Panel`
- Lo usa `Projects Panel`

### Por que los scripts Wasabi van a `LGA_NKS_Assignee_Panel_py/`

Porque hoy los invoca directamente solo `LGA_NKS_Assignee_Panel.py`:

- `LGA_NKS_Wasabi_PolicyAssign.py`
- `LGA_NKS_Wasabi_PolicyUnassign.py`
- `LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py`

## Matriz archivo -> quien lo usa

Esta seccion agrega el nivel fino: para cada `.py` relevante se indica si lo llama un panel directo o si lo usa otro `.py`, indicando de que panel es ese `.py`.

### Shared de dominio Flow

- `LGA_NKS_Flow_Task_Config.py`
  - Lo usan:
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py` del `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py` del `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py` del `Assignees Panel`
    - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` del `Coordination Panel`

- `LGA_NKS_Flow_Users.json`
  - Lo usan:
    - `LGA_NKS_Assignee_Panel.py` del `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py` del `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py` del `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py` del `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py` usado por `Assignees Panel`
    - `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py` usado por `Assignees Panel`

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`
  - Lo usan:
    - `LGA_NKS_Flow_Panel.py` del `Flow Panel`
    - `LGA_NKS_Assignee_Panel.py` del `Assignees Panel`
    - `LGA_NKS_Coordination_Panel.py` del `Coordination Panel`
    - `LGA_NKS_Edit_Panel.py` del `Edit Panel`
    - varios scripts de `LGA_NKS_Edit/`

- `LGA_NKS_Shared/SecureConfig_Reader.py`
  - Lo usan:
    - `LGA_NKS_ViewerTL_Panel.py` del `ViewerTL Panel`
    - scripts de `LGA_NKS_Flow_Panel_py/`
    - scripts de `LGA_NKS_Assignee_Panel_py/`
    - scripts de `LGA_NKS_Coordination_Panel_py/`

### Shared generales

- `LGA_QtAdapter_HieroTools.py`
  - Lo usan todos los paneles principales y la mayoria de los scripts auxiliares.

- `LGA_NKS_Shared/LGA_NKS_StyleUtils.py`
  - Lo usan:
    - `LGA_NKS_ClipColor_Panel.py` del `ClipColor Panel`
    - `LGA_NKS_Projects_Panel.py` del `Projects Panel`
    - `LGA_NKS_Review_Panel.py` del `Review Panel`
    - `LGA_NKS_ViewerTL_Panel.py` del `ViewerTL Panel`
    - `LGA_NKS_Flow_Panel.py` del `Flow Panel`
    - `LGA_NKS_Assignee_Panel.py` del `Assignees Panel`
    - `LGA_NKS_Coordination_Panel.py` del `Coordination Panel`
    - `LGA_NKS_Edit_Panel.py` del `Edit Panel`

- `LGA_NKS_Shared/LGA_NKS_GetClip.py`
  - Lo usan:
    - `LGA_NKS_Flow_Panel.py` del `Flow Panel`
    - `LGA_NKS_Assignee_Panel.py` del `Assignees Panel`
    - varios scripts de `LGA_NKS_Edit/`
    - varios scripts de `LGA_NKS_Coordination_Panel_py/`
    - algunos scripts de `LGA_NKS/`

### Shared actions

- `LGA_NKS_Shared/LGA_NKS_Delete_ClipTags.py`
  - Lo usan:
    - `LGA_NKS_Flow_Panel.py` del `Flow Panel`
    - `LGA_NKS_Edit_Panel.py` del `Edit Panel`
    - `LGA_NKS_NoFPT_Panel.py` lo intenta usar con nombre legacy

- `LGA_NKS_Shared/LGA_NKS_SelfReplaceClip.py`
  - Lo usan:
    - `LGA_NKS_Edit_Panel.py` del `Edit Panel`
    - `LGA_NKS_Review_Panel.py` del `Review Panel`

### Flow Panel

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py`
  - Lo usa `LGA_NKS_Flow_Panel.py`.

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py`
  - Lo usa `LGA_NKS_Flow_Panel.py`.
  - A su vez usa `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push_connector.py`.

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push_connector.py`
  - Lo usa `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py` del `Flow Panel`.

- `LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py`
  - Lo usa `LGA_NKS_Flow_Panel.py`.

- `LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py`
  - Lo usa `LGA_NKS_Flow_Panel.py`.

### Assignees Panel

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py`
  - Lo usa `LGA_NKS_Assignee_Panel.py`.

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py`
  - Lo usa `LGA_NKS_Assignee_Panel.py`.

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py`
  - Lo usa `LGA_NKS_Assignee_Panel.py`.

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py`
  - Lo usa `LGA_NKS_Assignee_Panel.py`.

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py`
  - Lo usa `LGA_NKS_Assignee_Panel.py`.

- `LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py`
  - Lo usa `LGA_NKS_Assignee_Panel.py`.

### Coordination Panel

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_Thumbs.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.
  - A su vez usa `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.
  - A su vez usa `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot_Folders.py`
  - Lo usan:
    - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py` del `Coordination Panel`
    - `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ModifyShot.py` del `Coordination Panel`

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

- `LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py`
  - Lo usa `LGA_NKS_Coordination_Panel.py`.

### ViewerTL Panel

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Viewer_Mask.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel.py`.

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel.py`.
  - A su vez usa:
    - `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh.py`
    - `LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py`
    - `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py`

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py` del `ViewerTL Panel`.

- `LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py`
  - Lo usan:
    - `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_Timeline_Refresh_Wrap.py` del `ViewerTL Panel`
    - `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py` del `Projects Panel`

- `LGA_NKS_Shared/LGA_NKS_ScrollTo_TopTrack.py`
  - Lo usan:
    - `LGA_NKS_ViewerTL_Panel.py` del `ViewerTL Panel`
    - `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py` del `Projects Panel`

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_InOut_Editref.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel.py`.

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel.py`.

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_SnapShot.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel.py`.

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel.py`.
  - A su vez usa `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber_Create.py`.

- `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber_Create.py`
  - Lo usa `LGA_NKS_ViewerTL_Panel_py/LGA_NKS_FrameNumber.py` del `ViewerTL Panel`.

### Edit Panel

- `LGA_NKS_Edit_Panel_py/LGA_NKS_ColorTransforms.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_FixColorspaces.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_CreateNewTrack.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_OrganizeProject.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_SetShotName.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_Trim_In.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_Trim_Out.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_Reconnect.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_CleanProject.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_mediaMissingFrames.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

- `LGA_NKS_Edit_Panel_py/LGA_NKS_CompareEXR_to_aPlate.py`
  - Lo usa `LGA_NKS_Edit_Panel.py`.

### Review Panel

- `LGA_NKS_Review_Panel_py/LGA_NKS_ON_Clips_OFF_v00-Clips.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_EXRTrack_Difference.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions_OFF.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealInExplorer.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealNKS_Project.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_RevealNK_Script.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_OpenInNukeX.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

- `LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py`
  - Lo usa `LGA_NKS_Review_Panel.py`.

### Projects Panel

- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

- `LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_SwitchSequence.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.
  - A su vez usa `LGA_NKS_Shared/LGA_NKS_Reduce_SeqWin.py`.

- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectItem.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

- `LGA_NKS_Projects_Panel_py/LGA_NKS_Workers.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

- `LGA_NKS_Projects_Panel_py/LGA_NKS_UIManager.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

- `LGA_NKS_Projects_Panel_py/LGA_NKS_ScanManager.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

- `LGA_NKS_Projects_Panel_py/LGA_NKS_ProjectHandler.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

- `LGA_NKS_Projects_Panel_py/LGA_NKS_Projects_Panel_Smart_Reload.py`
  - Lo usa `LGA_NKS_Projects_Panel.py`.

## Prioridad sugerida para implementar despues

1. Revisar docs y READMEs legacy que todavia mencionan rutas anteriores
2. Limpiar restos no operativos de `LGA_NKS_Flow/` si ya no hacen falta en runtime
3. Renombrar carpetas privadas para que coincidan con el panel cuando aparezcan nuevos casos
4. Mantener `+Building_Blocks/` como archivo de legacy, no como runtime
5. Mover `StyleUtils`, `GetClip` y `QtAdapter` a una carpeta shared unica

## Etapas sugeridas de implementacion

### Etapa 1. Shareds globales de bajo riesgo [completada]

- [x] Mover `LGA_QtAdapter_HieroTools.py` a `LGA_NKS_Shared/`
- [x] Mover `LGA_NKS_StyleUtils.py` a `LGA_NKS_Shared/`
- [x] Mover `LGA_NKS_GetClip.py` a `LGA_NKS_Shared/`
- [x] Actualizar imports directos y dejar wrappers de compatibilidad temporal donde convenga
- [x] Probar apertura y acciones basicas de los paneles que consumen estos shareds

### Etapa 2. Paneles de bajo acoplamiento

- Revisar `LGA_NKS_ClipColor_Panel.py` y dejarlo sin cambios estructurales salvo que aparezcan dependencias privadas nuevas
- Migrar `LGA_NKS_Review_Panel.py`
- Migrar `LGA_NKS_ViewerTL_Panel.py`
- Crear carpetas `_py` solo cuando el panel llame scripts externos privados
- Validar que cada panel abra y ejecute sus acciones principales

### Etapa 3. Edit Panel y shared actions

- Migrar `LGA_NKS_Edit_Panel.py`
- Separar `LGA_NKS_SelfReplaceClip.py` y `LGA_NKS_Delete_ClipTags.py` como shared actions reales
- Probar acciones de edit y las que comparte con Review y Flow

### Etapa 4. Assignees Panel

- Migrar `LGA_NKS_Assignee_Panel.py`
- Mover sus privados de Flow y Wasabi a `LGA_NKS_Assignee_Panel_py/`
- Validar lectura de users/config y ejecucion de acciones Flow/Wasabi

### Etapa 5. Coordination Panel

- Migrar `LGA_NKS_Coordination_Panel.py`
- Mover sus privados a `LGA_NKS_Coordination_Panel_py/`
- Validar helpers internos como `LGA_NKS_Flow_CreateShot_Folders.py`

### Etapa 6. Flow Panel

- Migrar `LGA_NKS_Flow_Panel.py`
- Mover sus privados a `LGA_NKS_Flow_Panel_py/`
- Validar `Pull`, `Push`, `Shot_info`, `ReviewPic` y `LGA_NKS_Flow_Push_connector.py`

### Etapa 7. NoFPT Panel

- Archivado en `+Building_Blocks/`
- No se migra como parte del runtime actual

### Etapa 8. Projects Panel

- Dejar `LGA_NKS_Projects_Panel.py` para el final
- Migrarlo cuando el resto del esquema ya este estable
- Validar sus dependencias cruzadas y `LGA_NKS_Reduce_SeqWin.py`

## Regla de implementacion por etapa

En cada etapa conviene:

1. mover un panel o grupo chico de shareds
2. actualizar imports y cargas dinamicas
3. probar manualmente en Hiero ese alcance acotado
4. recien despues seguir con la etapa siguiente

## Regla para ejecucion

Todos los movimientos y renombres deberian hacerse con:

```bash
git mv origen destino
```

Y luego actualizar:

- imports directos en paneles
- imports entre scripts movidos
- cargas dinamicas por nombre o ruta (`spec_from_file_location`, helpers `import_script`, `os.path.join` a `.py` y `.json`)
