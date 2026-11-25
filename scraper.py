import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def clean_number(text):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text.replace(",", ""))
    return float(nums[0]) if nums else 0

def fetch_ipo_data():
    url = "https://www.investorgain.com/report/live-ipo-gmp/331/"
    ipos = []
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table", {"id": "mainTable"})
        
        if not table:
            print("Table not found, keeping old data.")
            return None

        rows = table.find("tbody").find_all("tr")
        for row in rows[:25]: # Top 25 latest IPOs
            cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            if len(cols) < 8:
                continue

            raw_name = cols[0]
            price_str = cols[1]
            gmp_str = cols[2]
            est_listing = cols[3]
            ipo_size = cols[4]
            open_date = cols[5]
            close_date = cols[6]
            listing_date = cols[7]

            # Category check (SME vs Mainboard)
            category = "SME" if "SME" in raw_name.upper() else "MAINBOARD"
            clean_name = raw_name.replace("IPO", "").strip()

            # GMP ane Price mathi calculation
            gmp_val = clean_number(gmp_str.split("(")[0])
            upper_price = clean_number(price_str.split("-")[-1])
            gmp_percent = round((gmp_val / upper_price) * 100, 1) if upper_price > 0 else 0

            # Status logic (Open / Upcoming / Closed)
            status = "UPCOMING"
            row_text = " ".join(cols).lower()
            if "open" in row_text:
                status = "OPEN"
            elif "close" in row_text or "listed" in row_text:
                status = "CLOSED"

            # Default Lot Size estimation
            lot_size = 1000 if category == "SME" else 80
            retail_profit = round(gmp_val * lot_size, 2)
            hni_profit = round(retail_profit * (2 if category == "SME" else 14), 2)

            ipos.append({
                "id": len(ipos) + 1,
                "name": clean_name,
                "category": category,
                "status": status,
                "date_range": f"{open_date} - {close_date}",
                "price": price_str,
                "upper_price": upper_price,
                "lot_size": lot_size,
                "issue_size": ipo_size,
                "gmp": gmp_val,
                "gmp_percent": gmp_percent,
                "est_listing": round(upper_price + gmp_val, 2),
                "allotment_date": "TBA",
                "listing_date": listing_date,
                "retail_profit": retail_profit,
                "hni_profit": hni_profit,
                "subscription": "1.25x",
                "fundamentals": {
                    "score": "7.5/10",
                    "rating": "Good Fundamentals",
                    "pe": "18.4",
                    "eps": "₹4.10",
                    "roe": "16.5%",
                    "debt_equity": "0.38",
                    "pat": "₹12.8 Cr",
                    "revenue": "₹140 Cr",
                    "nav": "₹18.20"
                },
                "pros": [
                    "Consistent revenue and profit growth",
                    "Healthy return on net worth (RoNW)"
                ],
                "cons": [
                    "Competitive industry segment"
                ]
            })
        return ipos
    except Exception as e:
        print("Scraper Error:", e)
        return None

if __name__ == "__main__":
    data = fetch_ipo_data()
    if data and len(data) > 0:
        output = {
            "last_updated": datetime.now().strftime("%d %b, %I:%M %p"),
            "total": len(data),
            "ipos": data
        }
        with open("ipo_data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(data)} IPOs successfully.")
