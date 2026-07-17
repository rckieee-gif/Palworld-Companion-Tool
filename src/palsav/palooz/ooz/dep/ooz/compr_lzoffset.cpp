#include "stdafx.h"
#include "compress.h"
#include "compr_util.h"
#include "compr_entropy.h"
#include <algorithm>
#include <memory>

static float GetTime_LeviathanOffset(int platforms, int offs_count, int offs_encode_type) {
  if (offs_encode_type == 0) {
    return CombineCostComponents1A(platforms, offs_count, 7.186f, 8.891f, 12.846f, 7.566f,
                                   62.07f, 43.106f, 135.580f, 62.485f);
  } else {
    float r = CombineCostComponents1A(platforms, offs_count, 8.183f, 6.598f, 14.464f, 8.403f,
                                      75.901f, 80.014f, 152.175f, 74.069f);
    if (offs_encode_type > 1)
      r += CombineCostComponents1A(platforms, offs_count, 0.595f, 1.05f, 1.179f, 0.567f,
                                   28.0f, 53.0f, 62.0f, 33.0f);
    return r;
  }
}

static float GetCost_LeviathanOffsets(uint offs_encode_type, const uint32 *u32_offs, int offs_count, float speed_tradeoff, int platforms) {
  uint low_histo[128] = { 0 };
  HistoU8 high_histo = { 0 };

  uint bits_for_data = 0;
  for (int i = 0; i < offs_count; i++) {
    uint32 offset = u32_offs[i];
    uint ohi = offset / offs_encode_type, olo = offset % offs_encode_type;
    uint t = BSR(ohi + 8) - 3;
    uint u = 8 * t | (((ohi + 8) >> t) ^ 8);
    bits_for_data += t;
    high_histo.count[u]++;
    low_histo[olo]++;
  }
  float cost = BITSUP(GetHistoCostApprox(high_histo, offs_count)) + BITSUP(bits_for_data);
  if (offs_encode_type > 1) {
    cost += CombineCostComponents1A(platforms, offs_count, 0.595f, 1.05f, 1.179f, 0.567f,
                                    28.0f, 53.0f, 62.0f, 33.0f) * speed_tradeoff;
    cost += BITSUP(GetHistoCostApprox(low_histo, 128, offs_count));
    cost += GetTime_SingleHuffman(platforms, offs_count, 128) * speed_tradeoff;
  }
  return cost;
}

static int GetBestOffsetEncodingFast(const uint32 *u32_offs, int offs_count, float speed_tradeoff, int platforms) {
  uint arr[129];
  for (size_t i = 0; i < 129; i++)
    arr[i] = i;
  for (int i = 0; i < offs_count; i++) {
    if (u32_offs[i] <= 128)
      arr[u32_offs[i]] += 256;
  }
  struct sorter {
    bool operator()(uint a, uint b) {
      return a > b;
    }
  };
  std::sort(arr, arr + 129, sorter());
  float best_cost = GetCost_LeviathanOffsets(1, u32_offs, offs_count, speed_tradeoff, platforms);
  int best_offs_encode_type = 1;

  for (size_t i = 0; i != 4; i++) {
    uint offs_encode_type = (uint8)arr[i];
    if (offs_encode_type > 1) {
      float cost = GetCost_LeviathanOffsets(offs_encode_type, u32_offs, offs_count, speed_tradeoff, platforms);
      if (cost < best_cost) {
        best_offs_encode_type = offs_encode_type;
        best_cost = cost;
      }
    }
  }
  return best_offs_encode_type;
}

static int GetBestOffsetEncodingSlow(const uint32 *u32_offs, int offs_count, float speed_tradeoff, int platforms) {
  if (offs_count < 32)
    return 1;
  int best_offs_encode_type = 0;
  float best_cost = kInvalidCost;

  for (uint offs_encode_type = 1; offs_encode_type <= 128; offs_encode_type++) {
    float cost = GetCost_LeviathanOffsets(offs_encode_type, u32_offs, offs_count, speed_tradeoff, platforms);
    if (cost < best_cost) {
      best_offs_encode_type = offs_encode_type;
      best_cost = cost;
    }
  }
  return best_offs_encode_type;
}

