#!/usr/bin/env python3
import datetime as dt
import html
import json
import os
import re
import subprocess
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "daily-content.js"
ARCHIVE_DIR = BASE_DIR / "archive"
AUDIO_DIR = BASE_DIR / "audio"
OPENAI_API_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SOURCES = [
    {
        "name": "ArchDaily",
        "source_class": "archdaily",
        "topic": "Projects and Building Reuse",
        "url": "https://www.archdaily.com",
        "listing_url": "https://www.archdaily.com",
        "article_pattern": re.compile(r"https://www\.archdaily\.com/\d+/[a-z0-9\-]+"),
        "mode": "meta_page",
    },
    {
        "name": "Dezeen",
        "source_class": "dezeen",
        "topic": "Architecture and Interiors",
        "url": "https://www.dezeen.com/architecture/",
        "listing_url": "https://www.dezeen.com/architecture/feed/",
        "article_pattern": re.compile(r"https://www\.dezeen\.com/\d{4}/\d{2}/\d{2}/[a-z0-9\-/]+/"),
        "mode": "rss",
    },
    {
        "name": "Designboom",
        "source_class": "designboom",
        "topic": "Architecture and Urban Experience",
        "url": "https://www.designboom.com/architecture/",
        "listing_url": "https://www.designboom.com/architecture/feed/",
        "article_pattern": re.compile(r"https://www\.designboom\.com/architecture/[a-z0-9\-/]+/"),
        "mode": "rss",
    },
]

ARCHITECTURE_TERMS = {
    "adaptive reuse": {
        "pronunciation": "/əˌdæp.tɪv riːˈjuːs/",
        "meaning": "舊建築再利用。",
    },
    "permeability": {
        "pronunciation": "/ˌpɝː.mi.əˈbɪl.ə.ti/",
        "meaning": "穿透性，指空間是否容易被進入和穿越。",
    },
    "threshold": {
        "pronunciation": "/ˈθreʃ.hoʊld/",
        "meaning": "門檻、過渡地帶。",
    },
    "civic": {
        "pronunciation": "/ˈsɪv.ɪk/",
        "meaning": "與市民、公民生活有關的。",
    },
    "circulation": {
        "pronunciation": "/ˌsɝː.kjəˈleɪ.ʃən/",
        "meaning": "動線，人如何在空間中移動。",
    },
    "atmosphere": {
        "pronunciation": "/ˈæt.mə.sfɪr/",
        "meaning": "空間氛圍。",
    },
    "texture": {
        "pronunciation": "/ˈteks.tʃɚ/",
        "meaning": "材質肌理、表面觸感。",
    },
    "restraint": {
        "pronunciation": "/rɪˈstreɪnt/",
        "meaning": "克制，設計上不過度堆疊。",
    },
    "spectacle": {
        "pronunciation": "/ˈspek.tə.kəl/",
        "meaning": "視覺奇觀，常帶有批判意味。",
    },
    "grounded": {
        "pronunciation": "/ˈɡraʊn.dɪd/",
        "meaning": "沉穩、穩定、有落地感的。",
    },
    "massing": {
        "pronunciation": "/ˈmæs.ɪŋ/",
        "meaning": "量體配置。",
    },
    "setback": {
        "pronunciation": "/ˈset.bæk/",
        "meaning": "建築退縮。",
    },
    "podium": {
        "pronunciation": "/ˈpoʊ.di.əm/",
        "meaning": "塔樓下方的基座量體。",
    },
    "pedestrian": {
        "pronunciation": "/pəˈdes.tri.ən/",
        "meaning": "步行者，行人。",
    },
    "approachable": {
        "pronunciation": "/əˈproʊ.tʃə.bəl/",
        "meaning": "容易親近的、不讓人退縮的。",
    },
    "materiality": {
        "pronunciation": "/məˌtɪr.iˈæl.ə.t̬i/",
        "meaning": "材料性，材料被感知與表達的方式。",
    },
    "facade": {
        "pronunciation": "/fəˈsɑːd/",
        "meaning": "建築立面。",
    },
    "context": {
        "pronunciation": "/ˈkɑːn.tekst/",
        "meaning": "脈絡、周邊環境條件。",
    },
}


