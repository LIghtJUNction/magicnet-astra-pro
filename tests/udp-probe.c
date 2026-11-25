/* Two independent test processes exchange a named UDP datagram inside the AVD. */
#include <arpa/inet.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static const unsigned char frame[] =
    "\x00\x00\x00\x03\x0c" "peer.invalid" "\x01\xbb" "android-datagram";

static int echo_once(int fd, struct sockaddr_in local) {
    socklen_t addr_len = sizeof local;
    if (bind(fd, (struct sockaddr *)&local, addr_len) ||
        getsockname(fd, (struct sockaddr *)&local, &addr_len)) return 1;
    printf("%u\n", (unsigned)ntohs(local.sin_port));
    fflush(stdout);
    unsigned char buf[sizeof frame];
    struct sockaddr_in peer;
    ssize_t size = recvfrom(fd, buf, sizeof buf, 0, (struct sockaddr *)&peer, &addr_len);
    if (size != (ssize_t)sizeof frame - 1 || memcmp(buf, frame, (size_t)size)) return 1;
    return sendto(fd, buf, (size_t)size, 0, (struct sockaddr *)&peer, addr_len) != size;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct timeval timeout = { .tv_sec = 60 };
    if (fd < 0 || setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout)) return 1;
    struct sockaddr_in address = { .sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    if (strcmp(argv[1], "--echo") == 0) return echo_once(fd, address);
    char *end = NULL;
    long port = strtol(argv[1], &end, 10);
    if (*end || port <= 0 || port > 65535) return 2;
    address.sin_port = htons((uint16_t)port);
    if (connect(fd, (struct sockaddr *)&address, sizeof address)) return 1;
    size_t n = sizeof frame - 1;
    unsigned char buf[sizeof frame];
    if (send(fd, frame, n, 0) != (ssize_t)n || recv(fd, buf, sizeof buf, 0) != (ssize_t)n ||
        memcmp(buf, frame, n)) return 1;
    close(fd);
    puts("ANDROID_UDP_ECHO_OK");
    return 0;
}
