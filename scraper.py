import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.investorgain.com/"
}

def clean_num(val):
    if val is None:
        return 0.0
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val).replace(",", ""))
    return float(nums[0]) if nums else 0.0

def strip_html(raw):
    if not raw:
        return ""
    return BeautifulSoup(str(raw), "html.parser").get_text(" ", strip=True)

def get_status_from_dates(open_str, close_str):
    today = datetime.now().date()
    formats = ["%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"]
    
    def parse_dt(s):
        s = strip_html(s).strip()
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).date()
            except:
                continue
        return None

    o_dt = parse_dt(open_str)
    c_dt = parse_dt(close_str)

    if o_dt and c_dt:
        if o_dt <= today <= c_dt:
            return "OPEN"
        elif today < o_dt:
            return "UPCOMING"
        else:
            return "CLOSED"
    return None

def scrape_investorgain_api():
    # InvestorGain ki official live JSON feed (jahan se unki table load hoti hai)
    year = datetime.now().year
    month = datetime.now().month
    api_url = f"https://webnodejs.investorgain.com/cloud/report/data-read/331/1/{month}/{year}/2026-27/0/all"
    
    ipos = []
    try:
        res = requests.get(api_url, headers=HEADERS, timeout=20)
        data = res.json()
        rows = data.get("reportTableData", [])

        for row in rows:
            raw_name = strip_html(row.get("Name", ""))
            if not raw_name:
                continue

            open_dt = strip_html(row.get("Open", ""))
            close_dt = strip_html(row.get("Close", ""))
            listing_dt = strip_html(row.get("Listing", "")) or "TBA"
            price_str = strip_html(row.get("Price", ""))
            gmp_raw = strip_html(row.get("GMP", ""))
            est_raw = strip_html(row.get("Est Listing", ""))
            ipo_size = strip_html(row.get("IPO Size", ""))
            lot_raw = strip_html(row.get("Lot", ""))
            sub_raw = strip_html(row.get("Sub", "")) or "Live"

            # Unannounced / bina price ya bina date wale garbage IPO skip karo
            upper_price = clean_num(price_str.split("-")[-1])
            if upper_price <= 0 or not open_dt or open_dt == "-":
                continue

            status = get_status_from_dates(open_dt, close_dt)
            if not status:
                continue

            category = "SME" if "SME" in raw_name.upper() else "MAINBOARD"
            clean_name = re.sub(r"\s*(IPO|SME)\s*", " ", raw_name, flags=re.I).strip()

            gmp_val = clean_num(gmp_raw)
            lot_size = int(clean_num(lot_raw))
            if lot_size <= 0:
                lot_size = 1000 if category == "SME" else max(1, round(14500 / upper_price))

            gmp_percent = round((gmp_val / upper_price) * 100, 1) if upper_price > 0 else 0
            est_listing = clean_num(est_raw) if clean_num(est_raw) > 0 else round(upper_price + gmp_val, 2)
            retail_profit = round(gmp_val * lot_size, 2)
            hni_lots = 2 if category == "SME" else 14
            hni_profit = round(retail_profit * hni_lots, 2)

            # Detail slug se fundamentals fetch karne ki koshish
            url_rewrite = row.get("~urlrewrite_folder_name", "")
            ipo_id = row.get("~id", "")
            fund = fetch_fundamentals(ipo_id, url_rewrite, upper_price)

            ipos.append({
                "id": len(ipos) + 1,
                "name": clean_name,
                "category": category,
                "status": status,
                "date_range": f"{open_dt} - {close_dt}",
                "price": f"₹{price_str}" if "₹" not in price_str else price_str,
                "upper_price": upper_price,
                "lot_size": lot_size,
                "issue_size": f"₹{ipo_size}" if ipo_size and "₹" not in ipo_size else (ipo_size or "TBA"),
                "gmp": gmp_val,
                "gmp_percent": gmp_percent,
                "est_listing": est_listing,
                "allotment_date": strip_html(row.get("BoA Dt", "")) or "TBA",
                "listing_date": listing_dt,
                "retail_profit": retail_profit,
                "hni_profit": hni_profit,
                "subscription": sub_raw,
                "fundamentals": fund["metrics"],
                "pros": fund["pros"],
                "cons": fund["cons"]
            })

        return ipos
    except Exception as e:
        print("API Scrape Error:", e)
        return []

def fetch_fundamentals(ipo_id, slug, upper_price):
    metrics = {
        "score": "7.5/10",
        "rating": "Moderate",
        "pe": "N/A",
        "eps": "N/A",
        "roe": "N/A",
        "debt_equity": "N/A",
        "pat": "N/A",
        "revenue": "N/A",
        "nav": "N/A"
    }
    pros = ["Check RHP financials & subscription demand before applying"]
    cons = ["Grey market premium is unofficial & subject to market risk"]

    if not ipo_id or not slug:
        return {"metrics": metrics, "pros": pros, "cons": cons}

    try:
        detail_url = f"https://www.investorgain.com/ipo/{slug}/{ipo_id}/"
        res = requests.get(detail_url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Tables se exact financial ratios nikalna
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2:
                k, v = cells[0].lower(), cells[1]
                if "p/e" in k and metrics["pe"] == "N/A":
                    metrics["pe"] = v
                elif "eps" in k and metrics["eps"] == "N/A":
                    metrics["eps"] = v if "₹" in v else f"₹{v}"
                elif ("ronw" in k or "roe" in k) and metrics["roe"] == "N/A":
                    metrics["roe"] = v if "%" in v else f"{v}%"
                elif "debt" in k and metrics["debt_equity"] == "N/A":
                    metrics["debt_equity"] = v
                elif ("profit after tax" in k or k == "pat") and metrics["pat"] == "N/A":
                    metrics["pat"] = v
                elif ("revenue" in k or "total income" in k) and metrics["revenue"] == "N/A":
                    metrics["revenue"] = v
                elif "nav" in k and metrics["nav"] == "N/A":
                    metrics["nav"] = v if "₹" in v else f"₹{v}"

        # Rating calculation based on ROE & PE
        roe_num = clean_num(metrics["roe"])
        if roe_num >= 15:
            metrics["score"] = "8.2/10"
            metrics["rating"] = "Strong Fundamentals"
            pros.insert(0, f"Strong Return on Equity (RoE: {metrics['roe']})")
        elif roe_num > 0:
            metrics["score"] = "6.8/10"
            metrics["rating"] = "Average Fundamentals"

    except Exception as e:
        print("Detail page error:", e)

    return {"metrics": metrics, "pros": pros, "cons": cons}

if __name__ == "__main__":
    data = scrape_investorgain_api()
    if data:
        output = {
            "last_updated": datetime.now().strftime("%d %b, %I:%M %p"),
            "total": len(data),
            "ipos": data
        }
        with open("ipo_data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(data)} verified IPOs!")
    else:
        print("No valid IPOs returned; keeping existing file.")
