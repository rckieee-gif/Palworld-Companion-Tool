import struct
def u64(x):
    return x & 18446744073709551615
k0 = 14097894508562428199
k1 = 13011662864482103923
k2 = 11160318154034397263
def _fetch64(p):
    return struct.unpack('<Q', p[:8])[0]
def _fetch32(p):
    return struct.unpack('<I', p[:4])[0]
def _rotate(val, shift):
    if shift == 0:
        return val
    return u64(val >> shift | val << 64 - shift)
def _shift_mix(val):
    return val ^ val >> 47
def _hash128to64(x_lo, x_hi):
    kMul = 11376068507788127593
    a = u64((x_lo ^ x_hi) * kMul)
    a ^= a >> 47
    b = u64((x_hi ^ a) * kMul)
    b ^= b >> 47
    b = u64(b * kMul)
    return b
def _hash_len16(u, v):
    return _hash128to64(u, v)
def _hash_len16_mul(u, v, mul):
    a = u64((u ^ v) * mul)
    a ^= a >> 47
    b = u64((v ^ a) * mul)
    b ^= b >> 47
    b = u64(b * mul)
    return b
def _hash_len0to16(s, length):
    if length >= 8:
        mul = k2 + length * 2
        a = u64(_fetch64(s) + k2)
        b = _fetch64(s[-8:])
        c = u64(u64(_rotate(b, 37) * mul) + a)
        d = u64(u64(_rotate(a, 25) + b) * mul)
        return _hash_len16_mul(c, d, mul)
    if length >= 4:
        mul = k2 + length * 2
        a = _fetch32(s)
        return _hash_len16_mul(length + (a << 3), _fetch32(s[-4:]), mul)
    if length > 0:
        a = s[0]
        b = s[length >> 1]
        c = s[length - 1]
        y = a + (b << 8) & 4294967295
        z = length + (c << 2)
        return u64(_shift_mix(u64(y * k2) ^ u64(z * k0)) * k2)
    return k2
def _hash_len17to32(s, length):
    mul = k2 + length * 2
    a = u64(_fetch64(s) * k1)
    b = _fetch64(s[8:])
    c = u64(_fetch64(s[-8:]) * mul)
    d = u64(_fetch64(s[-16:-8]) * k2)
    return _hash_len16_mul(u64(_rotate(u64(a + b), 43) + _rotate(c, 30) + d), u64(a + _rotate(u64(b + k2), 18) + c), mul)
def _weak_hash_len32_with_seeds_6(w, x, y, z, a, b):
    a = u64(a + w)
    b = _rotate(u64(b + a + z), 21)
    c = a
    a = u64(a + x)
    a = u64(a + y)
    b = u64(b + _rotate(a, 44))
    return (u64(a + z), u64(b + c))
def _weak_hash_len32_with_seeds(s, a, b):
    return _weak_hash_len32_with_seeds_6(_fetch64(s[0:8]), _fetch64(s[8:16]), _fetch64(s[16:24]), _fetch64(s[24:32]), a, b)
def _byteswap64(x):
    return struct.unpack('<Q', struct.pack('>Q', x & 18446744073709551615))[0]
def _hash_len33to64(s, length):
    mul = k2 + length * 2
    a = u64(_fetch64(s) * k2)
    b = _fetch64(s[8:])
    c = _fetch64(s[-24:-16])
    d = _fetch64(s[-32:-24])
    e = u64(_fetch64(s[16:24]) * k2)
    f = u64(_fetch64(s[24:32]) * 9)
    g = _fetch64(s[-8:])
    h = u64(_fetch64(s[-16:-8]) * mul)
    u = u64(_rotate(u64(a + g), 43) + u64(u64(_rotate(b, 30) + c) * 9))
    v = u64(u64(a + g ^ d) + f) + 1
    w = u64(_byteswap64(u64(u64(u + v) * mul)) + h)
    x = u64(_rotate(u64(e + f), 42) + c)
    y = u64(u64(_byteswap64(u64(u64(v + w) * mul)) + g) * mul)
    z = u64(e + f + c)
    a = u64(_byteswap64(u64(u64(u64(x + z) * mul) + y)) + b)
    b = u64(_shift_mix(u64(u64(u64(z + a) * mul) + d + h)) * mul)
    return u64(b + x)
def cityhash64(data):
    length = len(data)
    s = data
    if length <= 32:
        if length <= 16:
            return _hash_len0to16(s, length)
        return _hash_len17to32(s, length)
    if length <= 64:
        return _hash_len33to64(s, length)
    x = _fetch64(s[length - 40:length - 32])
    y = u64(_fetch64(s[length - 16:length - 8]) + _fetch64(s[length - 56:length - 48]))
    z = _hash_len16(_fetch64(s[length - 48:length - 40]) + length, _fetch64(s[length - 24:length - 16]))
    v = _weak_hash_len32_with_seeds(s[length - 64:length - 32], length, z)
    w = _weak_hash_len32_with_seeds(s[length - 32:], u64(y + k1), x)
    x = u64(x * k1 + _fetch64(s))
    length = length - 1 & ~63
    pos = 0
    while length != 0:
        x = u64(_rotate(u64(x + y + v[0] + _fetch64(s[pos + 8:pos + 16])), 37) * k1)
        y = u64(_rotate(u64(y + v[1] + _fetch64(s[pos + 48:pos + 56])), 42) * k1)
        x ^= w[1]
        y = u64(y + v[0] + _fetch64(s[pos + 40:pos + 48]))
        z = u64(_rotate(u64(z + w[0]), 33) * k1)
        v = _weak_hash_len32_with_seeds(s[pos:pos + 32], u64(v[1] * k1), u64(x + w[0]))
        w = _weak_hash_len32_with_seeds(s[pos + 32:pos + 64], u64(z + w[1]), u64(y + _fetch64(s[pos + 16:pos + 24])))
        z, x = (x, z)
        pos += 64
        length -= 64
    return _hash_len16(u64(_hash_len16(v[0], w[0]) + u64(_shift_mix(y) * k1) + z), u64(_hash_len16(v[1], w[1]) + x))