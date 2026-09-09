import os
import json
import time
import re
import urllib.parse
import urllib.request
import requests
import feedparser

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DATA_FILE = "last_seen.json"

# YouTubeチャンネル一覧
YOUTUBE_CHANNELS = [
    {
        "name": "M!LK Official",
        "channel_id": "UCHqQCpqvSOcHQr6Oqa4_5wg",
        "color": 0xFF0000
    },
    {
        "name": "佐野勇斗だぞ",
        "channel_id": "UCKBT9RsmIdJDxoNXUIXvX6A",
        "color": 0xFF69B4
    },
    {
        "name": "じんだいチャンネル",
        "channel_id": "UCk8oGFgksVxjh2YiU_D6hFQ",
        "color": 0xF5A623
    }
]

# 公式サイト（sd-milk.com）掲載のアカウント設定
ACCOUNTS = [
    {
        "name": "M!LK 公式",
        "color": 0x333333,
        "twitter": "milk_info"
    },
    {
        "name": "佐野 勇斗",
        "color": 0xFF69B4,
        "twitter": "sanohayatodazo"
    },
    {
        "name": "塩﨑 太智",
        "color": 0x1E90FF,
        "twitter": "shiozaki__info"
    },
    {
        "name": "曽野 舜太",
        "color": 0xFF2800,
        "twitter": "sono_shunta_"
    },
    {
        "name": "山中 柔太朗",
        "color": 0xE8ECEF,
        "twitter": "jyu_ta_ro"
    },
    {
        "name": "吉田 仁人",
        "color": 0xFFD700,
        "twitter": "Y_Jinto_1215"
    }
]

def load_last_seen():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_last_seen(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def send_discord(title, text, url, color, bot_name, image_url=None):
    if not WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URL が設定されていません。")
        return False

    embed = {
        "title": title,
        "description": text[:250] + ("..." if len(text) > 250 else ""),
        "url": url,
        "color": color
    }

    # サムネイル画像がある場合はダウンロードして直接添付アップロード
    if image_url:
        try:
            req_img = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_img, timeout=5) as res_img:
                img_data = res_img.read()
            
            embed["image"] = {"url": "attachment://thumbnail.jpg"}
            payload_json = {
                "username": bot_name,
                "embeds": [embed]
            }
            files = {
                "payload_json": (None, json.dumps(payload_json), "application/json"),
                "file": ("thumbnail.jpg", img_data, "image/jpeg")
            }
            res = requests.post(WEBHOOK_URL, files=files)
            return res.status_code in [200, 204]
        except Exception as e:
            print(f"画像添付エラー (通常送信に切替): {e}")

    # 通常送信
    payload = {
        "username": bot_name,
        "embeds": [embed]
    }
    res = requests.post(WEBHOOK_URL, json=payload)
    return res.status_code in [200, 204]

# 1. YouTube巡回
def check_youtube(last_seen):
    for yt in YOUTUBE_CHANNELS:
        ch_id = yt["channel_id"]
        key = f"youtube:{ch_id}"
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            continue
        
        latest = feed.entries[0]
        video_id = latest.yt_videoid

        if key not in last_seen:
            last_seen[key] = video_id
            continue

        if video_id != last_seen.get(key):
            print(f"[YouTube] 新着 ({yt['name']}): {latest.title}")
            # YouTubeのサムネイル画像URL
            yt_thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            send_discord(
                title=f"🎬 YouTube新着: {latest.title}",
                text=f"{yt['name']} に新しい動画が公開されました！\n{latest.link}",
                url=latest.link,
                color=yt["color"],
                bot_name=f"{yt['name']} YouTube通知",
                image_url=yt_thumb
            )
            last_seen[key] = video_id
        time.sleep(1)

