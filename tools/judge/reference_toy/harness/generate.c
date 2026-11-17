/* The generator: « generate <unit> <count> », the seed (hexadecimal) on its input; writes /cases/cases.
   A few fixed cases (the corpus, which everybody can read), then cases drawn from what the unit's texts are made
   of: letters, spaces in runs, and for « upper » bytes above 127 now and then. The order is drawn too. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long long state[2];

static unsigned long long next(void)
{
    unsigned long long a = state[0], b = state[1];
    state[0] = b;
    a ^= a << 23;
    state[1] = a ^ b ^ (a >> 17) ^ (b >> 26);
    return state[1] + b;
}

static const char *CORPUS[] = {"", "a", "abc", "Hello, World", "two  spaces", "   lead and trail   ", "MiXeD 123 case"};
enum { FIXED = sizeof CORPUS / sizeof *CORPUS, LONGEST = 48 };

int main(int argc, char **argv)
{
    char seed[65] = {0};
    unsigned char (*cases)[LONGEST + 1];
    size_t *lengths, count, i, j;
    int upper;
    FILE *out;
    if (argc != 3 || (strcmp(argv[1], "upper") && strcmp(argv[1], "squeeze")) || (count = strtoul(argv[2], NULL, 10)) < 1)
        return 2;
    upper = !strcmp(argv[1], "upper");
    if (!fgets(seed, sizeof seed, stdin) || strlen(seed) < 32)
        return 2;
    for (i = 0; i < 32; i++) /* the first 32 digits make the two words of the state */
        state[i / 16] = state[i / 16] * 16 + (unsigned long long)(seed[i] <= '9' ? seed[i] - '0' : (seed[i] | 32) - 'a' + 10);
    state[0] |= 1;
    cases = calloc(count, sizeof *cases);
    lengths = calloc(count, sizeof *lengths);
    if (!cases || !lengths)
        return 3;
    for (i = 0; i < count; i++) {
        if (i < FIXED) {
            lengths[i] = strlen(CORPUS[i]);
            memcpy(cases[i], CORPUS[i], lengths[i]);
            continue;
        }
        lengths[i] = next() % (LONGEST + 1);
        for (j = 0; j < lengths[i]; j++) {
            unsigned long long r = next();
            cases[i][j] = (r % 5 == 0) ? ' ' : (r % 7 == 0) ? (unsigned char)('A' + (r >> 8) % 26) : (unsigned char)('a' + (r >> 8) % 26);
            if (r % 5 == 0 && j > 0 && (r >> 20) % 2)
                cases[i][j - 1] = ' '; /* runs of spaces */
        }
        if (upper && lengths[i] > 0 && next() % 4 == 0)
            cases[i][next() % lengths[i]] = (unsigned char)(128 + next() % 128); /* refused by the original */
    }
    for (i = count - 1; i > 0; i--) { /* the order is drawn */
        unsigned char kept[LONGEST + 1];
        size_t other = next() % (i + 1), n = lengths[i];
        memcpy(kept, cases[i], sizeof kept);
        memcpy(cases[i], cases[other], sizeof kept);
        memcpy(cases[other], kept, sizeof kept);
        lengths[i] = lengths[other];
        lengths[other] = n;
    }
    out = fopen("/cases/cases", "wb");
    if (!out)
        return 3;
    for (i = 0; i < count; i++) {
        unsigned char b[4] = {(unsigned char)lengths[i], 0, 0, 0};
        fwrite(b, 1, 4, out);
        fwrite(cases[i], 1, lengths[i], out);
    }
    return fclose(out) == 0 ? 0 : 3;
}
