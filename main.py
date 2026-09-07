import os
import json
import time
import re
import urllib.parse
import requests
import feedparser

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DATA_FILE = "last_seen.json"

# YouTubeチャンネル一覧
YOUTUBE_CHANNELS = [
    {
        "name": "M!LK Official",
        "channel_id": "UCHqQCpqvSOcHQr6Oqa4_5wg",
        "color": 0xFF0000 # 赤
    },
    {
        "name": "佐野勇斗だぞ",
        "channel_id": "UCKBT9RsmIdJDxoNXUIXvX6A",
        "color": 0xFF69B4 # ピーチヒップピンク
    },
    {
        "name": "じんだいチャンネル",
        "channel_id": "UCk8oGFgksVxjh2YiU_D6hFQ",
        "color": 0xF5A623 # オレンジ・イエロー系
    }
]

# メンバー＆公式アカウント設定（メンバーカラー付き）
ACCOUNTS = [
    {
        "name": "M!LK 公式",
        "color": 0x333333,
        "twitter": "milk_info",
        "instagram": "milk_official_2014"
    },
    {
        "name": "佐野 勇斗",
        "color": 0xFF69B4, # ピーチヒップピンク
        "twitter": "sanohayatodazo",
        "instagram": "sanohayato_milk"
    },
    {
        "name": "塩﨑 太智",
        "color": 0x1E90FF, # サファイアブルー
        "twitter": "shiozaki__info",
        "instagram": "daichi_shiozaki_milk_official"
    },
    {
        "name": "曽野 舜太",
        "color": 0xFF2800, # ハッピーレッド
        "twitter": "sono_shunta_",
        "instagram": "shunta_sono_milk_official"
    },
    {
        "name": "山中 柔太朗",
        "color": 0xE8ECEF, # クリスタルホワイト
        "twitter": "jyu_ta_ro",
        "instagram": "jutaro_yamanaka_milk_official"
    },
    {
        "name": "吉田 仁人",
        "color": 0xFFD700, # きらめきイエロー
        "twitter": "Y_Jinto_1215",
        "instagram": "jinto_yoshida_milk_official"
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

def send_discord(title, text, url, color, bot_name):
    if not WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URL が設定されていません。")
        return False
    
    payload = {
        "username": bot_name,
        "embeds": [{
            "title": title,
            "description": text[:250] + ("..." if len(text) > 250 else ""),
            "url": url,
            "color": color
        }]
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
            send_discord(
                title=f"🎬 YouTube新着: {latest.title}",
                text=f"{yt['name']} に新しい動画が公開されました！\n{latest.link}",
                url=latest.link,
                color=yt["color"],
                bot_name=f"{yt['name']} YouTube通知"
            )
            last_seen[key] = video_id
        time.sleep(1)

# 2. X (Twitter) 巡回（Yahoo!リアルタイム検索連携方式・高速＆確実）
def check_twitter(last_seen):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for member in ACCOUNTS:
        username = member.get("twitter")
        if not username:
            continue
            
        key = f"twitter:{username}"
        q = urllib.parse.quote("id:" + username)
        url = f"https://search.yahoo.co.jp/realtime/search?p={q}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                print(f"[X] HTTPエラー ({username}): {res.status_code}")
                continue

            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', res.text)
            if not match:
                continue

            data = json.loads(match.group(1))
            entries = data.get("props", {}).get("pageProps", {}).get("pageData", {}).get("timeline", {}).get("entry", [])
            
            # 本人の投稿を抽出
            user_tweets = [e for e in entries if e.get("screenName", "").lower() == username.lower()]
            if not user_tweets:
                continue

            latest_tweet = user_tweets[0]
            tweet_id = str(latest_tweet.get("id"))
            tweet_text = latest_tweet.get("displayText", "")
            tweet_url = f"https://x.com/{username}/status/{tweet_id}"

            # 動作確認テスト：M!LK公式の最新Xポストを1件送る
            if not last_seen.get("twitter_test_done_v2") and username == "milk_info":
                send_discord(
                    title=f"🐦 [X動作確認] {member['name']}",
                    text=f"Xの連携テスト成功です！\n\n{tweet_text}",
                    url=tweet_url,
                    color=member["color"],
                    bot_name=f"{member['name']} X通知"
                )
                last_seen["twitter_test_done_v2"] = True

            if key not in last_seen:
                last_seen[key] = tweet_id
                continue

            if tweet_id != last_seen.get(key):
                print(f"[X] 新着検知 ({member['name']}): {tweet_text[:20]}")
                send_discord(
                    title=f"🐦 X新着: {member['name']}",
                    text=tweet_text,
                    url=tweet_url,
                    color=member["color"],
                    bot_name=f"{member['name']} X通知"
                )
                last_seen[key] = tweet_id
        except Exception as e:
            print(f"[X] エラー ({username}): {e}")
        time.sleep(1.5)

def main():
    last_seen = load_last_seen()
    check_youtube(last_seen)
    check_twitter(last_seen)
    save_last_seen(last_seen)

if __name__ == "__main__":
    main()
