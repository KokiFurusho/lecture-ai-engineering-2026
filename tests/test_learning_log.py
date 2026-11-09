"""第3回 宿題（実装）: save_learning_log と、保存前の承認のテスト（LLMもAPIキーも使わない）。

TestModel は登録されたツールを呼ぶ偽モデル。call_tools で save_learning_log だけを呼ばせ、
- 承認が必要なので、いったん DeferredToolRequests が返って止まる（まだ保存されない）
- 承認すると保存され、拒否すると保存されない
ことを確かめる。保存先は tmp_path に差し替え、本物の learning_log/ は汚さない。
"""

import pytest
from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, run_with_approval

ARGS = {"title": "LoRAのまとめ", "content": "- 一部の重みだけを学習する", "lecture": 2}


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    path = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LOG_DIR", path)
    return path


def scripted(lines):
    it = iter(lines)
    return lambda prompt: next(it)


def _model():
    # 呼ぶツールだけを指定する。引数（title, content など）は TestModel がダミーを自動で作る
    return TestModel(call_tools=["save_learning_log"])


def test_save_learning_log_writes_markdown(log_dir):
    message = tools.save_learning_log(**ARGS)

    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    assert "保存しました" in message and files[0].name in message
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("# LoRAのまとめ")
    assert "第2回" in text
    assert "一部の重みだけを学習する" in text


def test_save_learning_log_does_not_overwrite(log_dir):
    tools.save_learning_log(**ARGS)
    tools.save_learning_log(**ARGS)  # 同じ秒・同じタイトルでも別ファイルになる
    assert len(list(log_dir.glob("*.md"))) == 2


def test_save_learning_log_rejects_empty_and_unsafe_title(log_dir):
    assert "保存しませんでした" in tools.save_learning_log(title=" ", content="本文")
    assert not log_dir.exists()

    tools.save_learning_log(title="../../外へ/出る", content="本文")
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1 and files[0].parent == log_dir  # learning_log/ の外には書かない


def test_tool_requires_approval_and_does_not_save_before_it(log_dir):
    with agent.override(model=_model()):
        result = agent.run_sync("学習ログに保存して")

    assert isinstance(result.output, DeferredToolRequests)
    assert [c.tool_name for c in result.output.approvals] == ["save_learning_log"]
    assert not log_dir.exists()  # 承認前なので、まだ何も保存されていない


def test_approved_call_is_saved(log_dir):
    with agent.override(model=_model()):
        first = agent.run_sync("学習ログに保存して")
        call = first.output.approvals[0]
        result = agent.run_sync(
            message_history=first.all_messages(),
            deferred_tool_results=DeferredToolResults(approvals={call.tool_call_id: True}),
        )

    assert isinstance(result.output, str)
    assert len(list(log_dir.glob("*.md"))) == 1
    returns = [p for m in result.new_messages() for p in m.parts if isinstance(p, ToolReturnPart)]
    assert "保存しました" in returns[0].content


def test_cli_flow_yes_saves(log_dir, capsys):
    result = run_with_approval(agent, "学習ログに保存して", _model(), read=scripted(["y"]))

    assert isinstance(result.output, str)
    assert len(list(log_dir.glob("*.md"))) == 1
    out = capsys.readouterr().out
    assert "[承認待ち] save_learning_log" in out
    assert "title:" in out and "content:" in out  # 何を保存するかを見せてから聞いている


@pytest.mark.parametrize("answer", ["n", "", "いいえ"])
def test_cli_flow_no_does_not_save(log_dir, answer):
    result = run_with_approval(agent, "学習ログに保存して", _model(), read=scripted([answer]))

    assert isinstance(result.output, str)
    assert not log_dir.exists()
    denied = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)]
    assert "拒否" in str(denied[-1].content)


def test_cli_flow_eof_is_treated_as_no(log_dir):
    def eof(prompt):
        raise EOFError

    run_with_approval(agent, "学習ログに保存して", _model(), read=eof)
    assert not log_dir.exists()


def test_usage_is_summed_over_both_runs(log_dir):
    result = run_with_approval(agent, "学習ログに保存して", _model(), read=scripted(["y"]))
    # 止まる前の1回 + 承認後の1回（TestModel は1回の実行で1リクエストずつ）
    assert result.usage.requests == 2
