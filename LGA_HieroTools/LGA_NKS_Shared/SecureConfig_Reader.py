"""
____________________________________________________________________

  SecureConfig_Reader v1.02 | Lega

  v1.02 (2026-07-21)
  - Reemplaza byte-lock local por lectura estable con fingerprint+retry
    compatible con reemplazo atómico de QSaveFile.
  - Expone metadata contextual runtime para cache seguro por perfil.

  v1.01 (2026-07-21)
  - Agrega lectura bloqueada (shared lock) para evitar lecturas parciales
    de config.secure y expone read_secure_config_with_status().

  v1.00:
  - Lectura y desencriptado de config.secure por contexto.

  Usado por runtime activo:
  - LGA_NKS_ViewerTL_Panel.py
  - LGA_NKS_Projects_Panel_py/LGA_Projects_Panel_ScanProjects.py
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py
  - LGA_NKS_Assignee_Panel_py/wasabi_policy_utils.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py
____________________________________________________________________
"""

import sys
import json
import base64
from pathlib import Path
import hashlib
import time
from LGA_NKS_ContextProfile import get_key_path as get_context_key_path
from LGA_NKS_ContextProfile import get_lga_appdata_root
from LGA_NKS_ContextProfile import get_secure_config_path
from LGA_NKS_ContextProfile import get_pipesync_profile_folder
from LGA_NKS_ContextProfile import get_context_mode


# Variable global para activar o desactivar los prints de debug
DEBUG = False


def debug_print(message):
    """Función de debug simple que imprime directamente si DEBUG está activado"""
    if DEBUG:
        print(f"[SecureConfig_Reader] {message}")


def _canonical_path(path_value):
    try:
        return str(Path(path_value).resolve())
    except Exception:
        return str(Path(path_value))


def _config_fingerprint(config_path):
    path_obj = Path(config_path)
    if not path_obj.exists():
        return {"exists": False, "size": -1, "mtime_ns": -1}
    stat = path_obj.stat()
    return {
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))),
    }


def _read_stable_config_payload(config_path, attempts=5, pause_seconds=0.03):
    last_error = ""
    for _ in range(max(1, int(attempts))):
        before = _config_fingerprint(config_path)
        if not before["exists"]:
            return None, before, "Config file does not exist."

        try:
            with open(config_path, "r", encoding="utf-8") as file_obj:
                encrypted_data = file_obj.read()
        except OSError as exc:
            last_error = str(exc)
            time.sleep(pause_seconds)
            continue

        after = _config_fingerprint(config_path)
        if before == after and after["exists"]:
            return encrypted_data, after, ""

        last_error = "Config changed while reading."
        time.sleep(pause_seconds)

    final_fp = _config_fingerprint(config_path)
    if not final_fp["exists"]:
        return None, final_fp, "Config file disappeared during read."
    return None, final_fp, last_error or "Could not obtain stable config snapshot."


def get_config_path():
    """Obtiene la ruta del archivo de configuración segura."""
    return get_secure_config_path()


def get_key_path():
    """Obtiene la ruta del archivo de clave."""
    return get_context_key_path()


def get_runtime_context_metadata():
    """Devuelve metadata contextual canónica del config.secure activo."""
    config_path = get_config_path()
    canonical_config_path = _canonical_path(config_path)
    profile_folder = str(get_pipesync_profile_folder() or "").strip() or "PipeSync"
    context_mode = str(get_context_mode() or "").strip().lower()
    if context_mode != "client":
        context_mode = "studio"
    context_identity = f"{profile_folder.lower()}|{context_mode}"
    return {
        "config_path": canonical_config_path,
        "profile_folder": profile_folder,
        "context_mode": context_mode,
        "context_identity": context_identity,
        "cache_key": f"{canonical_config_path}|{context_identity}",
    }


def get_system_identifier():
    """Obtiene un identificador único del sistema para generar la clave."""
    # Obtener información del sistema
    import platform

    system_info = platform.uname()

    # Crear un identificador único
    identifier = f"{system_info.node}{system_info.system}{system_info.machine}"

    # Añadir MAC address si es posible
    try:
        import uuid

        mac = ":".join(
            [
                "{:02x}".format((uuid.getnode() >> elements) & 0xFF)
                for elements in range(0, 8 * 6, 8)
            ][::-1]
        )
        identifier += mac
    except:
        pass

    return identifier


def generate_key():
    """Genera una clave de encriptación basada en el sistema."""
    system_id = get_system_identifier()
    return hashlib.sha256(system_id.encode()).digest()


