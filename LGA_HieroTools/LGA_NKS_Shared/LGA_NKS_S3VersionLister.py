"""
____________________________________________________________________

  LGA_NKS_S3VersionLister v1.00 | Lega

  Lista las versiones hermanas de un media en Wasabi para poder detectar
  ramas ANTES de lanzar la descarga.

  Por que en HieroTools y no en FileManager: el dialogo de "que rama
  bajar" tiene que salir donde el usuario hizo el click, y resolviendo
  aca las cabezas se le pasan a FileManager rutas explicitas con los
  flags que ya existen (--download / --download-file). Asi no cambia el
  contrato del CLI y las dos apps no quedan acopladas por version.

  El listado es una sola llamada list_objects_v2 con Delimiter='/' sobre
  la carpeta padre del media, igual que hace FileManager para resolver
  --download-latest.

  La funcion de listado es inyectable (`lister`) para poder testear la
  logica de ramas sin red ni credenciales.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import sys

from LGA_NKS_BucketResolver import resolve_bucket_from_local_path
from LGA_NKS_VersionBranching import extract_version_number, family_key


DEBUG = False


def debug_print(*message):
    if DEBUG:
        print("[S3VersionLister]", *message)


def _ensure_boto3_on_path():
    """Agrega al path el runtime de boto3 que vive dentro del Assignee Panel.

    Es el unico boto3 del repo (se mantiene autocontenido ahi para no
    duplicar el vendor); este modulo solo lo consume.

    Se inserta en la posicion 0 y no al final, igual que hace
    LGA_NKS_Wasabi_PolicyAssign.py. Agregandolo al final, cualquier otro
    boto3/botocore que ya este en el path gana la resolucion y se termina
    mezclando un boto3 con el botocore de otro runtime, que revienta con
    "cannot import name DEFAULT_CHECKSUM_ALGORITHM".
    """
    startup_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    boto3_dir = os.path.join(startup_dir, "LGA_NKS_Assignee_Panel_py")
    if not os.path.isdir(boto3_dir):
        return
    if boto3_dir in sys.path:
        sys.path.remove(boto3_dir)
    sys.path.insert(0, boto3_dir)


def _default_lister(bucket, prefix):
    """Lista un nivel de un prefijo en Wasabi. Devuelve (folders, files).

    Los nombres son relativos al prefijo (sin barra final en las carpetas).
    """
    _ensure_boto3_on_path()
    import boto3  # import diferido: solo cuando hay que ir a la red
    import botocore

    # Diagnostico: boto3 y botocore tienen que salir del MISMO runtime.
    debug_print(f"boto3={getattr(boto3, '__file__', '?')}")
    debug_print(f"botocore={getattr(botocore, '__file__', '?')}")

    from SecureConfig_Reader import get_s3_credentials

    access_key, secret_key, endpoint, region = get_s3_credentials()
    if not access_key or not secret_key or not endpoint:
        raise RuntimeError("Faltan credenciales de Wasabi en config.secure")

    # En config.secure el endpoint viene sin esquema (s3.wasabisys.com) y boto3
    # lo rechaza con "Invalid endpoint". PipeSync hace lo mismo al armar el suyo.
    endpoint_url = str(endpoint).strip()
    if not endpoint_url.startswith(("http://", "https://")):
        endpoint_url = "https://" + endpoint_url

    session = boto3.session.Session()
    client = session.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region or None,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    normalized_prefix = str(prefix or "").strip("/")
    list_prefix = (normalized_prefix + "/") if normalized_prefix else ""

    folders = []
    files = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=list_prefix, Delimiter="/"):
        for common in page.get("CommonPrefixes") or []:
            raw = str(common.get("Prefix") or "")
            name = raw[len(list_prefix):].strip("/")
            if name:
                folders.append(name)
        for content in page.get("Contents") or []:
            raw = str(content.get("Key") or "")
            if raw == list_prefix:
                continue
            name = raw[len(list_prefix):]
            if name and "/" not in name:
                files.append(name)
    return folders, files


def resolve_remote_context(target_local_path):
    """bucket/prefix del PADRE del target y nombre del target.

    `target_local_path` es la carpeta de version (secuencias) o el archivo
    (.mov). Devuelve dict con ok/error para no reventar el flujo de descarga.
    """
    normalized = str(target_local_path or "").replace("\\", "/").rstrip("/")
    if not normalized:
        return {"ok": False, "error": "Empty target path."}

    parent_local = os.path.dirname(normalized)
    target_name = os.path.basename(normalized)
    if not parent_local or not target_name:
        return {"ok": False, "error": f"Cannot split parent from '{normalized}'."}

    resolved = resolve_bucket_from_local_path(parent_local)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "error": resolved.get("error") or "Could not resolve bucket.",
        }

    return {
        "ok": True,
        "bucket": resolved["bucket"],
        "prefix": resolved.get("prefix", ""),
        "parent_local": parent_local,
        "target_name": target_name,
    }


def list_family_versions(target_local_path, is_single_file, lister=None):
    """Versiones hermanas del target en Wasabi, de la misma familia.

    Devuelve dict:
      ok, bucket, prefix, parent_local, target_name, target_version,
      versions {numero: nombre}
    Las carpetas se miran para secuencias y los archivos para media unico,
    igual que hace FileManager al resolver --download-latest.
    """
    context = resolve_remote_context(target_local_path)
    if not context.get("ok"):
        return context

    target_name = context["target_name"]
    target_version = extract_version_number(target_name)
    if target_version < 0:
        return {
            "ok": False,
            "error": f"'{target_name}' no tiene token _v###.",
        }

    list_fn = lister or _default_lister
    try:
        folders, files = list_fn(context["bucket"], context["prefix"])
    except Exception as exc:
        return {"ok": False, "error": f"Error listando Wasabi: {exc}"}

    candidates = folders if not is_single_file else files
    wanted_family = family_key(target_name)

    versions = {}
    for name in candidates or []:
        number = extract_version_number(name)
        if number < 0:
            continue
        if family_key(name) != wanted_family:
            continue
        # Si hay dos entradas con el mismo numero gana la primera: es el
        # mismo contenido con nombre distinto y no hay criterio mejor.
        versions.setdefault(number, name)

    debug_print(
        f"{context['bucket']}/{context['prefix']} familia={wanted_family} "
        f"versiones={sorted(versions)}"
    )

    result = dict(context)
    result["target_version"] = target_version
    result["versions"] = versions
    return result