def fetch_url(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def post_json(url: str, payload: dict, api_key: str) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def post_json_response(url: str, payload: dict, api_key: str) -> dict:
    return json.loads(post_json(url, payload, api_key).decode("utf-8"))


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_meta(html_text: str, property_name: str) -> str:
    patterns = [
        rf'<meta[^>]+property="{re.escape(property_name)}"[^>]+content="([^"]+)"',
        rf'<meta[^>]+content="([^"]+)"[^>]+property="{re.escape(property_name)}"',
        rf'<meta[^>]+name="{re.escape(property_name)}"[^>]+content="([^"]+)"',
        rf'<meta[^>]+content="([^"]+)"[^>]+name="{re.escape(property_name)}"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_title(html_text: str) -> str:
    title = extract_meta(html_text, "og:title") or extract_meta(html_text, "twitter:title")
    if title:
        return title

    match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    if match:
        return clean_text(match.group(1))
    return ""


def split_paragraphs(text: str, max_items: int = 4) -> list:
    chunks = []
    for raw in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text):
        sentence = raw.strip()
        if len(sentence) > 80:
            chunks.append(sentence)
        if len(chunks) == max_items:
            break
    if not chunks and text:
        chunks = textwrap.wrap(text, width=260)
    return chunks[:max_items]


def clean_feed_html(value: str) -> str:
    value = clean_text(value)
    value = re.sub(r"\bThe post .*?appeared first on .*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bContinue reading\b.*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bRead more\b.*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_title(title: str, source_name: str) -> str:
    title = title.replace("| ArchDaily", "").strip()
    title = title.replace("| Dezeen", "").strip()
    title = title.replace("| designboom | architecture & design magazine", "").strip()
    title = title.replace("| designboom", "").strip()
    return clean_text(title)


def first_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 40:
            return sentence
    return text.strip()


def make_learning_paragraphs(title: str, description: str, source_name: str, topic: str) -> list:
    description = clean_feed_html(description)
    if not description:
        return []

    first = first_sentence(description)
    second = (
        f"This {source_name} piece is useful for learners because it highlights {topic.lower()} through a concrete project or case."
    )
    third = (
        "When you read it, pay attention to how the article connects design decisions to daily use, public experience, materials, or urban context."
    )
    return [first, second, third]


def make_chinese_learning_paragraphs(title: str, description: str, source_name: str, topic: str) -> list:
    description = clean_feed_html(description)
    if not description:
        return []

    first = f"這篇來自 {source_name} 的文章重點是: {first_sentence(description)}"
    second = f"把它當成學習材料時，可以把焦點放在 {topic} 相關的設計概念，而不是只看圖片好不好看。"
    third = "閱讀時可以特別注意文章怎麼把空間決策、使用者感受、材料表現或城市關係連在一起。"
    return [first, second, third]


def extract_article_links(source: dict, listing_html: str) -> list:
    links = source["article_pattern"].findall(listing_html)
    deduped = []
    seen = set()
    for link in links:
        link = link.rstrip('"\'')
        if (
            link not in seen
            and "/tag/" not in link
            and "/page/" not in link
            and not link.endswith("/feed/")
            and link != source["url"]
        ):
            seen.add(link)
            deduped.append(link)
    return deduped[:5]


def extract_article_body(article_html: str) -> str:
    article_html = re.sub(r"<script[\s\S]*?</script>", " ", article_html, flags=re.IGNORECASE)
    article_html = re.sub(r"<style[\s\S]*?</style>", " ", article_html, flags=re.IGNORECASE)

    json_ld_match = re.search(r'"articleBody"\s*:\s*"(.+?)"', article_html, re.DOTALL)
    if json_ld_match:
        return clean_text(json_ld_match.group(1))

    if "Text description provided by the architects." in article_html:
        article_html = article_html.split("Text description provided by the architects.", 1)[1]
        for marker in ["Project gallery", "#Tags", "Published on"]:
            if marker in article_html:
                article_html = article_html.split(marker, 1)[0]

    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", article_html, re.DOTALL | re.IGNORECASE)
    cleaned = []
    for paragraph in paragraphs:
        text = clean_text(paragraph)
        if len(text) < 80:
            continue
        lower = text.lower()
        if "cookie" in lower or "subscribe" in lower or "whatsapp" in lower:
            continue
        cleaned.append(text)
    return " ".join(cleaned[:12])


def parse_feed_items(source: dict, feed_xml: str) -> list:
    root = ET.fromstring(feed_xml.lstrip())
    items = []
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    for item in root.findall("./channel/item"):
        title = clean_text(item.findtext("title", default=""))
        link = clean_text(item.findtext("link", default=""))
        description = item.findtext("description", default="")
        content_encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", default="")
        content_text = clean_feed_html(content_encoded)
        description_text = clean_feed_html(description)
        text_basis = content_text or description_text
        if not title or not link or not text_basis:
            continue
        if not source["article_pattern"].match(link):
            continue

        english = make_learning_paragraphs(title, text_basis, source["name"], source["topic"])
        chinese = make_chinese_learning_paragraphs(title, text_basis, source["name"], source["topic"])
        items.append(
            {
                "source": source["name"],
                "sourceClass": source["source_class"],
                "topic": source["topic"],
                "title": normalize_title(title, source["name"]),
                "url": link,
                "sourceExcerpt": text_basis,
                "english": english,
                "chinese": chinese,
                "vocabulary": pick_vocabulary(title, text_basis),
                "audio": {},
            }
        )
    return items


def pick_vocabulary(title: str, body: str) -> list:
    haystack = f"{title.lower()} {body.lower()}"
    chosen = []
    for term, meta in ARCHITECTURE_TERMS.items():
        if term in haystack:
            chosen.append(
                {
                    "term": term,
                    "pronunciation": meta["pronunciation"],
                    "meaning": meta["meaning"],
                    "usage": f"Usage: {term.capitalize()} appears here as a useful concept for describing the project.",
                }
            )
        if len(chosen) == 5:
            return chosen

    for term, meta in ARCHITECTURE_TERMS.items():
        if len(chosen) == 5:
            break
        if not any(item["term"] == term for item in chosen):
            chosen.append(
                {
                    "term": term,
                    "pronunciation": meta["pronunciation"],
                    "meaning": meta["meaning"],
                    "usage": f"Usage: You can use {term} when describing a project's spatial quality.",
                }
            )
    return chosen


def build_prompts(title: str) -> list:
    return [
        {
            "title": f"如果這個案子蓋在你家附近，你會想常常經過它嗎？",
            "description": f"試著從「{title}」帶給人的第一印象去想，它是親切、壓迫，還是有點距離感？",
        },
        {
            "title": "如果你要帶朋友去看這個案子，你會先介紹哪一個地方？",
            "description": "這題能幫你找到自己最在意的是入口、材料、光線，還是空間怎麼被使用。",
        },
        {
            "title": "這個設計是真的讓生活更方便，還是只是看起來很厲害？",
            "description": "你可以想想一般人每天走過、停留、使用時，會不會真的感受到它的好。",
        },
    ]


def heuristic_chinese_translation(english_paragraphs: list) -> list:
    return [
        "這段內容是系統自動抓到的英文原文。若要每天自動產生高品質中文翻譯，建議在執行環境補上一個翻譯或 LLM 服務的 API 金鑰。"
        if index == 0
        else f"原文段落 {index + 1}: {paragraph}"
        for index, paragraph in enumerate(english_paragraphs)
    ]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-") or "article"


def split_for_tts(text: str, max_chars: int = 3800) -> list:
    sentences = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [text]


def extract_response_text(response_json: dict) -> str:
    if response_json.get("output_text"):
        return response_json["output_text"]

    fragments = []
    for output in response_json.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if text:
                fragments.append(text)
    return "\n".join(fragments)


def openai_json_schema_request(system_prompt: str, user_prompt: str, schema_name: str, schema: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    response_json = post_json_response(
        OPENAI_RESPONSES_URL,
        {
            "model": os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        },
        api_key,
    )
    output_text = extract_response_text(response_json)
    return json.loads(output_text)


def generate_api_audio_variants(article: dict, article_slug: str, payload_date: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    target_dir = AUDIO_DIR / payload_date
    target_dir.mkdir(parents=True, exist_ok=True)
    text = " ".join(article["english"]).strip()
    if not text:
        return {}

    voices = [
        ("marin", "Marin"),
        ("alloy", "Alloy"),
    ]
    audio_map = {"english_models": {}}
    instructions = (
        "Read this architecture learning article in a warm, natural, editorial voice. "
        "Keep pacing calm and clear for English learners."
    )

    for voice_key, _label in voices:
        paths = []
        for index, chunk in enumerate(split_for_tts(text)):
            file_path = target_dir / f"{article_slug}-english-{voice_key}-{index + 1}.mp3"
            if not file_path.exists():
                audio_bytes = post_json(
                    OPENAI_API_URL,
                    {
                        "model": os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                        "voice": voice_key,
                        "input": chunk,
                        "instructions": instructions,
                        "response_format": "mp3",
                    },
                    api_key,
                )
                file_path.write_bytes(audio_bytes)
            paths.append(f"./audio/{payload_date}/{file_path.name}")
        audio_map["english_models"][voice_key] = paths

    return audio_map


def parse_article(source: dict, article_url: str) -> dict:
    article_html = fetch_url(article_url)
    title = extract_title(article_html)
    description = extract_meta(article_html, "description") or extract_meta(article_html, "og:description")
    body = extract_article_body(article_html)
    english_paragraphs = split_paragraphs(body or description, max_items=4)
    if not english_paragraphs and description:
        english_paragraphs = [description]

    return {
        "source": source["name"],
        "sourceClass": source["source_class"],
        "topic": source["topic"],
        "title": normalize_title(title or "Untitled article", source["name"]),
        "url": article_url,
        "english": english_paragraphs,
        "chinese": heuristic_chinese_translation(english_paragraphs),
        "vocabulary": pick_vocabulary(title or "", body or description or ""),
    }


ARTICLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topic": {"type": "string"},
        "english": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "chinese": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "vocabulary": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "term": {"type": "string"},
                    "pronunciation": {"type": "string"},
                    "meaning": {"type": "string"},
                    "usage": {"type": "string"},
                },
                "required": ["term", "pronunciation", "meaning", "usage"],
            },
        },
    },
    "required": ["topic", "english", "chinese", "vocabulary"],
}


PROMPTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "prompts": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        }
    },
    "required": ["prompts"],
}


def enrich_article_with_ai(article: dict) -> dict:
    source_excerpt = article.get("sourceExcerpt") or "\n".join(article.get("english", [])[:3])
    system_prompt = (
        "You are creating a bilingual architecture learning card. "
        "Return JSON only. Write concise, clean English and Traditional Chinese. "
        "Do not mention being an AI or summarize website UI. "
        "English should be article-length learning text in 3 paragraphs, each 1-3 sentences. "
        "Chinese should be faithful, natural Traditional Chinese translations of those 3 paragraphs. "
        "Vocabulary must be practical for architecture reading."
    )
    user_prompt = (
        f"Source: {article['source']}\n"
        f"Title: {article['title']}\n"
        f"URL: {article['url']}\n"
        f"Raw source excerpt:\n{source_excerpt}\n\n"
        "Create:\n"
        "1. a short topic label\n"
        "2. 3 English learning paragraphs\n"
        "3. 3 matching Traditional Chinese paragraphs\n"
        "4. 5 vocabulary items with IPA and usage\n"
    )
    enriched = openai_json_schema_request(system_prompt, user_prompt, "article_lesson", ARTICLE_SCHEMA)
    article["topic"] = enriched["topic"]
    article["english"] = enriched["english"]
    article["chinese"] = enriched["chinese"]
    article["vocabulary"] = enriched["vocabulary"]
    return article


