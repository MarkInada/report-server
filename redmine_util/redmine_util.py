from redminelib import Redmine
from multiprocessing import Pool
import datetime

PROCESS_NUMBER = 5
ISSUE_TYPE_DOING = "doing"
ISSUE_TYPE_CHANGED = "changed"

class Rissues:
    def __init__(self, rurl, rid, rpw, ruid, logger):
        self.redmine = Redmine(rurl, username=rid, password=rpw)
        self.userid = ruid
        self.issues = self.redmine.issue.all(sort='priority:desc,due_date:desc')
        self.count = len(self.issues)
        self.logger = logger

    def getIssues(self, both: bool):
        doing_issues = []
        changed_issues = []
        issue_list = []
        limit_interval = self.count // PROCESS_NUMBER
        for num in range(PROCESS_NUMBER-1):
            issue_list.append(self.redmine.issue.all(sort='priority:desc,due_date:desc', limit = limit_interval, offset = limit_interval * num))
        else:
            issue_list.append(self.redmine.issue.all(sort='priority:desc,due_date:desc', limit = self.count - (limit_interval * (PROCESS_NUMBER - 1)), offset = limit_interval * (PROCESS_NUMBER - 1)))
        with Pool(PROCESS_NUMBER) as p:
            doing_issues = p.map(self.getDoingIssues, issue_list)
            p.close()
            p.join()
        if both:
            with Pool(PROCESS_NUMBER) as p:
                changed_issues = p.map(self.getChangedIssues, issue_list)
                p.close()
                p.join()
        return doing_issues, changed_issues

    def getDoingIssues(self, issues):
        resultIssues= []
        for issue in issues:
            try:
                if self.userid == issue.assigned_to.id and (issue.status.name == "着手" or issue.status.name == "レビュー中"):
                    resultIssues.append(issue)
            except Exception as inst:
                self.logger.info(inst)
        return resultIssues

    def getChangedIssues(self, issues):
        resultIssues= []
        for issue in issues:
            try:
                journals = self.redmine.issue.get(issue.id, include=['journals'])
                for record in journals.journals:
                    if self.userid == record.user.id:
                        if int(record.created_on.year) == int(datetime.date.today().year) and int(record.created_on.month) == int(datetime.date.today().month) and int(record.created_on.day) == int(datetime.date.today().day):
                            resultIssues.append(issue)
                            break
            except Exception as inst:
                self.logger.info(inst)
        return resultIssues
