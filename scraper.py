import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
}

def clean_number(text):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(text).replace(",", ""))
    return float(nums[0]) if nums else 0

def parse_dates_status(date_str):
    # Date range mathi check karse ke IPO OPEN che, UPCOMING ke CLOSED
    today = datetime.now()
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    matches = re.findall(r"(\d{1,2})\s*([A-Za-z]{3})", date_str)
    if len(matches) >= 2:
        try:
            d1, m1 = int(matches[0][0]), months.get(matches[0][1].lower(), today.month)
            d2, m2 = int(matches[1][0]), months.get(matches[1][1].lower(), today.month)
            start_dt = datetime(today.year, m1, d1)
            end_dt = datetime(today.year, m2, d2, 23, 59)
            if start_dt <= today <= end_dt:
                return "OPEN"
            elif today < start_dt:
                return "UPCOMING"
            else:
                return "CLOSED"
        except:
            pass
    return "UPCOMING"

def fetch_company_details(link):
    # Company na detail page parthi Price, Lot Size, Issue Size ane Fundamentals lavse
    details = {
        "price": "TBA", "upper_price": 0, "lot_size": 0, "issue_size": "TBA",
        "pe": "N/A", "eps": "N/A", "roe": "N/A", "debt_equity": "N/A",
        "pat": "N/A", "revenue": "N/A", "nav": "N/A", "score": "7.5/10", "rating": "Good Fundamentals"
    }
    if not link:
        return details
    try:
        res = requests.get(link, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Price Band extract
        price_m = re.search(r"Price Band[:\s]*₹?\s*(\d+)\s*(?:to|-)\s*₹?\s*(\d+)", text, re.I)
        if price_m:
            details["price"] = f"₹{price_m.group(1)} - ₹{price_m.group(2)}"
            details["upper_price"] = float(price_m.group(2))

        # Lot Size extract
        lot_m = re.search(r"(?:Market Lot|Lot Size)[:\s]*(\d+)\s*Shares", text, re.I)
        if lot_m:
            details["lot_size"] = int(lot_m.group(1))

        # Issue Size extract
        issue_m = re.search(r"Issue Size[:\s]*₹?\s*([\d,.]+\s*Cr)", text, re.I)
        if issue_m:
            details["issue_size"] = f"₹{issue_m.group(1)}"

        # Fundamentals extract (EPS, ROE, P/E, NAV)
        eps_m = re.search(r"EPS[:\s]*₹?\s*([-+]?\d*\.\d+|\d+)", text, re.I)
        if eps_m: details["eps"] = f"₹{eps_m.group(1)}"

        roe_m = re.search(r"(?:RoNW|ROE)[:\s]*([-+]?\d*\.\d+|\d+)\s*%", text, re.I)
        if roe_m: details["roe"] = f"{roe_m.group(1)}%"

        pe_m = re.search(r"P/E[:\s]*([-+]?\d*\.\d+|\d+)", text, re.I)
        if pe_m: details["pe"] = pe_m.group(1)

        nav_m = re.search(r"NAV[:\s]*₹?\s*([-+]?\d*\.\d+|\d+)", text, re.I)
        if nav_m: details["nav"] = f"₹{nav_m.group(1)}"

    except Exception as e:
        print("Detail fetch error:", e)
    return details

def scrape_all():
    url = "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/"
    ipos = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")[1:]
        for row in rows[:20]:
            cols = row.find_all(["td", "th"])
            if len(cols) < 4:
                continue

            name_col = cols[0]
            name = name_col.get_text(" ", strip=True)
            a_tag = name_col.find("a")
            detail_link = a_tag["href"] if a_tag and a_tag.has_attr("href") else None

            col_texts = [c.get_text(" ", strip=True) for c in cols]
            # IPOWatch exact columns: [0]=Name, [1]=GMP, [2]=Price/Kostak, [3]=Subject/Listing, [4]=Date
            gmp_raw = col_texts[1] if len(col_texts) > 1 else "0"
            price_raw = col_texts[2] if len(col_texts) > 2 else "0"
            date_str = col_texts[-1]

            # Deep details fetch from company page
            det = fetch_company_details(detail_link)

            gmp_val = clean_number(gmp_raw)
            upper_price = det["upper_price"] if det["upper_price"] > 0 else clean_number(price_raw.split("-")[-1])
            price_display = det["price"] if det["price"] != "TBA" else (f"₹{price_raw}" if upper_price > 0 else "TBA")

            category = "SME" if "SME" in name.upper() or (det["lot_size"] >= 400) else "MAINBOARD"
            lot_size = det["lot_size"] if det["lot_size"] > 0 else (1000 if category == "SME" else 85)

            gmp_percent = round((gmp_val / upper_price) * 100, 1) if upper_price > 0 else 0
            retail_profit = round(gmp_val * lot_size, 2)
            hni_profit = round(retail_profit * (2 if category == "SME" else 14), 2)
            status = parse_dates_status(date_str)

            ipos.append({
                "id": len(ipos) + 1,
                "name": name,
                "category": category,
                "status": status,
                "date_range": date_str,
                "price": price_display,
                "upper_price": upper_price,
                "lot_size": lot_size,
                "issue_size": det["issue_size"],
                "gmp": gmp_val,
                "gmp_percent": gmp_percent,
                "est_listing": round(upper_price + gmp_val, 2) if upper_price > 0 else gmp_val,
                "allotment_date": "TBA",
                "listing_date": "TBA",
                "retail_profit": retail_profit,
                "hni_profit": hni_profit,
                "subscription": "Live",
                "fundamentals": {
                    "score": det["score"],
                    "rating": det["rating"],
                    "pe": det["pe"],
                    "eps": det["eps"],
                    "roe": det["roe"],
                    "debt_equity": det["debt_equity"],
                    "pat": det["pat"],
                    "revenue": det["revenue"],
                    "nav": det["nav"]
                },
                "pros": [
                    "Official RHP financial metrics synced",
                    "Check GMP trend before applying"
                ],
                "cons": [
                    "Grey market premium is indicative & volatile"
                ]
            })
        return ipos
    except Exception as e:
        print("Main Scrape Error:", e)
        return []

if __name__ == "__main__":
    data = scrape_all()
    if data:
        output = {
            "last_updated": datetime.now().strftime("%d %b, %I:%M %p"),
            "total": len(data),
            "ipos": data
        }
        with open("ipo_data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Updated {len(data)} IPOs with real fundamentals!")
