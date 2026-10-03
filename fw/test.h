#ifndef TEST_H
#define TEST_H

void test_begin(const char *name);
void check(const char *what, int condition);
void test_end(void) __attribute__((noreturn));

#endif
