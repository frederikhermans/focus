# The authors of this work have released all rights to it and placed it
# in the public domain under the Creative Commons CC0 1.0 waiver
# (http://creativecommons.org/publicdomain/zero/1.0/).
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Retrieved from: http://en.literateprograms.org/Generating_all_integer_lattice_points_(Python)?oldid=17065
# Modified for VLC project

'''Code for creating mappings that are used to place symbols in the matrix.'''

def _distance(p):
    return p[0]**2 + p[1]**2

def _may_use(vu, shape):
    '''Returns true if the entry v, u may be used in a conjugate symmetric matrix.
    
    In other words, the function returns false for v, u pairs that must be
    their own conjugate. These pairs cannot be used to store complex symbols.
    `shape` is the shape of the matrix into which the symbols are packed.
    '''
    n, m = shape
    m = (m/2) + 1
    v, u = vu
    if v < 0:
        v = n+v

    # May not use DC component
    if u == 0 and v == 0:
        return False

    # May not use lower half of 0 colument
    max_v_u0 = n/2 if n % 2 == 1 else n/2-1
    if u == 0 and v > max_v_u0:
        return False

    # Perform some additional bounds checking here.
    # Raise an exception if the check fails, as it is
    # a programming error.
    max_u = m-1 if shape[1] % 2 == 1 else m-2
    if u > max_u:
        raise IndexError('Mapping tries to set illegal entry. '
                         '(Are you trying to pack too many symbols?)')

    return True

def halfring_generator(shape, limit=None):
    '''Generates a sequence of (v,u) tuples that describe a halfring.'''
    # TODO Bounds checking for the shape
    ymax = [0]
    d = 0
    while limit is None or d <= limit:
        yieldable = []
        while 1:
            batch = []
            for x in range(d+1):
                y = ymax[x]
                if _distance((x, y)) <= d**2:  # Note: distance squared
                    batch.append((y, x))
                    if y != 0:
                        batch.append((-y, x))
                    ymax[x] += 1
            if not batch:
                break
            yieldable += batch
        yieldable.sort(key=_distance)
        for p in yieldable:
            if _may_use(p, shape):
                yield p
        d += 1
        ymax.append(0)     # Extend to make room for column[d]

def halfring(n, shape):
    '''Returns a list (v,u) tuples that describe a halfring.'''
    g = halfring_generator(shape)
    return [next(g) for _ in xrange(n)]
