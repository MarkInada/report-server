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
from record_util import record_util

# celery
from os.path import join, dirname
from celery import Celery
import settings
import time

def make_celery(app):
  celery = Celery(
    app.name,
    backend=app.config['CELERY_RESULT_BACKEND'],
    broker=app.config['CELERY_BROKER_URL']
  )
  celery.conf.update(app.config)

  class ContextTask(celery.Task):
    def __call__(self, *args, **kwargs):
      with app.app_context():
        return self.run(*args, **kwargs)

  celery.Task = ContextTask
  return celery

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # enable non-HTTPS for testing
app = flask.Flask(__name__)
app.debug = True
app.secret_key = 'development'
app.config.update(
  CELERY_BROKER_URL=settings.REDIS_URL,
  CELERY_RESULT_BACKEND=settings.REDIS_URL
)

SESSION = requests.Session()
celery = make_celery(app)

WORKING = "working"
NOTWORKING = "notworking"

def isHoliday(data):
    target = datetime.date(int(data[0:4]), int(data[4:6]), int(data[6:8]))
    if target.weekday() >= 5 or jpholiday.is_holiday(target):
        return True
    else:
        return False

@celery.task
def hello_task(data):
    # db: write hello state
    db = record_util.RecordDB(settings.MONGO_URL, settings.MONGO_USER, settings.MONGO_PW)
    result = db.insertRequest(data['email'], WORKING)
    app.logger.info(result)

    mgraph = microsoft_util.Mgraph(data['token'])

    rissues = redmine_util.Rissues(data['redmine_url'], data['redmine_id'], data['redmine_pw'], int(data['redmine_user_id']), app.logger)
    issue_results, _ = rissues.getIssues(False)

    result = ""
    result += "各位\n\n"
    result += data['department'] + "の" + data['name'] + "です\n\n"
    if not len(data['comment']) == 0:
        result += data['comment'] + "\n\n"
    result += "【勤務予定】" + str(datetime.datetime.now().hour)+":"+str(datetime.datetime.now().minute) + "～18:30\n\n"
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
    if error:
        app.logger.info("ms graph error")
        return
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
        app.logger.info("ms graph error")
        result = db.updateResult(data['email'], record_util.STATUS_FAILED)
        app.logger.info(result)
    else:
        result = db.updateResult(data['email'], record_util.STATUS_DONE)
        app.logger.info(result)

@celery.task
def goodbye_task(data):
    # db: write hello state
    db = record_util.RecordDB(settings.MONGO_URL, settings.MONGO_USER, settings.MONGO_PW)
    result = db.insertRequest(data['email'], NOTWORKING)
    app.logger.info(result)

    mgraph = microsoft_util.Mgraph(data['token'])

    rissues = redmine_util.Rissues(data['redmine_url'], data['redmine_id'], data['redmine_pw'], int(data['redmine_user_id']), app.logger)
    doing_issues, changed_issues = rissues.getIssues(True)

    result = ""
    result += "各位\n\n"
    result += data['department'] + "の" + data['name'] + "です\n\n"
    if not len(data['comment']) == 0:
        result += data['comment'] + "\n\n"
    # [TODO] must get 9:30 (start time) from db
    result += "【勤務実績】" + "9:30" + "～" + str(datetime.datetime.now().hour)+":"+str(datetime.datetime.now().minute) + "\n\n"
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
    if error:
        app.logger.info("ms graph error")
        result = db.updateResult(data['email'], record_util.STATUS_FAILED)
        app.logger.info(result)
        return
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
        if error:
            app.logger.info("ms graph error")
            return
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
    if error:
        app.logger.info("ms graph error")
        result = db.updateResult(data['email'], record_util.STATUS_FAILED)
        app.logger.info(result)
        return
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
        app.logger.info("ms graph error")
        result = db.updateResult(data['email'], record_util.STATUS_FAILED)
        app.logger.info(result)
    else:
        result = db.updateResult(data['email'], record_util.STATUS_DONE)
        app.logger.info(result)

@app.after_request
def after_request(response):
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
  return response

@app.route('/ping', methods=['GET'])
def ping():
    app.logger.info("ping")
    status = 200
    return flask.Response(response='pong\n', status=status, mimetype='application/json')

@app.route('/init', methods=['POST'])
def init():
    app.logger.info("init")
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)
    app.logger.info(data['job'])

    # db: write init data
    db = record_util.RecordDB(settings.MONGO_URL, settings.MONGO_USER, settings.MONGO_PW)
    result = db.insertRequest(data['email'], data['job'])
    app.logger.info(result)

    status = 200
    out = StringIO()
    x = '{ "id":' + ' 1, "title": "test' + '" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=status, mimetype='application/json')

@app.route('/state', methods=['POST'])
def state():
    app.logger.info("state")
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)

    # db: get last state
    db = record_util.RecordDB(settings.MONGO_URL, settings.MONGO_USER, settings.MONGO_PW)
    state, _ = db.getLastStateAndStatus(data['email'])
    if len(state) == 0:
        app.logger.info("not registered")
        state = NOTWORKING

    status = 200
    out = StringIO()
    x = '{ "State":"' + state + '" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=status, mimetype='application/json')

@app.route('/hello', methods=['POST'])
def hello():
    app.logger.info("hello")
    session.permanent = True
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)

    # hello task
    result = hello_task.delay(data)
    app.logger.info(result.id)
    app.logger.info(result.ready())

    out = StringIO()
    x = '{ "result": "sent hello request" }'
    resState = json.loads(x)
    json.dump(resState, out)
    return flask.Response(response=out.getvalue(), status=200, mimetype='text/json')

@app.route('/goodbye', methods=['POST'])
def goodbye():
    app.logger.info("goodbye")
    session.permanent = True
    data = flask.request.data.decode('utf-8')
    data = json.loads(data)

    # goodbye task
    result = goodbye_task.delay(data)
    app.logger.info(result.id)
    app.logger.info(result.ready())

    out = StringIO()
    x = '{ "result": "sent goodbye request" }'
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
        args = parse_args()
        app.run(host=args.host, port=args.port, debug=True)
    except Exception as e:
        app.logger.info(e)
    sys.exit(0)