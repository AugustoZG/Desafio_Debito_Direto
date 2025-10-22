# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_URL: str = "https://www.globo.com/"
DEFAULT_COLUMN_ID: str = "column-jornalismo"
DEFAULT_TIMEOUT: int = 20  

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def is_article(href: str) -> bool:

    if not href:
        return False
    return re.search(r"\.ghtml(?:$|\?)", href) is not None


def normalize_date(raw: str) -> str:
    if not raw:
        return ""
    match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", raw)
    if not match:
        return ""
    return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"


def build_driver(headless: bool) -> webdriver.Chrome:

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    chromedriver_path = os.environ.get("CHROMEDRIVER")
    if chromedriver_path and os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
    else:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except Exception:
            service = Service()

    return webdriver.Chrome(service=service, options=options)


def page_ready(driver: webdriver.Chrome) -> bool:
    return driver.execute_script("return document.readyState") == "complete"

@app.get("/noticias")
def noticias():
    driver: Optional[webdriver.Chrome] = None

    try:
        limit: Optional[int] = request.args.get("limit", type=int)
        headless: bool = (request.args.get("headless", "true").lower() == "true")
        timeout: int = request.args.get("timeout", default=DEFAULT_TIMEOUT, type=int)
        column_id: str = request.args.get("column_id", default=DEFAULT_COLUMN_ID, type=str)
        url: str = request.args.get("url", default=DEFAULT_URL, type=str)

        driver = build_driver(headless=headless)
        wait = WebDriverWait(driver, timeout)

        driver.get(url)
        wait.until(page_ready)

        wait.until(EC.presence_of_element_located((By.ID, column_id)))

        wrappers = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, f"#{column_id} .wrapper.theme-jornalismo")
            )
        )
        if limit:
            wrappers = wrappers[:limit]

        cards: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str]] = set()

        for wrapper in wrappers:
            classes = (wrapper.get_attribute("class") or "")
            featured = "first" in classes.split()

            try:
                anchor = wrapper.find_element(By.CSS_SELECTOR, "a.post__link")
            except Exception:
                continue  

            href = (anchor.get_attribute("href") or "").strip()
            if not is_article(href):
                continue

            title = (anchor.get_attribute("title") or "").strip()
            if not title:
                try:
                    title = wrapper.find_element(By.CSS_SELECTOR, "h2.post__title").text.strip()
                except Exception:
                    title = ""

            key = (href, title)
            if href and key not in seen:
                seen.add(key)
                cards.append({"title": title, "href": href, "featured": featured})

        for item in cards:
            try:
                driver.get(item["href"])
                wait.until(page_ready)

                subtitle = ""
                try:
                    subtitle_el = WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h2.content-head__subtitle"))
                    )
                    subtitle = subtitle_el.text.strip()
                except Exception:
                    for selector in (
                        "meta[property='og:description']",
                        ".content-head__subtitle",
                        "meta[name='description']",
                    ):
                        try:
                            if selector.startswith("meta"):
                                subtitle = (
                                    driver.find_element(By.CSS_SELECTOR, selector)
                                    .get_attribute("content")
                                    or ""
                                ).strip()
                            else:
                                subtitle = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                            if subtitle:
                                break
                        except Exception:
                            pass

                created_at = ""
                try:
                    t = driver.find_element(By.CSS_SELECTOR, "time[itemprop='datePublished']")
                    raw_dt = (t.get_attribute("datetime") or t.get_attribute("content") or t.text or "").strip()
                    created_at = normalize_date(raw_dt)
                except Exception:
                    pass

                if not created_at:
                    for selector in (
                        "meta[itemprop='datePublished']",
                        "meta[property='article:published_time']",
                        "meta[name='article:published_time']",
                    ):
                        try:
                            raw_dt = (
                                driver.find_element(By.CSS_SELECTOR, selector).get_attribute("content") or ""
                            ).strip()
                            created_at = normalize_date(raw_dt)
                            if created_at:
                                break
                        except Exception:
                            pass

                item["subtitle"] = subtitle
                item["createdAt"] = created_at

            except Exception as err:
                item["subtitle"] = ""
                item["createdAt"] = ""
                item["error"] = str(err)[:180]

        return app.response_class(
            response=json.dumps(cards, ensure_ascii=False, indent=2),
            status=200,
            mimetype="application/json; charset=utf-8",
        )

    except Exception as err:
        return jsonify({"error": str(err)}), 500

    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
