#include<stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/select.h>
#include <netdb.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <limits.h>

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
get_ctrl_sock(const char *host, const char *port) {
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
		fprintf(stderr, "Could not connect to %s:%s ... ", host, port);
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
auth_ctrl_sock(const int s) {
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
connect_target(const int s, const  char *fp, const unsigned num_conns) {
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
start_measurement(const int s, const unsigned dur) {
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
read_response(const int s, char *buf, const size_t max_len, struct timeval *t) {
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
get_ctrl_socks(const unsigned num_hostports, const char *hostports[], int ctrl_socks[]) {
	for (int i = 0; i < num_hostports; i++) {
		int host_idx = i * 2;
		int port_idx = host_idx + 1;
		int ctrl_sock;
		const char *host = hostports[host_idx];
		const char *port = hostports[port_idx];
		if ((ctrl_sock = get_ctrl_sock(host, port)) < 0) {
			return i;
		}
		fprintf(stderr, "connected to %s:%s\n", host, port);
		ctrl_socks[i] = ctrl_sock;
	}
	return num_hostports;
}

/*
 * provide an array of ctrl_socks and its length. authenticate to each one.
 * returns false if we fail to auth to any tor, otherwise true.
 */
int
auth_ctrl_socks(const int num_ctrl_socks, const int ctrl_socks[]) {
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
connect_target_all(const int num_ctrl_socks, const int ctrl_socks[], const char *fp, const unsigned num_conns_each) {
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
start_measurements(const int num_ctrl_socks, const int ctrl_socks[], const unsigned duration) {
	for (int i = 0; i < num_ctrl_socks; i++) {
		if (!(start_measurement(ctrl_socks[i], duration))) {
			return 0;
		}
	}
	return 1;
}

int
max(const int array[], const int array_len) {
	int the_max = INT_MIN;
	for (int i = 0; i < array_len; i++) {
		the_max = array[i] > the_max ? array[i] : the_max;
	}
	return the_max;
}

int
main(const int argc, const char *argv[]) {
	// all the socks we have to tor client ctrl ports
	int ctrl_socks[MAX_NUM_CTRL_SOCKS];
	// to tell select() all the sockets we care about reading from
	fd_set read_set;
	// the number of ctrl socks we make successfully
	int num_ctrl_socks = 0;
	// stores the return value from select()
	int select_result = 0;
	// tells select() how long to wait before timing out
	struct timeval select_timeout;
	// the return value of this func
	int ret = 0;
	// buffer to store responses from tor clients
	char resp_buf[READ_BUF_LEN];
	// used repeatedly to store the current time for printing
	struct timeval resp_time;
	// relay fingerprint to measure
	const char *fp = argv[1];
	// numer of host+port pairs that are specified on the cmd line
	unsigned num_hostports = atoi(argv[2]);
	if (argc != 3 + num_hostports * 2 + 2) {
		usage();
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
	// to tell select() the max fd we care about
	const int max_ctrl_sock = max(ctrl_socks, num_ctrl_socks);
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

	while (1) {
		FD_ZERO(&read_set);
		for (int i = 0; i < num_ctrl_socks; i++) {
			FD_SET(ctrl_socks[i], &read_set);
		}
		select_timeout.tv_sec = 3;
		select_timeout.tv_usec = 0;
		select_result = select(max_ctrl_sock+1, &read_set, NULL, NULL, &select_timeout);
		if (select_result < 0) {
			perror("Error on select()");
			ret = -1;
			goto cleanup;
		} else if (select_result == 0) {
			fprintf(stderr, "%ld.%06d sec timeout on select().\n", select_timeout.tv_sec, select_timeout.tv_usec);
			//ret = -1;
			goto cleanup;
		}
		for (int i = 0; i< num_ctrl_socks; i++) {
			if (FD_ISSET(ctrl_socks[i], &read_set)) {
				if (!read_response(ctrl_socks[i], resp_buf, READ_BUF_LEN, &resp_time)) {
					fprintf(stderr, "select() said there was something to read on %d, but read zero bytes or had error.\n", ctrl_socks[i]);
					ret = -1;
					goto cleanup;
				}
				printf("%ld.%06d %s", resp_time.tv_sec, resp_time.tv_usec, resp_buf);
			}
		}
	}

cleanup:
	for (int i = 0; i < num_ctrl_socks; i++) {
		fprintf(stderr, "Closing sock=%d\n", ctrl_socks[i]);
		close(ctrl_socks[i]);
	}
end:
	return ret;
}
