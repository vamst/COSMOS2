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

    def submit_job(self, task):
        ns = ' ' + task.drm_native_specification if task.drm_native_specification else ''
        bsub = 'mxqsub --stdout {stdout} --stderr {stderr}{ns} '.format(
            stdout=task.output_stdout_path,
            stderr=task.output_stderr_path,
            ns=ns)

        out = sp.check_output('{bsub} "{cmd_str}"'.format(cmd_str=self.jobmanager.get_command_str(task), bsub=bsub),
                              env=os.environ,
                              preexec_fn=exit_process_group,
                              shell=True)

        drm_jobID = int(re.search('mxq_job_id=(\d+)', out).group(1))
        return drm_jobID

    def filter_is_done(self, tasks):
        if len(tasks):
            bjobs = bjobs_all()

            def is_done(task):
                jid = str(task.drm_jobID)
                if jid not in bjobs:
                    # prob in history
                    # print 'missing %s %s' % (task, task.drm_jobID)
                    return True
                else:
                    return bjobs[jid]['STAT'] in ['DONE', 'EXIT', 'UNKWN', 'ZOMBI']

            return list(filter(is_done, tasks))
        else:
            return []

    def drm_statuses(self, tasks):
        """
        :param tasks: tasks that have been submitted to the job manager
        :returns: (dict) task.drm_jobID -> drm_status
        """
        if len(tasks):
            bjobs = bjobs_all()

            def f(task):
                return bjobs.get(str(task.drm_jobID), dict()).get('STAT', '???')

            return {task.drm_jobID: f(task) for task in tasks}
        else:
            return {}

    def kill(self, task):
        "Terminates a task"
        raise NotImplementedError
        # os.system('bkill {0}'.format(task.drm_jobID))

    def kill_tasks(self, tasks):
        for t in tasks:
            sp.check_call(['bkill', str(t.drm_jobID)], preexec_function=exit_process_group)


def bjobs_all():
    """
    returns a dict keyed by lsf job ids, who's values are a dict of bjob
    information about the job
    """
    try:
        lines = sp.check_output(['mxqdump', '-a'], preexec_function=exit_process_group).split('\n')
    except (sp.CalledProcessError, OSError):
        return {}
    bjobs = {}
    header = re.split("\s\s+", lines[0])
    for l in lines[1:]:
        items = re.split("\s\s+", l)
        bjobs[items[0]] = dict(list(zip(header, items)))
    return bjobs
