# Copyright (c) 2016, Frederik Hermans, Liam McNamara
#
# This file is part of FOCUS and is licensed under the 3-clause BSD license.
# The full license can be found in the file COPYING.

import itertools
import struct
import sys

import click
import numpy as np
import PIL.Image

import focus


def pack_header(nfragments, payload_len):
    return tuple(bytearray(struct.pack('!HH', nfragments, payload_len)))


def unpack_header(fragment):
    return struct.unpack('!HH', fragment[:4].tostring())


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return itertools.izip_longest(fillvalue=fillvalue, *args)


def get_nrequired_fragments(payload_len, fragment_size=64):
    return max(1,
               int(np.ceil(payload_len / float(fragment_size))))


def create_fragments(payload, header, nfragments, fragment_size=64):
    if len(payload) == 0:
        assert nfragments == 1
        fragments = np.zeros((1, fragment_size), dtype=np.uint8)
        fragments[0, :len(header)] = header
        return fragments
    else:
        fragments = list()
        for bytes in grouper(payload, fragment_size-len(header), 0):
            fragments.append(header + bytes)
        return np.array(fragments, dtype=np.uint8)


def fragments_to_string(fragments, header_len, payload_len):
    if len(fragments) == 0:
        return ''
    empty = 'X'*max(len(f) for f in fragments if f is not None)
    res = ''
    for frag in fragments:
        if frag is None:
            res += empty
        else:
            res += frag[header_len:].tostring()
    return res[:payload_len]


def extract_header(fragments):
    headers = set()

    for fragment in fragments:
        if fragment is not None:
            headers.add(unpack_header(fragment))

    if len(headers) == 1:
        return tuple(headers)[0]
    else:
        if len(headers) == 0:
            print 'Decoding failed.'
        elif len(headers) > 1:
            # XXX Depending on how commonly this situation occurs, we
            # may just pick the most common header.
            print('Headers are not unique. (Decoded {} different '
                  'headers.)'.format(len(headers)))
        return 0, 0


def load_img(imgfile):
    img = np.array(PIL.Image.open(imgfile))
    if len(img.shape) == 3:
        # Convert to grayscale by discarding red and blue
        img = img[:, :, 1]
    return img


def get_status(fragment_decoded):
    status = 'partially-decoded'
    if len(fragment_decoded) == 0 or not any(fragment_decoded):
        status = 'none-decoded'
    elif all(fragment_decoded):
        status = 'all-decoded'
    return status


@click.command('simplerx')
@click.option('--nsubchannels', type=int, default=32)
@click.option('--shape', type=str, default='768x768')
@click.argument('imgfile', type=click.File('rb'))
def rx(imgfile, nsubchannels, shape):
    recv = focus.receiver.Receiver(nsubchannels,
                                   shape=focus.util.parse_resolution(shape))
    print 'Receiver initialized'

    frame = load_img(imgfile)
    decoded = recv.decode(frame, debug=True)
    nfragments, payload_len = extract_header(decoded['fragments'])
    decoded['fragments'] = decoded['fragments'][:nfragments]
    decoded['payload_str'] = fragments_to_string(decoded['fragments'],
                                                 4, payload_len)
    decoded['fragment_decoded'] = [f is not None for
                                   f in decoded['fragments']]
    decoded['ndecoded'] = sum(decoded['fragment_decoded'])
    if decoded['status'] == 'found':
        decoded['status'] = get_status(decoded['fragment_decoded'])

    if len(decoded['payload_str']) > 0:
        print 'Payload: <<<{}>>>'.format(decoded['payload_str'])
    print 'Status: {}'.format(decoded['status'])
    print 'Number of decoded fragments: {}'.format(decoded['ndecoded'])


@click.command('simpletx')
@click.option('--shape', type=str, default='768x768')
@click.argument('outfile', type=click.File('wb'))
def tx(outfile, shape):
    payload = bytearray(sys.stdin.read())
    payload_len = len(payload)
    nfragments = get_nrequired_fragments(payload_len, 64-4)
    header = pack_header(nfragments, payload_len)
    fragments = create_fragments(payload, header, nfragments)
    shape = focus.util.parse_resolution(shape)
    transmitter = focus.transmitter.Transmitter(nfragments, shape=shape)
    frame = transmitter.encode(fragments)
    pil_img = PIL.Image.fromarray(frame)
    pil_img.save(outfile)
    print 'Wrote code with {} sub-channel(s).'.format(nfragments)
