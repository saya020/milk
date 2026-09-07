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

# TikTok公式oEmbedによる動画情報・サムネイル取得
def get_tiktok_info(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            final_url = res.geturl()
        
        if "tiktok.com" in final_url:
            oe_url = f"https://www.tiktok.com/oembed?url={final_url}"
            req_oe = urllib.request.Request(oe_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_oe, timeout=5) as res_oe:
                data = json.loads(res_oe.read().decode("utf-8"))
                return {
                    "url": final_url,
                    "title": data.get("title", "TikTok新着動画"),
                    "thumbnail": data.get("thumbnail_url")
                }
    except Exception as e:
        print(f"TikTok情報取得エラー: {e}")
    return None

# 2. X (Twitter) ＆ TikTok 最強ハイブリッド巡回
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

def check_twitter_and_tiktok(last_seen):
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

            # 動作テスト：画像を直接添付したTikTok通知テスト（1回送信）
            if not last_seen.get("tiktok_img_attach_test_v3") and username == "milk_info":
                tiktok_sample_img = "https://p16-common-sign.tiktokcdn.com/tos-alisg-p-0037/oYeSAPGAAQVALEFgYoeEjLF7AeYKhQIqAIDO5I~tplv-tiktokx-origin.image?dr=14575&x-expires=1788969600&x-signature=piB11E5VCXX9iMlZOBsorOvSTqw%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=43f4a2f9&idc=my"
                send_discord(
                    title="🎵 [動作確認] TikTok新着動画: M!LK",
                    text="新曲🪐 #時空超えてユニバース 略して #ときユニ 先行リリース❣️\nぜひ踊ってください🕺",
                    url="https://vt.tiktok.com/ZSq6mk9tU/",
                    color=0xEE1D52, # TikTokネオンピンク
                    bot_name="M!LK TikTok通知",
                    image_url=tiktok_sample_img
                )
                last_seen["tiktok_img_attach_test_v3"] = True

            if key not in last_seen:
                last_seen[key] = tweet_id
                continue

            if tweet_id != last_seen.get(key):
                print(f"[新着検知] ({member['name']}): {tweet_text[:20]}")
                
                # TikTok動画の更新告知かチェック
                tiktok_match = re.search(r"https?://[^\s]+", tweet_text)
                if username == "milk_info" and ("TikTok" in tweet_text or "tiktok" in tweet_text) and tiktok_match:
                    tiktok_url = tiktok_match.group(0)
                    tiktok_info = get_tiktok_info(tiktok_url)
                    if tiktok_info:
                        send_discord(
                            title=f"🎵 TikTok新着動画: M!LK",
                            text=tiktok_info["title"],
                            url=tiktok_info["url"],
                            color=0xEE1D52, # TikTokネオンピンク
                            bot_name="M!LK TikTok通知",
                            image_url=tiktok_info.get("thumbnail")
                        )
                    else:
                        send_discord(
                            title=f"🎵 TikTok新着: M!LK",
                            text=tweet_text,
                            url=tweet_url,
                            color=0xEE1D52,
                            bot_name="M!LK TikTok通知"
                        )
                else:
                    # 通常のXポスト通知
                    send_discord(
                        title=f"🐦 X新着: {member['name']}",
                        text=tweet_text,
                        url=tweet_url,
                        color=member["color"],
                        bot_name=f"{member['name']} X通知"
                    )

                last_seen[key] = tweet_id
        except Exception as e:
            print(f"[エラー] ({username}): {e}")
        time.sleep(1.5)

def main():
    last_seen = load_last_seen()
    check_youtube(last_seen)
    check_twitter_and_tiktok(last_seen)
    save_last_seen(last_seen)

if __name__ == "__main__":
    main()
