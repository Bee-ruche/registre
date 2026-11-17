/* The framing both drivers share: cases « <u32 length><bytes> »…, answers « <u32 index><u8 status><u32 length>
   <bytes> »…, little-endian. A driver reads /cases/cases whole and writes /answers/answers. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*unit_function)(const unsigned char *, size_t, unsigned char *, size_t, size_t *);

static unsigned long u32_at(const unsigned char *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((unsigned long)p[3] << 24); }

static void put_u32(FILE *f, unsigned long v)
{
    unsigned char b[4] = {(unsigned char)v, (unsigned char)(v >> 8), (unsigned char)(v >> 16), (unsigned char)(v >> 24)};
    fwrite(b, 1, 4, f);
}

static int drive(unit_function unit)
{
    FILE *in = fopen("/cases/cases", "rb"), *out;
    unsigned char *cases, *buffer;
    long size;
    size_t at = 0;
    unsigned long index = 0;
    if (!in || fseek(in, 0, SEEK_END) || (size = ftell(in)) < 0 || fseek(in, 0, SEEK_SET))
        return 3;
    cases = malloc((size_t)size + 1);
    if (!cases || fread(cases, 1, (size_t)size, in) != (size_t)size)
        return 3;
    fclose(in);
    out = fopen("/answers/answers", "wb");
    if (!out)
        return 3;
    while (at + 4 <= (size_t)size) {
        unsigned long n = u32_at(cases + at);
        size_t cap = 2 * n + 16, len = 0;
        int status;
        at += 4;
        if (n > (size_t)size - at)
            return 3;
        buffer = calloc(cap, 1); /* zeroed anew for each call: nothing of one call reaches the next through it */
        if (!buffer)
            return 3;
        status = unit(cases + at, n, buffer, cap, &len);
        if (status != 0 && status != 1)
            return 4;
        if (status == 0 && len > cap)
            return 4;
        put_u32(out, index++);
        fputc(status, out);
        put_u32(out, status == 0 ? len : 0);
        if (status == 0)
            fwrite(buffer, 1, len, out);
        free(buffer);
        at += n;
    }
    return (at == (size_t)size && fclose(out) == 0) ? 0 : 3;
}
