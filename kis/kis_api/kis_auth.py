# -*- coding: utf-8 -*-
# ====| Refer to the samples below for issuing (REST) Access Tokens / (Websocket) Approval Keys. |=====================
# ====| Includes common API call functions                                  |=====================

import asyncio
import copy
import json
import logging
import os
import time
from base64 import b64decode
from collections import namedtuple
from collections.abc import Callable
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd

# pip install requests (Package Installation)
import requests

# Declare WebSocket module.
import websockets

# pip install PyYAML (Package Installation)
import yaml
from Crypto.Cipher import AES

# pip install pycryptodome
from Crypto.Util.Padding import unpad

clearConsole = lambda: os.system("cls" if os.name in ("nt", "dos") else "clear")

key_bytes = 32
config_root = os.path.join(os.path.expanduser("~"), "steven", "KIS_config")
# config_root = "$HOME/KIS/config/"  # Folder where the token file is stored; set a path difficult for others to find.
# token_tmp = config_root + 'KIS000000'  # File name for local token storage; avoid names that make the token value predictable.
# token_tmp = config_root + 'KIS' + datetime.today().strftime("%Y%m%d%H%M%S")  # Token filename with timestamp (YYYYMMDDHHMMSS)
token_tmp = os.path.join(
    config_root, f"KIS{datetime.today().strftime('%Y%m%d')}"
)  # Token filename with current date (YYYYMMDD)

# Check if the token management file exists; if not, create it.
if os.path.exists(token_tmp) == False:
    f = open(token_tmp, "w+")

# Manage App Key, App Secret, Token, Account Number, etc. Please set your own path and filename.
# pip install PyYAML (Package Installation)
with open(os.path.join(config_root, "kis_devlp.yaml"), encoding="UTF-8") as f:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)

from .key.key import get_secrets_from_password
app_key, app_secret, app_hts_id = get_secrets_from_password()

if app_key is None or app_secret is None or app_hts_id is None:
    print("\033[91m\n[CRITICAL ERROR] Failed to load credentials.")
    print("Access denied. The program will now terminate.\033[0m")
    import sys
    sys.exit(1)

_cfg["my_app"] = app_key
_cfg["my_sec"] = app_secret
_cfg["my_htsid"] = app_hts_id

_TRENV = tuple()
_token_expire_time = None
_approval_received_time = None
_autoReAuth = True
_DEBUG = False
_isPaper = False
_smartSleep = 0.1

# Define base header values
_base_headers = {
    "Content-Type": "application/json",
    "Accept": "text/plain",
    "charset": "UTF-8",
    "User-Agent": _cfg["my_agent"],
}


# Save issued token (Token value, expiration: 1 day. Re-requesting within 6 hours returns the same token, notification sent on issuance)
def save_token(my_token, my_expired):
    # print(type(my_expired), my_expired)
    valid_date = datetime.strptime(my_expired, "%Y-%m-%d %H:%M:%S")
    # print('Save token date: ', valid_date)
    with open(token_tmp, "w", encoding="utf-8") as f:
        f.write(f"token: {my_token}\n")
        f.write(f"valid-date: {valid_date}\n")


# Verify token (Token value, expiration: 1 day. Re-requesting within 6 hours returns the same token, notification sent on issuance)
def read_token():
    try:
        # Read the stored token file
        with open(token_tmp, encoding="UTF-8") as f:
            tkg_tmp = yaml.load(f, Loader=yaml.FullLoader)

        # Token expiration date/time
        exp_dt = tkg_tmp["valid-date"]
        # If it's a string, convert to datetime
        if isinstance(exp_dt, str):
            exp_dt = datetime.strptime(exp_dt, "%Y-%m-%d %H:%M:%S")

        # Current time + 1 hour (Buffer)
        now_dt_plus_buffer = datetime.now() + timedelta(hours=1)

        # print('expire dt: ', exp_dt, ' vs check dt:', now_dt_plus_buffer)
        # Check expiration (Return stored token if expiration > current time + buffer)
        if exp_dt > now_dt_plus_buffer:
            return tkg_tmp
        else:
            logging.info(f'\033[31mNeed new token (Expires soon or expired): {tkg_tmp["valid-date"]}\033[0m')
            return None
    except Exception as e:
        logging.error(f'\033[31mread token error: {e}\033[0m')
        return None


# Check token validity and re-issue if the token has expired
def _getBaseHeader():
    if _autoReAuth:
        reAuth()
    return copy.deepcopy(_base_headers)


