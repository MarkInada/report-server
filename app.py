#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# api
import flask
from flask import session, app
import requests

# date
import datetime
from datetime import timedelta
import jpholiday

# util
from argparse import ArgumentParser
import json
import os
import sys
from io import BytesIO, StringIO

# own
from redmine_util import redmine_util
from microsoft_util import microsoft_util

WORKING = "working"
NOTWORKING = "notworking"
Current = None

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # enable non-HTTPS for testing
app = flask.Flask(__name__, template_folder='static/templates')
app.debug = True
app.secret_key = 'development'
SESSION = requests.Session()

class Work:
    def __init__(self):
        self.state = NOTWORKING
        self.start = ""
        self.bearer = ""

    def set(self, job):
        self.state = job
        self.start = "9:30"

    def auth(self, token):
        self.bearer = token

    def begin(self):
        self.state = WORKING
        self.start = str(datetime.datetime.now().hour)+":"+str(datetime.datetime.now().minute)

    def end(self):
        self.state = NOTWORKING

def isHoliday(data):
    target = datetime.date(int(data[0:4]), int(data[4:6]), int(data[6:8]))
    if target.weekday() >= 5 or jpholiday.is_holiday(target):
        return True
    else:
        return False

@app.after_request
def after_request(response):
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
  return response

@app.route('/ping', methods=['GET'])
def ping():
    status = 200
    return flask.Response(response='pong\n', status=status, mimetype='application/json')

@app.route('/init', methods=['POST'])
def init():
    app.logger.info("init")
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)
    app.logger.info(data['job'])
    Current.set(data['job'])
    status = 200
    out = StringIO()
    x = '{ "id":' + ' 1, "title": "test' + '" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=status, mimetype='application/json')

@app.route('/state', methods=['GET'])
def state():
    app.logger.info("state")
    status = 200
    out = StringIO()
    x = '{ "State":"' + Current.state + '" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=status, mimetype='application/json')

@app.route('/hello', methods=['POST'])
def hello():
    app.logger.info("hello")
    session.permanent = True
    Current.begin()
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)
    Current.auth(data['token'])

    mgraph = microsoft_util.Mgraph(Current.bearer)

    rissues = redmine_util.Rissues(data['redmine_url'], data['redmine_id'], data['redmine_pw'], int(data['redmine_user_id']), app.logger)
    issue_results, _ = rissues.getIssues(False)

    result = ""
    result += "各位\n\n"
    result += data['department'] + "の" + data['name'] + "です\n\n"
    if not len(data['comment']) == 0:
        result += data['comment'] + "\n\n"
    result += "【勤務予定】" + Current.start + "～18:30\n\n"
    result += "本日の予定\n"

    priority = ""
    for issue_result in issue_results:
        for issue in issue_result:
            if priority != issue.priority.name:
                priority = issue.priority.name
                result += "\n優先度: " + issue.priority.name + "\n"
            result += '- 作業: Redmine%d:%s/【%s】%s\n' % (issue.id, issue.project.name, issue.tracker.name, issue.subject)
            result += '  - 作業状況: %s\n' % issue.status.name
            try:
                result += '  - 期日:%s\n' % issue.due_date
            except:
                result += '  - 期日:%s\n' % "None"
                pass

    app.logger.info("redmine done" + result)
    
    result += "\n\n"
    result += "イベント\n"

    todayEvents, error = mgraph.getEvents(datetime.date.today()) 
    if error: return flask.Response(response="ERROR", status="ms graph error", mimetype='text/json')
    for evet in todayEvents['value']:
        if data['email'] == evet["organizer"]["emailAddress"]["address"]:
            result += "- " + evet["subject"] + "\n"
            continue
        for attend in evet["attendees"]:
            if data['email'] == attend["emailAddress"]["address"]:
                result += "- " + evet["subject"] + "\n"
                break
    else:
        result += "\n"

    app.logger.info("hello done" + result)

    emailtitle = '【始業連絡】'+datetime.date.today().strftime('%Y/%m/%d')
    error = mgraph.sendMail(emailtitle, result, data['to_recipients'], data['cc_recipients'])
    if error:
        return flask.Response(response="ERROR", status="ms graph error", mimetype='text/json')

    out = StringIO()
    x = '{ "result": "true" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=200, mimetype='text/json')

