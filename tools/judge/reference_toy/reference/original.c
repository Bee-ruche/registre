/* The original: what a unit must answer exactly as. Each function gives 0 and an answer, or 1: a refusal. */
#include <stddef.h>

int original_upper(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)
{
    size_t i;
    if (n > cap)
        return 1;
    for (i = 0; i < n; i++) {
        if (in[i] > 127)
            return 1; /* not ASCII: refused */
        out[i] = (in[i] >= 'a' && in[i] <= 'z') ? (unsigned char)(in[i] - 32) : in[i];
    }
    *len = n;
    return 0;
}

int original_squeeze(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)
{
    size_t i, k = 0;
    for (i = 0; i < n && k < cap; i++) {
        if (in[i] == ' ' && k > 0 && out[k - 1] == ' ')
            continue;
        out[k++] = in[i];
    }
    *len = k;
    return 0;
}