# Fetch: App Key, App Secret, Comprehensive Account (8 digits), Product Code (2 digits), Token, Domain
def _setTRENV(cfg):
    nt1 = namedtuple(
        "KISEnv",
        ["my_app", "my_sec", "my_acct", "my_prod", "my_htsid", "my_token", "my_url", "my_url_ws"],
    )
    d = {
        "my_app": cfg["my_app"],  # App Key
        "my_sec": cfg["my_sec"],  # App Secret
        "my_acct": cfg["my_acct"],  # Comprehensive Account (8 digits)
        "my_prod": cfg["my_prod"],  # Product Code (2 digits)
        "my_htsid": cfg["my_htsid"],  # HTS ID
        "my_token": cfg["my_token"],  # Token
        "my_url": cfg[
            "my_url"
        ],  # Real Trading Domain (https://openapi.koreainvestment.com:9443)
        "my_url_ws": cfg["my_url_ws"],
    }  # Paper Trading Domain (https://openapivts.koreainvestment.com:29443)

    # print(cfg['my_app'])
    global _TRENV
    _TRENV = nt1(**d)


def isPaperTrading():  # Paper Trading
    return _isPaper


# Set svr='prod' for Real Trading, svr='vps' for Paper Trading.
def changeTREnv(token_key, svr="prod", product=_cfg["my_prod"]):
    cfg = dict()

    global _isPaper
    if svr == "prod":  # Real Trading
        ak1 = "my_app"  # App Key for Real Trading
        ak2 = "my_sec"  # App Secret for Real Trading
        _isPaper = False
        _smartSleep = 0.05
    elif svr == "vps":  # Paper Trading
        ak1 = "paper_app"  # App Key for Paper Trading
        ak2 = "paper_sec"  # App Secret for Paper Trading
        _isPaper = True
        _smartSleep = 0.5

    cfg["my_app"] = _cfg[ak1]
    cfg["my_sec"] = _cfg[ak2]

    if svr == "prod" and product == "01":  # Real: Stock, Consignment, Investment Account
        cfg["my_acct"] = _cfg["my_acct_stock"]
    elif svr == "prod" and product == "03":  # Real: Futures & Options (Derivatives)
        cfg["my_acct"] = _cfg["my_acct_future"]
    elif svr == "prod" and product == "08":  # Real: Overseas Futures & Options
        cfg["my_acct"] = _cfg["my_acct_future"]
    elif svr == "prod" and product == "22":  # Real: Individual Pension Savings
        cfg["my_acct"] = _cfg["my_acct_stock"]
    elif svr == "prod" and product == "29":  # Real: Retirement Pension Account
        cfg["my_acct"] = _cfg["my_acct_stock"]
    elif svr == "vps" and product == "01":  # Paper: Stock, Consignment, Investment Account
        cfg["my_acct"] = _cfg["my_paper_stock"]
    elif svr == "vps" and product == "03":  # Paper: Futures & Options (Derivatives)
        cfg["my_acct"] = _cfg["my_paper_future"]

    cfg["my_prod"] = product
    cfg["my_htsid"] = _cfg["my_htsid"]
    cfg["my_url"] = _cfg[svr]

    try:
        my_token = _TRENV.my_token
    except AttributeError:
        my_token = ""
    cfg["my_token"] = my_token if token_key else token_key
    cfg["my_url_ws"] = _cfg["ops" if svr == "prod" else "vops"]

    # print(cfg)
    _setTRENV(cfg)


def _getResultObject(json_data):
    _tc_ = namedtuple("res", json_data.keys())

    return _tc_(**json_data)


def _handle_critical_error(msg):
    logging.error(msg)
    try:
        import display
        display.add_alert(msg, "ERROR")
    except ImportError:
        pass


