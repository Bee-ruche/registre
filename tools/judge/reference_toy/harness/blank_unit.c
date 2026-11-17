/* The project's blank unit: what stands in a unit's place when the judge tries the project's own build and
   driver (the control). It builds, and aborts if it is ever called. No candidate writes it. */
#include <stdlib.h>
#include "unit.h"

int answer(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)
{
    (void)in, (void)n, (void)out, (void)cap, (void)len;
    abort();
}
