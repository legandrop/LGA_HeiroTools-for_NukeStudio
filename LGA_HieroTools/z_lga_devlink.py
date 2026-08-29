"""
____________________________________________________________________

  z_lga_devlink v1.00 | Lega

  Dev-link para manejar NKS desde afuera durante desarrollo: un socket
  SOLO en localhost que recibe codigo python, lo ejecuta en el hilo
  principal (executeInMainThreadWithResult, patron de LGA_OpenInNukeX)
  y devuelve stdout + traceback si fallo.

  SEGURIDAD: completamente INERTE salvo que el proceso arranque con la
  variable de entorno LGA_DEVLINK=1. En uso normal de NKS no abre nada,
  no escucha nada y no ejecuta nada. Bind exclusivo a 127.0.0.1.

  Con el gate prendido ejecuta codigo arbitrario que le llegue por el
  socket: es RCE local por diseno. Por eso la env var SIEMPRE se setea
  POR LANZAMIENTO (en el comando que abre NKS), NUNCA como variable de
  sistema persistente: si quedara global, el server quedaria encendido y
  en silencio en cada sesion de NKS. El vector CSRF de browser esta
  cerrado (es un socket crudo, no HTTP: el preambulo del browser es
  SyntaxError), pero cualquier proceso local puede usarlo mientras este
  activo. Herramienta de desarrollo, no de runtime productivo.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os

DEVLINK_PORT = 54326


def _start_server():
    import contextlib
    import io
    import socket
    import threading
    import traceback

    import nuke

    def _run_code(code):
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                exec(compile(code, "<devlink>", "exec"), {"__name__": "__devlink__"})
            return "OK\n" + buffer.getvalue()
        except Exception:
            return "ERROR\n" + buffer.getvalue() + traceback.format_exc()

    def _handle(conn):
        with conn:
            try:
                chunks = []
                while True:
                    data = conn.recv(65536)
                    if not data:
                        break
                    chunks.append(data)
                    if b"\x00" in data:
                        break
                code = b"".join(chunks).split(b"\x00")[0].decode("utf-8")
                if not code.strip():
                    conn.sendall(b"ERROR\ncodigo vacio")
                    return
                result = nuke.executeInMainThreadWithResult(lambda: _run_code(code))
                conn.sendall(str(result).encode("utf-8"))
            except Exception as exc:
                try:
                    conn.sendall(("ERROR\n" + str(exc)).encode("utf-8"))
                except Exception:
                    pass

    def _serve():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("127.0.0.1", DEVLINK_PORT))
            server.listen(1)
            print("[z_lga_devlink] escuchando en 127.0.0.1:%d" % DEVLINK_PORT)
            while True:
                conn, _addr = server.accept()
                worker = threading.Thread(target=_handle, args=(conn,))
                worker.daemon = True
                worker.start()
        except Exception as exc:
            print("[z_lga_devlink] servidor caido: %s" % exc)
            try:
                server.close()
            except Exception:
                pass

    thread = threading.Thread(target=_serve)
    thread.daemon = True
    thread.name = "LGA_DevLink"
    thread.start()


if os.environ.get("LGA_DEVLINK") == "1":
    _start_server()