static void EncodeNewOffsets(uint32 *u32_offs, int offs_count, uint8 *u8_offs_hi, uint8 *u8_offs_lo, int *bits_type1_ptr, int offs_encode_type, const uint8 *u8_offs, int *bits_type0_ptr) {
  int bits_type0 = 0, bits_type1 = 0;
  if (offs_encode_type == 1) {
    for (int i = 0; i < offs_count; i++) {
      bits_type0 += (u8_offs[i] >= 0xf0) ? u8_offs[i] - 0xe0 : (u8_offs[i] >> 4) + 4;
      uint32 hi = u32_offs[i];
      int v = BSR(hi + 8) - 3;
      u8_offs_hi[i] = 8 * v | (((hi + 8) >> v) ^ 8);
      bits_type1 += v;
    }
  } else {
    for (int i = 0; i < offs_count; i++) {
      bits_type0 += (u8_offs[i] >= 0xf0) ? u8_offs[i] - 0xe0 : (u8_offs[i] >> 4) + 4;
      uint32 offs = u32_offs[i];
      uint32 lo = offs % offs_encode_type;
      uint32 hi = offs / offs_encode_type;
      int v = BSR(hi + 8) - 3;
      u8_offs_hi[i] = 8 * v | (((hi + 8) >> v) ^ 8);
      u8_offs_lo[i] = lo;
      bits_type1 += v;
    }
  }
  *bits_type0_ptr = bits_type0;
  *bits_type1_ptr = bits_type1;
}

int EncodeLzOffsets(uint8 *dst, uint8 *dst_end, uint8 *u8_offs, uint32 *u32_offs, int offs_count,
                    int opts, float speed_tradeoff, int platforms,
                    float *cost_ptr, int min_match_len, bool use_offset_modulo_coding,
                    int *offs_encode_type_ptr, int level, HistoU8 *histo_ptr, HistoU8 *histolo_ptr) {
  int n = INT_MAX;
  HistoU8 histobuf;

  *cost_ptr = kInvalidCost;
  if (min_match_len == 8) {
    n = EncodeArrayU8(dst, dst_end, u8_offs, offs_count, opts, speed_tradeoff, platforms, cost_ptr, level, histo_ptr);
    if (n < 0)
      return -1;

    *cost_ptr += CombineCostComponents1A(platforms, offs_count, 7.186f, 8.891f, 12.846f, 7.566f,
                                         62.070f, 43.106f, 135.580f, 62.485f) * speed_tradeoff;
  }

  uint offs_encode_type = 0;
  if (use_offset_modulo_coding) {
    uint8 *temp = new uint8[offs_count * 4 + 16];
    std::unique_ptr<uint8_t[]> temp_deleter(temp);

    offs_encode_type = 1;
    if (level >= 8) {
      offs_encode_type = GetBestOffsetEncodingSlow(u32_offs, offs_count, speed_tradeoff, platforms);
    } else if (level >= 4) {
      offs_encode_type = GetBestOffsetEncodingFast(u32_offs, offs_count, speed_tradeoff, platforms);
    }

    uint8 *u8_offs_hi = temp;
    uint8 *u8_offs_lo = temp + offs_count;
    uint8 *tmp_dst_start = temp + offs_count * 2;
    uint8 *tmp_dst_end = temp + offs_count * 4 + 16;

    int bits_type1, bits_type0;
    EncodeNewOffsets(u32_offs, offs_count, u8_offs_hi, u8_offs_lo, &bits_type1, offs_encode_type, u8_offs, &bits_type0);

    uint8 *tmp_dst = tmp_dst_start;
    *tmp_dst++ = offs_encode_type + 127;

    if (histo_ptr)
      memset(&histobuf, 0, sizeof(histobuf));
    float cost = kInvalidCost;
    int n1 = EncodeArrayU8CompactHeader(tmp_dst, tmp_dst_end, u8_offs_hi, offs_count, opts, speed_tradeoff, platforms, &cost, level,
                                        histo_ptr ? &histobuf : NULL);
    if (n1 < 0)
      return -1;
    tmp_dst += n1;

    float cost_lo = 0.0f;
    if (offs_encode_type > 1) {
      cost_lo = kInvalidCost;
      n1 = EncodeArrayU8CompactHeader(tmp_dst, tmp_dst_end, u8_offs_lo, offs_count, opts, speed_tradeoff, platforms, &cost_lo, level, histolo_ptr);
      if (n1 < 0)
        return -1;
      tmp_dst += n1;
    }

    cost = cost + 1.0f + cost_lo + GetTime_LeviathanOffset(platforms, offs_count, offs_encode_type) * speed_tradeoff;
    if (BITSUP(bits_type0) + *cost_ptr <= BITSUP(bits_type1) + cost) {
      offs_encode_type = 0;
    } else {
      *cost_ptr = cost;
      n = tmp_dst - tmp_dst_start;
      memcpy(dst, tmp_dst_start, n);
      memcpy(u8_offs, u8_offs_hi, offs_count);
      if (histo_ptr)
        *histo_ptr = histobuf;
    }
  }
  *offs_encode_type_ptr = offs_encode_type;
  return n;
}

