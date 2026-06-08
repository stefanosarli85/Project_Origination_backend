import json
import re
from datetime import datetime
from urllib.parse import quote_plus

import feedparser

KEYWORDS = {
    "MA_AND_CORPORATE_TRANSACTIONS": [
        "acquisition", "acquires", "acquire", "takeover",
        "buyout", "merger", "stake", "divestment",
        "acquisizione", "fusione", "partecipazione"
    ],

    "JOINT_VENTURES_AND_PARTNERSHIPS": [
        "joint venture", "partnership", "agreement",
        "alliance", "mou", "collaborazione",
        "accordo", "alleanza"
    ],

    "INTERNATIONAL_EXPANSION": [
        "expansion", "expands", "market entry",
        "international expansion", "new market",
        "espansione", "internazionalizzazione"
    ],

    "GEOGRAPHIES_GULF": [
        "dubai", "abu dhabi", "uae",
        "gcc", "gulf", "riyadh",
        "saudi arabia", "qatar"
    ],

    "GEOGRAPHIES_INDIA": [
        "india", "indian market",
        "mumbai", "new delhi",
        "bangalore"
    ],

    "GEOGRAPHIES_AFRICA_MATTEI": [
        "africa", "egypt", "morocco",
        "algeria", "tunisia",
        "kenya", "ethiopia",
        "mattei plan"
    ],

    "FUNDRAISING_AND_CAPITAL": [
        "funding", "fundraising",
        "capital raise",
        "investment",
        "private equity",
        "venture capital"
    ],

    "SOVEREIGN_WEALTH_FUNDS": [
        "mubadala",
        "adia",
        "adq",
        "pif",
        "qia",
        "investcorp"
    ],

    "SIGNALS_AND_INTENTIONS": [
        "considering",
        "plans to",
        "intends to",
        "in talks",
        "exploring",
        "eyeing"
    ],

    "INTERNATIONAL_CONTRACTS_AND_ORDERS": [
        "contract",
        "order",
        "tender",
        "awarded",
        "wins contract"
    ]
}


def clean_company_name(name):
    name = re.sub(
        r"\b(S\.P\.A\.|SPA|SRL|S\.R\.L\.|SOCIETA'|SOCIETA)\b",
        "",
        name,
        flags=re.IGNORECASE
    )

    return " ".join(name.split()).strip()


def detect_categories(text):

    text = text.lower()

    matched_categories = []
    matched_keywords = []

    score = 0

    for category, keywords in KEYWORDS.items():

        found = []

        for keyword in keywords:
            if keyword.lower() in text:
                found.append(keyword)

        if found:
            matched_categories.append(category)
            matched_keywords.extend(found)

            if category == "MA_AND_CORPORATE_TRANSACTIONS":
                score += 30

            elif category == "JOINT_VENTURES_AND_PARTNERSHIPS":
                score += 25

            elif category == "FUNDRAISING_AND_CAPITAL":
                score += 25

            elif category == "GEOGRAPHIES_GULF":
                score += 20

            elif category == "GEOGRAPHIES_INDIA":
                score += 20

            elif category == "GEOGRAPHIES_AFRICA_MATTEI":
                score += 20

            elif category == "SOVEREIGN_WEALTH_FUNDS":
                score += 35

            elif category == "INTERNATIONAL_CONTRACTS_AND_ORDERS":
                score += 15

            elif category == "SIGNALS_AND_INTENTIONS":
                score += 10

    return matched_categories, list(set(matched_keywords)), score


def search_google_news(query):

    rss_url = (
        f"https://news.google.com/rss/search?"
        f"q={quote_plus(query)}"
        f"&hl=it"
        f"&gl=IT"
        f"&ceid=IT:it"
    )

    feed = feedparser.parse(rss_url)

    return feed.entries


def get_company_news(company_name):

    clean_name = clean_company_name(company_name)

    search_queries = [
        company_name,
        clean_name,
        f'"{clean_name}"',
        f'"{clean_name}" Italia',
        f'"{clean_name}" azienda'
    ]

    all_articles = {}
    found_entries = []

    for query in search_queries:

        entries = search_google_news(query)

        if entries:
            found_entries.extend(entries)

    for article in found_entries:

        link = article.get("link")

        if link:
            all_articles[link] = article

    articles = []

    for article in all_articles.values():

        title = article.get("title", "")
        summary = article.get("summary", "")

        content = f"{title} {summary}"

        categories, keywords, score = detect_categories(content)

        articles.append({
            "title": title,
            "link": article.get("link"),
            "published": article.get("published"),
            "summary": summary,
            "matched_categories": categories,
            "matched_keywords": keywords,
            "priority_score": score
        })

    articles.sort(
        key=lambda x: x["priority_score"],
        reverse=True
    )

    return {
        "company_name": company_name,
        "search_timestamp": datetime.utcnow().isoformat() + "Z",
        "total_articles": len(articles),
        "articles": articles
    }