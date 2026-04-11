import requests
import json
from datetime import datetime
from urllib.parse import urlparse, urlencode, parse_qsl
import sys
import re
from typing import Dict, Tuple, Optional, Any, List

def print_colored(text: str, color: str) -> None:
    colors = {"green": "\033[92m", "red": "\033[91m", "blue": "\033[94m", "yellow": "\033[93m", "cyan": "\033[96m", "magenta": "\033[95m"}
    print(f"{colors.get(color.lower(), '')}{text}\033[0m")

def input_colored(prompt: str, color: str) -> str:
    colors = {"cyan": "\033[96m", "yellow": "\033[93m", "red": "\033[91m"}
    return input(f"{colors.get(color.lower(), '')}{prompt}\033[0m")

def clean_url(url: str, keep_token: bool) -> str:
    """ลบพารามิเตอร์ที่มีคำว่า token ออกทั้งหมด"""
    url = url.replace("ffmpeg ", "")
    if not keep_token:
        parsed = urlparse(url)
        params = dict(parse_qsl(parsed.query))
        
        # ลบทุก Key ที่มีคำว่า 'token'
        keys_to_remove = [k for k in params.keys() if 'token' in k.lower()]
        for k in keys_to_remove:
            del params[k]
            
        new_query = urlencode(params)
        url = parsed._replace(query=new_query).geturl()
        
        # ล้างซ้ำด้วย Regex เผื่อกรณี Query String ผิดรูป
        url = re.sub(r'[&?]+play_token=[^&]*', '', url)
        url = re.sub(r'[&?]+token=[^&]*', '', url)
    return url

def run_exporter():
    while True:
        print_colored("\n" + "="*45, "magenta")
        print_colored("   IPTV Portal M3U Exporter (Type '0' to Exit)", "magenta")
        print_colored("="*45, "magenta")
        
        # 1. รับค่า URL พร้อมเงื่อนไขออกจากโปรแกรม
        base_url_input = input_colored("Enter IPTV link (or 0 to exit): ", "cyan").strip()
        
        if base_url_input == '0':
            print_colored("Exiting program... Goodbye!", "yellow")
            break

        try:
            parsed_url = urlparse(base_url_input)
            domain_name = parsed_url.hostname if parsed_url.hostname else "playlist"
            safe_domain = domain_name.replace('.', '_')
            
            scheme = parsed_url.scheme or "http"
            host = parsed_url.hostname
            port = parsed_url.port or 80
            base_url = f"{scheme}://{host}:{port}"

            mac = input_colored("Input Mac address: ", "cyan").upper().strip()
            if mac == '0': break

            # 2. เมนูเลือก Option
            print_colored("\n--- Output Option ---", "magenta")
            print("1. Keep Token")
            print("2. Remove Token (Clean play_token)")
            choice = input_colored("Select choice (1 or 2): ", "yellow")
            if choice == '0': break
            keep_token = choice == "1"

            # 3. Session Setup
            session = requests.Session()
            session.cookies.update({"mac": mac})
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
                "Referer": f"{base_url}/c/",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            })

            # 4. Handshake
            print_colored("\nConnecting...", "yellow")
            token_url = f"{base_url}/portal.php?action=handshake&type=stb&token=&JsHttpRequest=1-xml"
            res = session.get(token_url, headers={"Authorization": f"MAC {mac}"}, timeout=10)
            token = res.json()["js"]["token"]
            
            if token:
                print_colored(f"[✔] Connected to {domain_name}", "green")
                
                # 5. Account Info
                info_url = f"{base_url}/portal.php?type=account_info&action=get_main_info&JsHttpRequest=1-xml"
                info_res = session.get(info_url, headers={"Authorization": f"Bearer {token}"})
                info_data = info_res.json()["js"]
                print_colored(f"MAC: {info_data['mac']} | Expiry: {info_data.get('phone', 'N/A')}", "green")

                # 6. Fetch Data
                print_colored("Fetching channel list...", "cyan")
                genre_url = f"{base_url}/server/load.php?type=itv&action=get_genres&JsHttpRequest=1-xml"
                genre_data = session.get(genre_url, headers={"Authorization": f"Bearer {token}"}).json()["js"]
                group_info = {group["id"]: group["title"] for group in genre_data}

                chan_url = f"{base_url}/portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
                channels_data = session.get(chan_url, headers={"Authorization": f"Bearer {token}"}).json()["js"]["data"]

                # 7. Save File
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                filename = f"{safe_domain}_{timestamp}.m3u"
                
                count = 0
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for channel in channels_data:
                        group_id = channel.get("tv_genre_id", "0")
                        group_name = group_info.get(group_id, "General")
                        name = channel.get("name", "Unknown")
                        logo = channel.get("logo", "")
                        
                        cmd_url_raw = channel.get("cmds", [{}])[0].get("url", "")
                        
                        if "localhost" in cmd_url_raw:
                            ch_id_match = re.search(r"/ch/(\d+)", cmd_url_raw)
                            if ch_id_match:
                                ch_id = ch_id_match.group(1)
                                final_url = f"{base_url}/play/live.php?mac={mac}&stream={ch_id}&extension=ts"
                            else: continue
                        else:
                            final_url = clean_url(cmd_url_raw, keep_token)

                        f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}",{name}\n{final_url}\n')
                        count += 1

                print_colored(f"\n[Success] Found {count} channels", "green")
                print_colored(f"File saved as: {filename}", "blue")
            
        except Exception as e:
            print_colored(f"\n[Error] {e}", "red")
            print_colored("Please check your Link/MAC and try again.", "yellow")

if __name__ == "__main__":
    try:
        run_exporter()
    except KeyboardInterrupt:
        print_colored("\nInterrupted by user. Closing...", "red")