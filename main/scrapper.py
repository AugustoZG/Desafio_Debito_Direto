from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys, json, re


CHROMEDRIVER = r"C:\Program Files (x86)\chromedriver.exe"
URL = "https://www.globo.com/"
LIMIT = 2  

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def is_article(href: str) -> bool:
    """Apenas links de artigo (.ghtml)."""
    if not href:
        return False
    return re.search(r"\.ghtml(?:$|\?)", href) is not None

def normalize_date(raw: str) -> str:
    """Extrai 'YYYY/MM/DD' de ISO ou similar."""
    if not raw:
        return ""
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", raw)
    if not m:
        return ""
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

opts = Options()

driver = webdriver.Chrome(service=Service(CHROMEDRIVER), options=opts)
wait = WebDriverWait(driver, 20)

driver.get(URL)


col = wait.until(EC.presence_of_element_located((By.ID, "column-jornalismo")))


wrappers = wait.until(EC.presence_of_all_elements_located(
    (By.CSS_SELECTOR, "#column-jornalismo .wrapper.theme-jornalismo")
))
if LIMIT:
    wrappers = wrappers[:LIMIT]


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

def page_ready(drv):
    return drv.execute_script("return document.readyState") == "complete"

for item in cards:
    href = item["href"]
    try:
        driver.get(href)
        wait.until(page_ready)

        subtitle = ""
        try:
            el = WebDriverWait(driver, 8).until(
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
                        subtitle = (driver.find_element(By.CSS_SELECTOR, sel)
                                    .get_attribute("content") or "").strip()
                    else:
                        subtitle = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
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
            for sel in [
                "meta[itemprop='datePublished']",
                "meta[property='article:published_time']",
                "meta[name='article:published_time']",
            ]:
                try:
                    raw_dt = (driver.find_element(By.CSS_SELECTOR, sel).get_attribute("content") or "").strip()
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
        item["error"] = str(e)[:200]

print(json.dumps(cards, ensure_ascii=False, indent=2))
driver.quit()
