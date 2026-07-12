#!/usr/bin/env python3
"""毎日のSNS投稿(ベトナム語)を生成するスクリプト。

themes.yaml の曜日設定に従い、Claude API で以下を1セット生成して
content/queue/YYYY-MM-DD.md に保存する:
  - 文字投稿(Facebook用、ベトナム語+日本語訳)
  - 30秒ショート動画の台本(秒単位、ベトナム語+日本語訳)
  - TikTok / Instagram / Facebook それぞれのキャプションとハッシュタグ

生成物は「下書き」であり、人間がレビューしてから投稿する前提。
"""

import os
import re
import sys
import datetime
from pathlib import Path

import yaml
import anthropic

ROOT = Path(__file__).resolve().parent
QUEUE_DIR = ROOT.parent.parent / "content" / "queue"
MODEL = os.environ.get("CONTENT_MODEL", "claude-opus-4-8")

SYSTEM_PROMPT = """\
あなたは「Gieo Hạt」というベトナム向けSNSチャネルの編集者です。
発起人は Park Teo(韓国人投資家・ベトナム在住3年以上)と Aki(日本人YouTuber・
約10年前にベトナム在住、孤児院への食料・学用品支援を継続)。2人は私財で
学校・井戸・孤児院支援を行い、お金の知識と生き方の考え方を無料で発信しています。

## 声のトーン
温かく、誠実で、押し付けない。「一緒に考えよう」と誘う姿勢。
ベトナムへの愛と敬意が土台。読者を見下さない。説教しない。

## 絶対的な禁止事項(1つでも違反したら生成失敗)
- 特定の投資商品・トレード・コピートレード・副業案件・儲け話への言及や示唆
- 「確実に儲かる」「必ず増える」「リスクなし」等の断定表現(例え話でも不可)
- 収益額の提示、贅沢な生活の誇示
- 出典を示せない統計・数字(数字を使うなら「〜と言われています」ではなく出典名を書く。
  出典が書けないなら数字を使わずに書く)
- 有料商品・講座・グループへの誘導(すべてのコンテンツは無料であることが信条)
- 政治・宗教団体・特定企業への批判

## 推奨事項
- 詐欺対策コンテンツでは「確実に儲かる話は全て疑え」を一貫したメッセージにする
- 金融教育は「貯める・守る・使う」の範囲のみ。「増やす(投資実践)」には踏み込まない
- ベトナムの読者の日常(給料日、家族への仕送り、SNS、市場、カフェ)に引き付ける
- 各投稿の最後は、宣伝ではなく「考えさせる一言」で締める

## 出力形式
必ず次のMarkdown構造で出力してください。ベトナム語本文の直後に日本語訳を置きます。

# {今日のトピックのタイトル(ベトナム語)}

## 1. Facebook文字投稿
### VN
(300〜500語のベトナム語投稿。改行と絵文字を適度に。ハッシュタグは末尾に3〜5個)
### JP訳
(日本語訳)

## 2. ショート動画台本(30秒)
| 秒 | 画面・カット | セリフ/字幕(VN) | 日本語訳 |
|---|---|---|---|
(0-3秒フック / 3-20秒本題 / 20-30秒締め の構成で5〜7行)

## 3. キャプション
### TikTok
(短いVNキャプション+ハッシュタグ5〜7個)
### Instagram Reels
(VNキャプション+ハッシュタグ5〜7個)
### Facebook(動画転載用)
(VNキャプション2〜3文+ハッシュタグ3個)

## 4. 制作メモ
(撮影・素材・図解の指示を日本語で2〜3行)
"""

TEMPLATE_MODE_INSTRUCTION = """\
今日は「活動レポート」の日です。実際の写真と事実は人間が用意するため、
完全な投稿ではなく【】プレースホルダー付きの「キャプション雛形」を生成してください。
場所・日付・活動内容・人数などはすべて【場所】【日付】のようなプレースホルダーにし、
埋め方の注意(写真掲載同意の確認、数字は領収書等で裏付けられるもののみ)を
制作メモに含めてください。出力形式は通常と同じMarkdown構造を使います。
"""


def load_config() -> dict:
    with open(ROOT / "themes.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def recent_topics(limit: int = 14) -> list[str]:
    """直近の生成ファイルからタイトル行を集め、トピックの重複を避ける。"""
    if not QUEUE_DIR.exists():
        return []
    topics = []
    for path in sorted(QUEUE_DIR.glob("*.md"), reverse=True)[:limit]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                topics.append(line[2:].strip())
                break
    return topics


def build_user_prompt(cfg: dict, today: datetime.date) -> str:
    day = cfg["weekdays"][today.weekday()]
    brand = cfg["brand"]
    parts = [
        f"今日は {today.isoformat()}({'月火水木金土日'[today.weekday()]}曜日)です。",
        f"今日のテーマ: {day['theme']}",
        f"テーマの説明: {day['description']}",
        f"主な配信先: {', '.join(day['channels'])}",
        f"ブランドの声: {brand['voice']}",
    ]
    if day.get("mode") == "template":
        parts.append(TEMPLATE_MODE_INSTRUCTION)
    if topics := recent_topics():
        parts.append(
            "直近に生成したトピック(重複を避けること):\n- " + "\n- ".join(topics)
        )
    parts.append(
        "このテーマの中から、上記と重複しない具体的なトピックを1つ選び、"
        "指定のMarkdown形式で今日の投稿セットを生成してください。"
    )
    return "\n\n".join(parts)


FORBIDDEN_PATTERNS = [
    r"copy\s*trad", r"chắc chắn (có lãi|thắng|sinh lời)", r"cam kết lợi nhuận",
    r"không rủi ro", r"forex", r"コピートレード", r"必ず儲か", r"確実に儲か",
]


def compliance_check(text: str) -> list[str]:
    """禁止表現の機械チェック(最終判断は人間レビュー)。"""
    return [p for p in FORBIDDEN_PATTERNS if re.search(p, text, re.IGNORECASE)]


def main() -> int:
    today = datetime.date.today()
    out_path = QUEUE_DIR / f"{today.isoformat()}.md"
    if out_path.exists():
        print(f"skip: {out_path} は既に存在します")
        return 0

    cfg = load_config()
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から読む

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(cfg, today)}],
    )

    if response.stop_reason == "refusal":
        print("error: モデルが生成を拒否しました。テーマ設定を確認してください。")
        return 1
    if response.stop_reason == "max_tokens":
        print("warning: 出力が途中で切れた可能性があります。")

    body = "".join(b.text for b in response.content if b.type == "text")

    if hits := compliance_check(body):
        print(f"error: 禁止表現を検出したため保存しません: {hits}")
        return 1

    header = (
        f"<!-- 生成日: {today.isoformat()} / model: {response.model} / "
        f"テーマ: {cfg['weekdays'][today.weekday()]['theme']} -->\n"
        "<!-- ⚠️ これは下書きです。事実確認・同意確認・表現チェックをしてから投稿してください -->\n\n"
    )
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + body, encoding="utf-8")
    print(f"created: {out_path}")
    print(
        f"tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
