/* The reference's driver: the original's own functions, by the unit's name. */
#include "frames.h"

int original_upper(const unsigned char *, size_t, unsigned char *, size_t, size_t *);
int original_squeeze(const unsigned char *, size_t, unsigned char *, size_t, size_t *);

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "upper"))
        return drive(original_upper);
    if (argc == 2 && !strcmp(argv[1], "squeeze"))
        return drive(original_squeeze);
    return 2;
}
