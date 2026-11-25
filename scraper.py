import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
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

def determine_status(open_str, close_str):
    today = datetime.now().date()
    formats = ["%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y", "%d %b"]
    
    def parse_d(s):
        s = strip_html(s).strip()
        for fmt in formats:
            try:
                dt = datetime.strptime(s, fmt)
                if dt.year == 1900:
                    dt = dt.replace(year=today.year)
                return dt.date()
            except:
                continue
        return None

    o_dt = parse_d(open_str)
    c_dt = parse_d(close_str)
    if o_dt and c_dt:
        if o_dt <= today <= c_dt:
            return "OPEN"
        elif today < o_dt:
            return "UPCOMING"
        else:
            return "CLOSED"
    return None

def build_lot_distribution(category, lot_size, upper_price):
    if upper_price <= 0 or lot_size <= 0:
        return []
    if category == "SME":
        ind_shares = lot_size * 2 if (lot_size * upper_price) < 200000 else lot_size
        shni_shares = ind_shares + lot_size
        bhni_shares = lot_size * 8
        return [
            {"cat": "Individual", "shares": ind_shares, "amt": round(ind_shares * upper_price), "lots": ind_shares // lot_size},
            {"cat": "sHNI", "shares": shni_shares, "amt": round(shni_shares * upper_price), "lots": shni_shares // lot_size},
            {"cat": "bHNI", "shares": bhni_shares, "amt": round(bhni_shares * upper_price), "lots": bhni_shares // lot_size}
        ]
    else:
        ind_lots = 1
        shni_lots = max(14, int(205000 // (lot_size * upper_price)) + 1)
        bhni_lots = max(68, int(1005000 // (lot_size * upper_price)) + 1)
        return [
            {"cat": "Individual", "shares": lot_size * ind_lots, "amt": round(lot_size * ind_lots * upper_price), "lots": ind_lots},
            {"cat": "sHNI", "shares": lot_size * shni_lots, "amt": round(lot_size * shni_lots * upper_price), "lots": shni_lots},
            {"cat": "bHNI", "shares": lot_size * bhni_lots, "amt": round(lot_size * bhni_lots * upper_price), "lots": bhni_lots}
        ]

def scrape_investorgain_endpoints():
    now = datetime.now()
    fy = f"{now.year}-{str(now.year + 1)[-2:]}" if now.month >= 4 else f"{now.year - 1}-{str(now.year)[-2:]}"
    urls = [
        f"https://webnodejs.investorgain.com/cloud/report/data-read/331/1/{now.month}/{now.year}/{fy}/0/all",
        f"https://www.investorgain.com/cloud/report/data-read/331/1/{now.month}/{now.year}/{fy}/0/all"
    ]
    for url in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            if res.status_code == 200 and "reportTableData" in res.text:
                return res.json().get("reportTableData", [])
        except Exception as e:
            print("Endpoint try failed:", url, e)
    return []

def fetch_detail_tables(ipo_id, slug):
    sub_rows = []
    fundamentals = {"pe": "N/A", "eps": "N/A", "roe": "N/A", "debt": "N/A", "pat": "N/A", "revenue": "N/A", "nav": "N/A"}
    registrar = {"name": "Link Intime / KFinTech", "url": "https://linkintime.co.in/initial_offer/public-issues.html"}
    
    if not ipo_id or not slug:
        return sub_rows, fundamentals, registrar

    try:
        url = f"https://www.investorgain.com/ipo/{slug}/{ipo_id}/"
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        full_text = soup.get_text(" ", strip=True)

        # Registrar detection
        if "kfintech" in full_text.lower():
            registrar = {"name": "KFin Technologies Ltd", "url": "https://kosmic.kfintech.com/ipostatus/"}
        elif "bigshare" in full_text.lower():
            registrar = {"name": "Bigshare Services Pvt Ltd", "url": "https://ipo.bigshareonline.com/ipo_status.html"}
        elif "skyline" in full_text.lower():
            registrar = {"name": "Skyline Financial Services", "url": "https://www.skylinerta.com/ipo.php"}
        elif "maashitla" in full_text.lower():
            registrar = {"name": "Maashitla Securities", "url": "https://maashitla.com/allotment-status/public-issues"}
        elif "purva" in full_text.lower():
            registrar = {"name": "Purva Sharegistry", "url": "https://www.purvashare.com/investor-service/ipo-query"}

        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2:
                k = cells[0].lower()
                v = cells[1]
                if "p/e" in k and fundamentals["pe"] == "N/A": fundamentals["pe"] = v
                elif "eps" in k and fundamentals["eps"] == "N/A": fundamentals["eps"] = v
                elif ("roe" in k or "ronw" in k) and fundamentals["roe"] == "N/A": fundamentals["roe"] = v
                elif "debt" in k and fundamentals["debt"] == "N/A": fundamentals["debt"] = v
                elif ("pat" in k or "profit after tax" in k) and fundamentals["pat"] == "N/A": fundamentals["pat"] = v
                elif ("revenue" in k or "total income" in k) and fundamentals["revenue"] == "N/A": fundamentals["revenue"] = v
                elif "nav" in k and fundamentals["nav"] == "N/A": fundamentals["nav"] = v

                # Subscription table rows (QIB, NII/HNI, Retail/Individual, Total)
                if len(cells) >= 3 and any(x in k for x in ["qib", "nii", "hni", "retail", "individual", "total"]):
                    if len(sub_rows) < 8:
                        sub_rows.append({
                            "category": cells[0],
                            "offered": cells[1],
                            "applied": cells[2] if len(cells) > 2 else "-",
                            "times": cells[-1]
                        })
    except Exception as e:
        print("Detail scrape warning:", e)

    return sub_rows, fundamentals, registrar

def run_scraper():
    rows = scrape_investorgain_endpoints()
    ipos = []
    now_str = datetime.now().strftime("%d %b, %I:%M %p")

    for row in rows:
        raw_name = strip_html(row.get("Name", ""))
        if not raw_name:
            continue

        open_dt = strip_html(row.get("Open", ""))
        close_dt = strip_html(row.get("Close", ""))
        price_str = strip_html(row.get("Price", ""))
        upper_price = clean_num(price_str.split("-")[-1])

        # Sirf active/announced dates aur price band wale IPOs
        if upper_price <= 0 or not open_dt or open_dt == "-":
            continue

        status = determine_status(open_dt, close_dt)
        if not status:
            continue

        category = "SME" if "SME" in raw_name.upper() else "MAINBOARD"
        gmp_val = clean_num(strip_html(row.get("GMP", "")))
        lot_size = int(clean_num(strip_html(row.get("Lot", ""))))
        if lot_size <= 0:
            lot_size = 1000 if category == "SME" else max(1, round(14500 / upper_price))

        gmp_pct = round((gmp_val / upper_price) * 100, 1) if upper_price > 0 else 0
        est_listing = round(upper_price + gmp_val, 2)
        
        lot_dist = build_lot_distribution(category, lot_size, upper_price)
        ind_shares = lot_dist[0]["shares"] if lot_dist else lot_size
        hni_shares = lot_dist[1]["shares"] if len(lot_dist) > 1 else (lot_size * 14)

        gmp_ind = round(gmp_val * ind_shares, 2)
        gmp_hni = round(gmp_val * hni_shares, 2)

        ipo_id = row.get("~id", "")
        slug = row.get("~urlrewrite_folder_name", "")
        sub_rows, fundamentals, registrar = fetch_detail_tables(ipo_id, slug)

        if not sub_rows:
            total_sub = strip_html(row.get("Sub", "")) or "0.00x"
            sub_rows = [
                {"category": "QIB", "offered": "-", "applied": "-", "times": "-"},
                {"category": "HNIs (NII)", "offered": "-", "applied": "-", "times": "-"},
                {"category": "Individual (Retail)", "offered": "-", "applied": "-", "times": "-"},
                {"category": "Total", "offered": "-", "applied": "-", "times": total_sub}
            ]

        ipos.append({
            "id": len(ipos) + 1,
            "name": raw_name,
            "category": category,
            "status": status,
            "open_date": open_dt,
            "close_date": close_dt,
            "date_range": f"{open_dt} - {close_dt}",
            "price": f"₹{price_str}" if "₹" not in price_str else price_str,
            "upper_price": upper_price,
            "lot_size": lot_size,
            "issue_size": strip_html(row.get("IPO Size", "")) or "TBA",
            "gmp": gmp_val,
            "gmp_percent": gmp_pct,
            "last_heard": strip_html(row.get("GMP Updated", "")) or now_str,
            "est_listing": est_listing,
            "allotment_date": strip_html(row.get("BoA Dt", "")) or "TBA",
            "listing_date": strip_html(row.get("Listing", "")) or "TBA",
            "gmp_ind": gmp_ind,
            "gmp_hni": gmp_hni,
            "subscription_total": strip_html(row.get("Sub", "")) or "Live",
            "subscription_table": sub_rows,
            "lot_distribution": lot_dist,
            "fundamentals": fundamentals,
            "registrar": registrar
        })

    if ipos:
        with open("ipo_data.json", "w", encoding="utf-8") as f:
            json.dump({"last_updated": now_str, "ipos": ipos}, f, indent=2, ensure_ascii=False)
        print(f"Successfully updated {len(ipos)} live IPOs.")
    else:
        print("API returned 0 rows.")

if __name__ == "__main__":
    run_scraper()
