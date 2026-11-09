# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：
- `--trace` で見えたツール呼び出し（ツール名と引数）：
- 1つの質問での LLM 呼び出し回数（`requests`）：
- 追加したツールと、docstring に書いた説明：

## 宿題

- 取り組んだレベル：実装
- 使ったモデル：gemini-3.5-flash-lite（既定。`AIE_MODEL` は変えていない）
- やったこと：
  - `app/tools.py` に `save_learning_log(title, content, lecture=None)` を追加した。学習の記録を `learning_log/日時_タイトル.md` に Markdown で保存する
    - docstring には「記録・保存をはっきり頼まれたときだけ使う。質問に答えるだけのときは使わない」と書き、勝手に保存しないようにした
    - タイトルの `/` や `..` などは `_` に置き換え、`learning_log/` の外には書き込まない。同じ秒・同じタイトルでも上書きせず別ファイルにする（保存は取り消しにくいので、既存の記録を守る）
    - `learning_log/` は `.gitignore` 済みなので、個人の記録はコミットされない
  - `app/agent.py` で `agent.tool_plain(tools.save_learning_log, requires_approval=True)` として登録し、`output_type=[str, DeferredToolRequests]` にした。`INSTRUCTIONS` に「学習の記録や保存を頼まれたら save_learning_log で保存する。頼まれていないときは保存しない」を追加した
  - CLI に承認の流れを追加した（`run_with_approval` / `ask_approvals`）
    1. 1回目の `run_sync` で、モデルが `save_learning_log` を呼ぼうとすると実行が止まり、`DeferredToolRequests` が返る
    2. 保存しようとしている `title` / `content` / `lecture` を表示し、「実行してよいですか？ [y/N]」と聞く。`y` / `yes` / `はい` 以外（空行・Ctrl-D を含む）は拒否として扱う（安全側に倒す）
    3. 承認なら `True`、拒否なら `ToolDenied("利用者が保存を拒否しました。…")` を `DeferredToolResults` に入れ、`message_history=result.all_messages()` と一緒にもう一度 `run_sync` する。承認されたときだけツールが実行され、モデルはその結果を見て回答を続ける
    4. 2回目の `run_sync` に `usage=result.usage` を渡し、`[usage]` に止まる前と後の合計が出るようにした
    ```bash
    uv run python -m app.agent --trace "LoRAについて学んだことを学習ログに保存して"
    ```
  - `tests/test_learning_log.py` を追加した（TestModel を使い、API キー不要。保存先は `tmp_path` に差し替え）
    - ツール単体：Markdown で保存される／上書きしない／空のタイトルは保存しない／`../../` を含むタイトルでも `learning_log/` の外に書かない
    - 承認：呼ばれた時点では `DeferredToolRequests` が返り、まだファイルはない。承認すると1件保存され、拒否（`n`・空行・`いいえ`・Ctrl-D）すると保存されず、モデルには拒否のメッセージが返る
    - `[usage]` の `requests` が止まる前と後の合計（2）になる
  - 既存の `tests/test_agent.py` は「呼ばれたツールの数 ＝ 返ってきた結果の数」を確かめていたが、承認待ちのツールは実行されず結果が返らないため、承認待ちの数を引いて比べるように直した
- 結果：
  - `uv run pytest -q`：22 passed（追加した 11 件を含む）
  - `--list-tools` で `save_learning_log` と docstring・引数（`title`, `content`, `lecture`）がモデルに見えていることを確認した
  - TestModel に差し替えて CLI を動かしたときの `--trace`（`y` と答えた場合）
    ```
    [承認待ち] save_learning_log を次の引数で実行しようとしています:
      title: a
      content: a
    実行してよいですか？ [y/N]
    --- trace ---
    [tool call]   save_learning_log({'title': 'a', 'content': 'a'})
    [tool return] save_learning_log -> 学習の記録を保存しました: learning_log/20261109-052741_a.md…
    [usage] RunUsage(input_tokens=105, output_tokens=20, requests=2, tool_calls=1)
    ```
    `n` と答えた場合は `[tool return]` が「利用者が保存を拒否しました。…」になり、ファイルは作られず、`tool_calls` も数えられなかった
  - 実際の API（Gemini）での実行結果：（Codespaces で実行して記入）
- 気づき・疑問：
  - 承認が必要なツールは「呼ばれたら実行」ではなく、実行がいったん止まり、承認の結果を渡して続きを実行する、という2段階になる。そのため1つの質問で `run_sync` が2回、LLM の呼び出しも最低2回になる
  - 拒否したときもモデルには「拒否された」という結果が返るので、モデルはそれを見て「保存していない」と伝えられる。黙って止めるより会話として自然
  - 確認の画面で引数（保存する中身）を見せることが大事だと感じた。名前だけ見せて「実行してよいか」と聞いても、何が保存されるか分からず判断できない
  - 疑問：`requires_approval=True` は毎回確認を求めるが、「同じ会話の中で一度承認したら次からは聞かない」のような条件付きの承認はどう書くのがよいか（`ApprovalRequired` を条件付きで投げる方法がありそう）
