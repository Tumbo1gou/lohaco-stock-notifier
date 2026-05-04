import json
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

PRODUCTS_FILE = "products.json"
STATUS_FILE = "stock_status.json"

# 在庫あり確定テキスト（どれか1つでもあれば在庫あり）
IN_STOCK_KEYWORDS = ["在庫あり"]

# 在庫なし確定テキスト（どれか1つでもあれば在庫なし）
OUT_OF_STOCK_KEYWORDS = ["在庫切れ", "入荷待ち", "売り切れ", "品切れ", "在庫なし", "販売終了"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def check_stock(url):
    """Return (in_stock: bool | None, product_name: str)

    判定優先順位:
    1. 「在庫あり」テキストあり → 在庫あり
    2. 「カートに入れる」ボタンが有効 → 在庫あり
    3. 在庫なしキーワードあり → 在庫なし
    4. 上記いずれも該当しない → 在庫なし（保守的判定）
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 商品名（h1タグから取得）
        title_tag = soup.find("h1")
        product_name = title_tag.get_text(strip=True) if title_tag else url

        page_text = soup.get_text()

        # 判定1: 「在庫あり」テキストが明示されている
        if any(kw in page_text for kw in IN_STOCK_KEYWORDS):
            return True, product_name

        # 判定2: 「カートに入れる」ボタンが存在しdisabledでない
        cart_btn = soup.find("button", string=lambda t: t and "カートに入れる" in t)
        if cart_btn and cart_btn.get("disabled") is None:
            return True, product_name

        # 判定3 / 4: 在庫なしキーワード or 判定できない → 在庫なし
        return False, product_name

    except requests.RequestException as e:
        print(f"  [ERROR] Request failed: {e}")
        return None, url
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
        return None, url


def send_notification(to_email, product_name, product_url, smtp_cfg):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【在庫入荷】{product_name}"
    msg["From"] = smtp_cfg["from_addr"]
    msg["To"] = to_email

    html_body = f"""\
<html>
<body style="font-family: sans-serif; color: #333;">
  <h2 style="color: #e60012;">&#128230; 在庫入荷のお知らせ</h2>
  <p>監視中の商品に在庫が入荷しました。お早めにご確認ください。</p>
  <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
    <tr>
      <th style="text-align:left; padding:8px; background:#f5f5f5; border:1px solid #ddd; width:120px;">商品名</th>
      <td style="padding:8px; border:1px solid #ddd;">{product_name}</td>
    </tr>
    <tr>
      <th style="text-align:left; padding:8px; background:#f5f5f5; border:1px solid #ddd;">URL</th>
      <td style="padding:8px; border:1px solid #ddd;">
        <a href="{product_url}">{product_url}</a>
      </td>
    </tr>
  </table>
  <p style="margin-top:24px; font-size:12px; color:#999;">
    このメールは LOHACO 在庫監視ツールによって自動送信されました。
  </p>
</body>
</html>
"""
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    port = int(smtp_cfg["port"])
    if port == 465:
        with smtplib.SMTP_SSL(smtp_cfg["host"], port) as server:
            server.login(smtp_cfg["user"], smtp_cfg["password"])
            server.sendmail(smtp_cfg["from_addr"], to_email, msg.as_string())
    else:
        with smtplib.SMTP(smtp_cfg["host"], port) as server:
            server.starttls()
            server.login(smtp_cfg["user"], smtp_cfg["password"])
            server.sendmail(smtp_cfg["from_addr"], to_email, msg.as_string())


def main():
    data = load_products()
    products = data.get("products", [])
    # メールアドレスは必ず GitHub Secret (NOTIFY_EMAIL) から取得する
    notify_email = os.environ.get("NOTIFY_EMAIL", "")

    smtp_cfg = {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": os.environ.get("SMTP_PORT", "465"),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }

    if not smtp_cfg["user"]:
        print("[WARN] SMTP_USER not set — email notifications disabled.")

    prev_status = load_status()
    new_status = dict(prev_status)

    for product in products:
        url = product["url"]
        name = product.get("name", "")

        print(f"Checking: {url}")
        in_stock, fetched_name = check_stock(url)

        # Use fetched name if name not set in products.json
        display_name = name or fetched_name

        if in_stock is None:
            print(f"  -> Skip (fetch error)")
            time.sleep(3)
            continue

        was_in_stock = prev_status.get(url)  # None = first check
        new_status[url] = in_stock

        if in_stock:
            print(f"  -> IN STOCK: {display_name}")
            # Notify only when transitioning from out-of-stock (or first check)
            if was_in_stock is False:
                print(f"  -> Sending notification to {notify_email}")
                if smtp_cfg["user"] and notify_email:
                    try:
                        send_notification(notify_email, display_name, url, smtp_cfg)
                        print(f"  -> Notification sent.")
                    except Exception as e:
                        print(f"  -> [ERROR] Email failed: {e}")
                else:
                    print("  -> (email skipped: SMTP not configured)")
        else:
            print(f"  -> Out of stock: {display_name}")

        time.sleep(3)

    save_status(new_status)
    print("Done.")


if __name__ == "__main__":
    main()
