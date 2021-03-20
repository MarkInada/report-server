import datetime
from datetime import timedelta
import requests
import json

MESSAGE_STRUCT = {
  "message": {
    "subject": "Title",
    "body": {
      "contentType": "Text",
      "content": "TextBody"
    },
    "toRecipients": [
      {
        "emailAddress": {
          "address": "Address"
        }
      }
    ],
    "ccRecipients": [
      {
        "emailAddress": {
          "address": "Address"
        }
      }
    ]
  },
  "saveToSentItems": "true"
}

class Mgraph:
    def __init__(self, bearer):
        self.bearer = bearer

    def getEvents(self, start):
        error = False
        end = start + timedelta(days=1)
        response = self.getGraph("https://graph.microsoft.com/v1.0/me/calendar/calendarView",
                                self.bearer,
                                params={
                                    'startDateTime': start.isoformat(),
                                    'endDateTime': end.isoformat(),
                                    '$orderby': 'start/dateTime',
                                })
        if response.status_code != 200:
            error = True
        return response.json(), error

    def sendMail(self, title, message, to, cc):
        error = False

        sendMsg = MESSAGE_STRUCT
        sendMsg['message']['subject'] = title
        sendMsg['message']['body']['content'] = message
        sendMsg['message']['toRecipients'][0]['emailAddress']['address'] = to
        sendMsg['message']['ccRecipients'][0]['emailAddress']['address'] = cc

        response = self.postGraph("https://graph.microsoft.com/v1.0/me/sendMail",
                                self.bearer,
                                sendMsg)
        if response.status_code != 202:
            error = True
        return error

    def getGraph(self, path, bearer, params={}):
        headers = {
            'Authorization': 'Bearer %s' % self.bearer,
            'Prefer': 'outlook.timezone="Asia/Tokyo", outlook.body-content-type="text"'
        }
        response = requests.get(
            path,
            params=params,
            headers=headers,
        )
        return response

    def postGraph(self, path, bearer, message):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.bearer
        }
        response = requests.post(
            path,
            json.dumps(message),
            headers=headers,
            proxies={
                        'http': '',
                        'https': '',
                    },
            timeout=10
        )
        return response