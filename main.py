import os
import json
import time
import re
import urllib.parse
import urllib.request
import subprocess

import requests
import feedparser


WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DATA_FILE = "last_seen.json"


# ============================================================
# YouTube
# ============================================================

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


# ============================================================
# X
# ============================================================

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


# ============================================================
# TikTok
# ============================================================

TIKTOK_ACCOUNTS = [
    {
        "name": "M!LK Official",
        "username": "milk_official",
        "color": 0xEE1D52
    },
    {
        "name": "M!LK ウシ活",
        "username": "milk_ushikatsu",
        "color": 0xEE1D52
    }
]


# ============================================================
# 共通
# ============================================================

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


def send_discord(
    title,
    text,
    url,
    color,
    bot_name,
    image_url=None
):
    if not WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URL が設定されていません。")
        return False

    embed = {
        "title": title,
        "description": text[:250] + ("..." if len(text) > 250 else ""),
        "url": url,
        "color": color
    }

    # --------------------------------------------------------
    # 画像がある場合はDiscordへ直接添付
    # --------------------------------------------------------
    if image_url:
        try:
            req_img = urllib.request.Request(
                image_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urllib.request.urlopen(req_img, timeout=8) as res_img:
                img_data = res_img.read()

            embed["image"] = {
                "url": "attachment://thumbnail.jpg"
            }

            payload_json = {
                "username": bot_name,
                "embeds": [embed]
            }

            files = {
                "payload_json": (
                    None,
                    json.dumps(payload_json, ensure_ascii=False),
                    "application/json"
                ),
                "file": (
                    "thumbnail.jpg",
                    img_data,
                    "image/jpeg"
                )
            }

            res = requests.post(
                WEBHOOK_URL,
                files=files,
                timeout=15
            )

            return res.status_code in [200, 204]

        except Exception as e:
            print(f"画像添付エラー（通常送信へ切替）: {e}")

    # --------------------------------------------------------
    # 通常送信
    # --------------------------------------------------------

    payload = {
        "username": bot_name,
        "embeds": [embed]
    }

    try:
        res = requests.post(
            WEBHOOK_URL,
            json=payload,
            timeout=15
        )

        return res.status_code in [200, 204]

    except Exception as e:
        print(f"Discord送信エラー: {e}")
        return False


# ============================================================
# 1. YouTube
# ============================================================

def check_youtube(last_seen):

    for yt in YOUTUBE_CHANNELS:

        ch_id = yt["channel_id"]
        key = f"youtube:{ch_id}"

        rss_url = (
            "https://www.youtube.com/feeds/videos.xml"
            f"?channel_id={ch_id}"
        )

        try:
            feed = feedparser.parse(rss_url)

            if not feed.entries:
                continue

            latest = feed.entries[0]
            video_id = latest.yt_videoid

            # 初回は現在の動画を記録するだけ
            if key not in last_seen:
                last_seen[key] = video_id
                print(
                    f"[YouTube] 初期化: {yt['name']} "
                    f"{video_id}"
                )
                continue

            # 新着
            if video_id != last_seen.get(key):

                print(
                    f"[YouTube] 新着: "
                    f"{yt['name']} - {latest.title}"
                )

                yt_thumb = (
                    f"https://i.ytimg.com/vi/"
                    f"{video_id}/hqdefault.jpg"
                )

                send_discord(
                    title=f"🎬 YouTube新着: {latest.title}",
                    text=(
                        f"{yt['name']} に"
                        f"新しい動画が公開されました！"
                    ),
                    url=latest.link,
                    color=yt["color"],
                    bot_name=f"{yt['name']} YouTube通知",
                    image_url=yt_thumb
                )

                last_seen[key] = video_id

        except Exception as e:
            print(
                f"[YouTubeエラー] "
                f"{yt['name']}: {e}"
            )

        time.sleep(1)


# ============================================================
# 2. X
# ============================================================

def verify_and_get_tweet(username, tweet_id):

    oe_url = (
        "https://publish.twitter.com/oembed"
        f"?url=https://x.com/{username}/status/{tweet_id}"
    )

    try:
        req = urllib.request.Request(
            oe_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(
                res.read().decode("utf-8")
            )

        author = data.get(
            "author_url",
            ""
        ).lower()

        if username.lower() in author:

            html = data.get("html", "")

            clean_text = re.sub(
                r"<[^>]+>",
                "",
                html
            )

            clean_text = (
                clean_text
                .split("—")[0]
                .strip()
            )

            return str(tweet_id), clean_text

    except Exception:
        pass

    return None, None


def get_latest_tweet_smart(username):

    candidates = []

    # --------------------------------------------------------
    # Yahooリアルタイム検索
    # --------------------------------------------------------

    q1 = urllib.parse.quote(
        "id:" + username
    )

    url1 = (
        "https://search.yahoo.co.jp/realtime/search"
        f"?p={q1}"
    )

    try:

        req1 = urllib.request.Request(
            url1,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(
            req1,
            timeout=8
        ) as res:

            html1 = res.read().decode("utf-8")

        match = re.search(
            r'<script id="__NEXT_DATA__" '
            r'type="application/json">([^<]+)</script>',
            html1
        )

        if match:

            data = json.loads(match.group(1))

            entries = (
                data
                .get("props", {})
                .get("pageProps", {})
                .get("pageData", {})
                .get("timeline", {})
                .get("entry", [])
            )

            for e in entries:

                if (
                    e.get("screenName", "")
                    .lower()
                    == username.lower()
                ):

                    tid_str = str(e.get("id"))

                    candidates.append(
                        (
                            int(tid_str),
                            e.get("displayText", ""),
                            tid_str
                        )
                    )

    except Exception:
        pass

    # --------------------------------------------------------
    # @username検索
    # --------------------------------------------------------

    q2 = urllib.parse.quote(
        "@" + username
    )

    url2 = (
        "https://search.yahoo.co.jp/realtime/search"
        f"?p={q2}"
    )

    try:

        req2 = urllib.request.Request(
            url2,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(
            req2,
            timeout=8
        ) as res:

            html2 = res.read().decode("utf-8")

        match = re.search(
            r'<script id="__NEXT_DATA__" '
            r'type="application/json">([^<]+)</script>',
            html2
        )

        if match:

            data = json.loads(match.group(1))

            entries = (
                data
                .get("props", {})
                .get("pageProps", {})
                .get("pageData", {})
                .get("timeline", {})
                .get("entry", [])
            )

            reply_targets = set(
                str(e.get("inReplyTo"))
                for e in entries
                if e.get("inReplyTo")
            )

            for target_id in reply_targets:

                candidates.append(
                    (
                        int(target_id),
                        None,
                        target_id
                    )
                )

    except Exception:
        pass

    if not candidates:
        return None, None

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    for _, text, tid_str in candidates:

        if text:
            return tid_str, text

        valid_id, valid_text = (
            verify_and_get_tweet(
                username,
                tid_str
            )
        )

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

            tweet_id, tweet_text = (
                get_latest_tweet_smart(username)
            )

            if not tweet_id:
                continue

            tweet_url = (
                f"https://x.com/{username}"
                f"/status/{tweet_id}"
            )

            # 初回
            if key not in last_seen:

                last_seen[key] = tweet_id

                print(
                    f"[X] 初期化: "
                    f"{member['name']} {tweet_id}"
                )

                continue

            # 新着
            if tweet_id != last_seen.get(key):

                print(
                    f"[X] 新着: "
                    f"{member['name']}"
                )

                send_discord(
                    title=(
                        f"🐦 X新着: "
                        f"{member['name']}"
                    ),
                    text=tweet_text or "",
                    url=tweet_url,
                    color=member["color"],
                    bot_name=(
                        f"{member['name']} X通知"
                    )
                )

                last_seen[key] = tweet_id

        except Exception as e:

            print(
                f"[Xエラー] "
                f"{username}: {e}"
            )

        time.sleep(1.5)


# ============================================================
# 3. TikTok
# ============================================================

def run_tiktok_cli(username):

    """
    tiktok-cliで最新動画を1件取得する。
    """

    command = [
        "tt",
        "posts",
        f"@{username}",
        "-n",
        "1",
        "-o",
        "json",
        "-q"
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:

            print(
                f"[TikTok] {username} "
                f"取得失敗 "
                f"(exit={result.returncode})"
            )

            if stderr:
                print(stderr[-1000:])

            return None

        if not stdout:
            return None

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        try:

            data = json.loads(stdout)

            if isinstance(data, list):

                if not data:
                    return None

                return data[0]

            if isinstance(data, dict):

                # videos/itemsなどに入っている場合
                for key in [
                    "videos",
                    "items",
                    "data",
                    "results"
                ]:

                    value = data.get(key)

                    if isinstance(value, list):
                        if value:
                            return value[0]

                return data

        except json.JSONDecodeError:
            pass

        # ----------------------------------------------------
        # JSONL
        # ----------------------------------------------------

        for line in stdout.splitlines():

            line = line.strip()

            if not line:
                continue

            try:
                obj = json.loads(line)

                if isinstance(obj, dict):
                    return obj

            except Exception:
                continue

        return None

    except subprocess.TimeoutExpired:

        print(
            f"[TikTok] {username}: タイムアウト"
        )

    except FileNotFoundError:

        print(
            "[TikTok] tt コマンドが見つかりません。"
        )

    except Exception as e:

        print(
            f"[TikTok] {username}: {e}"
        )

    return None


def get_tiktok_value(data, keys):

    for key in keys:

        value = data.get(key)

        if value is not None and value != "":
            return value

    return None


def normalize_tiktok_video(data, username):

    if not isinstance(data, dict):
        return None

    video_id = get_tiktok_value(
        data,
        [
            "id",
            "video_id",
            "aweme_id"
        ]
    )

    if not video_id:
        return None

    url = get_tiktok_value(
        data,
        [
            "url",
            "permalink",
            "share_url",
            "web_url"
        ]
    )

    if not url:

        url = (
            f"https://www.tiktok.com/"
            f"@{username}/video/{video_id}"
        )

    description = get_tiktok_value(
        data,
        [
            "desc",
            "description",
            "title"
        ]
    )

    if not description:
        description = "TikTokに新しい動画が投稿されました。"

    thumbnail = get_tiktok_value(
        data,
        [
            "cover",
            "cover_url",
            "thumbnail",
            "thumbnail_url",
            "origin_cover"
        ]
    )

    return {
        "id": str(video_id),
        "url": url,
        "description": str(description),
        "thumbnail": thumbnail
    }


def check_tiktok(last_seen):

    for account in TIKTOK_ACCOUNTS:

        username = account["username"]
        name = account["name"]

        key = f"tiktok:{username}"

        try:

            raw = run_tiktok_cli(
                username
            )

            if not raw:
                continue

            video = normalize_tiktok_video(
                raw,
                username
            )

            if not video:
                print(
                    f"[TikTok] {name}: "
                    f"動画情報を取得できませんでした"
                )
                continue

            video_id = video["id"]

            # ------------------------------------------------
            # 初回
            # ------------------------------------------------

            if key not in last_seen:

                last_seen[key] = video_id

                print(
                    f"[TikTok] 初期化: "
                    f"{name} / {video_id}"
                )

                continue

            # ------------------------------------------------
            # 新着
            # ------------------------------------------------

            if video_id != last_seen.get(key):

                print(
                    f"[TikTok] 新着: "
                    f"{name} / {video_id}"
                )

                send_discord(
                    title=(
                        f"🎵 TikTok新着: "
                        f"{name}"
                    ),
                    text=video["description"],
                    url=video["url"],
                    color=account["color"],
                    bot_name=(
                        f"{name} TikTok通知"
                    ),
                    image_url=video.get(
                        "thumbnail"
                    )
                )

                last_seen[key] = video_id

        except Exception as e:

            print(
                f"[TikTokエラー] "
                f"{username}: {e}"
            )

        time.sleep(2)


# ============================================================
# Main
# ============================================================

def main():

    print("================================")
    print("M!LK 通知チェック開始")
    print("================================")

    last_seen = load_last_seen()

    # YouTube
    check_youtube(last_seen)

    # X
    check_twitter(last_seen)

    # TikTok
    check_tiktok(last_seen)

    save_last_seen(last_seen)

    print("================================")
    print("M!LK 通知チェック終了")
    print("================================")


if __name__ == "__main__":
    main()
