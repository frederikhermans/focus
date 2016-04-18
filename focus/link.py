# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import numpy as np

_MASKS = dict()


def mask_fragments(fragments, channel_idx):
    '''Apply a constant pseudo-random bitmask to fragments (in-place)

    This function is its own inverse.

    This function is useful since it masks the structure of data, which
    could give rise to a large peak/average ratio.
    Note that the mask is dependent on the channel index. Again, this allows
    to avoid identical data across channels, which could give rise to a large
    peak/average ratio.'''
    if channel_idx not in _MASKS:
        rand = np.random.RandomState(seed=39402+channel_idx)
        _MASKS[channel_idx] = rand.randint(0, 255, 32768).astype(np.uint8)
    if len(fragments.shape) > 1:
        fragment_size = fragments.shape[1]
    else:
        fragment_size = fragments.shape[0]
    fragments ^= _MASKS[channel_idx][:fragment_size]


def test_mask_fragments():
    frags = np.random.randint(0, 255, (10, 1024)).astype(np.uint8)
    copy = frags.copy()
    # Masking twice should have no effect
    mask_fragments(copy, 0)
    mask_fragments(copy, 0)
    if not np.all(frags == copy):
        raise RuntimeError('test_mask_fragments() failed.')
