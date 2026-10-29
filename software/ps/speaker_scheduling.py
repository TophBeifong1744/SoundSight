"""Linux process-local CPU policy. No MMIO, realtime scheduler or global settings."""
import os
import shutil


class CaptureScheduling:
    def __enter__(self):
        self.original = set(os.sched_getaffinity(0))
        if len(self.original) < 2:
            raise RuntimeError('SPEAKER_REQUIRES_TWO_AVAILABLE_CPUS')
        self.cpus = sorted(self.original)[:2]
        self.taskset = shutil.which('taskset')
        self.nice = shutil.which('nice')
        if not self.taskset or not self.nice:
            raise RuntimeError('SPEAKER_REQUIRES_TASKSET_AND_NICE')
        # The hardware owner is single-threaded. The algorithm interpreter and
        # native frontend run on the other CPU with their own GIL and workers.
        os.sched_setaffinity(0, {self.cpus[0]})
        try:
            if set(os.sched_getaffinity(0)) != {self.cpus[0]}:
                raise RuntimeError('SPEAKER_CAPTURE_AFFINITY_NOT_APPLIED')
            self.info = dict(revision='rx3', capture_cpus=[self.cpus[0]], frontend_cpus=[self.cpus[1]],
                ps_optimization='opt1',
                algorithm_process_cpus=[self.cpus[1]],capture_gil_shared=False,
                embedding_cpus=self.cpus, embedding_threads=2, embedding_nice_increment=10,
                policy='capture_interpreter_isolated_algorithms_on_other_cpu_embedding_lower_priority',
                realtime_scheduler=False)
            return self
        except BaseException:
            os.sched_setaffinity(0, self.original)
            raise

    def prefix(self, role):
        if role == 'front':
            return [self.taskset, '-c', str(self.cpus[1])]
        if role == 'embed':
            return [self.taskset, '-c', ','.join(map(str, self.cpus)), self.nice, '-n', '10']
        raise ValueError('BACKEND_ROLE')

    def __exit__(self, *exc):
        os.sched_setaffinity(0, self.original)
