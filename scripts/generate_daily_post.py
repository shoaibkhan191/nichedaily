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
    # AI-focused structured article with comprehensive coverage
    keyword_lower = keyword.lower()
    
    # Determine the AI category based on keywords
    if any(term in keyword_lower for term in ['machine learning', 'ml', 'algorithm']):
        category = 'machine-learning'
        focus = 'algorithms, techniques, and practical applications'
    elif any(term in keyword_lower for term in ['deep learning', 'neural network', 'cnn', 'rnn']):
        category = 'deep-learning'
        focus = 'neural network architectures and training methodologies'
    elif any(term in keyword_lower for term in ['computer vision', 'image', 'detection']):
        category = 'computer-vision'
        focus = 'visual AI technologies and applications'
    elif any(term in keyword_lower for term in ['nlp', 'language', 'text', 'transformer']):
        category = 'ai-applications'
        focus = 'natural language processing and text understanding'
    elif any(term in keyword_lower for term in ['ethics', 'governance', 'responsible']):
        category = 'ai-ethics'
        focus = 'responsible AI development and ethical considerations'
    elif any(term in keyword_lower for term in ['tool', 'framework', 'platform', 'library']):
        category = 'ai-tools'
        focus = 'AI development tools and resources'
    elif any(term in keyword_lower for term in ['data', 'statistics', 'analysis']):
        category = 'data-science'
        focus = 'data preprocessing and analysis for AI'
    else:
        category = 'ai-applications'
        focus = 'artificial intelligence applications and use cases'
    
    # AI-focused article structure
    article = f"""# {keyword}: A Comprehensive Guide

## Introduction

{keyword} represents one of the most significant developments in artificial intelligence today. This comprehensive guide explores the fundamentals, applications, and future directions of this transformative technology that is reshaping industries and creating new possibilities across various domains.

## Understanding {keyword}

{keyword} encompasses a range of techniques and methodologies that enable machines to learn, adapt, and perform tasks that traditionally required human intelligence. From basic implementations to advanced applications, this field continues to evolve rapidly, driven by both theoretical breakthroughs and practical innovations.

## Key Concepts and Fundamentals

### Core Principles
The foundation of {keyword} lies in several fundamental principles that guide its development and application. Understanding these core concepts is essential for anyone working in or studying artificial intelligence.

### Technical Foundations
{keyword} builds upon established mathematical and computational principles, including algorithms, statistical methods, and computational frameworks that enable intelligent behavior in machines.

## Practical Applications

### Industry Use Cases
{keyword} is being applied across numerous industries, from healthcare and finance to transportation and entertainment. These applications demonstrate the versatility and impact of AI technologies in solving real-world problems.

### Real-World Examples
Concrete examples of {keyword} in action help illustrate the practical value and potential of these technologies. From recommendation systems to autonomous vehicles, the applications are diverse and growing.

## Current Trends and Developments

### Recent Breakthroughs
The field of {keyword} is experiencing rapid advancement, with new research and developments emerging regularly. Staying current with these trends is essential for practitioners and researchers alike.

### Emerging Technologies
New approaches and methodologies are constantly being developed, pushing the boundaries of what's possible with {keyword}. These innovations often build upon existing work while opening new avenues for exploration.

## Best Practices and Implementation

### Development Guidelines
Successful implementation of {keyword} requires careful planning and adherence to established best practices. These guidelines help ensure robust, reliable, and ethical AI systems.

### Common Challenges
Implementing {keyword} solutions often involves overcoming various technical and practical challenges. Understanding these obstacles and their solutions is crucial for successful deployment.

## Future Outlook

### Emerging Directions
The future of {keyword} holds tremendous promise, with new applications and capabilities on the horizon. These developments will likely transform industries and create new opportunities for innovation.

### Long-term Impact
The long-term implications of {keyword} extend beyond immediate applications, potentially reshaping how we work, live, and interact with technology. Understanding these broader impacts is important for strategic planning and decision-making.

## Conclusion

{keyword} represents a fundamental shift in how we approach problem-solving and automation. As the technology continues to mature and evolve, its impact will only grow, creating new opportunities and challenges for individuals, organizations, and society as a whole.

The journey into {keyword} is both exciting and challenging, requiring continuous learning and adaptation. Whether you're a researcher, developer, or business professional, staying engaged with this field will be essential for future success and innovation.

---

*This guide provides a comprehensive overview of {keyword}. For more detailed information on specific aspects, explore our related articles and resources on artificial intelligence and machine learning.*"""

    # Ensure word count is within limits
    words = len(article.split())
    if words < min_words:
        # Add more content to meet minimum
        additional_content = f"""

## Additional Resources

### Learning Paths
For those interested in diving deeper into {keyword}, we recommend following a structured learning path that builds foundational knowledge before advancing to more complex topics.

### Community and Support
The {keyword} community is active and supportive, with numerous forums, conferences, and online resources available for learning and collaboration.

### Tools and Platforms
Various tools and platforms support the development and deployment of {keyword} solutions, from open-source libraries to commercial platforms offering enterprise-grade capabilities."""
        article += additional_content
    elif words > max_words:
        # Truncate to meet maximum
        sentences = article.split('. ')
        truncated = '. '.join(sentences[:len(sentences)//2])
        article = truncated + '.'

    return article


def build_prompt(keyword: str, niche: str, min_words: int, max_words: int) -> str:
    return f"""Write a comprehensive, professional article about {keyword} in the field of artificial intelligence.

Requirements:
- Target audience: AI professionals, researchers, students, and enthusiasts
- Length: {min_words}-{max_words} words
- Style: Educational, engaging, with practical insights and real-world examples
- Structure: Include introduction, main sections with headings, and conclusion
- Tone: Professional but accessible, authoritative but not overly technical
- Content: Cover fundamentals, applications, current trends, and future outlook
- SEO: Include relevant keywords naturally throughout the content
- Examples: Provide concrete examples and use cases where possible

Focus on making the content valuable for the AI community, with insights that help readers understand and apply {keyword} in their work or studies.

The article should be informative, well-structured, and demonstrate expertise in artificial intelligence topics."""


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
