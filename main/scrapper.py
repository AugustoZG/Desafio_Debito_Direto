# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys, json, re, os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DEFAULT_URL = "https://www.globo.com/"
DEFAULT_COLUMN_ID = "column-jornalismo"
DEFAULT_TIMEOUT = 20  

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def is_article(href: str) -> bool:
    """Somente páginas de artigo (.ghtml)."""
    if not href:
        return False
    return re.search(r"\.ghtml(?:$|\?)", href) is not None

def normalize_date(raw: str) -> str:
    """Extrai 'YYYY/MM/DD' de ISO/texto."""
    if not raw:
        return ""
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", raw)
    if not m:
        return ""
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

def build_driver(headless: bool):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    chromedriver_path = os.environ.get("CHROMEDRIVER")
    if chromedriver_path and os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
    else:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except Exception:
            service = Service()
    return webdriver.Chrome(service=service, options=opts)

def page_ready(drv):
    return drv.execute_script("return document.readyState") == "complete"

@app.get("/noticias")
def noticias():
    """
    GET /noticias?limit=3&headless=true&timeout=20&column_id=column-jornalismo
    Retorna cards de Jornalismo com featured, subtitle e createdAt (YYYY/MM/DD).
    """
    try:
        limit = request.args.get("limit", type=int)
        headless = (request.args.get("headless", "true").lower() == "true")
        timeout = request.args.get("timeout", default=DEFAULT_TIMEOUT, type=int)
        column_id = request.args.get("column_id", default=DEFAULT_COLUMN_ID, type=str)
        url = request.args.get("url", default=DEFAULT_URL, type=str)

        drv = build_driver(headless=headless)
        wait = WebDriverWait(drv, timeout)

        drv.get(url)
        wait.until(page_ready)

        col = wait.until(EC.presence_of_element_located((By.ID, column_id)))

        wrappers = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, f"#{column_id} .wrapper.theme-jornalismo")
        ))
        if limit:
            wrappers = wrappers[:limit]

        cards = []
        visto = set()

        for wrap in wrappers:
            classes = (wrap.get_attribute("class") or "")
            featured = "first" in classes.split()
            try:
                a = wrap.find_element(By.CSS_SELECTOR, "a.post__link")
            except Exception:
                continue

            href = (a.get_attribute("href") or "").strip()
            if not is_article(href):
                continue

            title = (a.get_attribute("title") or "").strip()
            if not title:
                try:
                    title = a.find_element(By.CSS_SELECTOR, "h2.post__title").text.strip()
                except Exception:
                    title = ""

            key = (href, title)
            if href and key not in visto:
                visto.add(key)
                cards.append({"title": title, "href": href, "featured": featured})

        for item in cards:
            try:
                drv.get(item["href"])
                wait.until(page_ready)

                subtitle = ""
                try:
                    el = WebDriverWait(drv, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h2.content-head__subtitle"))
                    )
                    subtitle = el.text.strip()
                except Exception:
                    for sel in [
                        "meta[property='og:description']",
                        ".content-head__subtitle",
                        "meta[name='description']",
                    ]:
                        try:
                            if sel.startswith("meta"):
                                subtitle = (drv.find_element(By.CSS_SELECTOR, sel)
                                            .get_attribute("content") or "").strip()
                            else:
                                subtitle = drv.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if subtitle:
                                break
                        except Exception:
                            pass

                created_at = ""
                try:
                    t = drv.find_element(By.CSS_SELECTOR, "time[itemprop='datePublished']")
                    raw_dt = (t.get_attribute("datetime") or t.get_attribute("content") or t.text or "").strip()
                    created_at = normalize_date(raw_dt)
                except Exception:
                    pass

                if not created_at:
                    for sel in [
                        "meta[itemprop='datePublished']",
                        "meta[property='article:published_time']",
                        "meta[name='article:published_time']",
                    ]:
                        try:
                            raw_dt = (drv.find_element(By.CSS_SELECTOR, sel).get_attribute("content") or "").strip()
                            created_at = normalize_date(raw_dt)
                            if created_at:
                                break
                        except Exception:
                            pass

                item["subtitle"] = subtitle
                item["createdAt"] = created_at

            except Exception as e:
                item["subtitle"] = ""
                item["createdAt"] = ""
                item["error"] = str(e)[:180]

        return app.response_class(
            response=json.dumps(cards, ensure_ascii=False, indent=2),
            status=200,
            mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            drv.quit()
        except Exception:
            pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
