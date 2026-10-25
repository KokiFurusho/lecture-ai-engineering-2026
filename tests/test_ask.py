"""第1回 ask.py のテスト（LLMもAPIキーも使わない）。

google-genai の本物の Chat に、API を呼ばない偽の Models を渡して、
2回目の質問で1回目のやりとりが履歴として送られることを確かめる。
"""

from google.genai import chats, types

from app import ask


class FakeModels:
    """generate_content に渡された contents を記録し、決まった回答を返す。"""

    def __init__(self):
        self.calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append([c.parts[0].text for c in contents])
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(role="model", parts=[types.Part(text=f"回答{len(self.calls)}")])
                )
            ],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=10 * len(self.calls), candidates_token_count=3
            ),
        )


def scripted(lines):
    it = iter(lines)
    return lambda prompt: next(it)


def test_chat_loop_keeps_history(capsys):
    models = FakeModels()
    chat = chats.Chats(modules=models).create(model="fake")

    turns = ask.chat_loop(chat, read=scripted(["私の名前は佐藤です", "私の名前は？", "exit"]))

    assert turns == 2
    assert models.calls[0] == ["私の名前は佐藤です"]
    # 2回目は、1回目の質問と回答も一緒に送られている
    assert models.calls[1] == ["私の名前は佐藤です", "回答1", "私の名前は？"]
    assert len(chat.get_history()) == 4
    out = capsys.readouterr().out
    assert "[tokens] 入力: 20 / 出力: 3" in out


def test_chat_loop_ends_on_empty_line_and_eof():
    models = FakeModels()
    chat = chats.Chats(modules=models).create(model="fake")
    assert ask.chat_loop(chat, read=scripted([""])) == 0

    def eof(prompt):
        raise EOFError

    assert ask.chat_loop(chat, read=eof) == 0
    assert models.calls == []


def test_format_usage_handles_missing_metadata():
    assert "取得できませんでした" in ask.format_usage(types.GenerateContentResponse())
    with_thoughts = types.GenerateContentResponse(
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=5, candidates_token_count=7, thoughts_token_count=2
        )
    )
    assert ask.format_usage(with_thoughts) == "[tokens] 入力: 5 / 出力: 7 / 思考: 2"
