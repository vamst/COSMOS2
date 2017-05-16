import subprocess as sp
import re
import os

from .DRM_Base import DRM
from .util import exit_process_group

STATUSES = {
'0': 'INQ',
'100': 'ASSIGNED',
'150': 'LOADED',
'200': 'RUNNING',
'250': 'UNKNOWN_RUN',
'300': 'EXTRUNNING',
'350': 'STOPPED',
'399': 'KILLING',
'400': 'KILLED',
'750': 'FAILED',
'755': 'UNKNOWN_PRE',
'989': 'CANCELLING',
'990': 'CANCELLED',
'999': 'UNKNOWN',
'1000': 'FINISHED',
'1024': 'EXIT',
}

class DRM_MXQ(DRM):
    name = 'mxq'
    poll_interval = 5

    def submit_job(self, task):
        ns = ' ' + task.drm_native_specification if task.drm_native_specification else ''
        bsub = 'mxqsub --stdout {stdout} --stderr {stderr}{ns} '.format(
            stdout=task.output_stdout_path,
            stderr=task.output_stderr_path,
            ns=ns)

        out = sp.check_output(
            '{bsub} {cmd_str}'.format(
                cmd_str=task.output_command_script_path,
                bsub=bsub
            ),
          env=os.environ,
          preexec_fn=exit_process_group,
          shell=True).decode('utf8')

        drm_jobID = re.search('mxq_job_id=(\d+)', out).group(1)
        return drm_jobID

    def filter_is_done(self, tasks):
        if len(tasks):
            def is_done(task):
                try:
                    jid = str(task.drm_jobID)
                    status = STATUSES[get_status_from_jid(jid)]
                except:
                    return False

                if status in ('KILLED', 'FAILED', 'FINISHED', 'EXIT'): 
                    return True
                else:
                    return False

            bjobs = bjobs_all()
            res = []
            for task in tasks:
                if is_done(task):
                    res.append((task, bjobs[str(task.drm_jobID)]))
            return res

        else:
            return []

    def drm_statuses(self, tasks):
        """
        USED ONLY for the web information

        :param tasks: tasks that have been submitted to the job manager
        :returns: (dict) task.drm_jobID -> drm_status
        """
        if len(tasks):
            # bjobs = bjobs_all()

            def f(task):
                return STATUSES[get_status_from_jid(str(task.drm_jobID))]
                # return bjobs.get(str(task.drm_jobID), dict()).get('status', '???')
                # return bjobs.get(str(task.drm_jobID), dict()).get('status', 'FINISHED')

            return {task.drm_jobID: f(task) for task in tasks}
        else:
            return {}

    def kill(self, task):
        "Terminates a task"
        raise NotImplementedError
        # os.system('bkill {0}'.format(task.drm_jobID))

    def kill_tasks(self, tasks):
        for t in tasks:
            # sp.check_call(['mxqkill', '-J', str(t.drm_jobID)])
            g = get_gid_from_jid(t.drm_jobID)
            if g:
                sp.check_call(['mxqkill', '-g', str(g)])


# def get_gid_from_jid(jid):
    # groups = [x.split('group_id=')[1].split(' ')[0] for x in os.popen('mxqdump').readlines() if 'group_id=' in x]
    # for g in groups:
    #     for opt in ('-q', '-r', '-f', '-F', '-K', '-C', '-U'):
    #         for l in os.popen('mxqdump -j {opt} -g {g} 2> /dev/null'.format(**locals())).readlines():
    #             if jid in l:
    #                 return g
    # return False

def get_gid_from_jid(jid):
    try:
        resp =  os.popen('mysql -u ronly -p1234 -A --host mxq -D mxq -e \
            "select group_id from mxq_job where job_id={}"'.format(jid)).readlines()[-1].strip()
    except:
        resp = '999'

    if resp and len(resp)>3 and resp.isdigit():
        return resp
    else:
        return '999'

def get_status_from_jid(jid):
    try:
        resp =  os.popen('mysql -u ronly -p1234 -A --host mxq -D mxq -e \
            "select job_status from mxq_job where job_id={}"'.format(jid)).readlines()[-1].strip()
    except:
        resp = False

    if resp and len(resp)>=3 and resp.isdigit():
        return resp
    else:
        return False

# TODO: use mysql API
def bjobs_all():
    user_name = 'amstisla'
    user_id = '1991'

    header = False
    bjobs = {}
    for i in os.popen('mysql -u ronly -p1234 -A --host mxq -D mxq -e \
        "select * from mxq_job where (group_id) in \
        (select group_id from mxq_group where user_name=\'{}\' \
            and date_submit>DATE_SUB(NOW(), INTERVAL 3 DAY) );"'.format(user_name)).readlines():
        if not header:
            header = i.split()
        else:
            fs = i.split()
            bjobs[fs[0]] = dict(list(zip(header, fs)))
            if bjobs[fs[0]]['job_status'] in ('0', '1000'):
                bjobs[fs[0]]['exit_status'] = 0
            # elif get_status_from_jid(fs[0]) == '1000':
            #     bjobs[fs[0]]['exit_status'] = 0
            else:
                bjobs[fs[0]]['exit_status'] = 1
                # bjobs[fs[0]]['exit_status'] = bjobs[fs[0]]['job_status']

            bjobs[fs[0]]['status'] = STATUSES[bjobs[fs[0]]['job_status']].lower()
            bjobs[fs[0]]['job'] = '{}({}):{}:{}'.format(user_name, user_id, bjobs[fs[0]]['group_id'], bjobs[fs[0]]['job_id'])
    return bjobs


# def bjobs_all():
#     """
#     returns a dict keyed by mxq job ids, who's values are a dict of mxqdump
#     information about the job
#     """
#     # try:
#     if True:
#         lines = []
#         groups = [x.split('group_id=')[1].split(' ')[0] for x in os.popen('mxqdump').readlines() if 'group_id=' in x]
#         for g in groups:
#             for opt in ('-q', '-r', '-f', '-F', '-K', '-C', '-U'):
#                 out = os.popen('mxqdump -j {opt} -g {g} 2> /dev/null'.format(**locals())).readlines()
#                 lines += out
#     # except (sp.CalledProcessError, OSError):
#     #     lines=[]

#     if len(lines)>0 and '=' in lines[0]: header = [x.split('=')[0] for x in lines[0].split(' ') if '=' in x]
#     else: header = []
#     bjobs = {}

#     for l in lines:
#         if '=' not in l: continue
#         items = [x.split('=')[1] for x in l.split(' ') if '=' in x]
#         bjobs[items[0].split(':')[-1]] = dict(list(zip(header, items)))
        
#         status = bjobs[items[0].split(':')[-1]]['status'].split('(')[0]
#         bjobs[items[0].split(':')[-1]]['status'] = status

#         if 'finished' in status: bjobs[items[0].split(':')[-1]]['exit_status'] = 0
#         else: bjobs[items[0].split(':')[-1]]['exit_status'] = 1

#     return bjobs