def generate_daily_prompts(articles: list) -> list:
    system_prompt = (
        "You are generating simple, everyday critical thinking prompts for architecture learners. "
        "Return JSON only. Prompts should be easy to answer, practical, and not academic."
    )
    article_lines = "\n".join([f"- {article['title']}: {article['topic']}" for article in articles])
    user_prompt = (
        "Based on these article themes, create 3 short prompts in Traditional Chinese.\n"
        f"{article_lines}\n"
        "Each prompt needs a title and one-sentence description."
    )
    result = openai_json_schema_request(system_prompt, user_prompt, "daily_prompts", PROMPTS_SCHEMA)
    return result["prompts"]


def parse_meta_page(source: dict) -> dict:
    listing_html = fetch_url(source["listing_url"])
    article_links = extract_article_links(source, listing_html)
    if not article_links:
        raise RuntimeError("No article links found")

    article_url = article_links[0]
    article_html = fetch_url(article_url)
    title = normalize_title(extract_title(article_html) or "Untitled article", source["name"])
    description = (
        extract_meta(article_html, "description")
        or extract_meta(article_html, "og:description")
        or extract_meta(article_html, "twitter:description")
    )
    description = clean_feed_html(description)
    body = clean_feed_html(extract_article_body(article_html))
    source_excerpt = body or description
    english = make_learning_paragraphs(title, source_excerpt, source["name"], source["topic"])
    chinese = make_chinese_learning_paragraphs(title, source_excerpt, source["name"], source["topic"])
    return {
        "source": source["name"],
        "sourceClass": source["source_class"],
        "topic": source["topic"],
        "title": title,
        "url": article_url,
        "sourceExcerpt": source_excerpt,
        "english": english,
        "chinese": chinese,
        "vocabulary": pick_vocabulary(title, source_excerpt),
        "audio": {},
    }


