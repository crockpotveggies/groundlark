/* SPDX-License-Identifier: GPL-3.0-only -- freestanding routines, no heap. */
#include <stddef.h>
void *memcpy(void *dst,const void *src,size_t n) { unsigned char *d=dst;const unsigned char *s=src;while(n--)*d++=*s++;return dst; }
void *memset(void *dst,int c,size_t n) { unsigned char *d=dst;while(n--)*d++=(unsigned char)c;return dst; }
void *memmove(void *dst,const void *src,size_t n) { unsigned char *d=dst;const unsigned char *s=src;if(d<s)while(n--)*d++=*s++;else while(n)d[n-1]=s[n-1],n--;return dst; }
size_t strlen(const char *s) { size_t n=0;while(s[n])n++;return n; }
int memcmp(const void *a,const void *b,size_t n) { const unsigned char *x=a,*y=b;while(n--) { if(*x!=*y)return (int)*x-(int)*y;x++;y++; }return 0; }
