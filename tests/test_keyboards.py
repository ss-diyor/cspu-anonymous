from app.keyboards import anonymous_comment_button, moderation_submission


def test_anonymous_comment_uses_opaque_deep_link() -> None:
    markup = anonymous_comment_button("@sample_bot", "Abcd_1234")
    button = markup.inline_keyboard[0][0]
    assert button.url == "https://t.me/sample_bot?start=comment_Abcd_1234"


def test_moderation_keyboard_callback_data_is_small() -> None:
    markup = moderation_submission(123, "sample_bot", "Abcd_1234")
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert all(value is None or len(value.encode()) <= 64 for value in callbacks)