@app.route('/goodbye', methods=['POST'])
def goodbye():
    app.logger.info("goodbye")
    session.permanent = True
    Current.end()
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)
    Current.auth(data['token'])

    mgraph = microsoft_util.Mgraph(Current.bearer)

    rissues = redmine_util.Rissues(data['redmine_url'], data['redmine_id'], data['redmine_pw'], int(data['redmine_user_id']), app.logger)
    doing_issues, changed_issues = rissues.getIssues(True)

    result = ""
    result += "各位\n\n"
    result += data['department'] + "の" + data['name'] + "です\n\n"
    if not len(data['comment']) == 0:
        result += data['comment'] + "\n\n"
    result += "【勤務実績】" + Current.start + "～" + str(datetime.datetime.now().hour)+":"+str(datetime.datetime.now().minute) + "\n\n"
    result += "業務\n"

    priority = ""
    for issue_result in changed_issues:
        for issue in issue_result:
            if priority != issue.priority.name:
                priority = issue.priority.name
                result += "\n優先度: " + issue.priority.name + "\n"
            result += '- 作業: Redmine%d:%s/【%s】%s\n' % (issue.id, issue.project.name, issue.tracker.name, issue.subject)
            result += '  - 作業状況: %s\n' % issue.status.name
            try:
                result += '  - 期日:%s\n' % issue.due_date
            except:
                result += '  - 期日:%s\n' % "None"
                pass  
            
    app.logger.info("redmine done" + result)

    result += "\n\n"
    result += "イベント\n"

    todayEvents, error = mgraph.getEvents(datetime.date.today()) 
    if error: return flask.Response(response="ERROR", status="ms graph error", mimetype='text/json')
    for evet in todayEvents['value']:
        if data['email'] == evet["organizer"]["emailAddress"]["address"]:
            result += "- " + evet["subject"] + "\n"
            continue
        for attend in evet["attendees"]:
            if data['email'] == attend["emailAddress"]["address"]:
                result += "- " + evet["subject"] + "\n"
                break
    else:
        result += "\n"

    start = datetime.date.today() + timedelta(days=1)
    for i in range (100):
        todayEvents, error = mgraph.getEvents(start) 
        if error: return flask.Response(response="ERROR", status="ms graph error", mimetype='text/json')
        for evet in todayEvents['value']:
            if data['email'] == evet["organizer"]["emailAddress"]["address"]:
                if "休暇" == evet["subject"]:
                    start = start + timedelta(days=2)
        if isHoliday(start.strftime('%Y%m%d')):
            start = start + timedelta(days=1)
        else:
            break
    else:
        app.logger.info("bad date")
    end = start + timedelta(days=1)

    result += "【次の勤務予定】" + start.strftime('%Y/%m/%d') + " 9:30～18:30\n\n"
    result += "業務\n"

    priority = ""
    for issue_result in doing_issues:
        for issue in issue_result:
            if priority != issue.priority.name:
                priority = issue.priority.name
                result += "\n優先度: " + issue.priority.name + "\n"
            result += '- 作業: Redmine%d:%s/【%s】%s\n' % (issue.id, issue.project.name, issue.tracker.name, issue.subject)
            result += '  - 作業状況: %s\n' % issue.status.name
            try:
                result += '  - 期日:%s\n' % issue.due_date
            except:
                result += '  - 期日:%s\n' % "None"
                pass

    result += "\n\n"
    result += "イベント\n"
    todayEvents, error = mgraph.getEvents(start) 
    if error: return flask.Response(response="ERROR", status="ms graph error", mimetype='text/json')
    for evet in todayEvents['value']:
        if data['email'] == evet["organizer"]["emailAddress"]["address"]:
            result += "- " + evet["subject"] + "\n"
            continue
        for attend in evet["attendees"]:
            if data['email'] == attend["emailAddress"]["address"]:
                result += "- " + evet["subject"] + "\n"
                break
    else:
        result += "\n"

    app.logger.info("goodbye done" + result)

    emailtitle = '【終業連絡】'+datetime.date.today().strftime('%Y/%m/%d')
    error = mgraph.sendMail(emailtitle, result, data['to_recipients'], data['cc_recipients'])
    if error:
        return flask.Response(response="ERROR", status="ms graph error", mimetype='text/json')

    out = StringIO()
    x = '{ "result": "true" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=200, mimetype='text/json')

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=5000)
    parser.add_argument('--debug', default=True)
    return parser.parse_args()

if __name__ == '__main__':
    try:
        Current = Work()
        args = parse_args()
        app.run(host=args.host, port=args.port, debug=True)
    except Exception as e:
        app.logger.info(e)
    sys.exit(0)