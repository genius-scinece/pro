# 投稿自動生成システム(content-engine)

毎日1回、その曜日のテーマに沿ったSNS投稿セット(ベトナム語)を自動生成し、
`content/queue/YYYY-MM-DD.md` に下書きとして保存するシステム。

## 生成されるもの(1日1ファイル)

1. **Facebook文字投稿**(VN 300〜500語+日本語訳)
2. **30秒ショート動画台本**(秒単位のカット割り、VN+日本語訳)
3. **キャプション** — TikTok / Instagram Reels / Facebook それぞれ+ハッシュタグ
4. **制作メモ**(撮影・図解の指示)

月曜(活動レポートの日)だけは、実際の写真・事実で埋めるための
プレースホルダー付き「雛形」を生成します。実績の捏造を防ぐためです。

## 仕組み

```
GitHub Actions (毎日 ベトナム時間 朝4:00)
   └─ generate_posts.py
        ├─ themes.yaml から今日の曜日テーマを読む
        ├─ 直近14日のトピックを読み、重複を回避
        ├─ Claude API で生成(禁止表現ルールをシステムプロンプトに内蔵)
        ├─ 禁止表現の機械チェック(検出したら保存せず失敗)
        └─ content/queue/YYYY-MM-DD.md にコミット
              ↓
   人間がレビュー(事実・同意・表現の確認)
              ↓
   Meta Business Suite / TikTok Web で予約投稿(→ 03-無料投稿運用システム.md)
```

**自動生成 ≠ 自動投稿。** 生成物は必ず下書きです。SNSへの投稿は人間のレビューを
通してから行います(禁止表現チェックは機械+人間の二重)。

## セットアップ(1回だけ)

1. [Claude Console](https://platform.claude.com/) でAPIキーを作成
2. GitHubリポジトリの **Settings → Secrets and variables → Actions** で
   - Secret `ANTHROPIC_API_KEY` にAPIキーを設定
3. 以上。翌日から毎朝 `content/queue/` に下書きが積まれます
   (**Actions タブ → Daily SNS Content Generation → Run workflow** で手動実行も可能)

## コスト

「無料で運用」の唯一の例外がこのAPI利用料です(GitHub Actions自体は無料枠内)。

| モデル | 品質 | 目安(1日1生成) |
|---|---|---|
| `claude-opus-4-8`(デフォルト) | 高。ベトナム語の自然さ・構成力が高い | 約 $0.08/日 ≒ **$2.5/月** |
| `claude-haiku-4-5`(節約) | 実用レベル。要レビュー強化 | 約 $0.02/日 ≒ **$0.6/月** |

節約モードに切り替えるには、リポジトリの **Settings → Secrets and variables →
Actions → Variables** で `CONTENT_MODEL` に `claude-haiku-4-5` を設定します。

## テーマの調整

`themes.yaml` を編集するだけです(コードの変更は不要)。
- 曜日ごとの `description` を書き換えるとその日の生成内容が変わる
- ブランドの声は `brand.voice`
- 禁止事項はシステム全体の信条なので `generate_posts.py` の `SYSTEM_PROMPT` にあります。
  変更する場合は必ず「独立発信の原則」(01-発信戦略全体設計.md の第6章)を守ること

## ローカルでの実行(テスト用)

```bash
pip install anthropic pyyaml
export ANTHROPIC_API_KEY=sk-ant-...
python social-impact-media/content-engine/generate_posts.py
```

## レビューのチェックリスト(投稿前に毎回)

- [ ] 投資・儲け話への言及や匂わせがないか(機械チェックは完全ではない)
- [ ] 数字・統計に出典があるか(なければ削る)
- [ ] ベトナム語として自然か(可能ならネイティブが一読)
- [ ] 写真を使う場合、掲載同意があるか
- [ ] 締めの一言が「考えさせる」ものになっているか(宣伝臭くないか)