def get_encryption_key():
    """Obtiene la clave de encriptación."""
    key_path = get_key_path()

    if key_path.exists():
        # Eliminado log detallado
        with open(key_path, "rb") as f:
            key = f.read()
            return key
    else:
        # Si no existe el archivo de clave, generar una nueva
        key = generate_key()
        return key


def decrypt(encrypted_text, key):
    """Desencripta un texto usando XOR con la clave proporcionada."""
    if not encrypted_text:
        return ""

    try:
        # Decodificar de base64
        encrypted_data = base64.b64decode(encrypted_text)

        # Desencriptar usando XOR
        decrypted_data = bytearray()
        for i in range(len(encrypted_data)):
            decrypted_data.append(encrypted_data[i] ^ key[i % len(key)])

        result = decrypted_data.decode("utf-8")
        return result
    except Exception as e:
        debug_print(f"[SecureConfig_Reader::decrypt] Error al desencriptar: {str(e)}")
        return ""


def read_secure_config_with_status():
    """Lee config.secure activo y devuelve (config_dict, error_message)."""
    config, error, _ = read_secure_config_with_runtime_metadata()
    return config, error


def read_secure_config_with_runtime_metadata():
    """
    Lee config.secure activo y devuelve:
    (config_dict | None, error_message, runtime_metadata)
    """
    try:
        config_path = get_config_path()
        key_path = get_key_path()
        metadata = get_runtime_context_metadata()
        debug_print(
            f"[SecureConfig_Reader::read_secure_config_with_status] Ruta de configuración segura: {config_path}"
        )
        config, read_error, fingerprint = _read_secure_config_from_paths(
            config_path, key_path
        )
        metadata["config_fingerprint"] = fingerprint
        if config is None:
            return None, (read_error or "Could not read or decrypt config.secure."), metadata
        return config, "", metadata
    except Exception as e:
        debug_print(
            f"[SecureConfig_Reader::read_secure_config_with_status] Error al leer la configuración segura: {str(e)}"
        )
        import traceback

        debug_print(traceback.format_exc())
        return None, str(e), get_runtime_context_metadata()


def read_secure_config():
    """Lee la configuración segura y devuelve un diccionario con los valores."""
    config, _ = read_secure_config_with_status()
    return config


def _read_secure_config_from_paths(config_path, key_path):
    config_path = Path(config_path)
    key_path = Path(key_path)

    if not config_path.exists():
        debug_print(
            f"[SecureConfig_Reader::_read_secure_config_from_paths] Archivo no encontrado en: {config_path}"
        )
        return None, "Config file does not exist.", _config_fingerprint(config_path)

    if key_path.exists():
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        key = generate_key()

    encrypted_data, fingerprint, read_error = _read_stable_config_payload(config_path)
    if encrypted_data is None:
        debug_print(
            "[SecureConfig_Reader::_read_secure_config_from_paths] "
            f"No se pudo obtener lectura estable: {read_error}"
        )
        return None, read_error, fingerprint

    json_data = decrypt(encrypted_data, key)
    if not json_data:
        debug_print(
            "[SecureConfig_Reader::_read_secure_config_from_paths] No se pudo desencriptar la configuración"
        )
        return None, "Could not decrypt config.secure.", fingerprint

    try:
        parsed = json.loads(json_data)
    except Exception as exc:
        debug_print(
            "[SecureConfig_Reader::_read_secure_config_from_paths] "
            f"JSON inválido: {exc}"
        )
        return None, "Config JSON is corrupt.", fingerprint

    return parsed, "", fingerprint


def read_secure_config_for_profile(profile_folder):
    """
    Lee config.secure para un perfil específico de PipeSync.

    profile_folder:
        - "PipeSync" (perfil normal/studio)
        - "PipeSyncClient" (perfil client)
    """
    folder = str(profile_folder or "").strip()
    if not folder:
        return None

    config_path = get_lga_appdata_root() / folder / "config.secure"
    key_path = get_lga_appdata_root() / folder / ".key"

    try:
        config, _, _ = _read_secure_config_from_paths(config_path, key_path)
        return config
    except Exception as e:
        debug_print(
            f"[SecureConfig_Reader::read_secure_config_for_profile] Error leyendo perfil {folder}: {e}"
        )
        return None


def get_flow_login_for_profile(profile_folder):
    """Devuelve Flow.Login para un perfil específico o cadena vacía."""
    config = read_secure_config_for_profile(profile_folder) or {}
    flow_cfg = config.get("Flow", {}) if isinstance(config, dict) else {}
    return str(flow_cfg.get("Login", "")).strip()