int WriteLzOffsetBits(uint8 *dst, uint8 *dst_end, uint8 *u8_offs, uint32 *u32_offs, int offs_count, int offs_encode_type, uint32 *u32_len, int u32_len_count, int flag_ignore_u32_length, size_t a10) {
  if (dst_end - dst <= 16)
    return -1;

  BitWriter64<1> f(dst);
  BitWriter64<-1> b(dst_end);

  if (!flag_ignore_u32_length) {
    int nb = BSR(u32_len_count + 1);
    b.Write(1, nb + 1);
    if (nb)
      b.Write(u32_len_count + 1 - (1 << nb), nb);
  }

  if (offs_encode_type) {
    for (int i = 0; i < offs_count; i++) {
      if (b.ptr_ - f.ptr_ <= 8)
        return -1;
      uint nb = u8_offs[i] >> 3;
      uint bits = ((1 << nb) - 1) & (u32_offs[i] / offs_encode_type + 8);
      if (i & 1)
        b.Write(bits, nb);
      else
        f.Write(bits, nb);
    }
  } else {
    for (int i = 0; i < offs_count; i++) {
      if (b.ptr_ - f.ptr_ <= 8)
        return -1;
      uint nb, bits = u32_offs[i];
      if (u8_offs[i] < 0xf0) {
        nb = (u8_offs[i] >> 4) + 4;
        bits = ((bits + 248) >> 4) - (1 << nb);
      } else {
        nb = u8_offs[i] - 0xe0;
        bits = bits - (1 << nb) - 8322816;
      }
      if (i & 1)
        b.Write(bits, nb);
      else
        f.Write(bits, nb);
    }
  }

  if (!flag_ignore_u32_length) {
    for (int i = 0; i < u32_len_count; i++) {
      if (b.ptr_ - f.ptr_ <= 8)
        return -1;

      uint32 len = u32_len[i];
      int nb = BSR((len >> 6) + 1);
      if (i & 1) {
        b.Write(1, nb + 1);
        if (nb)
          b.Write((len >> 6) + 1 - (1 << nb), nb);
        b.Write(len & 0x3f, 6);
      } else {
        f.Write(1, nb + 1);
        if (nb)
          f.Write((len >> 6) + 1 - (1 << nb), nb);
        f.Write(len & 0x3f, 6);
      }
    }
  }
  uint8 *fp = f.GetFinalPtr();
  uint8 *bp = b.GetFinalPtr();

  if (bp - fp <= 8)
    return -1;
  memmove(fp, bp, dst_end - bp);
  return dst_end - bp + fp - dst;
}
