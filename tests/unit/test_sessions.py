from app.sessions import SessionStore


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_guarda_solo_los_ultimos_turnos():
    store = SessionStore(max_turns=2, ttl_seconds=100, max_sessions=10)
    for i in range(5):
        store.add("s", f"pregunta {i}", f"respuesta {i}")
    history = store.history("s")
    assert len(history) == 4
    assert history[0] == {"role": "user", "content": "pregunta 3"}
    assert history[-1] == {"role": "assistant", "content": "respuesta 4"}


def test_olvida_sesiones_inactivas():
    clock = Clock()
    store = SessionStore(max_turns=2, ttl_seconds=60, max_sessions=10, clock=clock)
    store.add("vieja", "a", "b")
    clock.now = 30
    store.add("nueva", "c", "d")
    clock.now = 61
    assert store.history("vieja") == []
    assert store.history("nueva") != []
    assert len(store) == 1


def test_tope_de_sesiones_descarta_la_mas_antigua():
    store = SessionStore(max_turns=1, ttl_seconds=100, max_sessions=2)
    store.add("a", "1", "1")
    store.add("b", "2", "2")
    store.add("a", "3", "3")  # "a" vuelve a ser la más reciente
    store.add("c", "4", "4")
    assert store.history("b") == []
    assert store.history("a") and store.history("c")


def test_reset_y_copia():
    store = SessionStore(max_turns=2, ttl_seconds=100, max_sessions=10)
    store.add("s", "a", "b")
    store.history("s").clear()  # modificar la copia no cambia la sesión
    assert len(store.history("s")) == 2
    store.reset("s")
    assert store.history("s") == []