def get_flow_credentials():
    """Obtiene las credenciales de Flow desde la configuración segura."""
    config = read_secure_config()

    if not config:
        debug_print(
            f"[SecureConfig_Reader::get_flow_credentials] No se pudo leer la configuración segura"
        )
        return None, None, None

    if "Flow" not in config:
        debug_print(
            f"[SecureConfig_Reader::get_flow_credentials] No se encontró la sección 'Flow' en la configuración segura"
        )
        return None, None, None

    flow_config = config["Flow"]

    url = flow_config.get("Url", "")
    login = flow_config.get("Login", "")
    password = flow_config.get("Password", "")

    return url, login, password


def get_s3_credentials():
    """Obtiene las credenciales de Wasabi S3 desde la configuración segura."""
    config = read_secure_config()

    if not config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_credentials] No se pudo leer la configuración segura"
        )
        return None, None, None, None

    if "Wasabi" not in config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_credentials] No se encontró la sección 'Wasabi' en la configuración segura"
        )
        return None, None, None, None

    wasabi_config = config["Wasabi"]

    access_key = wasabi_config.get("AccessKey", "")
    secret_key = wasabi_config.get("SecretKey", "")
    endpoint = wasabi_config.get("Endpoint", "")
    region = wasabi_config.get("Region", "")

    return access_key, secret_key, endpoint, region


def get_s3_connection_limits():
    """
    Obtiene el número máximo de conexiones S3 permitidas desde la configuración segura.

    Returns:
        int: Número máximo de conexiones. Por defecto 30 si no está configurado.
    """
    config = read_secure_config()

    if not config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_connection_limits] No se pudo leer la configuración segura para los límites de conexión"
        )
        return 30

    if "Wasabi" not in config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_connection_limits] No se encontró la sección 'Wasabi' en la configuración para los límites de conexión"
        )
        return 30

    wasabi_config = config["Wasabi"]

    # Leer el número de conexiones, por defecto 30
    connections = wasabi_config.get("Connections", 30)

    # Asegurar que es un número válido
    try:
        connections = int(connections)
        if connections <= 0:
            debug_print(
                f"[SecureConfig_Reader::get_s3_connection_limits] Número de conexiones inválido: {connections}, usando el valor por defecto (30)"
            )
            return 30
        debug_print(
            f"[SecureConfig_Reader::get_s3_connection_limits] Límite de conexiones S3 configurado: {connections}"
        )
        return connections
    except (ValueError, TypeError):
        debug_print(
            f"[SecureConfig_Reader::get_s3_connection_limits] Error al leer el número de conexiones: {wasabi_config.get('Connections')}, usando el valor por defecto (30)"
        )
        return 30


def get_s3_download_connection_limit():
    """
    Obtiene el número máximo de conexiones de descarga S3 permitidas desde la configuración segura.

    Returns:
        int: Número máximo de conexiones de descarga. Por defecto 30 si no está configurado o es inválido.
    """
    config = read_secure_config()
    default_limit = 30  # Coincide con el default en C++

    if not config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_download_connection_limit] No se pudo leer la configuración segura. Usando default: {default_limit}"
        )
        return default_limit

    if "Wasabi" not in config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_download_connection_limit] No se encontró la sección 'Wasabi'. Usando default: {default_limit}"
        )
        return default_limit

    wasabi_config = config["Wasabi"]

    # Leer el número de conexiones de descarga, por defecto el valor default_limit
    connections = wasabi_config.get("DownloadConnections", default_limit)

    # Asegurar que es un número válido
    try:
        connections = int(connections)
        if connections <= 0:
            debug_print(
                f"[SecureConfig_Reader::get_s3_download_connection_limit] Número de conexiones de descarga inválido: {connections}. Usando default: {default_limit}"
            )
            return default_limit
        debug_print(
            f"[SecureConfig_Reader::get_s3_download_connection_limit] Límite de conexiones de descarga S3 leído: {connections}"
        )
        return connections
    except (ValueError, TypeError):
        debug_print(
            f"[SecureConfig_Reader::get_s3_download_connection_limit] Error al leer el número de conexiones de descarga: '{wasabi_config.get('DownloadConnections')}. Usando default: {default_limit}"
        )
        return default_limit