# Token issuance, valid for 1 day. Re-requesting within 6 hours returns the same token, notification sent on issuance.
# For paper trading, change svr='vps'. For non-stock accounts (not 01), change product='XX' (last 2 digits of account).
def auth(svr="prod", product=_cfg["my_prod"], url=None):
    p = {
        "grant_type": "client_credentials",
    }
    # Fetch App Key and Secret from personal "kis_devlp.yaml" file.
    # Set the file name and location to a path known only to you.
    if svr == "prod":  # Real Trading
        ak1 = "my_app"  # App Key (Real)
        ak2 = "my_sec"  # App Secret (Real)
    elif svr == "vps":  # Paper Trading
        ak1 = "paper_app"  # App Key (Paper)
        ak2 = "paper_sec"  # App Secret (Paper)

    # Fetch App Key and App Secret
    p["appkey"] = _cfg[ak1]
    p["appsecret"] = _cfg[ak2]

    # Check if an issued token already exists
    saved_token_info = read_token()  # Check for existing token (Returns dict or None)

    global _token_expire_time

    if saved_token_info is None:  # Process issuance if no valid token is found
        url = f"{_cfg[svr]}/oauth2/tokenP"
        res = requests.post(
            url, data=json.dumps(p), headers=copy.deepcopy(_base_headers)
        )  # Token issuance call
        rescode = res.status_code
        if rescode == 200:  # Successful issuance
            my_token = _getResultObject(res.json()).access_token  # Get token value
            my_expired = _getResultObject(
                res.json()
            ).access_token_token_expired  # Get token expiration
            save_token(my_token, my_expired)  # Save the new token

            # my_expired format: "2025-01-01 12:00:00"
            _token_expire_time = datetime.strptime(my_expired, "%Y-%m-%d %H:%M:%S")
        else:
            _handle_critical_error("Get Authentification token fail!\nYou have to restart your app!!!")
            return
    else:
        my_token = saved_token_info["token"]  # Existing token found; use the existing token

        valid_date = saved_token_info["valid-date"]
        # Ensure it's a datetime object
        if isinstance(valid_date, str):
            valid_date = datetime.strptime(valid_date, "%Y-%m-%d %H:%M:%S")

        _token_expire_time = valid_date

    # Manage header values including the issued token, required for API calls
    changeTREnv(my_token, svr, product)

    _base_headers["authorization"] = f"Bearer {my_token}"
    _base_headers["appkey"] = _TRENV.my_app
    _base_headers["appsecret"] = _TRENV.my_sec

    logging.info(f"[{datetime.now()}] => get Access Token completed! (Exp: {_token_expire_time})")


# end of initialize, Re-authentication: Checks validity and re-issues token if expired
# Store in _token_expire_time during execution to check validity; re-issue token upon expiration.
def reAuth(svr="prod", product=_cfg["my_prod"]):
    if _token_expire_time is not None:
        if datetime.now() + timedelta(hours=1) >= _token_expire_time:
            auth(svr, product)


def getEnv():
    return _cfg


async def smart_sleep_async():
    if _DEBUG:
        logging.info(f"[RateLimit] Sleeping {_smartSleep}s ")
    await asyncio.sleep(_smartSleep)


def getTREnv():
    return _TRENV


# Function to receive a hash key for order APIs and set it in the header.
# Currently, the hash key is optional/can be omitted; used if tampering is a concern.
# Input: HTTP Header, HTTP post param
# Output: None
def set_order_hash_key(h, p):
    url = f"{getTREnv().my_url}/uapi/hashkey"  # Hashkey issuance API URL

    res = requests.post(url, data=json.dumps(p), headers=h)
    rescode = res.status_code
    if rescode == 200:
        h["hashkey"] = _getResultObject(res.json()).HASH
    else:
        _handle_critical_error(f"Error: {rescode}")


# Common class for handling API call responses
class APIResp:
    def __init__(self, resp):
        self._rescode = resp.status_code
        self._resp = resp
        self._header = self._setHeader()
        self._body = self._setBody()
        self._err_code = self._body.msg_cd
        self._err_message = self._body.msg1

    def getResCode(self):
        return self._rescode

    def _setHeader(self):
        fld = dict()
        for x in self._resp.headers.keys():
            if x.islower():
                fld[x] = self._resp.headers.get(x)
        _th_ = namedtuple("header", fld.keys())

        return _th_(**fld)

    def _setBody(self):
        _tb_ = namedtuple("body", self._resp.json().keys())

        return _tb_(**self._resp.json())

    def getHeader(self):
        return self._header

    def getBody(self):
        return self._body

    def getResponse(self):
        return self._resp

    def isOK(self):
        try:
            if self.getBody().rt_cd == "0":
                return True
            else:
                return False
        except:
            return False

    def getErrorCode(self):
        return self._err_code

    def getErrorMessage(self):
        return self._err_message

    def printAll(self):
        logging.debug("<Header>")
        for x in self.getHeader()._fields:
            val = getattr(self.getHeader(), x)
            # Mask sensitive tokens in header output
            if x.lower() in ["authorization", "appkey", "appsecret", "secretkey", "approval_key"]:
                val = "********"
            logging.debug(f"\t-{x}: {val}")
        logging.debug("<Body>")
        for x in self.getBody()._fields:
            val = getattr(self.getBody(), x)
            # Mask sensitive body fields
            if x.lower() in ["appkey", "appsecret", "secretkey"]:
                val = "********"
            logging.debug(f"\t-{x}: {val}")

    def printError(self, url):
        logging.error("-" * 31)
        logging.error(f"Error in response: {self.getResCode()} url={url}")
        logging.error(
            f"rt_cd : {self.getBody().rt_cd} / msg_cd : {self.getErrorCode()} / msg1 : {self.getErrorMessage()}"
        )
        logging.error("-" * 31)

    # end of class APIResp


