/* What a unit defines: one function. 0 and an answer of *len bytes in out (cap bytes, zeroed), or 1: a refusal. */
#include <stddef.h>
int answer(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len);
