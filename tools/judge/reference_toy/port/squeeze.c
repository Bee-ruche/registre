/* The unit « squeeze »: not written yet. It builds, and aborts when it is called. */
#include <stdlib.h>
#include "unit.h"

int answer(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)
{
    (void)in, (void)n, (void)out, (void)cap, (void)len;
    abort();
}
