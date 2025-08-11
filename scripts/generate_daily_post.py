#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import io
import json
import time
import random
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import requests
import yaml
from slugify import slugify
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from pytrends.request import TrendReq
except Exception:
    TrendReq = None  # pytrends might fail to import on first run; handled below

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "_posts"
IMAGES_DIR = ROOT / "assets" / "images"
AUTOMATION_DIR = ROOT / ".automation"
USED_KEYWORDS_FILE = AUTOMATION_DIR / "used_keywords.json"
CONFIG_FILE = ROOT / "_config.yml"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
HUGGINGFACE_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN", "")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs() -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    AUTOMATION_DIR.mkdir(parents=True, exist_ok=True)


def load_used_keywords() -> List[str]:
    if USED_KEYWORDS_FILE.exists():
        try:
            return json.loads(USED_KEYWORDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_used_keywords(keywords: List[str]) -> None:
    USED_KEYWORDS_FILE.write_text(json.dumps(sorted(set(keywords))), encoding="utf-8")


def normalize_keyword(kw: str) -> str:
    kw = re.sub(r"\s+", " ", kw.strip())
    return kw


def get_pytrends_keywords(niche: str, country: str) -> List[str]:
    if TrendReq is None:
        return []
    try:
        # tz 0 UTC to be consistent with Actions runner
        pytrends = TrendReq(hl="en-US", tz=0, retries=2, backoff_factor=0.2)
        # Suggestions around the niche
        suggestions = pytrends.suggestions(keyword=niche) or []
        suggestion_titles = [s.get("title", "") for s in suggestions]
        # Daily trending searches for region (best-effort)
        pn = country.lower().replace(" ", "_")
        try:
            trending_df = pytrends.trending_searches(pn=pn)
            trending_list = trending_df[0].tolist() if not trending_df.empty else []
        except Exception:
            trending_list = []
        # Filter trending by niche keyword presence (loose)
        filtered_trending = [t for t in trending_list if niche.lower().split()[0] in t.lower()]
        keywords = suggestion_titles + filtered_trending
        keywords = [normalize_keyword(k) for k in keywords if k and isinstance(k, str)]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for k in keywords:
            if k.lower() not in seen:
                unique.append(k)
                seen.add(k.lower())
        return unique
    except Exception:
        return []


def read_backup_keywords(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = [normalize_keyword(l) for l in path.read_text(encoding="utf-8").splitlines()]
    return [l for l in lines if l]


def choose_new_keyword(candidates: List[str], used: List[str]) -> Optional[str]:
    used_lower = {u.lower() for u in used}
    for kw in candidates:
        if kw.lower() not in used_lower:
            return kw
    return None


def build_title(keyword: str, site_title: str) -> str:
    base = keyword.strip()
    base = base[0].upper() + base[1:] if base else keyword
    suffixes = [
        "A Practical Guide",
        "What You Need to Know",
        "Tips, Examples, and Use Cases",
        "Beginner-Friendly Overview",
        "Comprehensive Walkthrough",
    ]
    suffix = random.choice(suffixes)
    return f"{base}: {suffix}"


def build_description(keyword: str, niche: str) -> str:
    text = (
        f"Learn about {keyword} in the {niche} space with practical tips, pros and cons, and examples. "
        f"Understand how it works and when to use it in real projects."
    )
    return text[:158]


def generate_with_openai(prompt: str, max_tokens: int = 1000) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    try:
        # Use the Chat Completions API via HTTP to avoid extra deps
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an expert SEO copywriter. Write clear, original, factually correct content."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    return None


def generate_with_hf(prompt: str, model: str = "google/flan-t5-large") -> Optional[str]:
    if not HUGGINGFACE_API_TOKEN:
        return None
    try:
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
        payload = {"inputs": prompt}
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            # Some models return a dict with a 'generated_text' directly
            if isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"].strip()
    except Exception:
        return None
    return None


def generate_with_template(keyword: str, niche: str, min_words: int, max_words: int) -> str:
    # Heuristic, structured article with headings for SEO
    sections = []
    sections.append(f"## What is {keyword}?\n{keyword} is a concept, tool, or technique often discussed in the {niche} niche. "
                    f"This overview explains what it means, why it matters, and how to apply it in the real world.")

    sections.append(f"## Key takeaways\n- {keyword} helps practitioners improve outcomes in {niche}.\n- Start small, validate results, and iterate.\n- Combine qualitative insights with data-driven decisions.")

    sections.append(f"## How {keyword} works\nIn practice, {keyword} involves a few stages: discovery, planning, execution, and continuous evaluation. "
                    f"Teams align on goals, collect relevant inputs, and measure the impact to refine the approach.")

    sections.append(f"## Practical steps\n1. Define your objective for using {keyword}.\n2. List constraints and resources.\n3. Pilot a small, low-risk experiment.\n4. Document results and lessons.\n5. Expand the scope with guardrails.")

    sections.append(f"## Benefits\n- Faster experimentation and learning cycles\n- Clearer decision-making in {niche}\n- Better alignment across stakeholders")

    sections.append(f"## Limitations\n- Results depend on the quality of inputs and context\n- May require additional tooling or skills\n- Not a one-size-fits-all solution")

    sections.append(f"## Common mistakes\n- Skipping clear goals before adopting {keyword}\n- Over-optimizing without baseline metrics\n- Ignoring qualitative feedback from users")

    sections.append(f"## Examples and use cases\nConsider small pilots such as a weekly workflow using {keyword} to automate a tedious task, or a month-long evaluation to assess real-world value in your team.")

    sections.append(f"## FAQs\n### Is {keyword} suitable for beginners?\nYes. Start with simple use cases and clear success criteria.\n\n### How long does it take to see results?\nOften within weeks if you measure leading indicators.\n\n### What skills are helpful?\nBasic research, experimentation, and documentation skills go a long way.")

    sections.append(f"## Conclusion\n{keyword} can create real value when implemented thoughtfully. Focus on goals, measure impact, and iterate.")

    body = "\n\n".join(sections)

    # Expand to target word count by lightly paraphrasing
    target = random.randint(min_words, max_words)
    while len(body.split()) < target:
        body += "\n\n" + random.choice([
            f"Remember that success with {keyword} comes from deliberate practice and consistent review.",
            f"In the {niche} landscape, {keyword} is most effective when paired with sound fundamentals.",
            f"Document your assumptions and outcomes to learn faster with {keyword}.",
        ])
    return body


def build_prompt(keyword: str, niche: str, min_words: int, max_words: int) -> str:
    return textwrap.dedent(f"""
    Write an original, SEO-optimized article in English about: "{keyword}" in the "{niche}" niche.
    Requirements:
    - Word count between {min_words} and {max_words}
    - Clear H2/H3 structure: Introduction, What is it, How it works, Practical steps, Benefits, Limitations, Examples, FAQs, Conclusion
    - Use concise paragraphs and bullet lists where helpful
    - Avoid fluff, use actionable language, no plagiarism
    - Include alt text suggestions inline as (Alt: ...)
    """)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=False)
def fetch_unsplash_image(keyword: str) -> Optional[bytes]:
    if not UNSPLASH_ACCESS_KEY:
        return None
    params = {
        "query": keyword,
        "orientation": "landscape",
        "content_filter": "high",
        "per_page": 1,
    }
    headers = {"Accept-Version": "v1", "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    resp = requests.get("https://api.unsplash.com/search/photos", params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None
    url = results[0]["urls"]["regular"]
    img = requests.get(url, timeout=60)
    img.raise_for_status()
    return img.content


def get_image(keyword: str, dest_path: Path) -> str:
    # Try API download
    try:
        img_bytes = fetch_unsplash_image(keyword)
        if img_bytes:
            dest_path.write_bytes(img_bytes)
            return str(dest_path.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        pass
    # Fallback to Unsplash source hotlink
    from urllib.parse import quote
    return f"https://source.unsplash.com/1024x640/?{quote(keyword)}"


def build_internal_links(max_links: int, baseurl: str) -> str:
    posts = sorted(POSTS_DIR.glob("*.md"))
    if not posts:
        return ""
    # Exclude today's soon-to-be post by using last few existing
    recent = posts[-(max_links+2):]
    lines = ["## You might also like"]
    count = 0
    for p in reversed(recent):
        # Parse front matter title quickly
        try:
            content = p.read_text(encoding="utf-8")
            m = re.search(r"^title:\s*\"?(.*?)\"?\s*$", content, re.M)
            title = m.group(1).strip() if m else p.stem
            slug = p.name[11:-3]  # strip date and .md
            # Build a plain URL path and optionally prefix baseurl
            url_path = f"/{slug}/"
            if baseurl:
                base = "/" + baseurl.strip("/")
                url_path = f"{base}{url_path}"
            lines.append(f"- [{title}]({url_path})")
            count += 1
            if count >= max_links:
                break
        except Exception:
            continue
    return "\n".join(lines) if count else ""


def write_post(front_matter: Dict[str, object], body_md: str, date: datetime, slug: str) -> Path:
    filename = f"{date.strftime('%Y-%m-%d')}-{slug}.md"
    out_path = POSTS_DIR / filename
    fm_yaml = yaml.safe_dump(front_matter, allow_unicode=True, sort_keys=False)
    out_path.write_text("---\n" + fm_yaml + "---\n\n" + body_md + "\n", encoding="utf-8")
    return out_path


def main() -> None:
    ensure_dirs()
    cfg = load_config()
    site_title = cfg.get("title", "Niche Daily")
    automation = cfg.get("automation", {})
    niche = automation.get("niche", "AI tools")
    country = automation.get("country", "united_states")
    language = automation.get("language", "en")
    min_words = int(automation.get("min_word_count", 900))
    max_words = int(automation.get("max_word_count", 1500))
    backend = automation.get("generation_backend", "template")
    internal_links_max = int(automation.get("internal_links_max", 3))
    backup_file = automation.get("backup_keywords_file", "scripts/backup_keywords.txt")

    used = load_used_keywords()
    candidates = []

    # Gather candidates
    candidates.extend(get_pytrends_keywords(niche, country))
    candidates.extend(read_backup_keywords(ROOT / backup_file))
    # Deduplicate
    seen = set()
    unique_candidates = []
    for c in candidates:
        lc = c.lower()
        if lc not in seen:
            unique_candidates.append(c)
            seen.add(lc)

    keyword = choose_new_keyword(unique_candidates, used)
    if not keyword:
        print("No new keyword available. Exiting without changes.")
        return

    now = datetime.now(timezone.utc)
    slug = slugify(keyword)
    # If today's file already exists, exit (idempotent)
    todays = POSTS_DIR / f"{now.strftime('%Y-%m-%d')}-{slug}.md"
    if todays.exists():
        print("Today's post already exists. Exiting.")
        return

    title = build_title(keyword, site_title)
    description = build_description(keyword, niche)

    # Generate content
    prompt = build_prompt(keyword, niche, min_words, max_words)
    content_md: Optional[str] = None
    if backend == "openai":
        content_md = generate_with_openai(prompt)
    elif backend == "hf_api":
        content_md = generate_with_hf(prompt)
    if not content_md or len(content_md.split()) < min_words // 2:
        content_md = generate_with_template(keyword, niche, min_words, max_words)

    # Internal links section
    internal_links_md = build_internal_links(internal_links_max, cfg.get("baseurl", "") or "")
    if internal_links_md:
        content_md += "\n\n" + internal_links_md

    # Image handling
    image_filename = IMAGES_DIR / f"{now.strftime('%Y%m%d')}-{slug}.jpg"
    image_url_or_path = get_image(keyword, image_filename)

    # Front matter
    front_matter = {
        "layout": "post",
        "title": json.dumps(title)[1:-1],  # ensure quotes safe
        "description": json.dumps(description)[1:-1],
        "date": now.strftime("%Y-%m-%d %H:%M:%S %z"),
        "tags": [t for t in re.split(r"[\s,/]+", keyword.lower()) if t and len(t) <= 24][:6],
        "image": image_url_or_path,
    }

    out_path = write_post(front_matter, content_md, now, slug)

    # Track used keyword
    used.append(keyword)
    save_used_keywords(used)

    print(f"Generated post: {out_path}")


if __name__ == "__main__":
    main()
