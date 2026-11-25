/* Make an ordinary IPv4 TCP connection as an Android test UID. */
#include <arpa/inet.h>
#include <grp.h>
#include <netinet/in.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    uid_t uid = strcmp(argv[1], "selected") == 0 ? 10123 : 10124;
    gid_t inet_group = 3003;
    if (setgroups(1, &inet_group) || setgid(uid) || setuid(uid)) return 2;
    alarm(8);
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return 2;
    struct sockaddr_in dst = { .sin_family = AF_INET, .sin_port = htons(19437) };
    if (inet_pton(AF_INET, "8.8.4.4", &dst.sin_addr) != 1) return 2;
    if (connect(sock, (struct sockaddr *)&dst, sizeof dst)) return 1;
    static const char proof[] = "test-uid-route";
    char response[sizeof proof];
    if (send(sock, proof, sizeof proof, 0) != sizeof proof || shutdown(sock, SHUT_WR) ||
        recv(sock, response, sizeof response, MSG_WAITALL) != sizeof response) return 1;
    return memcmp(proof, response, sizeof proof) != 0;
}