class APIRespError(APIResp):
    def __init__(self, status_code, error_text):
        # Initialize directly without calling parent constructor
        self.status_code = status_code
        self.error_text = error_text
        self._error_code = str(status_code)
        self._error_message = error_text

    def isOK(self):
        return False

    def getErrorCode(self):
        return self._error_code

    def getErrorMessage(self):
        return self._error_message

    def getBody(self):
        # Return empty object (to prevent AttributeError on property access)
        class EmptyBody:
            def __getattr__(self, name):
                return None

        return EmptyBody()

    def getHeader(self):
        # Return empty object
        class EmptyHeader:
            tr_cont = ""

            def __getattr__(self, name):
                return ""

        return EmptyHeader()

    def printAll(self):
        logging.error(f"=== ERROR RESPONSE ===")
        logging.error(f"Status Code: {self.status_code}")
        logging.error(f"Error Message: {self.error_text}")
        logging.error(f"======================")

    def printError(self, url=""):
        msg = f"Error Code : {self.status_code} | {self.error_text}"
        if url:
            msg += f" (URL: {url})"

        _handle_critical_error(msg)


########### Common API Call Wrapping


def _url_fetch(
        api_url, ptr_id, tr_cont, params, appendHeaders=None, postFlag=False, hashFlag=True
):
    url = f"{getTREnv().my_url}{api_url}"

    headers = _getBaseHeader()  # Define basic header values

    # Set additional Headers
    tr_id = ptr_id
    if ptr_id[0] in ("T", "J", "C"):  # Check Real Trading TR ID
        if isPaperTrading():  # Identify Paper Trading TR ID
            tr_id = "V" + ptr_id[1:]

    headers["tr_id"] = tr_id  # Transaction TR ID
    headers["custtype"] = "P"  # General (Individual/Corporate) "P", Partner "B"
    headers["tr_cont"] = tr_cont  # Transaction TR ID

    if appendHeaders is not None:
        if len(appendHeaders) > 0:
            for x in appendHeaders.keys():
                headers[x] = appendHeaders.get(x)

    if _DEBUG:
        # Global masking helper
        def _mask_dict(d):
            if not isinstance(d, dict): return d
            masked = copy.deepcopy(d)
            for k in masked.keys():
                if k.lower() in ["appkey", "appsecret", "authorization", "secretkey", "approval_key", "my_hts_id"]:
                    masked[k] = "********"
            return masked

        logging.debug("< Sending Info >")
        logging.debug(f"URL: {url}, TR: {tr_id}")
        logging.debug(f"<header>\n{_mask_dict(headers)}")
        logging.debug(f"<body>\n{_mask_dict(params)}")

    if postFlag:
        # if (hashFlag): set_order_hash_key(headers, params)
        res = requests.post(url, headers=headers, data=json.dumps(params))
    else:
        res = requests.get(url, headers=headers, params=params)

    if res.status_code == 200:
        ar = APIResp(res)
        if _DEBUG:
            ar.printAll()
        return ar
    else:
        logging.error("Error Code : " + str(res.status_code) + " | " + res.text)
        return APIRespError(res.status_code, res.text)


# auth()
# print("Pass through the end of the line")


########### New - WebSocket Support

_base_headers_ws = {
    "content-type": "utf-8",
}


def _getBaseHeader_ws():
    if _autoReAuth:
        reAuth_ws()

    return copy.deepcopy(_base_headers_ws)


def auth_ws(svr="prod", product=_cfg["my_prod"]):
    p = {"grant_type": "client_credentials"}
    if svr == "prod":
        ak1 = "my_app"
        ak2 = "my_sec"
    elif svr == "vps":
        ak1 = "paper_app"
        ak2 = "paper_sec"

    p["appkey"] = _cfg[ak1]
    p["secretkey"] = _cfg[ak2]

    url = f"{_cfg[svr]}/oauth2/Approval"
    res = requests.post(url, data=json.dumps(p), headers=copy.deepcopy(_base_headers))  # Token issuance call
    rescode = res.status_code
    if rescode == 200:  # Successful issuance
        approval_key = _getResultObject(res.json()).approval_key
    else:
        _handle_critical_error("Get Approval token fail!\nYou have to restart your app!!!")
        return

    changeTREnv(None, svr, product)

    _base_headers_ws["approval_key"] = approval_key

    global _approval_received_time
    _approval_received_time = datetime.now()

    logging.info(f"[{_approval_received_time}] => get Approval Key completed!")


