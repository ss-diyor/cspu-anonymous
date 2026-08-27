from app.services.content import rendered_text


def test_channel_post_layout_is_clean() -> None:
    assert (
        rendered_text("O‘qish qachondan", prefix="#1", footer="#question")
        == "#1\n\nO‘qish qachondan\n\n#question"
    )