def get_s3_upload_connection_limit():
    """
    Obtiene el número máximo de conexiones de subida S3 permitidas desde la configuración segura.

    Returns:
        int: Número máximo de conexiones de subida. Por defecto 10 si no está configurado o es inválido.
    """
    config = read_secure_config()
    default_limit = 10  # Cambio: Nuevo máximo permitido

    if not config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_upload_connection_limit] No se pudo leer la configuración segura. Usando default: {default_limit}"
        )
        return default_limit

    if "Wasabi" not in config:
        debug_print(
            f"[SecureConfig_Reader::get_s3_upload_connection_limit] No se encontró la sección 'Wasabi'. Usando default: {default_limit}"
        )
        return default_limit

    wasabi_config = config["Wasabi"]

    # Leer el número de conexiones de subida, por defecto el valor default_limit
    connections = wasabi_config.get("UploadConnections", default_limit)

    # Asegurar que es un número válido
    try:
        connections = int(connections)
        if connections <= 0:
            debug_print(
                f"[SecureConfig_Reader::get_s3_upload_connection_limit] Número de conexiones de subida inválido: {connections}. Usando default: {default_limit}"
            )
            return default_limit
        # Ajustar automáticamente valores mayores al máximo permitido
        if connections > 10:
            debug_print(
                f"[SecureConfig_Reader::get_s3_upload_connection_limit] Valor de conexiones de subida mayor al máximo permitido ({connections} > 10). Ajustando a 10."
            )
            connections = 10
        debug_print(
            f"[SecureConfig_Reader::get_s3_upload_connection_limit] Límite de conexiones de subida S3 leído: {connections}"
        )
        return connections
    except (ValueError, TypeError):
        debug_print(
            f"[SecureConfig_Reader::get_s3_upload_connection_limit] Error al leer el número de conexiones de subida: '{wasabi_config.get('UploadConnections')}'. Usando default: {default_limit}"
        )
        return default_limit


def save_flow_permission_group(permission_group):
    """Guarda el grupo de permisos del usuario de Flow en la configuración segura."""
    try:
        # Leer la configuración actual
        config = read_secure_config()

        if not config:
            debug_print(
                f"[SecureConfig_Reader::save_flow_permission_group] Error: No se pudo leer la configuración segura para guardar el grupo de permisos"
            )
            return False

        # Asegurar que existe la sección 'Flow'
        if "Flow" not in config:
            config["Flow"] = {}

        # Guardar el grupo de permisos
        config["Flow"]["PermissionGroup"] = permission_group

        # Convertir a JSON
        json_data = json.dumps(config)

        # Encriptar
        key = get_encryption_key()
        encrypted_data = encrypt(json_data, key)

        # Guardar en el archivo
        config_path = get_config_path()
        with open(config_path, "w") as f:
            f.write(encrypted_data)

        debug_print(
            f"[SecureConfig_Reader::save_flow_permission_group] Grupo de permisos '{permission_group}' guardado en la configuración"
        )
        return True

    except Exception as e:
        debug_print(
            f"[SecureConfig_Reader::save_flow_permission_group] Error al guardar el grupo de permisos: {str(e)}"
        )
        import traceback

        debug_print(traceback.format_exc())
        return False


def encrypt(text, key):
    """Encripta un texto usando XOR con la clave proporcionada."""
    if not text:
        return ""

    try:
        # Encriptar usando XOR
        encrypted_data = bytearray()
        text_bytes = text.encode("utf-8")
        for i in range(len(text_bytes)):
            encrypted_data.append(text_bytes[i] ^ key[i % len(key)])

        # Codificar en base64
        result = base64.b64encode(encrypted_data).decode("utf-8")
        return result
    except Exception as e:
        debug_print(f"[SecureConfig_Reader::encrypt] Error al encriptar: {str(e)}")
        return ""


# Función principal para pruebas
if __name__ == "__main__":
    debug_print("[SecureConfig_Reader::main] Iniciando lectura de configuración segura")

    url, login, password = get_flow_credentials()

    if url and login and password:
        debug_print(
            f"[SecureConfig_Reader::main] Credenciales obtenidas. URL: {url}, Usuario: {login}"
        )
        debug_print(
            f"[SecureConfig_Reader::main] URL: {url}, Usuario: {login}, Contraseña: {'*' * len(password)}"
        )
    else:
        debug_print(
            "[SecureConfig_Reader::main] No se pudieron obtener las credenciales de Flow"
        )
        debug_print(
            "[SecureConfig_Reader::main] ERROR: No se pudieron obtener las credenciales de Flow"
        )
