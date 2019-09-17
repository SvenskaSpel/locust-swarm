import sys
import psutil
import subprocess
import logging
import os
import time
import argparse
from datetime import datetime, timezone
import atexit
import signal
import socket
import re
import locust_plugins


def main():
    parser = argparse.ArgumentParser(
        description="A tool for running locust/jmeter in a distributed fashion.",
        epilog="Any parameters not listed here are forwarded to locust unmodified, so go ahead and use things like -c, -r, --host, ...",
    )
    parser.add_argument("-f", type=str, dest="testplan")
    parser.add_argument("-t", type=str, dest="run_time")
    parser.add_argument("--processes-per-loadgen", type=int, default=4)
    parser.add_argument("--loadgens", type=int, default=2)
    parser.add_argument("--loadgen-list", type=str, default=os.environ.get("LOADGEN_LIST"))
    parser.add_argument("-L", type=str, dest="loglevel")
    parser.add_argument("--port", type=str, default="5557")
    parser.add_argument("--jmeter", action="store_true")
    parser.add_argument("--jmeter-gui", action="store_true")

    args, unrecognized_args = parser.parse_known_args()

    if args.jmeter_gui:
        args.jmeter = True
        args.loadgens = 0

    if args.loadgen_list is None:
        parser.error("No loadgens specified on command line (--loadgen-list) or env var (LOADGEN_LIST)")

    if not args.jmeter:
        if not args.run_time:
            parser.error("Run time (-t) not specified. This is mandatory when running locust.")
        client_count = None
        for i, argument in enumerate(unrecognized_args):
            if argument == "-c":
                client_count = int(unrecognized_args[i + 1])
        if not client_count:
            parser.error("Client count (-c) not specified. This is mandatory when running locust.")

    if args.testplan is None:
        if args.jmeter:
            args.testplan = "testplan.jmx"
        else:
            args.testplan = "locustfile.py"

    testplan = args.testplan
    testplan_filename = os.path.split(testplan)[1]
    run_time = args.run_time
    port = int(args.port)
    processes_per_loadgen = args.processes_per_loadgen
    loadgens = args.loadgens
    slave_process_count = processes_per_loadgen * loadgens

    server_list = args.loadgen_list.split(",")

    slaves = []

    logging.basicConfig(
        format="%(asctime)s,%(msecs)d %(levelname)-4s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
        level=logging.INFO,
    )

    if args.loglevel:
        logging.getLogger().setLevel(args.loglevel.upper())

    try:
        subprocess.check_output(f"ssh -o LogLevel=error -o BatchMode=yes {server_list[0]} true", shell=True)
        if args.jmeter:
            subprocess.check_output(
                f"ssh -o LogLevel=error -o BatchMode=yes {os.environ['JMETER_MASTER']} true", shell=True
            )
    except Exception:
        logging.error(
            "Error ssh:ing to load generators. Maybe you dont have permission to log on to them? Or your ssh key requires a password? (in that case, use ssh-agent)"
        )
        raise

    signal.signal(signal.SIGTERM, sigHandler)

    while is_port_in_use(port):
        port += 2

    slaves = get_available_servers_and_lock_them(loadgens, server_list)
    slave_procs = []

    start_time = datetime.now(timezone.utc)

    atexit.register(cleanup, slaves, args)

    if args.jmeter:
        JMETER_GRAFANA_URL = os.environ["JMETER_GRAFANA_URL"]
        jmeter_params = " -t " + testplan_filename + " " + " ".join(unrecognized_args)
        if args.jmeter_gui:
            check_output("/usr/local/bin/jmeter" + jmeter_params)
            exit(0)
        else:
            master_command = [
                "ssh",
                "-q",
                os.environ["JMETER_MASTER"],
                f"nohup bash -c 'jmeter/bin/jmeter -n -R {f':{port},'.join(slaves)}:{port} -Jjmeterengine.nongui.port=0 {jmeter_params}'",
            ]
        try:
            check_output(f"ssh -q {os.environ['JMETER_MASTER']} pgrep -c -u \\$USER java")
            raise Exception("Master was busy running another jmeter test. Bailing out!")
            # check_output(f"ssh -q {os.environ['JMETER_MASTER']} pkill -9 -u \\$USER java &>/dev/null || true")
        except subprocess.CalledProcessError:
            logging.debug("There was no jmeter master running, great.")

        for slave in slaves:
            check_output(f"scp -q load_profile.csv {slave}:")
            # this should not really be needed, but we do it to be extra sure nothing else is running
            check_output(f"ssh -q {slave} pkill -9 -u \\$USER java || true")
            cmd = f'''ssh -q {slave} "nohup bash -lc 'jmeter/bin/jmeter-server -Jserver={slave} -Jjava.server.rmi.ssl.disable=true -Jserver_port={port} -Jsample_variables=server {" ".join(unrecognized_args)}'"'''
            logging.debug("Slave: " + cmd)
            slave_procs.append(subprocess.Popen(cmd, shell=True))

        time.sleep(3)
        print("All jmeter slaves started")
        check_output(f"scp -q {{{testplan},load_profile.csv}} {os.environ['JMETER_MASTER']}:")
        log_folder = f"logs/{start_time.strftime('%Y-%m-%d-%H.%M')}"
        check_output(f"ssh -q {os.environ['JMETER_MASTER']} mkdir -p {log_folder}")
        # upload an extra copy of test plan & load profile to log folder, just for keeping track of previous runs:
        check_output(f"scp -q {{{testplan},load_profile.csv}} {os.environ['JMETER_MASTER']}:{log_folder}")

    else:
        os.environ["LOCUST_RUN_ID"] = start_time.isoformat()

        master_command = [
            "locust",
            "--master",
            "--master-bind-port",
            str(port),
            "--master-bind-host=127.0.0.1",  # this avoids MacOS popups about opening firewall for python
            "--expect-slaves",
            str(slave_process_count),
            "--no-web",
            "-f",
            testplan,
            "-t",
            run_time,
            "--exit-code-on-error",
            "0",  # return zero even if there is a failed sample (locust default is to fail then)
            *unrecognized_args,
        ]

    logging.info(f"launching master: {' '.join(master_command)}")

    master_start_time = datetime.now()

    master_proc = subprocess.Popen(master_command)

    locust_env_vars = []

    if not args.jmeter:
        for varname in os.environ:
            if varname.startswith("LOCUST_") or varname.startswith("PG"):
                if varname == "LOCUST_RPS":
                    # distribute the rps over the locust slave processes
                    # when client count < slave_process count, not all locust processes will get a client,
                    # so use the minium of the two when distributing rps.
                    locust_env_vars.append(
                        f'LOCUST_RPS="{float(os.environ[varname])/min(slave_process_count, client_count)}"'
                    )
                else:
                    locust_env_vars.append(f'{varname}="{os.environ[varname]}"')

        for slave in slaves:
            # fail early if master has already terminated
            check_proc(master_proc)

            # upload test plan and any other files in the current directory
            check_output(f"rsync -qr * {slave}:")

            # upload locust-extensions
            check_output(f"rsync -qr {locust_plugins.__path__[0]} {slave}:")

            port_forwarding_parameters = ["-R", f"{port}:localhost:{port}", "-R", f"{port+1}:localhost:{port+1}"]

            for i in range(args.processes_per_loadgen):
                cmd = " ".join(
                    [
                        "ssh",
                        "-q",
                        *port_forwarding_parameters,
                        slave,
                        "'",
                        *locust_env_vars,
                        "locust",
                        "--slave",
                        "--master-port",
                        str(port),
                        "--no-web",
                        "-f",
                        testplan_filename,
                        "'",
                    ]
                )

                if i == 0:
                    logging.info("First slave: " + cmd)
                else:
                    logging.debug("Slave: " + cmd)

                slave_procs.append(subprocess.Popen(cmd, shell=True))
                port_forwarding_parameters = []  # only first ssh session should do port forwarding

    # check that slave procs didnt immediately terminate for some reason
    for i in range(3):
        time.sleep(0.5)
        for proc in slave_procs:
            check_proc(proc)

    while True:
        try:
            code = master_proc.wait(timeout=10)
            break
        except subprocess.TimeoutExpired:
            pass
        for proc in slave_procs:
            check_proc(proc)

    if args.jmeter:
        # jmeter (unlike locust with its reporter.py) doesnt output a link to its report so we do it from here

        host_arg = list(filter(lambda k: "host=" in k, unrecognized_args))

        if host_arg:
            host_with_protocol = host_arg[0].split("=")[1]
            application = re.sub(r"http[s]*://", "", host_with_protocol)
        else:
            # if host name is not explicitly set, then we cant know which application jmeter will log to, so dont try to filter
            application = "All"

        logging.info(
            f"Report: {JMETER_GRAFANA_URL}&var-application={application}&var-send_interval=5&from={int(master_start_time.timestamp()*1000)}&to={int((time.time())*1000)}\n"
        )

    logging.info(f"Load gen master process finished (return code {code})")
    sys.exit(code)


