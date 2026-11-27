"""Memoria de las conversaciones (contexto de varios turnos).

Antes era un diccionario que crecía sin límite: cada conversación guardaba todos sus mensajes
y nunca se borraba. Con un asistente encendido días enteros en un kiosco o en reuniones, la
memoria solo subía. Ahora cada sesión guarda solo los turnos que se le mandan al modelo, se
olvida tras un rato sin uso y hay un tope de sesiones (se descarta la más antigua).
"""
import threading
import time
from collections import OrderedDict

from . import config


class SessionStore:
    def __init__(self, max_turns: int, ttl_seconds: float, max_sessions: int, clock=time.monotonic):
        self.max_messages = 2 * max_turns
        self.ttl = ttl_seconds
        self.max_sessions = max_sessions
        self._clock = clock
        self._data: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
        self._lock = threading.Lock()

    def history(self, session_id: str) -> list[dict]:
        """Mensajes previos de la sesión (copia), del más viejo al más nuevo."""
        with self._lock:
            self._expire()
            entry = self._data.get(session_id)
            return list(entry[1]) if entry else []

    def add(self, session_id: str, user: str, assistant: str) -> None:
        with self._lock:
            self._expire()
            _, messages = self._data.pop(session_id, (0.0, []))
            messages = (messages + [{"role": "user", "content": user},
                                    {"role": "assistant", "content": assistant}])[-self.max_messages:]
            self._data[session_id] = (self._clock(), messages)
            while len(self._data) > self.max_sessions:
                self._data.popitem(last=False)

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._data.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            self._expire()
            return len(self._data)

    def _expire(self) -> None:
        limit = self._clock() - self.ttl
        while self._data:
            oldest_id, (last_used, _) = next(iter(self._data.items()))
            if last_used >= limit:
                break
            del self._data[oldest_id]


store = SessionStore(config.MAX_TURNS, config.SESSION_TTL_MINUTES * 60, config.MAX_SESSIONS)
