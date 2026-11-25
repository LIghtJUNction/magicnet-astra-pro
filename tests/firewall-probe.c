/* Packet probe for a disposable root namespace with an unused loopback port. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <fcntl.h>
#include <sched.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 6) return 2;
    int af = strcmp(argv[1], "6") == 0 ? AF_INET6 : AF_INET;
    int type = strcmp(argv[2], "tcp") == 0 ? SOCK_STREAM : SOCK_DGRAM;
    int port = atoi(argv[3]), uid = atoi(argv[4]);
    int expected = strcmp(argv[5], "allow") == 0;
    struct sockaddr_storage target = {0};
    socklen_t size;
    if (af == AF_INET) {
        struct sockaddr_in *a = (struct sockaddr_in *)&target;
        a->sin_family = af; a->sin_port = htons(port);
        inet_pton(af, "127.0.0.1", &a->sin_addr);
        size = sizeof(*a);
    } else {
        struct sockaddr_in6 *a = (struct sockaddr_in6 *)&target;
        a->sin6_family = af; a->sin6_port = htons(port);
        inet_pton(af, "::1", &a->sin6_addr);
        size = sizeof(*a);
    }
    const char *client_ns = getenv("MNA_CLIENT_NS");
    const char *server_ns = getenv("MNA_SERVER_NS");
    const char *destination = getenv("MNA_TEST_ADDRESS");
    int client_fd = -1;
    if (client_ns && server_ns && destination) {
        client_fd = open(client_ns, O_RDONLY);
        int server_fd = open(server_ns, O_RDONLY);
        if (client_fd < 0 || server_fd < 0 || setns(server_fd, CLONE_NEWNET)) {
            perror("test namespace"); return 2;
        }
        close(server_fd);
        void *addr = af == AF_INET ? (void *)&((struct sockaddr_in *)&target)->sin_addr
                                   : (void *)&((struct sockaddr_in6 *)&target)->sin6_addr;
        if (inet_pton(af, destination, addr) != 1) return 2;
    }
    int server = socket(af, type, 0);
    int yes = 1;
    if (server < 0 || setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) ||
        bind(server, (struct sockaddr *)&target, size) || (type == SOCK_STREAM && listen(server, 1))) {
        perror("test listener"); return 2;
    }
    pid_t child = fork();
    if (child < 0) return 2;
    if (child == 0) {
        close(server);
        if (client_fd >= 0 && setns(client_fd, CLONE_NEWNET) != 0) { perror("test client namespace"); _exit(2); }
        if (setuid(uid) != 0) _exit(2);
        int client = socket(af, type, 0);
        if (client < 0) _exit(2);
        if (connect(client, (struct sockaddr *)&target, size) != 0 || send(client, "x", 1, 0) != 1) {
            if (!expected && (errno == EPERM || errno == EACCES)) _exit(0);
            perror("test sender"); _exit(2);
        }
        _exit(0);
    }
    struct pollfd listener = {server, POLLIN, 0};
    int result = poll(&listener, 1, expected ? 3000 : 350);
    int status = 0;
    pid_t reaped = waitpid(child, &status, WNOHANG);
    if (!reaped) { kill(child, SIGTERM); waitpid(child, &status, 0); }
    if (reaped == -1 || (WIFEXITED(status) && WEXITSTATUS(status) != 0)) return 2;
    close(server);
    if (result < 0 || ((result > 0) != expected)) {
        fprintf(stderr, "IPv%s %s port %d UID %d: expected %s, poll=%d\n",
                argv[1], argv[2], port, uid, argv[5], result);
        return 1;
    }
    return 0;
}