def is_port_in_use(_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("localhost", _port)) == 0


def check_output(command):
    logging.debug(command)
    logging.debug(subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).rstrip().decode())


def check_proc(process):
    if process.poll() is not None:
        logging.error(f"{process.args} finished unexpectedly with return code {process.returncode}")
        sys.exit(1)


def get_available_servers_and_lock_them(server_count, server_list):
    if server_count == 0:
        return []
    while True:
        available_servers = []
        for server in server_list:
            if check_and_lock_server(server):
                available_servers.append(server)
            if len(available_servers) == server_count:
                return available_servers
        logging.info("Didnt get enough servers. Will try again...")
        available_servers = []
        time.sleep(25)


def check_and_lock_server(server):
    # a server is considered busy if it is either running a locust/jmeter process or
    # is "locked" by a sleep command with somewhat unique syntax.
    # the regex uses a character class ([.]) to avoid matching with the pgrep command itself
    check_command = f"ssh -o LogLevel=error {server} \"pgrep -u \\$USER -f '^sleep 1 19|[l]ocust --slave|[j]meter/bin/ApacheJMeter.jar' && echo busy || (echo available && sleep 1 19)\""

    logging.debug(check_command)
    p = subprocess.Popen(check_command, stdout=subprocess.PIPE, shell=True)

    line = None
    while p.poll() is None:
        line = p.stdout.readline().decode().strip()
        if line == "available":
            logging.debug(f"found available slave {server}")
            return True
        if line == "busy":
            logging.debug(f"found busy slave {server}")
            return False

    raise Exception(
        f'could not determine if slave {server} was busy!? check command must have failed to return "available" or "busy". Maybe try it manually: {check_command}'
    )


def cleanup(slaves, args):  # pylint: disable=W0612
    logging.debug("cleanup started")
    procs = psutil.Process().children()
    for p in procs:
        logging.debug(f"killing subprocess {p}")
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=3)
    for server in slaves:
        if args.jmeter:
            check_output(f"ssh -q {server} pkill -9 -u \\$USER -f jmeter/bin/ApacheJMeter.jar || true")
        else:
            check_output(f'ssh -q {server} pkill -9 -u \\$USER -f "locust --slave"\' || true')
    logging.debug("cleanup complete")


# ensure atexit handler gets called even if we get a signal (typically when terminating the debugger)
def sigHandler(_signo, _frame):
    sys.exit(0)
