import subprocess as sp
import re
import os

from .DRM_Base import DRM
from .util import exit_process_group

# decode_lsf_state = dict([
#     ('UNKWN', 'process status cannot be determined'),
#     ('PEND', 'job is queued and active'),
#     ('PSUSP', 'job suspended while pending'),
#     ('RUN', 'job is running'),
#     ('SSUSP', 'job is system suspended'),
#     ('USUSP', 'job is user suspended'),
#     ('DONE', 'job finished normally'),
#     ('EXIT', 'job finished, but failed'),
# ])


class DRM_MXQ(DRM):
    name = 'mxq'
    poll_interval = 5
    # poll_interval = 50

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
        # return tasks

        if len(tasks):
            bjobs = bjobs_all()

            def is_done(task):
                jid = str(task.drm_jobID)
                if jid not in bjobs:
                    # prob in history
                    # print 'missing %s %s' % (task, task.drm_jobID)
                    return True
                else:
                    # print(bjobs[jid]['status'])
                    return 'running' not in bjobs[jid]['status']
            # return list(filter(is_done, tasks))

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
            bjobs = bjobs_all()

            def f(task):
                return bjobs.get(str(task.drm_jobID), dict()).get('status', '???')
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
            sp.check_call(['mxqkill', '-J', str(t.drm_jobID)])
            g = get_gid_from_jid(t.drm_jobID)
            if g:
                sp.check_call(['mxqkill', '-g', str(g)])


def get_gid_from_jid(jid):
    groups = [x.split('group_id=')[1].split(' ')[0] for x in os.popen('mxqdump').readlines() if 'group_id=' in x]
    for g in groups:
        for opt in ('-q', '-r', '-f', '-F', '-K', '-C', '-U'):
            for l in os.popen('mxqdump -j {opt} -g {g} 2> /dev/null'.format(**locals())).readlines():
                if jid in l:
                    return g
    return False

def bjobs_all():
    """
    returns a dict keyed by mxq job ids, who's values are a dict of mxqdump
    information about the job
    """
    # try:
    if True:
        lines = []
        groups = [x.split('group_id=')[1].split(' ')[0] for x in os.popen('mxqdump').readlines() if 'group_id=' in x]
        for g in groups:
            for opt in ('-q', '-r', '-f', '-F', '-K', '-C', '-U'):
                # out = sp.check_output(['mxqdump', '-j {opt} -g {g}'.format(**locals())]).decode('utf8').split('\n')
                # out = os.popen('mxqdump -j {opt} -g {g} 2> /dev/null'.format(**locals())).readlines()
                out = os.popen('mxqdump -j {opt} -g {g} 2> /dev/null'.format(**locals())).readlines()
                lines += out
    # except (sp.CalledProcessError, OSError):
    #     lines=[]

    if len(lines)>0 and '=' in lines[0]: header = [x.split('=')[0] for x in lines[0].split(' ') if '=' in x]
    else: header = []
    bjobs = {}

    for l in lines:
        if '=' not in l: continue
        items = [x.split('=')[1] for x in l.split(' ') if '=' in x]
        bjobs[items[0].split(':')[-1]] = dict(list(zip(header, items)))
        
        status = bjobs[items[0].split(':')[-1]]['status'].split('(')[0]
        bjobs[items[0].split(':')[-1]]['status'] = status

        if 'finished' in status: bjobs[items[0].split(':')[-1]]['exit_status'] = 0
        else: bjobs[items[0].split(':')[-1]]['exit_status'] = 1

    return bjobs
