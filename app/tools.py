"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
import re
from datetime import datetime
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_RESULTS = 3
# 第3回 宿題（実装）: 学習の記録の保存先。.gitignore 済みなので個人の記録は共有されない
LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回（1始まりの整数）の用語から1つを選び、確認問題とその答えを返す。

    「第2回の確認問題を出して」「第3回の復習クイズがほしい」のように、
    回を指定して確認問題・復習問題を求められたときに使う。
    答えは用語集の定義なので、問題だけを先に出し、答えは利用者が考えてから示すとよい。
    """
    terms = [e for e in load_glossary() if e["lecture"] == lecture]
    if not terms:
        available = sorted({e["lecture"] for e in load_glossary()})
        return f"第{lecture}回の用語は用語集にありません。用語がある回: {', '.join(map(str, available))}"
    entry = random.choice(terms)
    return json.dumps(
        {
            "lecture": lecture,
            "question": f"「{entry['term']}」とはどういう意味ですか？",
            "answer": entry["definition"],
        },
        ensure_ascii=False,
    )


def _slug(text: str) -> str:
    """ファイル名に使えない文字を _ に置き換え、長すぎるタイトルは切り詰める。"""
    slug = re.sub(r'[\\/:*?"<>|\s]+', "_", text.strip()).strip("._")
    return slug[:40] or "log"


def save_learning_log(title: str, content: str, lecture: int | None = None) -> str:
    """学習の記録（学んだこと・気づき・疑問など）を learning_log/ フォルダに Markdown で保存する。

    利用者が「今日学んだことを記録して」「このメモを学習ログに保存して」のように、
    記録・保存をはっきり頼んだときだけ使う。質問に答えるだけのときは使わない。
    title には記録の短い見出し、content には保存する本文（箇条書きでよい）、
    lecture には関係する回（1始まりの整数、分からなければ省略）を入れる。
    ファイルを書き込むため、実行前に利用者の承認が必要。
    """
    if not title.strip() or not content.strip():
        return "保存しませんでした。title と content の両方を指定してください。"
    now = datetime.now()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{now:%Y%m%d-%H%M%S}_{_slug(title)}.md"
    # 同じ秒に同じタイトルで保存しても上書きしない（保存は取り消しにくい操作なので既存の記録を守る）
    n = 2
    while path.exists():
        path = LOG_DIR / f"{now:%Y%m%d-%H%M%S}_{_slug(title)}_{n}.md"
        n += 1
    header = [f"# {title.strip()}", "", f"- 日時: {now:%Y-%m-%d %H:%M}"]
    if lecture is not None:
        header.append(f"- 関係する回: 第{lecture}回")
    path.write_text("\n".join(header) + "\n\n" + content.strip() + "\n", encoding="utf-8")
    return f"学習の記録を保存しました: {path.relative_to(LOG_DIR.parent)}"
