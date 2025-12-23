# /// script
# dependencies = [
#     "yt-dlp",
#     "streamlink",
# ]
# ///

import subprocess
import os
import sys
import re
import argparse
import yt_dlp

# ==========================================
# デフォルト設定
# ==========================================
# デフォルトの保存先（引数で指定がない場合）
DEFAULT_OUTPUT_DIR = "."
# ==========================================

# グローバル変数として保持（関数内から参照するため）
OUTPUT_DIR = DEFAULT_OUTPUT_DIR

def sanitize_filename(name):
    """
    ファイル名に使えない文字を削除・置換する関数
    """
    if not name:
        return "unknown_title"
    # Windows等の禁止文字を除去
    name = re.sub(r'[\\/*?"<>|]', '', name)
    # 非表示文字（制御文字など）を除去
    name = "".join(c for c in name if c.isprintable())
    # 長すぎるファイル名はカット
    return name[:200]

def get_episode_urls(title_url):
    print(f"[*] エピソード一覧(URL)を取得中...: {title_url}")

    # URLのリストだけを高速に取得
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'ignoreerrors': True,
    }

    urls = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(title_url, download=False)

            # プレイリスト（シリーズ）の場合
            if 'entries' in info:
                for entry in info['entries']:
                    if entry and 'url' in entry:
                        urls.append(entry['url'])
            # 単一動画の場合
            elif 'url' in info:
                urls.append(info['url'])
            # WebページURLそのものを返す必要がある場合（yt-dlpの挙動による）
            elif 'webpage_url' in info:
                 urls.append(info['webpage_url'])

    except Exception as e:
        print(f"エラー: URL一覧の取得に失敗しました。\n{e}")
        sys.exit(1)

    # 重複除去（順序保持）
    return list(dict.fromkeys(urls))

def get_video_title(url):
    """
    個別の動画URLから正式なタイトルを取得する
    """
    ydl_opts = {
        'quiet': True,
        'ignoreerrors': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'title' in info:
                return info['title']
    except:
        pass
    return None

def download_and_convert(url, index):
    # まずタイトルを取得しにいく
    print(f"\n[{index:02d}] タイトル情報を取得中...")
    raw_title = get_video_title(url)

    # ID取得（タイトル取得失敗時の保険）
    episode_id = url.split('/')[-1]

    # ファイル名の作成
    safe_title = sanitize_filename(raw_title) if raw_title else episode_id
    base_name = f"{safe_title}"

    ts_filename = os.path.join(OUTPUT_DIR, f"{base_name}.ts")
    mp4_filename = os.path.join(OUTPUT_DIR, f"{base_name}.mp4")

    if os.path.exists(mp4_filename):
        print(f"[スキップ] 既に存在します: {mp4_filename}")
        return

    print(f"[処理開始] {safe_title}")

    # 1. Streamlinkでダウンロード
    print("  -> Downloading (.ts)...")

    cmd_dl = ["streamlink", url, "best", "-o", ts_filename]

    try:
        # 外部コマンド実行
        ret_dl = subprocess.run(cmd_dl, capture_output=False)
    except FileNotFoundError:
        # フォールバック（環境によっては streamlink が PATH にない場合のため）
        import shutil
        streamlink_path = shutil.which("streamlink")
        if not streamlink_path:
             # PyInstallerやvenv環境下のフォールバック
            streamlink_path = os.path.join(os.path.dirname(sys.executable), "streamlink")

        cmd_dl[0] = streamlink_path
        try:
            ret_dl = subprocess.run(cmd_dl, capture_output=False)
        except:
             print("  [!] streamlink コマンドが見つかりませんでした。インストールされているか確認してください。")
             return

    if ret_dl.returncode != 0 or not os.path.exists(ts_filename):
        print(f"  [!] ダウンロード失敗 (プレミアム限定やジオブロックの可能性があります)")
        if os.path.exists(ts_filename):
            os.remove(ts_filename) # 0バイトファイルなどが残らないように
        return

    # 2. ffmpegでmp4に変換
    print("  -> Converting to .mp4...")
    cmd_conv = ["ffmpeg", "-y", "-i", ts_filename, "-c", "copy", mp4_filename, "-loglevel", "error"]

    try:
        ret_conv = subprocess.run(cmd_conv)
        if ret_conv.returncode == 0:
            print(f"  [完了] 保存しました: {mp4_filename}")
            if os.path.exists(ts_filename):
                os.remove(ts_filename)
        else:
            print("  [!] 変換に失敗しました")
    except FileNotFoundError:
        print("  [!] ffmpeg が見つかりません。PATHが通っているか確認してください。")

def main():
    global OUTPUT_DIR

    # 引数の解析設定
    parser = argparse.ArgumentParser(description="AbemaTV Video Downloader using yt-dlp and streamlink")
    parser.add_argument("url", help="ダウンロードしたいタイトルまたは動画のURL")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help=f"保存先フォルダ (デフォルト: {DEFAULT_OUTPUT_DIR})")

    args = parser.parse_args()

    target_url = args.url
    OUTPUT_DIR = args.output

    # 保存先ディレクトリの作成
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
        except OSError as e:
            print(f"エラー: 保存先フォルダを作成できませんでした。\n{e}")
            return

    # URL取得処理
    urls = get_episode_urls(target_url)

    if not urls:
        print("動画が見つかりませんでした。")
        return

    print(f"[*] 合計 {len(urls)} 件のエピソードが見つかりました。\n")

    for i, url in enumerate(urls, 1):
        download_and_convert(url, i)

    print("\n[*] 全ての処理が完了しました。")

if __name__ == "__main__":
    main()
