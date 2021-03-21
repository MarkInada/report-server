import os
from os.path import join, dirname
from dotenv import load_dotenv
import base64

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

b64redis = os.environ.get("REDIS_URL").encode()
REDIS_URL = base64.b64decode(b64redis).decode()