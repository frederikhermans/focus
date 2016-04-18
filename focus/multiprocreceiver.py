# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import cPickle as pickle
import select
import subprocess
import sys
import time

from focus.util import is_android, load_frames


def take_n(iterable, n):
    elems = list()
    for element in iterable:
        elems.append(element)
        if len(elems) == n:
            yield elems
            elems = list()
    if len(elems) > 0:
        yield elems


class MultiProcReceiver(object):
    def __init__(self, nsubchannels, nprocesses, nframes_per_process,
                 callback=None, **kwargs):
        path = '/data/data/se.sics.vizpy/files/' if is_android() else ''
        cmd = [path+'python', '-u', '-m', 'focus.cli', 'receiver',
               '--nsubchannels', str(nsubchannels)]
        for key, value in kwargs.iteritems():
            if value is not None:
                cmd.append('--' + key.replace('_', '-'))
                cmd.append(str(value))
        self.processes = tuple(subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                close_fds=True)
                               for _ in xrange(nprocesses))
        self.stdout_to_proc = {p.stdout.fileno(): p for p in self.processes}
        self.callback = callback
        self.nframes_per_process = nframes_per_process

    def decode_many(self, frames):
        frames = take_n(frames, self.nframes_per_process)
        # Send a first chunk to all processes
        # XXX fails if there are more processes than chunk
        pending = 0
        self.start_time = time.time()
        for i, proc in enumerate(self.processes):
            pending += 1
            send_to_process(next(frames), proc)

        print 'All processes started.'

        rlist = tuple(self.stdout_to_proc.keys())
        empty = tuple()
        try:
            while True:
                # Wait for next processes to become ready
                ready, _, _ = select.select(rlist, empty, empty)
                for stdout in ready:
                    proc = self.stdout_to_proc[stdout]
                    self.try_callback(recv_from_process(proc))
                    send_to_process(next(frames), proc)
        except StopIteration:
            pending -= 1

        while pending > 0:
            ready, _, _ = select.select(rlist, empty, empty)
            for stdout in ready:
                proc = self.stdout_to_proc[stdout]
                self.try_callback(recv_from_process(proc))
                pending -= 1

    def try_callback(self, data):
        if self.callback is None:
            return
        self.callback(data)

    def close(self):
        for proc in self.processes:
            proc.stdout.close()
            proc.stdin.close()
            proc.wait()


def send_to_process(chunk, proc):
    pickle.dump(chunk, proc.stdin, protocol=pickle.HIGHEST_PROTOCOL)
    proc.stdin.flush()


def recv_from_process(proc):
    try:
        return pickle.load(proc.stdout)
    except pickle.UnpicklingError:
        print '>>>', proc.stdout.read(16)
        raise


def benchmark(frames='frames.pickle', nprocesses=4, nframes_per_process=20,
              repeat=1):
    import time
    recv = MultiProcReceiver(nprocesses, nframes_per_process)

    if isinstance(frames, basestring):
        frames = load_frames(frames)

    if repeat != 1:
        frames = frames * repeat

    start = time.time()
    recv.decode_many(frames)
    stop = time.time()

    print 'Processed {} frames'.format(len(frames))
    print 'Took {:.2f} ms'.format((stop-start) * 1000.)
    print 'Frame rate: {:.2f} fps'.format(len(frames) / (stop-start))

    recv.close()
