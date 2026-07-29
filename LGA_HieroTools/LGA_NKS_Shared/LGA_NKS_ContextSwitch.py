"""
____________________________________________________________________

  LGA_NKS_ContextSwitch v1.00 | Lega

  Gate y bus del switch Studio/Client de los paneles.

  El switch existe para UN solo usuario: el que tiene los dos perfiles de
  PipeSync instalados y va y viene entre estudio y cliente. El resto de la
  gente tiene un contexto FIJO, definido por el zip que instalo, y nunca lo
  cambia en caliente.

  Por eso todo lo dinamico esta detras de `has_context_switch()`:

    - si el gate da False, `subscribe()` y `notify()` no hacen absolutamente
      nada. No se crea el QObject, no se conecta ninguna senal, no queda ningun
      callback vivo. El panel arma sus botones una vez en __init__ leyendo
      `get_context_mode()` y ahi termina;
    - si da True, recien ahi se instancia el bus.

  El gate se memoiza a nivel de modulo porque resolverlo implica leer y
  desencriptar `config.secure`. Projects Panel y ViewerTL ya lo resolvian cada
  uno por su cuenta; pasando por aca se hace una sola vez por sesion de Hiero.

  v1.00: Version inicial.
____________________________________________________________________

"""

# Unico login habilitado para cambiar de contexto en caliente. Se compara
# contra el Flow.Login del perfil PipeSync NORMAL (no el del contexto activo):
# en modo client el login es el de la editora del cliente.
SWITCH_USER_LOGIN = "lega@wanka.tv"

# None = todavia no se resolvio. "" = se resolvio y no hay login.
_normal_login = None
_bus = None


def _read_normal_login():
    try:
        from LGA_NKS_Shared.LGA_NKS_PipeSyncPreflight import (
            get_normal_pipesync_flow_login,
        )
    except ImportError:
        try:
            from LGA_NKS_PipeSyncPreflight import get_normal_pipesync_flow_login
        except Exception:
            return ""
    except Exception:
        return ""

    try:
        return str(get_normal_pipesync_flow_login() or "").strip().lower()
    except Exception:
        return ""


def get_normal_login():
    """
    Flow.Login del perfil PipeSync NORMAL, en minusculas, memoizado por sesion.

    Resolverlo implica leer y desencriptar `config.secure`. Sin cache lo hacian
    por separado el Projects Panel (dos veces: el panel y el UIManager) y el
    ViewerTL Panel, cada uno en su arranque.
    """
    global _normal_login
    if _normal_login is None:
        _normal_login = _read_normal_login()
    return _normal_login


def has_context_switch():
    """
    True solo para el usuario que puede alternar contexto en caliente.

    El resultado no cambia dentro de una sesion de Hiero: depende de que perfiles
    de PipeSync hay instalados, no del contexto activo.
    """
    return get_normal_login() == SWITCH_USER_LOGIN


def _get_bus():
    """Instancia el bus la primera vez que se lo pide. Solo se llama con gate True."""
    global _bus
    if _bus is None:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

        class _ContextBus(QtCore.QObject):
            # Emite el modo nuevo ya normalizado ("studio" | "client").
            contextChanged = QtCore.Signal(str)

        _bus = _ContextBus()
    return _bus


def subscribe(callback):
    """
    Conecta `callback(mode)` al cambio de contexto.

    Devuelve False y no hace nada si el usuario no tiene el switch, que es el
    caso de todos salvo uno. El caller no necesita chequear nada antes.
    """
    if not has_context_switch():
        return False
    try:
        _get_bus().contextChanged.connect(callback)
    except Exception:
        return False
    return True


def notify(mode):
    """Avisa a los paneles suscriptos. No-op si no hay switch."""
    if not has_context_switch():
        return False
    try:
        _get_bus().contextChanged.emit(str(mode))
    except Exception:
        return False
    return True
