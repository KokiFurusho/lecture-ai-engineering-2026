"""第1回: 素のLLMに質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする
    uv run python -m app.ask --chat     # 会話履歴を保ったまま続けて質問する（第1回 宿題・実装）

ツールを持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse
from collections.abc import Callable

from google import genai
from google.genai import errors

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"

# --chat で会話を終える入力
EXIT_WORDS = ("", "exit", "quit")


def format_usage(response) -> str:
    """response.usage_metadata から入力トークン数と出力トークン数を1行にする。"""
    usage = response.usage_metadata
    if usage is None:
        return "[tokens] 取得できませんでした"
    line = f"[tokens] 入力: {usage.prompt_token_count} / 出力: {usage.candidates_token_count}"
    # 思考（thinking）するモデルでは、出力とは別に思考のトークン数も返る
    if usage.thoughts_token_count:
        line += f" / 思考: {usage.thoughts_token_count}"
    return line


def ask(question: str) -> str:
    client = genai.Client(api_key=get_api_key())
    response = client.models.generate_content(model=MODEL, contents=question)

    print(format_usage(response) + "\n")

    return response.text


def chat_loop(chat, read: Callable[[str], str] = input) -> int:
    """会話履歴を保ったまま続けて質問する。空行・exit・quit で終わる。

    chat は client.chats.create() の戻り値。送った質問と返ってきた回答は chat が履歴として持ち、
    次の send_message で履歴ごとモデルに送られる。戻り値はやりとりできた回数。
    """
    turns = 0
    while True:
        try:
            question = read("あなた> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in EXIT_WORDS:
            break
        try:
            response = chat.send_message(question)
        except errors.APIError as e:
            # レート制限などで失敗しても、それまでの履歴は残したまま続けられる
            print(api_error_message(e.code, e.message) + "\n")
            continue
        turns += 1
        print(f"\nモデル> {response.text}")
        print(format_usage(response) + "\n")
    return turns


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--chat", action="store_true", help="会話履歴を保ったまま続けて質問する")
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    if args.chat:
        client = genai.Client(api_key=get_api_key())
        print("会話モードです。空行か exit で終わります。\n")
        chat_loop(client.chats.create(model=MODEL))
        return

    print(f"[質問] {args.question}\n")
    try:
        print(ask(args.question))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
