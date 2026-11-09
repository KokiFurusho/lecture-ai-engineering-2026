# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：
  - 第1回の `app.ask` は講座を知らないまま一般論でもっともらしく答えた（宿題の3レベルを「基礎・応用・発展」などと推測）
  - エージェントに「AIE2026の講座で使う「lecNN-start タグ」とは何ですか？」と聞くと、「各回の演習を開始する時点のコードに付けられている Git タグで、前の回が終わっていなくてもこのタグからブランチを作れば演習を始められる」と、用語集（`data/glossary.json`）の定義どおりに答え、最後に関係する回（第1回）を示した
- `--trace` で見えたツール呼び出し（ツール名と引数）：
  - 「LoRAとQLoRAの違いは？」
    ```
    [tool call]   search_glossary({'query': 'LoRA'})
    [tool call]   search_glossary({'query': 'QLoRA'})
    [tool return] search_glossary -> [{"term": "LoRA", "lecture": 2, ...
    [tool return] search_glossary -> [{"term": "QLoRA", "lecture": 2, ...
    ```
    docstring の「query には調べたい用語を1つだけ入れる」に従い、2つの用語を別々に検索していた。2つの呼び出しは1回の応答でまとめて依頼されている（call が2つ並んでから return が2つ返る）
- 1つの質問での LLM 呼び出し回数（`requests`）：
  - 「LoRAとQLoRAの違いは？」：`requests=2, tool_calls=2`（1回目でツールを2つ依頼 → 結果を見て2回目で回答）。入力 1648 / 出力 190 トークン
- 追加したツールと、docstring に書いた説明：
  - `make_quiz(lecture: int) -> str`：用語集から指定した回の用語を1つランダムに選び、`{"lecture", "question": "「X」とはどういう意味ですか？", "answer": 定義}` を JSON で返す。用語がない回（0 や 99）には、用語がある回の一覧を返す
  - docstring：「指定した回（1始まりの整数）の用語から1つを選び、確認問題とその答えを返す。『第2回の確認問題を出して』『第3回の復習クイズがほしい』のように、回を指定して確認問題・復習問題を求められたときに使う。答えは用語集の定義なので、問題だけを先に出し、答えは利用者が考えてから示すとよい。」
  - `INSTRUCTIONS` にも「確認問題・復習問題を求められたら make_quiz を使う。」を追加した
  - `make_quiz` を作る前に「第2回の内容から確認問題を1問出して」と聞いたときは、`get_lecture_summary({'lecture': 2})` で第2回の要点を読み、そこからモデルが自分で3択問題（ファインチューニングが向く場面）を作っていた（`requests=2, tool_calls=1`）。ツールがなくても問題は出せるが、問題の中身はモデル任せになる
  - `make_quiz` 追加後の `--trace`：（Codespaces で実行して記入）
  - `uv run pytest -q`：24 passed（`make_quiz` のテスト2件を追加）

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
  - `uv run pytest -q`：22 passed（追加した 11 件を含む。演習の `make_quiz` を足したあとは 24 passed）
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
  - 実際の API（Gemini）での実行結果（`y` と答えた場合）
    ```
    [承認待ち] save_learning_log を次の引数で実行しようとしています:
      content: - 事前学習済みの重みを固定し、低ランク行列の積（更新分）のみを学習するPEFT手法であること。
        - 学習パラメータやファイルサイズを大幅に削減できること。
      lecture: 2
      title: LoRAについての学習記録
    実行してよいですか？ [y/N] y
    「LoRA」について学んだ内容を、学習ログとして保存しました。

    （関係する回：第2回）

    --- trace ---
    [tool call]   search_glossary({'query': 'LoRA'})
    [tool return] search_glossary -> [{"term": "LoRA", "lecture": 2, ...
    [tool call]   save_learning_log({'content': '- 事前学習済みの重みを固定し、…', 'lecture': 2, 'title': 'LoRAについての学習記録'})
    [tool return] save_learning_log -> 学習の記録を保存しました: learning_log/20261109-054327_LoRAについての学習記録.md…
    [usage] RunUsage(... input_tokens=2386, output_tokens=119, requests=3, tool_calls=2)
    ```
    - モデルはまず `search_glossary` で LoRA の定義を調べ、その内容を要約して `save_learning_log` を呼ぼうとした。ここで実行が止まり、保存する title・content・lecture が表示されて確認を求められた
    - `y` と答えると `learning_log/20261109-054327_LoRAについての学習記録.md` が作られ、中身は見出し・日時・「関係する回: 第2回」・本文の箇条書きだった
    - `requests=3`：①検索を依頼 → ②検索結果を見て保存を依頼（ここで止まる）→ 承認後 ③保存の結果を見て回答。止まる前と後の合計が `[usage]` に出ている
- 気づき・疑問：
  - 承認が必要なツールは「呼ばれたら実行」ではなく、実行がいったん止まり、承認の結果を渡して続きを実行する、という2段階になる。そのため1つの質問で `run_sync` が2回、LLM の呼び出しも最低2回になる。実際の API では、保存前に用語集を検索したこともあり `requests=3` だった
  - 「保存して」としか頼んでいないのに、モデルが用語集で調べた定義を要約して本文を作っていた。何が保存されるかはモデル次第なので、確認画面で中身を見せる意味がある
  - 拒否したときもモデルには「拒否された」という結果が返るので、モデルはそれを見て「保存していない」と伝えられる。黙って止めるより会話として自然
  - 確認の画面で引数（保存する中身）を見せることが大事だと感じた。名前だけ見せて「実行してよいか」と聞いても、何が保存されるか分からず判断できない
  - 疑問：`requires_approval=True` は毎回確認を求めるが、「同じ会話の中で一度承認したら次からは聞かない」のような条件付きの承認はどう書くのがよいか（`ApprovalRequired` を条件付きで投げる方法がありそう）
