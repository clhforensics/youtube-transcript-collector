from app.output import extension_for_format, save_output


def test_extensions():
    assert extension_for_format("text") == "txt"
    assert extension_for_format("timestamped") == "txt"
    assert extension_for_format("json") == "json"
    assert extension_for_format("srt") == "srt"
    assert extension_for_format("vtt") == "vtt"


def test_save_output(tmp_path):
    path = save_output(tmp_path, "sample", "hello", "text")
    assert path.read_text(encoding="utf-8") == "hello"
