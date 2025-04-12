# main.py 主逻辑：包括字段拼接、模拟请求
import re
import json
import time
import random
import logging
import hashlib
import requests
import urllib.parse
from push import push
from config import dataArray, headers, cookies, READ_NUM, PUSH_METHOD
import uuid

# 配置日志格式
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')

# 加密盐及其它默认值
KEY = "3c5c8717f3daf09iop3423zafeqoi"
COOKIE_DATA = {"rq": "%2Fweb%2Fbook%2Fread"}
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"
NOTIFY_URL = "https://weread.qq.com/web/login/notify"

def encode_data(data):
    """数据编码"""
    return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))


def cal_hash(input_string):
    """计算哈希值"""
    _7032f5 = 0x15051505
    _cc1055 = _7032f5
    length = len(input_string)
    _19094e = length - 1

    while _19094e > 0:
        _7032f5 = 0x7fffffff & (_7032f5 ^ ord(input_string[_19094e]) << (length - _19094e) % 30)
        _cc1055 = 0x7fffffff & (_cc1055 ^ ord(input_string[_19094e - 1]) << _19094e % 30)
        _19094e -= 2

    return hex(_7032f5 + _cc1055)[2:].lower()


def get_wr_skey():
    """刷新cookie密钥"""
    response = requests.post(RENEW_URL, headers=headers, cookies=cookies,
                             data=json.dumps(COOKIE_DATA, separators=(',', ':')))
    for cookie in response.headers.get('Set-Cookie', '').split(';'):
        if "wr_skey" in cookie:
            return cookie.split('=')[-1][:8]
    return None

def pre_reading():
    new_trace_id_1 = str(uuid.uuid4().hex)
    new_trace_id_2 = str(uuid.uuid4().hex[:16])
    if 'sentry-trace' in headers:
        logging.info(f"sentry-trace:{headers['sentry-trace']}")
        headers['sentry-trace'] = f"{new_trace_id_1}-{new_trace_id_2}"
        logging.info(f"sentry-trace:{headers['sentry-trace']}")
    else:
        logging.warning("No sentry-trace")
    
    if 'baggage' in headers:
        logging.info(f"baggage:{headers['baggage']}")
        pairs = headers['baggage'].split(',')
        updated_pairs = [
            f"sentry-trace_id={new_trace_id_1}" if pair.startswith("sentry-trace_id=") else pair
            for pair in pairs
        ]
        headers['baggage'] = ','.join(updated_pairs)
        logging.info(f"baggage:{headers['baggage']}")
    else:
        logging.warning("No baggage")
    response = requests.get(NOTIFY_URL, headers=headers, cookies=cookies)
    logging.info(f"🔄 prereading: {response}")

pre_reading()
total_ream_time_in_seconds = 0
index = 1
while index <= READ_NUM:
    data = dataArray[index % len(dataArray)]
    data.pop('s',None)
    data['ct'] = int(time.time())
    data['ts'] = int(time.time() * 1000)
    data['rn'] = random.randint(0, 1000)
    data['sg'] = hashlib.sha256(f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
    # Add a random read time
    # random_read_time = random.randint(28, 120)
    random_read_time = 30
    data['rt'] = random_read_time
    # prepare hash
    data['s'] = cal_hash(encode_data(data))
    logging.info(f"⏱️ 尝试第 {index} 次阅读, 时间：{random_read_time}s, data['co']: {data['co']}...")

    # Sleep to mimic reading
    time.sleep(random_read_time + 10)
    response = requests.post(READ_URL, headers=headers, cookies=cookies, data=json.dumps(data, separators=(',', ':')))
    resData = response.json()

    if 'succ' in resData:
        index += 1
        # update the total read time counter
        total_ream_time_in_seconds += random_read_time
        logging.info(f"✅ 阅读成功，阅读进度：{total_ream_time_in_seconds // 60} 分钟")

    else:
        logging.error(f"阅读失败，response：{resData}")
        logging.warning("❌ cookie 已过期，尝试刷新...")
        new_skey = get_wr_skey()
        if new_skey:
            cookies['wr_skey'] = new_skey
            logging.info(f"✅ 密钥刷新成功，新密钥：{new_skey}")
            logging.info(f"🔄 重新本次阅读。")
        else:
            ERROR_CODE = "❌ 无法获取新密钥或者WXREAD_CURL_BASH配置有误，终止运行。"
            logging.error(ERROR_CODE)
            push(ERROR_CODE, PUSH_METHOD)
            raise Exception(ERROR_CODE)
    data.pop('s', None)

logging.info("🎉 阅读脚本已完成！")

if PUSH_METHOD not in (None, ''):
    logging.info("⏱️ 开始推送...")
    push(f"🎉 微信读书自动阅读完成！\n⏱️ 阅读时长：{total_ream_time_in_seconds // 60}分钟。", PUSH_METHOD)
