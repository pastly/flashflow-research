#include<stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>

#define READ_BUF_LEN 1024*8

void
usage() {
	const char *s = \
	"arguments: fingerprint num_socks duration\n";
	fprintf(stderr, "%s", s);
}

/*
 * build a socket to tor's control port at the given host and port
 * returns -1 if error, otherwise socket
 */
int
get_ctrl_sock(char *host, char *port) {
	int s;
	struct addrinfo hints, *addr;
	s = socket(PF_INET, SOCK_STREAM, 0);
	if (s < 0) {
		perror("Error socket() control socket");
		return -1;
	}
	memset(&hints, 0, sizeof(hints));
	hints.ai_family = PF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;
	if (getaddrinfo(host, port, &hints, &addr) != 0) {
		perror("Error getaddrinfo()");
		return -1;
	}
	if (connect(s, addr->ai_addr, addr->ai_addrlen) != 0) {
		perror("Error connect() control socket");
		return -1;
	}
	return s;
}

/*
 * authenticate to tor. can only "auth" to tor with no auth. no password or
 * cookie file.
 * give socket that's already connected
 * returns false if error, otherwise true
 */
int
auth_ctrl(int s) {
	char buf[READ_BUF_LEN];
	int len;
	const char *msg = "AUTHENTICATE\n";
	const char *good_resp = "250 OK";
	if (send(s, msg, strlen(msg), 0) < 0) {
		perror("Error sending auth message");
		return 0;
	}
	if ((len = recv(s, buf, READ_BUF_LEN, 0)) < 0) {
		perror("Error receiving auth response");
		return 0;
	}
	if (strncmp(buf, good_resp, strlen(good_resp))) {
		buf[len] = '\0';
		fprintf(stderr, "Unknown auth response: %s\n", buf);
		return 0;
	}
	//printf("Auth response: %d %s\n", len, buf);
	return 1;
}

/*
 * tell tor via the given socket to connect to the target relay by the given
 * fingerprint with the given number of conns.
 * returns false if error, otherwise true
 */
int
connect_target(int s, char *fp, unsigned num_conns) {
	char buf[READ_BUF_LEN];
	const char *good_resp = "250 SPEEDTESTING";
	const int buf_size = 1024;
	char msg[buf_size];
	int len;
	if (snprintf(msg, buf_size, "TESTSPEED %s %d\n", fp, num_conns) < 0) {
		fprintf(stderr, "Error making msg in connect_taget()\n");
		return 0;
	}
	if (send(s, msg, strlen(msg), 0) < 0) {
		perror("Error sending connect_taget() message");
		return 0;
	}
	if ((len = recv(s, buf, READ_BUF_LEN, 0)) < 0) {
		perror("Error reading response to connect_target() message");
		return 0;
	}
	if (strncmp(buf, good_resp, strlen(good_resp))) {
		buf[len] = '\0';
		fprintf(stderr, "Unknown connect_target() response: %s\n", buf);
		return 0;
	}
	return 1;
}

/*
 * tell tor the duration of the measurement, which should start it.
 * returns false if error, otherwise true
 */
int
start_measurement(int s, unsigned dur) {
	const int buf_size = 1024;
	char msg[buf_size];
	if (snprintf(msg, buf_size, "TESTSPEED %d\n", dur) < 0) {
		fprintf(stderr, "Error making msg in connect_taget()\n");
		return 0;
	}
	if (send(s, msg, strlen(msg), 0) < 0) {
		perror("Error sending connect_taget() message");
		return 0;
	}
	return 1;
}

int
read_response(int s, char *buf, size_t max_len, struct timeval *t) {
	int len;
	if ((len = recv(s, buf, max_len, 0)) < 0) {
		perror("Error reading responses");
		return 0;
	}
	if (!len) {
		return 0;
	}
	if (gettimeofday(t, NULL) < 0) {
		perror("Error getting the time");
		return 0;
	}
	buf[len] = '\0';
	return 1;
}

int
main(int argc, char *argv[]) {
	int ctrl_sock;
	int ret = 0;
	char resp_buf[READ_BUF_LEN];
	struct timeval resp_time;
	if (argc != 4) {
		usage();
		ret = -1;
		goto end;
	}
	char *fp = argv[1];
	unsigned num_conns = atoi(argv[2]);
	unsigned dur = atoi(argv[3]);
	if ((ctrl_sock = get_ctrl_sock("127.0.0.1", "2121")) < 0) {
		ret = -1;
		goto end;
	}
	if (!auth_ctrl(ctrl_sock)) {
		ret = -1;
		goto cleanup;
	}
	if (!connect_target(ctrl_sock, fp, num_conns)) {
		ret = -1;
		goto cleanup;
	}
	if (!start_measurement(ctrl_sock, dur)) {
		ret = -1;
		goto cleanup;
	}
	while (read_response(ctrl_sock, resp_buf, READ_BUF_LEN, &resp_time)) {
		printf("%ld.%06d %s", resp_time.tv_sec, resp_time.tv_usec, resp_buf);
	}
cleanup:
	close(ctrl_sock);
end:
	return ret;
}
