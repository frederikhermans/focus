# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import cPickle as pickle
import sys

import click
import imageframer
import numpy as np
import rscode

import focus


def _grayscale(frame):
    if len(frame.shape) == 2:
        return frame            # Is already grayscale
    elif len(frame.shape) == 3:
        return frame[:, :, 1]   # Return green channel
    else:
        raise ValueError('Unexpected data format {}.'.format(frame.shape))


class Receiver(object):
    def __init__(self, nsubchannels, nelements_per_subchannel=(64+16)*4,
                 parity=16, shape=(512, 512), border=0.15, cyclic_prefix=8,
                 use_hints=True, calibration_profile=None):
        self.rs = rscode.RSCode(parity)
        self.qpsk = focus.modulation.QPSK()
        self.idxs = focus.spectrum.subchannel_idxs(nsubchannels,
                                                   nelements_per_subchannel,
                                                   shape)
        self.shape_with_cp = tuple(np.array(shape) + 2*cyclic_prefix)

        self.framer = imageframer.Framer(self.shape_with_cp, border,
                                         calibration_profile=calibration_profile)
        self.cyclic_prefix = cyclic_prefix
        # Crop indices
        self.spectrum_bbox = focus.spectrum.get_bbox(self.idxs)
        cropped_idxs = tuple(focus.spectrum.crop(i, *self.spectrum_bbox)
                             for i in self.idxs)
        self.idxs = np.array(cropped_idxs)

        if use_hints:
            self.hints = list()
        else:
            self.hints = None

    def decode(self, frame, debug=False, copy_frame=True):
        # Locate
        try:
            corners = self.framer.locate(frame, hints=self.hints)
        except ValueError as ve:
#            sys.stderr.write('WARNING: {}\n'.format(ve))
            result = {'fragments': []}
            if debug:
                result['status'] = 'notfound'
                result['locator-message'] = str(ve)
            return result
        if copy_frame:
            frame = frame.copy()
        code = self.framer.extract(_grayscale(frame), self.shape_with_cp,
                                   corners, hints=self.hints)
        code = focus.phy.strip_cyclic_prefix(code, self.cyclic_prefix)

        # Compute, crop and unload spectrum
        spectrum = focus.phy.rx(code)
        # -> complex64 makes angle() faster.
        spectrum = spectrum.astype(np.complex64)
        spectrum = focus.spectrum.crop(spectrum, *self.spectrum_bbox)
        # Unload symbols from the spectrum
        symbols = focus.spectrum.unload(spectrum, self.idxs)

        # Modulate all symbols with one call to demodulate()
        coded_fragments = self.qpsk.demodulate(np.array(symbols).T).T
        # Make array contiguous, so we can pass it to rs.decode()
        coded_fragments = np.ascontiguousarray(coded_fragments)

        # Recover and unmask all fragments
        fragments = list()
        for channel_idx, coded_frag in enumerate(coded_fragments):
            nerrors, fragment = self.rs.decode(coded_frag)
            if nerrors < 0:
                # Recovery failed
                fragment = None
            else:
                focus.link.mask_fragments(fragment, channel_idx)
            fragments.append(fragment)

        result = {'fragments': fragments}
        if debug:
            result.update({'coded_fragments': coded_fragments,
                           'symbols': symbols,
                           'corners': corners,
                           'status': 'found'})
        return result

    def decode_many(self, frames, debug=False):
        return tuple(self.decode(frame, debug=debug) for frame in frames)


def benchmark(frames='frames.pickle'):
    import cProfile as profile
    import pstats
    if isinstance(frames, basestring):
        frames = focus.util.load_frames(frames)
    pr = profile.Profile()
    recv = Receiver(16)
    pr.enable()
    recv.decode_many(frames)
    pr.disable()
    stats = pstats.Stats(pr).sort_stats(2)
    stats.print_stats()


@click.command('receiver')
@click.option('--nsubchannels', type=int, default=16)
@click.option('--calibration-profile', type=str, default=None)
@click.option('--shape', type=str, default='512x512')
@click.option('--cyclic-prefix', type=int, default=8)
@click.option('--verbosity', type=int, default=0)
def main(nsubchannels, calibration_profile, shape, cyclic_prefix, verbosity):
    shape = focus.util.parse_resolution(shape)
    recv = Receiver(nsubchannels, calibration_profile=calibration_profile,
                    shape=shape, cyclic_prefix=cyclic_prefix)
    while True:
        try:
            frames = pickle.load(sys.stdin)
        except EOFError:
            break
        fragments = recv.decode_many(frames, debug=verbosity > 0)
        pickle.dump(fragments, sys.stdout, protocol=pickle.HIGHEST_PROTOCOL)
        sys.stdout.flush()


if __name__ == '__main__':
    main()