def reAuth_ws(svr="prod", product=_cfg["my_prod"]):
    if _approval_received_time is not None:
        if (datetime.now() - _approval_received_time).total_seconds() >= 86400:
            auth_ws(svr, product)


def data_fetch(tr_id, tr_type, params, appendHeaders=None) -> dict:
    headers = _getBaseHeader_ws()  # Define basic header values

    headers["tr_type"] = tr_type
    headers["custtype"] = "P"

    if appendHeaders is not None:
        if len(appendHeaders) > 0:
            for x in appendHeaders.keys():
                headers[x] = appendHeaders.get(x)

    if _DEBUG:
        def _mask_dict(d):
            if not isinstance(d, dict): return d
            masked = copy.deepcopy(d)
            for k in list(masked.keys()):
                if k.lower() in ["appkey", "appsecret", "authorization", "secretkey", "approval_key"]:
                    masked[k] = "********"
            return masked

        logging.debug(f"<Sending Info> TR: {tr_id}")
        logging.debug(f"<header>\n{_mask_dict(headers)}")

    inp = {
        "tr_id": tr_id,
    }
    inp.update(params)

    return {"header": headers, "body": {"input": inp}}


# Process system responses (Extraction of decryption keys, etc.)
def system_resp(data):
    isPingPong = False
    isUnSub = False
    isOk = False
    tr_msg = None
    tr_key = None
    encrypt, iv, ekey = None, None, None

    rdic = json.loads(data)

    tr_id = rdic["header"]["tr_id"]
    if tr_id != "PINGPONG":
        tr_key = rdic["header"]["tr_key"]
        encrypt = rdic["header"]["encrypt"]
    if rdic.get("body", None) is not None:
        isOk = True if rdic["body"]["rt_cd"] == "0" else False
        tr_msg = rdic["body"]["msg1"]
        # Extract keys for decryption
        if "output" in rdic["body"]:
            iv = rdic["body"]["output"]["iv"]
            ekey = rdic["body"]["output"]["key"]
        isUnSub = True if tr_msg[:5] == "UNSUB" else False
    else:
        isPingPong = True if tr_id == "PINGPONG" else False

    nt2 = namedtuple(
        "SysMsg",
        [
            "isOk",
            "tr_id",
            "tr_key",
            "isUnSub",
            "isPingPong",
            "tr_msg",
            "iv",
            "ekey",
            "encrypt",
        ],
    )
    d = {
        "isOk": isOk,
        "tr_id": tr_id,
        "tr_key": tr_key,
        "tr_msg": tr_msg,
        "isUnSub": isUnSub,
        "isPingPong": isPingPong,
        "iv": iv,
        "ekey": ekey,
        "encrypt": encrypt,
    }

    return nt2(**d)


def aes_cbc_base64_dec(key, iv, cipher_text):
    if key is None or iv is None:
        raise AttributeError("key and iv cannot be None")

    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))


##### Subscription Management
open_map: dict = {}


def add_open_map(
        name: str,
        request: Callable[[str, str, ...], (dict, list[str])],
        data: str | list[str],
        kwargs: dict = None,
):
    if open_map.get(name, None) is None:
        open_map[name] = {
            "func": request,
            "items": [],
            "kwargs": kwargs,
        }

    if type(data) is list:
        open_map[name]["items"] += data
    elif type(data) is str:
        open_map[name]["items"].append(data)
data_map: dict = {}


# Overseas TR Compatibility Mapping
# Real field counts per record in the WebSocket stream vs what's defined in official samples.
_OVERSEAS_TR_FIX = {
    "HDFSASP0": {"real_size": 71, "skip_idx": 2}, # Asking Price
    "HDFSCNT0": {"real_size": 26, "skip_idx": 2}, # Execution
    'H0GSCNI0': {'real_size': 25, 'skip_idx': 0},  # Market type MTYP at index 0 (Real)
    'H0GSCNI9': {'real_size': 25, 'skip_idx': 0},  # Market type MTYP at index 0 (Demo)
}

