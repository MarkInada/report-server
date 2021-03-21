import os
from os.path import join, dirname
from dotenv import load_dotenv
import base64

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

REDIS_URL = os.environ.get("REDIS_URL")

b64pw = os.environ.get("REDIS_PASS").encode()
if len(b64pw) != 0:
    # insert password to redis://:[HERE!!]@ec2
    pw = base64.b64decode(b64pw).decode()
    idx = REDIS_URL.rfind(r'@')
    REDIS_URL = REDIS_URL[:idx] + pw + REDIS_URL[idx:]
