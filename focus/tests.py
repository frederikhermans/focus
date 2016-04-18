# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import sys

import focus


def run_tests():
    tests = (focus.transmitter.test_tx_rx,
             focus.fft.test_irfft2, focus.fft.test_rfft2,
             focus.link.test_mask_fragments,
             focus.modulation.test_mod_demod,
             focus.phy.test_add_strip_cyclic_prefix,
             focus.spectrum.test_bbox)
    count = 0
    success = 0
    for test_func in tests:
        try:
            count += 1
            print '\r{:30} '.format(test_func.func_name),
            sys.stdout.flush()
            test_func()
            success += 1
        except Exception as e:
            print '\r{} failed: {}'.format(test_func.func_name, e.message)
    print '\rSucceeded: {}/{} {:30}'.format(success, count, ' ')
