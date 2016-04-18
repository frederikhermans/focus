# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import collections
import itertools
import sys
import subprocess
import time

import click
import cv2
import numpy as np
import PIL

import multiprocreceiver
import transmitter
import util


def video_frame_src(filename, resolution, start_at, duration=None,
                    grayscale=True):
    # Warning: make sure you consume all the frames from the source,
    # otherwise the process will hang around!
    bytes_per_frame = resolution[0]*resolution[1]

    duration_opt = '-t {}'.format(duration) if duration is not None else ''
    cmd = ('ffmpeg -ss {} {} -i {} -loglevel fatal '
           '-an -c:v rawvideo -pix_fmt yuv420p '
           '-f rawvideo -'.format(start_at, duration_opt, filename))
    ffmpeg = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                              close_fds=True)

    while True:
        bytes = ffmpeg.stdout.read(bytes_per_frame*3/2)
        if len(bytes) != bytes_per_frame*3/2:
            break
        if grayscale:
            bytes = bytes[:bytes_per_frame]
            frame = np.fromstring(bytes, dtype=np.uint8).reshape(*resolution)
        else:
            frame = np.fromstring(bytes, dtype=np.uint8)
            frame = frame.reshape((resolution[0]+resolution[0]/2,
                                   resolution[1]))
            frame = cv2.cvtColor(frame, cv2.COLOR_YUV420P2BGR)
        yield frame

    ffmpeg.stdout.close()
    ffmpeg.wait()


class DecodeCallback(object):
    def __init__(self, out):
        self.out = out
        self.framecount = 0
        self.fragments_total = 0
        self.fragments_ok = 0
        self.start = None
        self.status_count = collections.defaultdict(int)

    def callback(self, data):
        if self.start is None:
            self.start = time.time()
        for d in data:
            self.framecount += 1
            for fragment in d['fragments']:
                if fragment is not None:
                    self.fragments_ok += 1
                    fragment.tofile(self.out)
            self.fragments_total += len(d['fragments'])
            if 'status' in d:
                self.status_count[d['status']] += 1
        self.status_stats()

    def status_stats(self):
        fmt_string = ('frames={s.framecount}, '
                      'fragments={s.fragments_ok}/{s.fragments_total} '
                      '({fragment_ratio:.2f}%) ')
        if self.fragments_total == 0:
            fragment_ratio = 0
        else:
            fragment_ratio = 100. * self.fragments_ok / self.fragments_total
        print '\r', fmt_string.format(s=self, fragment_ratio=fragment_ratio),

    def final_stats(self):
        # Cave: the rates (data rate, frame rate) calculated here are an
        # overestimate, in particular for short input videos. The reason is
        # that we start keeping time only when we get the very first result,
        # which means that we don't account for the decoding time of the
        # first `nframes_per_process` frames.
        # To get a better measure of decoding speed, use the multiprocreceiver
        # with a high `repeat` parameter.

        nbytes = util.sizeof_fmt(self.fragments_ok*64)
        duration = time.time() - self.start
        datarate = util.sizeof_fmt(self.fragments_ok*64./duration,
                                   suffix='B/s')
        framerate = self.framecount / duration
        fmt = 'Decoded {nbytes} from {s.framecount} frames in {duration:.2f} s'
        print fmt.format(s=self, nbytes=nbytes, duration=duration)
        print 'Data rate: {}, frame rate: {:3.1f} frames/s'.format(datarate,
                                                                   framerate)
        if len(self.status_count) > 0:
            print 'Status:',
            print ', '.join('{}={}'.format(key, value)
                            for key, value in self.status_count.iteritems())


@click.command('videorx')
@click.argument('filename')
@click.option('--resolution', type=str, default='1920x1080')
@click.option('--nsubchannels', type=int, required=True)
@click.option('--nprocesses', type=int, default=6)
@click.option('--nframes-per-process', type=int, default=20)
@click.option('--receiver-args', type=str, default='')
@click.option('--video-start', type=float, default=0.0)
@click.option('--video-duration', type=float)
def rx(filename, resolution, nsubchannels, nprocesses, nframes_per_process,
       receiver_args, video_start, video_duration):
    receiver_args = eval('dict({})'.format(receiver_args))
    resolution = util.parse_resolution(resolution)

    out = sys.stdout
    sys.stdout = sys.stderr
    cb = DecodeCallback(out)
    frames = video_frame_src(filename, resolution, video_start, video_duration)
    recv = multiprocreceiver.MultiProcReceiver(nsubchannels, nprocesses,
                                               nframes_per_process,
                                               callback=cb.callback,
                                               **receiver_args)
    recv.decode_many(frames)
    print
    cb.final_stats()
    recv.close()


