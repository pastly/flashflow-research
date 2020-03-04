=====================================
RUNNING A SHADOW FLASHFLOW EXPERIMENT
=====================================

Step 1: install needed Rust program
-------

cargo install cbindgen

If unable to communicate with the Internet well enough to get it, perform this
step on koios2 instead (as it has more complete access to the Internet than the
rest of the lab machines as of 19 Aug 2019). It'll be installed in
~/.cargo/bin, which is shared on all our lab machines, so it'll be available on
all machines.

Step 1.1: add ~/.cargo/bin to your PATH
---------

Add something like the following to your ~/.bash_profile.

export PATH="$HOME/.cargo/bin:$PATH"

Remember it won't apply to existing shells, so either source ~/.bash_profile or
close/reopen all necessary shells.

Step 2: get flashflow code, compile
-------

Into some directory, probably on your /scratch, clone
mtraudt/purple-hurtz-code.git from rhea. For example,

git clone git@rhea:mtraudt/purple-hurtz-code.git

Once you have the code, run make.

Compiling the Rust library will require downloading some crates on the
first compile. If unable to communicate with the Internet well enough to
do so, perform this step on koios2 first (as it can download the necessary
libraries and will cache them in ~/.cargo, which is available on all machines)
and then start this step over on the actually desired machine. You will know
that you're unable to talk to the Internet very well by either the cbindgen
step taking more than 1 minute or by the "cargo build" step making no progress
on downloading.

A successful compile should leave you with a flashflow executable and
libflashflow.so. Running flashflow should output brief usage information.

Note the location of libflashflow.so

Step 2.1: get Tor code, compile
---------

Into some directory on your /scratch, clone mtraudt/tor-securebw.git.
For example,

git clone git@rhea:mtraudt/tor-securebw.git

Checkout the appropriate branch.

git checkout echo-server4-v0.3.5.7

Verify the latest commit is as follows.

commit 07b8db027526d8862362722609248e2db9683ce6
Author: Matt Traudt <sirmatt@ksu.edu>
Date:   Mon Aug 19 07:34:48 2019 -0400

    Log SPEEDTESTING timestamp with bw

Do a clean rebuild and install of shadow-plugin-tor while pointing it at
this directory.

Step 3: get shadow config directory
-------

I tar'ed it up and put it at
/storage/mtraudt/share/shadowtor-0.05-flashflow.tar. Extract it
somewhere, probably your /scratch.

Step 4: edit shadow.config.xml
-------

The <plugin> tag for flashflow at the top needs to point to your
libflashflow.so. Edit the path.

Step 5: run shadow, monitor for issues
-------

Run Shadow. You know how.

All the FlashFlow Tor clients start at 240s. The coordinator starts at 300s.

shadow.data/hosts/ffcoord/stderr-ffcoord.flashflow.1000.log contains the
log output of FlashFlow.

shadow.data/hosts/ffcoord/stdout-ffcoord.flashflow.1000.log contains the
results from FlashFlow.

A quick check for success/fail measurements can be done with

grep -E '(WOOHOO|FAIL)'
shadow.data/hosts/ffcoord/stderr-ffcoord.flashflow.1000.log

If FlashFlow has logged something like the following two lines to
stderr, it is done.

ALLLLLLLL DOOOONNEEEEE
XX success, YY failed, ZZ total

shadow.data/hosts/ffcoord/clients.txt is probably uninteresting. It
lists the known measurer processes.

shadow.data/hosts/ffcoord/fps.txt is the schedule it is following. It
isn't easily readable by humans, especially humans other than me.
