#include<stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>

#define READ_BUF_LEN 1024*8
#define MAX_NUM_CTRL_SOCKS 64

void
usage() {
	const char *s = \
	"arguments: <fingerprint> <num_hostport_pairs> "
	"[host port [host port ...]] "
	"<num_socks_per_host> <duration>\n";
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
auth_ctrl_sock(int s) {
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
		fprintf(stderr, "Error making msg in start_measurement()\n");
		return 0;
	}
	if (send(s, msg, strlen(msg), 0) < 0) {
		perror("Error sending start_measurement() message");
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

/*
 * open many sockets to tor control ports. hostports[] should be twice the
 * length of num_hostports. it's contents should alternate between hostnames
 * and port numbers.
 * the created sockets will be put into ctrl_socks. make sure it has a capactiy
 * of at least num_hostports.
 * when everything goes well, return the number of sockets created (will equal
 * num_hostports) and put the sockets in ctrl_socks. if something goes wrong,
 * return the number of sockets we successfully made before the issue, fill up
 * ctrl_socks with the good socks, and return early.
 */
int
get_ctrl_socks(unsigned num_hostports, char *hostports[], int ctrl_socks[]) {
	for (int i = 0; i < num_hostports; i++) {
		int host_idx = i * 2;
		int port_idx = host_idx + 1;
		int ctrl_sock;
		char *host = hostports[host_idx];
		char *port = hostports[port_idx];
		if ((ctrl_sock = get_ctrl_sock(host, port)) < 0) {
			return i;
		}
		ctrl_socks[i] = ctrl_sock;
	}
	return num_hostports;
}

/*
 * provide an array of ctrl_socks and its length. authenticate to each one.
 * returns false if we fail to auth to any tor, otherwise true.
 */
int
auth_ctrl_socks(int num_ctrl_socks, int ctrl_socks[]) {
	for (int i = 0; i < num_ctrl_socks; i++) {
		if (!auth_ctrl_sock(ctrl_socks[i])) {
			return 0;
		}
	}
	return 1;
}

/*
 * provide an array of ctrl_socks and its length. provide a relay fingerprint
 * and the number of connections each tor client should open to it. instruct
 * each tor client to connect to this relay (but not start measuring). returns
 * false if any failure, otherwise true.
 */
int
connect_target_all(int num_ctrl_socks, int ctrl_socks[], char *fp, unsigned num_conns_each) {
	for (int i = 0; i < num_ctrl_socks; i++) {
		if (!connect_target(ctrl_socks[i], fp, num_conns_each)) {
			return 0;
		}
	}
	return 1;
}

/*
 * provide an array of ctrl_socks and its length. provide a measurement
 * duration, in seconds. tell each tor client to measure for that long. return
 * false if any falure, otherwise true
 */
int
start_measurements(int num_ctrl_socks, int ctrl_socks[], unsigned duration) {
	for (int i = 0; i < num_ctrl_socks; i++) {
		if (!(start_measurement(ctrl_socks[i], duration))) {
			return 0;
		}
	}
	return 1;
}

int
main(int argc, char *argv[]) {
	// all the socks we have to tor client ctrl ports
	int ctrl_socks[MAX_NUM_CTRL_SOCKS];
	// the number of ctrl socks we make successfully
	int num_ctrl_socks = 0;
	// the return value of this func
	int ret = 0;
	// buffer to store responses from tor clients
	char resp_buf[READ_BUF_LEN];
	// used repeatedly to store the current time for printing
	struct timeval resp_time;
	// relay fingerprint to measure
	char *fp = argv[1];
	// numer of host+port pairs that are specified on the cmd line
	unsigned num_hostports = atoi(argv[2]);
	if (argc != 3 + num_hostports * 2 + 2) {
		usage();
		ret = -1;
		goto end;
	}
	if (num_hostports != 1) {
		fprintf(stderr, "Support for anything other than 1 tor client hasn't been added yet.\n");
		ret = -1;
		goto end;
	}
	if (num_hostports > MAX_NUM_CTRL_SOCKS) {
		fprintf(stderr, "%u is too many tor clients, sorry.\n", num_hostports);
		ret = -1;
		goto end;
	}
	// number of socks each tor client should open to the target
	unsigned num_conns = atoi(argv[3+num_hostports*2]);
	// how long the clients should measure for, in seconds
	unsigned dur = atoi(argv[3+num_hostports*2+1]);
	if ((num_ctrl_socks = get_ctrl_socks(num_hostports, &argv[3], ctrl_socks)) != num_hostports) {
		fprintf(stderr, "Unable to open all sockets\n");
		ret = -1;
		goto cleanup;
	}
	if (!auth_ctrl_socks(num_ctrl_socks, ctrl_socks)) {
		ret = -1;
		goto cleanup;
	}
	if (!connect_target_all(num_ctrl_socks, ctrl_socks, fp, num_conns)) {
		ret = -1;
		goto cleanup;
	}
	if (!start_measurements(num_ctrl_socks, ctrl_socks, dur)) {
		fprintf(stderr, "Error starting all measurements\n");
		ret = -1;
		goto cleanup;
	}
	while (read_response(ctrl_socks[0], resp_buf, READ_BUF_LEN, &resp_time)) {
		printf("%ld.%06d %s", resp_time.tv_sec, resp_time.tv_usec, resp_buf);
	}
cleanup:
	for (int i = 0; i < num_ctrl_socks; i++) {
		printf("Closing sock=%d\n", ctrl_socks[i]);
		close(ctrl_socks[i]);
	}
end:
	return ret;
}