# Twitter公式oEmbedによる本人確認＆本文取得
def verify_and_get_tweet(username, tweet_id):
    oe_url = f"https://publish.twitter.com/oembed?url=https://x.com/{username}/status/{tweet_id}"
    try:
        req = urllib.request.Request(oe_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            author = data.get("author_url", "").lower()
            if username.lower() in author:
                clean_text = re.sub(r"<[^>]+>", "", data.get("html", "")).split("—")[0].strip()
                return str(tweet_id), clean_text
    except Exception:
        pass
    return None, None

# TikTokはRSSHub経由で巡回
TIKTOK_ACCOUNTS = [
    {
        "name": "M!LK 公式",
        "username": "milk_official",
        "color": 0xEE1D52
    },
    {
        "name": "M!LK 牛カツ",
        "username": "milk_ushikatsu",
        "color": 0xEE1D52
    }
]

def get_tiktok_thumbnail(entry):
    # RSSHub / feedparser が返す代表的な画像フィールドを順番に確認
    for key in ("media_thumbnail", "media_content"):
        values = entry.get(key, [])
        if isinstance(values, dict):
            values = [values]
        for item in values:
            if isinstance(item, dict) and item.get("url"):
                return item["url"]

    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("image/") and enclosure.get("href"):
            return enclosure["href"]
        if enclosure.get("url"):
            return enclosure["url"]

    # description/content 内の img src を最後に確認
    html = entry.get("summary", "") or entry.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', html, re.I)
    return match.group(1) if match else None

def check_tiktok(last_seen):
    for account in TIKTOK_ACCOUNTS:
        username = account["username"]
        key = f"tiktok:{username}"
        rss_url = f"https://rsshub.app/tiktok/user/{username}"

        try:
            response = requests.get(
                rss_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"[TikTok] RSSに投稿がありません: @{username}")
                continue

            latest = feed.entries[0]
            item_id = str(latest.get("id") or latest.get("guid") or latest.get("link") or "")
            item_url = latest.get("link") or f"https://www.tiktok.com/@{username}"
            title = latest.get("title") or "TikTok新着動画"
            pub_date = latest.get("published") or latest.get("updated") or ""
            thumbnail = get_tiktok_thumbnail(latest)

            if not item_id:
                print(f"[TikTok] 識別子を取得できません: @{username}")
                continue

            if key not in last_seen:
                # 初回実行では既存投稿を通知しない
                last_seen[key] = item_id
                print(f"[TikTok] 初回登録: @{username} -> {title}")
                continue

            if item_id != last_seen.get(key):
                print(f"[TikTok] 新着 ({account['name']}): {title}")
                text = title
                if pub_date:
                    text += f"\n投稿日: {pub_date}"

                send_discord(
                    title=f"🎵 TikTok新着: {account['name']}",
                    text=text,
                    url=item_url,
                    color=account["color"],
                    bot_name=f"{account['name']} TikTok通知",
                    image_url=thumbnail
                )
                last_seen[key] = item_id

        except Exception as e:
            print(f"[TikTokエラー] (@{username}): {e}")

        time.sleep(1)

def get_latest_tweet_smart(username):
    candidates = []
    q1 = urllib.parse.quote("id:" + username)
    url1 = f"https://search.yahoo.co.jp/realtime/search?p={q1}"
    try:
        req1 = urllib.request.Request(url1, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req1, timeout=8) as res:
            html1 = res.read().decode("utf-8")
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', html1)
        if match:
            data = json.loads(match.group(1))
            entries = data.get("props", {}).get("pageProps", {}).get("pageData", {}).get("timeline", {}).get("entry", [])
            for e in entries:
                if e.get("screenName", "").lower() == username.lower():
                    tid_str = str(e.get("id"))
                    candidates.append((int(tid_str), e.get("displayText", ""), tid_str))
    except Exception:
        pass

    q2 = urllib.parse.quote("@" + username)
    url2 = f"https://search.yahoo.co.jp/realtime/search?p={q2}"
    try:
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=8) as res:
            html2 = res.read().decode("utf-8")
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', html2)
        if match:
            data = json.loads(match.group(1))
            entries = data.get("props", {}).get("pageProps", {}).get("pageData", {}).get("timeline", {}).get("entry", [])
            reply_targets = set([str(e.get("inReplyTo")) for e in entries if e.get("inReplyTo")])
            for target_id in reply_targets:
                candidates.append((int(target_id), None, target_id))
    except Exception:
        pass

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0], reverse=True)
    
    for _, text, tid_str in candidates:
        if text:
            return tid_str, text
        valid_id, valid_text = verify_and_get_tweet(username, tid_str)
        if valid_id:
            return valid_id, valid_text

    return None, None

def check_twitter(last_seen):
    for member in ACCOUNTS:
        username = member.get("twitter")
        if not username:
            continue

        key = f"twitter:{username}"
        try:
            tweet_id, tweet_text = get_latest_tweet_smart(username)
            if not tweet_id:
                continue

            tweet_url = f"https://x.com/{username}/status/{tweet_id}"

            if key not in last_seen:
                last_seen[key] = tweet_id
                continue

            if tweet_id != last_seen.get(key):
                print(f"[X] 新着 ({member['name']}): {tweet_text[:20] if tweet_text else ''}")
                send_discord(
                    title=f"🐦 X新着: {member['name']}",
                    text=tweet_text or "新しいポストが投稿されました。",
                    url=tweet_url,
                    color=member["color"],
                    bot_name=f"{member['name']} X通知"
                )
                last_seen[key] = tweet_id
        except Exception as e:
            print(f"[Xエラー] ({username}): {e}")
        time.sleep(1.5)


def main():
    last_seen = load_last_seen()
    check_youtube(last_seen)
    check_twitter(last_seen)
    check_tiktok(last_seen)
    save_last_seen(last_seen)

if __name__ == "__main__":
    main()
