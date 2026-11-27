import os

from app.config import load_env_file


def test_lee_valores_comentarios_y_comillas(tmp_path, monkeypatch):
    for key in ("PRUEBA_A", "PRUEBA_B", "PRUEBA_C", "PRUEBA_D"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# comentario\n"
        "PRUEBA_A=gemma3:4b\n"
        "PRUEBA_B = \"con espacios # no es comentario\"\n"
        "PRUEBA_C=small  # comentario al final\n"
        "linea sin igual\n"
        "\n"
        "PRUEBA_D='x'\n",
        encoding="utf-8",
    )
    loaded = load_env_file(env)
    assert loaded == {"PRUEBA_A": "gemma3:4b", "PRUEBA_B": "con espacios # no es comentario",
                      "PRUEBA_C": "small", "PRUEBA_D": "x"}
    assert os.environ["PRUEBA_C"] == "small"


def test_no_pisa_variables_ya_definidas(tmp_path, monkeypatch):
    monkeypatch.setenv("PRUEBA_E", "de la terminal")
    env = tmp_path / ".env"
    env.write_text("PRUEBA_E=del archivo\n", encoding="utf-8")
    assert load_env_file(env) == {}
    assert os.environ["PRUEBA_E"] == "de la terminal"


def test_archivo_inexistente(tmp_path):
    assert load_env_file(tmp_path / "no-existe.env") == {}
