import logging
import socket
import subprocess
import sys
import time

import psutil

import locust_plugins


def is_port_in_use(_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("localhost", _port)) == 0


def check_output(command):
    logging.debug(command)
    try:
        subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logging.error(e.output.decode().strip())
        raise


def check_output_multiple(list_of_commands):
    running_procs = []
    for command in list_of_commands:
        logging.debug(command)
        running_procs.append(subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT))

    while running_procs:
        for proc in running_procs:
            retcode = proc.poll()
            if retcode is not None:  # Process finished.
                running_procs.remove(proc)
                if retcode != 0:
                    raise Exception(f"Bad return code {retcode} from command: {proc.args}")
                break
            else:  # No process is done, wait a bit and check again.
                time.sleep(0.1)
                continue


def check_proc_running(process):
    retcode = process.poll()
    if retcode is not None:
        raise subprocess.CalledProcessError(retcode, process.args)


def get_available_servers_and_lock_them(server_count, server_list):
    attempts = 0
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
        attempts += 1
        if attempts > 5:
            raise Exception("Never found enough servers :(")


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
            check_output(f"ssh -q {server} 'kill -9 $(pgrep -u $USER -f \"[j]meter/bin/ApacheJMeter.jar\")' || true")
        else:
            check_output(f"ssh -q {server} bash -c 'pkill -9 -u $USER -f \"locust --slave\" || true'")
    logging.debug("cleanup complete")


def start_locust_processes(slave, port, processes_per_loadgen, locust_env_vars, testplan_filename):
    # upload test plan and any other files in the current directory
    check_output(f"rsync -qr * {slave}:")
    # upload locust-extensions
    check_output(f"rsync -qr {locust_plugins.__path__[0]} {slave}:")
    port_forwarding_parameters = ["-R", f"{port}:localhost:{port}", "-R", f"{port+1}:localhost:{port+1}"]
    procs = []
    for i in range(processes_per_loadgen):
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

        procs.append(subprocess.Popen(cmd, shell=True))
        port_forwarding_parameters = []  # only first ssh session should do port forwarding
    return procs


def start_jmeter_process(slave, port, unrecognized_args):
    check_output(f"scp -q load_profile.csv {slave}:")
    # this should not really be needed, but we do it to be extra sure nothing else is running
    check_output(f"ssh -q {slave} pkill -9 -u \\$USER java || true")
    cmd = f'''ssh -q {slave} "nohup bash -lc 'jmeter/bin/jmeter-server -Jserver={slave} -Jjava.server.rmi.ssl.disable=true -Jserver_port={port} -Jsample_variables=server {" ".join(unrecognized_args)}'"'''
    logging.debug("Slave: " + cmd)
    return subprocess.Popen(cmd, shell=True)


# ensure atexit handler gets called even if we get a signal (typically when terminating the debugger)
def sig_handler(_signo, _frame):
    sys.exit(0)