def build_payload() -> dict:
    articles = []
    failures = []

    for source in SOURCES:
        try:
            if source["mode"] == "rss":
                feed_xml = fetch_url(source["listing_url"])
                feed_items = parse_feed_items(source, feed_xml)
                if not feed_items:
                    raise RuntimeError("No clean feed items found")
                articles.append(feed_items[0])
            else:
                articles.append(parse_meta_page(source))
        except Exception as error:  # noqa: BLE001
            failures.append(f"{source['name']}: {error}")

    hero_note = "頁面已支援整篇英文與中文朗讀、單字點讀，以及由每日資料檔自動渲染。"
    if failures:
        hero_note += " 抓文失敗來源: " + " | ".join(failures)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the deployed daily pipeline")

    enriched_articles = []
    for article in articles:
        try:
            enriched_articles.append(enrich_article_with_ai(article))
        except Exception as error:  # noqa: BLE001
            failures.append(f"{article['source']} AI: {error}")
            enriched_articles.append(article)

    payload = {
        "date": dt.date.today().isoformat(),
        "settings": {
            "defaultEnglishVoice": "marin",
            "englishVoiceOptions": [
                {"key": "marin", "label": "Marin (Default)"},
                {"key": "alloy", "label": "Alloy"},
            ],
        },
        "hero": {
            "title": "完整英中內容，不只是一小段摘錄",
            "summary": "這個頁面會每天自動抓取 ArchDaily、Dezeen、Designboom 的新內容，並透過 API 生成雙語學習內容、專業字彙和英文語音。",
            "note": hero_note,
            "points": [
                "每篇都有 API 生成的完整英文學習內容",
                "三篇都支援兩種 API 英文語音切換",
                "每篇 5 個單字加發音與例句",
            ],
        },
        "sourceNote": "原站文章請保留到原媒體閱讀；這個頁面呈現的是適合學習的整理版內容，方便每日閱讀與語言訓練。",
        "articles": enriched_articles,
        "prompts": generate_daily_prompts(enriched_articles),
    }

    tts_failures = []
    for article in payload["articles"]:
        try:
            article_slug = slugify(article["title"])
            article["audio"] = generate_api_audio_variants(article, article_slug, payload["date"])
        except Exception as error:  # noqa: BLE001
            tts_failures.append(f"{article['source']}: {error}")
            article["audio"] = {}
        article.pop("sourceExcerpt", None)

    if failures:
        payload["hero"]["note"] += " 內容生成失敗來源: " + " | ".join(failures)
    if tts_failures:
        payload["hero"]["note"] += " 語音生成失敗來源: " + " | ".join(tts_failures)
    else:
        payload["hero"]["note"] += " 三篇英文都已生成兩種 API 語音，預設使用 Marin。"
    return payload


def write_payload(payload: dict) -> None:
    OUTPUT_PATH.write_text(
        "window.DAILY_CONTENT = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    ARCHIVE_DIR.mkdir(exist_ok=True)
    archive_path = ARCHIVE_DIR / f"{payload['date']}.json"
    archive_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = ARCHIVE_DIR / "index.json"
    existing = []
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    if payload["date"] not in existing:
        existing.append(payload["date"])
    existing = sorted(set(existing), reverse=True)
    index_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    payload = build_payload()
    write_payload(payload)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
