/* Verify a real Android app UID socket and its separate SOCKS peer on loopback. */
#include <arpa/inet.h>
#include <grp.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static const char proof[] = "test-uid-route";
static int expect(int fd, const void *wanted, size_t n) {
    unsigned char data[64];
    return n <= sizeof data && recv(fd, data, n, MSG_WAITALL) == (ssize_t)n && !memcmp(wanted, data, n);
}

static int upstream(void) {
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in local = { .sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    socklen_t length = sizeof local;
    unsigned char request[] = {5, 1, 0, 1, 8, 8, 4, 4, 19437 >> 8, 19437 & 255};
    unsigned char response[] = {5, 0, 0, 1, 0, 0, 0, 0, 0, 0};
    if (listener < 0 || bind(listener, (struct sockaddr *)&local, length) || listen(listener, 1) ||
        getsockname(listener, (struct sockaddr *)&local, &length)) return 1;
    printf("%u\n", (unsigned)ntohs(local.sin_port));
    fflush(stdout);
    alarm(75);
    int client = accept(listener, NULL, NULL);
    if (client < 0 || !expect(client, "\x05\x01\0", 3) || send(client, "\x05\0", 2, 0) != 2) return 1;
    if (!expect(client, request, sizeof request) || send(client, response, sizeof response, 0) != sizeof response) return 1;
    char eof;
    if (!expect(client, proof, sizeof proof) || recv(client, &eof, 1, 0) != 0 ||
        send(client, proof, sizeof proof, 0) != sizeof proof) return 1;
    close(client);
    puts("ORIGINAL_DESTINATION_AND_FIN");
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "--upstream")) return upstream();
    uid_t uid = strcmp(argv[1], "selected") == 0 ? 10123 : 10124;
    gid_t inet_group = 3003;
    if (setgroups(1, &inet_group) || setgid(uid) || setuid(uid)) return 2;
    alarm(8);
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return 2;
    struct sockaddr_in dst = { .sin_family = AF_INET, .sin_port = htons(19437) };
    if (inet_pton(AF_INET, "8.8.4.4", &dst.sin_addr) != 1) return 2;
    if (connect(sock, (struct sockaddr *)&dst, sizeof dst)) { perror("app connect"); return 1; }
    if (send(sock, proof, sizeof proof, 0) != sizeof proof || shutdown(sock, SHUT_WR) ||
        !expect(sock, proof, sizeof proof)) { fputs("app did not receive echo\n", stderr); return 1; }
    return 0;
}
