# mongo
import pymongo
from pymongo import DESCENDING
from pymongo import ASCENDING
from bson import ObjectId
from datetime import datetime
import base64

STATUS_DOING = "doing"
STATUS_FAILED = "failed"
STATUS_DONE = "done"

class RecordDB:
    def __init__(self, url: str, user: str, pw: str):
        if len(user) == 0:
            self.client = pymongo.MongoClient(url)
        else:
            self.client = pymongo.MongoClient(url, username=url, password=pw)

    def insertRequest(self, address: str, state: str):
        addb64 = base64.b64encode(address.encode()).decode('utf-8')
        db = self.client.get_database(addb64)
        result = db[addb64].insert_one({
            'state': state,
            'datetime': datetime.now(),
            'status': STATUS_DOING
        })
        return result

    def updateResult(self, address: str, status: str):
        result = "db update error"
        addb64 = base64.b64encode(address.encode()).decode('utf-8')
        db = self.client.get_database(addb64)
        cursor = db[addb64].find().sort([('datetime', DESCENDING)]).limit(1)
        for doc in cursor:
            query_filter1 = {'_id': ObjectId(doc['_id'])}
            result = db[addb64].update_one(query_filter1, {'$set': {'status': status}})
        return result

    def getLastStateAndStatus(self, address: str):
        state = ""
        status = ""
        addb64 = base64.b64encode(address.encode()).decode('utf-8')
        db = self.client.get_database(addb64)
        cursor = db[addb64].find().sort([('datetime', DESCENDING)]).limit(1)
        for doc in cursor:
            state = doc['state']
            status = doc['status']
        return state, status