def add_data_map(
        tr_id: str,
        columns: list = None,
        encrypt: str = None,
        key: str = None,
        iv: str = None,
):
    if data_map.get(tr_id, None) is None:
        data_map[tr_id] = {"columns": [], "encrypt": False, "key": None, "iv": None}

    if columns is not None:
        data_map[tr_id]["columns"] = columns

    if encrypt is not None:
        data_map[tr_id]["encrypt"] = encrypt

    if key is not None:
        data_map[tr_id]["key"] = key

    if iv is not None:
        data_map[tr_id]["iv"] = iv


class KISWebSocket:
    api_url: str = ""
    on_result: Callable[
        [websockets.ClientConnection, str, pd.DataFrame, dict], None
    ] = None
    result_all_data: bool = False

    retry_count: int = 0
    amx_retries: int = 0

    # init
    def __init__(self, api_url: str, max_retries: int = 3):
        self.api_url = api_url
        self.max_retries = max_retries

    # private
    async def __subscriber(self, ws: websockets.ClientConnection):
        async for raw in ws:
            # Debug: Log ALL raw messages at the very beginning
            logging.debug(f"### [RAW RECV] {raw[:200]}...")

            show_result = False
            df = pd.DataFrame()

            if raw[0] in ["0", "1"]:
                # Standard format: 0(or 1)|TR_ID|COUNT|DATA|
                parts = raw.split("|", 3)
                if len(parts) < 4:
                    logging.warning(f"Malformed real-time message: {raw}")
                    continue

                tr_id = parts[1].strip()
                count_str = parts[2]
                data_segment = parts[3]

                dm = data_map.get(tr_id)
                if not dm:
                    logging.warning(f"No column mapping for TR {tr_id}")
                    continue

                # Decrypt if lead-char is '1'
                if raw[0] == '1':
                    if dm.get("key") and dm.get("iv"):
                        data_segment = aes_cbc_base64_dec(dm["key"], dm["iv"], data_segment)
                    else:
                        logging.warning(f"Decryption failed: No key/iv for TR {tr_id}")
                        continue

                # Remove trailing pipe
                if data_segment.endswith("|"):
                    data_segment = data_segment[:-1]

                if "^" in data_segment:
                    raw_values = data_segment.split("^")
                else:
                    raw_values = data_segment.split("|")

                # Prepend the market division code (e.g. '1' or '0') for Overseas Notifications
                # to align with official column definitions (CUST_ID, ACNT_NO, etc.)
                if tr_id in ["H0GSCNI0", "H0GSCNI9"]:
                    raw_values.insert(0, raw[0])

                num_cols = len(dm["columns"])
                if num_cols == 0:
                    logging.warning(f"TR {tr_id} has 0 columns defined.")
                    continue

                # Record size and Alignment compatibility
                fix = _OVERSEAS_TR_FIX.get(tr_id)
                real_size = fix["real_size"] if fix else num_cols

                try:
                    count = int(count_str)
                except:
                    count = 1

                records = []
                # Process records based on actual stream size
                for i in range(0, len(raw_values), real_size):
                    record = raw_values[i:i + real_size]
                    if len(record) < real_size: continue

                    # Apply alignment skip if needed (skipping index 2 to align with official files)
                    if fix and "skip_idx" in fix:
                        s = fix["skip_idx"]
                        record = record[:s] + record[s+1:]

                    # Truncate to match official column definition
                    records.append(record[:num_cols])

                # Failsafe: if count is 1 but we produced multiple records due to size mismatch,
                # only keep the first one to avoid treating trailing fields as new records.
                if count == 1 and len(records) > 1:
                    records = [records[0]]

                if records:
                    df = pd.DataFrame(records, columns=dm["columns"])
                    show_result = True
                else:
                    logging.warning(f"Could not parse records for {tr_id}. len={len(raw_values)}, cols={num_cols}, count={count}")

            else:
                rsp = system_resp(raw)

                tr_id = rsp.tr_id
                add_data_map(
                    tr_id=rsp.tr_id, encrypt=rsp.encrypt, key=rsp.ekey, iv=rsp.iv
                )

                if rsp.isPingPong:
                    # logging.info(f"### RECV [PINGPONG] [{raw}]")
                    await ws.pong(raw)
                    # logging.info(f"### SEND [PINGPONG] [{raw}]")
                    show_result = True  # Allow PINGPONG to trigger on_result for testing

                if self.result_all_data:
                    show_result = True

            if show_result is True and self.on_result is not None:
                self.on_result(ws, tr_id, df, data_map[tr_id])

    # Reconnection wait times: 5s, 30s, 1m, 5m, 20m (no limit on attempts)
    WAIT_TIMES = [5, 30, 60, 300, 1200]

    def _check_server_connectivity(self, host: str, port: int, timeout: float = 3) -> dict:
        """Test TCP connectivity to the WebSocket server."""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return {"reachable": result == 0, "error_code": result}
        except Exception as e:
            return {"reachable": False, "error": str(e)}

    def _add_alert(self, message: str, level: str = "INFO"):
        """Add alert to UI display."""
        try:
            import display
            first_line = message.split('\n')[0][:60]
            display.add_alert(f"[WS] {first_line}", level)
        except Exception as e:
            logging.error(f"Failed to add alert: {e}")

    def _send_telegram_notification(self, message: str):
        """Send notification via Telegram (thread-safe)."""
        try:
            from telegram_bot.telegram_utils import send_notification
            send_notification(message, parse_mode='HTML')
        except Exception as e:
            logging.warning(f"Failed to send Telegram notification: {e}")

    def _update_ws_status(self, status: str):
        """Update WebSocket connection status in thread_state."""
        try:
            from thread_state import update_kis_state, WebSocketStatus
            status_map = {
                "connected": WebSocketStatus.CONNECTED,
                "connecting": WebSocketStatus.CONNECTING,
                "reconnecting": WebSocketStatus.RECONNECTING,
                "disconnected": WebSocketStatus.DISCONNECTED,
                "error": WebSocketStatus.ERROR,
            }
            if status in status_map:
                update_kis_state(ws_status=status_map[status])
        except Exception as e:
            logging.debug(f"Failed to update ws_status: {e}")

    async def __runner(self):
        if len(open_map.keys()) > 40:
            raise ValueError("Subscription's max is 40")

        url = f"{getTREnv().my_url_ws}{self.api_url}"
        was_connected = False  # Track if we were previously connected

        while True:
            try:
                # Log approval key time remaining before connect attempt
                if _approval_received_time is not None:
                    elapsed = (datetime.now() - _approval_received_time).total_seconds()
                    remaining_hours = max(0, (86400 - elapsed) / 3600)
                    logging.info(f"Connecting to WebSocket: {url} (Approval key: {remaining_hours:.1f}h remaining)")
                else:
                    logging.info(f"Connecting to WebSocket: {url}")
                async with websockets.connect(url, ping_interval=60, ping_timeout=120) as ws:
                    # Send reconnection success notification if we were reconnecting
                    if self.retry_count > 0:
                        self._send_telegram_notification(
                            f"✅ <b>WebSocket Reconnected</b>\n"
                            f"Successfully reconnected after {self.retry_count} attempt(s)."
                        )
                    self.retry_count = 0  # Reset on successful connection
                    was_connected = True
                    self._update_ws_status("connected")
                    logging.info("WebSocket Connected!")
                    self._add_alert("WebSocket Connected!", "SUCCESS")

                    # Request initial subscriptions
                    for name, obj in open_map.items():
                        await self.send_multiple(
                            ws, obj["func"], "1", obj["items"], obj["kwargs"]
                        )

                    # Start subscriber loop
                    await asyncio.gather(
                        self.__subscriber(ws),
                    )
            except websockets.exceptions.ConnectionClosed as e:
                self._update_ws_status("reconnecting")
                logging.warning(f"WebSocket Connection Closed: {e}")
                self._add_alert(f"Connection Closed (#{self.retry_count + 1}): {e}")
                # Send disconnect notification on first disconnect
                if self.retry_count == 0:
                    self._send_telegram_notification(
                        f"⚠️ <b>WebSocket Disconnected</b>\n"
                        f"Connection closed: {e}\n"
                        f"Attempting to reconnect..."
                    )
                # Send status update every 5 failed attempts
                elif (self.retry_count + 1) % 5 == 0:
                    self._send_telegram_notification(
                        f"❌ <b>WebSocket Reconnection Failed</b>\n"
                        f"Attempt {self.retry_count + 1} failed.\n"
                        f"Error: Connection closed"
                    )
            except Exception as e:
                self._update_ws_status("reconnecting")
                logging.error(f"WebSocket Connection Error: {e}")
                self._add_alert(f"Connection Error (#{self.retry_count + 1}): {e}")
                # Send disconnect notification on first disconnect
                if self.retry_count == 0:
                    self._send_telegram_notification(
                        f"⚠️ <b>WebSocket Disconnected</b>\n"
                        f"Error: {e}\n"
                        f"Attempting to reconnect..."
                    )
                # Send status update every 5 failed attempts
                elif (self.retry_count + 1) % 5 == 0:
                    self._send_telegram_notification(
                        f"❌ <b>WebSocket Reconnection Failed</b>\n"
                        f"Attempt {self.retry_count + 1} failed.\n"
                        f"Error: {e}"
                    )

            self.retry_count += 1

            # Check and refresh approval_key if expired (24h validity)
            try:
                if _approval_received_time is not None:
                    elapsed = (datetime.now() - _approval_received_time).total_seconds()
                    if elapsed >= 86400:  # 24 hours
                        logging.info("[Auth] Approval key expired, re-authenticating...")
                        self._add_alert("Approval key expired, refreshing...")
                        reAuth_ws()
                        logging.info("[Auth] Approval key refreshed successfully")
                        self._add_alert("Approval key refreshed successfully")
            except Exception as e:
                logging.error(f"[Auth] Failed to refresh approval key: {e}")
                self._add_alert(f"Key refresh FAILED: {e}")
                self._send_telegram_notification(
                    f"🔑 <b>Approval Key Refresh Failed</b>\n"
                    f"Error: {e}\n"
                    f"Manual intervention may be required."
                )

            # Check server connectivity and log result
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                host = parsed.hostname or "ops.koreainvestment.com"
                port = parsed.port or 21000
                conn_check = self._check_server_connectivity(host, port)
                if conn_check.get("reachable"):
                    logging.info(f"[Connectivity] Server {host}:{port} is reachable")
                else:
                    error_info = conn_check.get("error") or f"error_code={conn_check.get('error_code')}"
                    logging.warning(f"[Connectivity] Server {host}:{port} is NOT reachable: {error_info}")
                    # Show alert every 5 attempts to avoid spam
                    if self.retry_count % 5 == 0:
                        self._add_alert(f"Server unreachable (#{self.retry_count}): {error_info}")
            except Exception as e:
                logging.warning(f"[Connectivity] Check failed: {e}")

            # Custom wait times: 5s, 30s, 1m, 5m, 20m
            wait_idx = min(self.retry_count - 1, len(self.WAIT_TIMES) - 1)
            wait_time = self.WAIT_TIMES[max(0, wait_idx)]
            logging.info(f"Reconnecting in {wait_time} seconds (Attempt {self.retry_count})...")

            await asyncio.sleep(wait_time)

    # func
    @classmethod
    async def send(
            cls,
            ws: websockets.ClientConnection,
            request: Callable[[str, str, ...], (dict, list[str])],
            tr_type: str,
            data: str,
            kwargs: dict = None,
    ):
        k = {} if kwargs is None else kwargs
        msg, columns = request(tr_type, data, **k)

        add_data_map(tr_id=msg["body"]["input"]["tr_id"], columns=columns)

        # Mask sensitive data in WebSocket logs
        def _mask_recursive(d):
            if isinstance(d, dict):
                return {k: ("********" if k.lower() in ["appkey", "secretkey", "tr_key", "approval_key"] else _mask_recursive(v)) for k, v in d.items()}
            elif isinstance(d, list):
                return [_mask_recursive(i) for i in d]
            return d

        logging.info("send message >> %s" % json.dumps(_mask_recursive(msg)))

        await ws.send(json.dumps(msg))
        await asyncio.sleep(0.5) # Reverted to 0.5s as requested

    async def send_multiple(
            self,
            ws: websockets.ClientConnection,
            request: Callable[[str, str, ...], (dict, list[str])],
            tr_type: str,
            data: list | str,
            kwargs: dict = None,
    ):
        if type(data) is str:
            await self.send(ws, request, tr_type, data, kwargs)
        elif type(data) is list:
            for d in data:
                await self.send(ws, request, tr_type, d, kwargs)
        else:
            raise ValueError("data must be str or list")

    @classmethod
    def subscribe(
            cls,
            request: Callable[[str, str, ...], (dict, list[str])],
            data: list | str,
            kwargs: dict = None,
    ):
        add_open_map(request.__name__, request, data, kwargs)

    def unsubscribe(
            self,
            ws: websockets.ClientConnection,
            request: Callable[[str, str, ...], (dict, list[str])],
            data: list | str,
    ):
        self.send_multiple(ws, request, "2", data)

    # start loop
    def start(
            self,
            on_result: Callable[
                [websockets.ClientConnection, str, pd.DataFrame, dict], None
            ],
            result_all_data: bool = False,
    ):
        self.on_result = on_result
        self.result_all_data = result_all_data
        try:
            asyncio.run(self.__runner())
        except KeyboardInterrupt:
            print("Closing by KeyboardInterrupt")
