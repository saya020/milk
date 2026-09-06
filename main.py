import os
import json
import time
import requests
import feedparser
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DATA_FILE = "last_seen.json"

# YouTubeチャンネル一覧
YOUTUBE_CHANNELS = [
    {
        "name": "M!LK Official",
        "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
        "color": 0xFF0000 # 赤
    },
    {
        "name": "佐野勇斗だぞ",
        "channel_id": "UCx89B48_6GfM05n6iJ83-6A",
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

# テスト通知：最新のYouTube動画を確実に1件飛ばす
def send_youtube_test(last_seen):
    if not last_seen.get("youtube_test_done"):
        print("YouTubeテスト送信中...")
        rss_url = "https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            latest = feed.entries[0]
            send_discord(
                title=f"🎬 [動作テスト] {latest.title}",
                text=f"M!LK公式の最新動画です！新着動画が出るとこのように通知されます。\n{latest.link}",
                url=latest.link,
                color=0xFF0000,
                bot_name="M!LK YouTube通知"
            )
            last_seen["youtube_test_done"] = True

# YouTube巡回
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
            print(f"[YouTube] 新着: {latest.title}")
            send_discord(
                title=f"🎬 YouTube新着: {latest.title}",
                text=f"{yt['name']} に新しい動画が公開されました！\n{latest.link}",
                url=latest.link,
                color=yt["color"],
                bot_name=f"{yt['name']} YouTube通知"
            )
            last_seen[key] = video_id
        time.sleep(1)

# X (Twitter) 巡回
def check_twitter(last_seen):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    for member in ACCOUNTS:
        username = member.get("twitter")
        if not username:
            continue
            
        key = f"twitter:{username}"
        url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if not script:
                continue

            data = json.loads(script.string)
            timeline = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
            
            for item in timeline:
                tweet = item.get("content", {}).get("tweet")
                if not tweet:
                    continue
                tweet_id = tweet.get("id_str")
                tweet_text = tweet.get("text", "")
                tweet_url = f"https://x.com/{username}/status/{tweet_id}"

                if key not in last_seen:
                    last_seen[key] = tweet_id
                    break

                if tweet_id != last_seen.get(key):
                    print(f"[X] 新着 ({member['name']}): {tweet_text[:20]}")
                    send_discord(
                        title=f"🐦 X新着: {member['name']}",
                        text=tweet_text,
                        url=tweet_url,
                        color=member["color"],
                        bot_name=f"{member['name']} X通知"
                    )
                    last_seen[key] = tweet_id
                break
        except Exception as e:
            print(f"[X] エラー ({username}): {e}")
        time.sleep(1.5)

# Instagram 巡回
def check_instagram(last_seen):
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for member in ACCOUNTS:
        username = member.get("instagram")
        if not username:
            continue
            
        key = f"instagram:{username}"
        url = f"https://imginn.com/{username}/"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                first_post = soup.find("a", class_="item")
                if first_post and first_post.get("href"):
                    post_path = first_post.get("href")
                    post_url = f"https://www.instagram.com{post_path}"

                    if key not in last_seen:
                        last_seen[key] = post_path
                        continue

                    if post_path != last_seen.get(key):
                        print(f"[Instagram] 新着 ({member['name']}): {post_url}")
                        send_discord(
                            title=f"📸 Instagram新着: {member['name']}",
                            text=f"{member['name']} のInstagramが新しく投稿されました！\n{post_url}",
                            url=post_url,
                            color=member["color"],
                            bot_name=f"{member['name']} インスタ通知"
                        )
                        last_seen[key] = post_path
        except Exception as e:
            print(f"[Instagram] エラー ({username}): {e}")
        time.sleep(1.5)

def main():
    last_seen = load_last_seen()
    send_youtube_test(last_seen)  # YouTubeのテスト送信
    check_youtube(last_seen)
    check_twitter(last_seen)
    check_instagram(last_seen)
    save_last_seen(last_seen)

if __name__ == "__main__":
    main()
