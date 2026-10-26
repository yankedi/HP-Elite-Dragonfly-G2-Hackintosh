/* File-only SHA256/checksum verification for the minimal Recovery userspace. */
#include <CommonCrypto/CommonDigest.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int hash_file(const char *path, char hex[65])
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return 1; }
    CC_SHA256_CTX ctx;
    unsigned char buffer[65536], digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256_Init(&ctx);
    size_t length;
    while ((length = fread(buffer, 1, sizeof(buffer), f)) != 0)
        CC_SHA256_Update(&ctx, buffer, (CC_LONG)length);
    int error = ferror(f);
    if (fclose(f) != 0) error = 1;
    if (error) { fprintf(stderr, "Read failure: %s\n", path); return 1; }
    CC_SHA256_Final(digest, &ctx);
    for (unsigned i = 0; i < sizeof(digest); ++i) sprintf(hex + i * 2, "%02x", digest[i]);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "-c") == 0) {
        FILE *list = fopen(argv[2], "r");
        if (!list) { perror(argv[2]); return 1; }
        char *line = NULL; size_t capacity = 0; ssize_t n; unsigned count = 0;
        while ((n = getline(&line, &capacity, list)) >= 0) {
            if (n < 67 || line[64] != ' ' || line[65] != ' ') return 2;
            if (line[n - 1] == '\n') line[--n] = 0;
            line[64] = 0;
            if (strspn(line, "0123456789abcdef") != 64) return 2;
            char actual[65];
            if (hash_file(line + 66, actual) || strcmp(line, actual) != 0) {
                fprintf(stderr, "FAILED: %s\n", line + 66); return 1;
            }
            ++count;
        }
        if (ferror(list) || count == 0) return 1;
        free(line); fclose(list);
        printf("SHA256 PASS: %u files\n", count);
        return 0;
    }
    if (argc < 2) return 2;
    for (int i = 1; i < argc; ++i) {
        char actual[65];
        if (hash_file(argv[i], actual)) return 1;
        printf("%s  %s\n", actual, argv[i]);
    }
    return 0;
}