def add_frame_number(tx_img, frame_no):
    text = 'Frame {:03d}'.format(frame_no)
    font_scale = 1.0
    twidth, theight = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX,
                                      font_scale, 2)[0]
    strip = np.ones((tx_img.shape[0], twidth), dtype=np.uint8)*255
    offset = int(theight*1.5) if frame_no % 2 else 0
    for y in xrange(10 + theight, tx_img.shape[0]-offset, 3*theight):
        cv2.putText(strip, text, (0, y+offset), cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, 0, thickness=2)
    if len(tx_img.shape) == 3 and tx_img.shape[2] == 3:
        strip = np.dstack((strip, strip, strip))
    return np.hstack((strip, tx_img, strip))


def render(codes, fname, fps=30, height=1080, width=1920, video_fps=30):
    # XXX There seems to be an issue with the first frame.
    if video_fps > 30:
        print 'WARNING: Video will not play on iPad.'
    cmd = ('ffmpeg -loglevel fatal -framerate {} '
           '-f image2pipe -vcodec png -i - '
           '-pix_fmt yuv420p -r {} -c:v libx264 -crf 1 '
           '-profile:v high -level 4.1 '
           '-vf pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white '
           '-y {}').format(fps, video_fps, fname)

    ffmpeg = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE)
    spinner = itertools.cycle('|/-\\')

    for frame_no, code in enumerate(codes):
        code = add_frame_number(code, frame_no)

        # Render PNG and write to ffmpeg
        pil_img = PIL.Image.fromarray(code)
        pil_img.save(ffmpeg.stdin, format='png')
        if frame_no == 0:
            pil_img.save(ffmpeg.stdin, format='png')
        print '\r{} txframe={}'.format(next(spinner), frame_no),
        sys.stdout.flush()
    print '\rCompleted.        '
    ffmpeg.stdin.close()
    ffmpeg.wait()
    if ffmpeg.returncode != 0:
        raise RuntimeError('ffmpeg failed.')


def code_generator(transmitter, infile=sys.stdin):
    nsubchannels = transmitter.nsubchannels
    while True:
        fragments = np.fromfile(infile, dtype=np.uint8, count=nsubchannels*64)
        fragments = fragments.reshape(-1, 64)
        if len(fragments) == 0:
            return
        if len(fragments) != nsubchannels:
            padded = np.zeros((nsubchannels, 64), dtype=np.uint8)
            for i in xrange(0, nsubchannels, len(fragments)):
                j = min(i+len(fragments), nsubchannels)
                padded[i:j] = fragments[:j-i]
            fragments = padded
        yield transmitter.encode(fragments)


@click.command('videotx')
@click.argument('filename')
@click.option('--transmitter-args', type=str, default='')
@click.option('--txrate', type=int, default=15)
@click.option('--nsubchannels', type=int, required=True)
@click.option('--video-fps', type=int, default=30)
def tx(filename, transmitter_args, txrate, nsubchannels, video_fps):
    transmitter_args = eval('dict({})'.format(transmitter_args))
    trans = transmitter.Transmitter(nsubchannels, **transmitter_args)
    render(code_generator(trans), filename, fps=txrate, video_fps=video_fps)


@click.command('multirate')
@click.argument('infile', type=click.File('rb'))
@click.option('--nsubchannels', type=int, required=True)
@click.option('--update-every', type=str, required=True)
def multirate(infile, nsubchannels, update_every):
    update_every = eval(update_every)
    if len(update_every) != nsubchannels:
        raise ValueError('Must specify a rate for every subchannel!')
    frameno = 0
    fragments = np.zeros((nsubchannels, 64), dtype=np.uint8)
    done = False
    while not done:
        for i in xrange(nsubchannels):
            if frameno == 0 or frameno % update_every[i] == 0:
                buf = np.fromfile(infile, dtype=np.uint8, count=64)
                if len(buf) != 64:
                    done = True
                    break
                fragments[i, :] = buf

        frameno += 1
        fragments.tofile(sys.stdout)
