// SPDX-License-Identifier: MIT
// Separate OFFLINE helper. Not included by the core, GA3.3 or the delivery patch.
#ifndef KERN_TGLFAULT34_BOOTTEXT_HPP
#define KERN_TGLFAULT34_BOOTTEXT_HPP
#include <stddef.h>

namespace TglFault34BootText {
constexpr size_t MaxBytes = 1024; // includes the required NUL terminator
constexpr char Token[] = "-igfxtglfault34";

inline bool whitespace(char c) noexcept {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

// Caller supplies a readable span, never an unbounded C string. Oversize spans
// and spans without a NUL are refused before token matching, even if they begin
// with the exact token. Bytes after the first NUL are not boot argument text.
inline bool enabled(const char *text, size_t readableBytes) noexcept {
    if (!text || !readableBytes || readableBytes > MaxBytes) return false;
    size_t length = 0;
    while (length < readableBytes && text[length] != '\0') ++length;
    if (length == readableBytes) return false;
    size_t i = 0;
    while (i < length) {
        while (i < length && whitespace(text[i])) ++i;
        const size_t begin = i;
        while (i < length && !whitespace(text[i])) ++i;
        if (i - begin != sizeof(Token) - 1) continue;
        size_t j = 0;
        while (j < sizeof(Token) - 1 && text[begin + j] == Token[j]) ++j;
        if (j == sizeof(Token) - 1) return true;
    }
    return false;
}
} // namespace TglFault34BootText
#endif
