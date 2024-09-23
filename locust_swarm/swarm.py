try:
    import svs_locust
except ModuleNotFoundError:
    # svs-locust is a library that is only used internally at Svenska Spel, please ignore it
    # We need to import it here to get some variables and the path to the installed package
    pass
import atexit
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime, timezone

import configargparse
import locust.util.timespan
import psutil

from locust_swarm._version import version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class LocustTomlConfigParser(configargparse.TomlConfigParser):
    def parse(self, stream):
        try:
            config = tomllib.loads(stream.read())
        except Exception as e:
            raise configargparse.ConfigFileParserException(f"Couldn't parse TOML file: {e}")

        # convert to dict and filter based on section names
        result = OrderedDict()

        for section in self.sections:
            data = configargparse.get_toml_section(config, section)
            if data:
                for key, value in data.items():
                    if isinstance(value, list):
                        result[key] = value
                    elif value is None:
                        pass
                    else:
                        result[key] = str(value)
                break

        return result


logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-4s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)

parser = configargparse.ArgumentParser(
    # swarm is compatible with locust config files, but locust is not necessarily compatible
    # with swarm config files (it will give an error on swarm-specific settings), so we enable both
    default_config_files=[
        "~/.locust.conf",
        "locust.conf",
        "pyproject.toml",
        "~/.swarm.conf",
        "swarm.conf",
    ],
    auto_env_var_prefix="LOCUST_",
    formatter_class=configargparse.RawDescriptionHelpFormatter,
    config_file_parser_class=configargparse.CompositeConfigParser([
        LocustTomlConfigParser(["tool.locust"]),
        configargparse.DefaultConfigFileParser,
    ]),
    description="""A tool for automating distributed locust runs using ssh.

Example: swarm -f test.py --loadgen-list loadgen1.domain.com,loadgen2.domain.com --users 50""",
    epilog="""Any parameters not listed here are forwarded to locust master unmodified, so go ahead and use things like --users, --host, --run-time, ...

Swarm config can also be set using config file (~/.locust.conf, locust.conf, pyproject.toml, ~/.swarm.conf or swarm.conf).
Parameters specified on command line override env vars, which in turn override config files.""",
    add_config_file_help=False,
    add_env_var_help=False,
)

parser.add_argument(
    "-f",
    "--locustfile",
    type=str,
)
parser.add_argument(
    "--headless",
    action="store_true",
    dest="ignore_this",
    help=configargparse.SUPPRESS,
)
parser.add_argument(
    "--loadgen-list",
    type=str,
    required=True,
    help="A comma-separated list of ssh servers on which to launch locust workers",
)
parser.add_argument(
    "--loadgens",
    "-l",
    type=int,
    default=-1,
    help="Number of servers to run locust workers on. Defaults to -1, meaning all of them.",
)
parser.add_argument(
    "--processes-per-loadgen",
    "-p",
    type=int,
    default=0,
    help=configargparse.SUPPRESS,
)
parser.add_argument(
    "--processes",
    type=int,
    default=4,
    help="This is passed on to locust unchanged and determines the number of worker processes per load generator.",
)

parser.add_argument(
    "--selenium",
    action="store_true",
    default=False,
    help="Start selenium server on load gens for use with locust-plugins's WebdriverUser",
)
parser.add_argument(
    "--playwright",
    action="store_true",
    default=False,
    help="Set LOCUST_PLAYWRIGHT env var for workers",
    env_var="LOCUST_PLAYWRIGHT",
)
parser.add_argument(
    "--test-env",
    type=str,
    default="",
    help="Pass LOCUST_TEST_ENV to workers (in case your script needs it *before* argument parsing)",
    env_var="LOCUST_TEST_ENV",
)
parser.add_argument(
    "--loglevel",
    "-L",
    type=str,
    help="Use DEBUG for tracing issues with load gens etc",
)
parser.add_argument("--port", type=str, default="5557")
parser.add_argument(
    "--remote-master",
    type=str,
    help="An ssh server to use as locust master (default is to run the master locally). This is useful to prevent interrupting the load test if your workstation gets disconnected/goes to sleep.",
)
parser.add_argument(
    "--exit-timeout",
    type=int,
    default=31,
    help=configargparse.SUPPRESS,
)
parser.add_argument(
    "-t",
    "--run-time",
    help=configargparse.SUPPRESS,
    env_var="LOCUST_RUN_TIME",
)
parser.add_argument(
    "-i",
    "--iterations",
    help=configargparse.SUPPRESS,
    type=int,
    env_var="LOCUST_ITERATIONS",
    default=0,
)
parser.add_argument(
    "--extra-files",
    nargs="+",
    default=[],
    help="A list of extra files or directories to upload. Space-separated, e.g. --extra-files testdata.csv *.py my-directory/",
)
parser.add_argument(
    "--skip-plugins",
    action="store_true",
    default=False,
    help=configargparse.SUPPRESS,
)
parser.add_argument(
    "--upload-plugins",
    action="store_true",
    default=False,
    help="Upload locust-plugins to load gens (useful if you are developing locust-plugins)",
)
parser.add_argument(
    "--timescale",
    action="store_true",
    default=False,
    help="Explicitly enable timescale plugin on master/workers nodes",
)

parser.add_argument(
    "--version",
    "-V",
    action="version",
    help="Show program's version number and exit",
    version=f"%(prog)s {version}",
)

args, unrecognized_args = parser.parse_known_args()
master_proc = None


def is_port_in_use(portno: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("localhost", portno)) == 0


def check_output(command):
    logging.debug(command)
    try:
        subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, executable="/bin/bash")
    except subprocess.CalledProcessError as e:
        logging.error(f"command failed: {command}")
        logging.error(e.output.decode().strip())
        if master_proc:
            master_proc.kill()
        raise


def check_output_multiple(list_of_commands):
    running_procs = []
    for command in list_of_commands:
        logging.debug(command)
        running_procs.append(subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT))

    while running_procs:
        for process in running_procs:
            retcode = process.poll()
            if retcode is not None:  # Process finished.
                running_procs.remove(process)
                if retcode != 0:
                    raise Exception(f"Bad return code {retcode} from command: {process.args}")
                break
            else:  # No process is done, wait a bit and check again.
                time.sleep(0.1)
                continue


def check_proc_running(process):
    retcode = process.poll()
    if retcode is not None:
        raise subprocess.CalledProcessError(retcode, process.args)


def check_and_lock_server(server):
    # a server is considered busy if it is either running a locust process or
    # is "locked" by a sleep command with somewhat unique syntax.
    # the regex uses a character class ([.]) to avoid matching with the pgrep command itself
    check_command = f"ssh -o LogLevel=error {server} \"pgrep -f '^sleep 1 19|[l]ocust --worker' && echo busy || (echo available && sleep 1 19)\""

    logging.debug(check_command)
    p = subprocess.Popen(check_command, stdout=subprocess.PIPE, shell=True)

    line = None
    while p.poll() is None:
        line = p.stdout.readline().decode().strip()
        if line == "available":
            logging.debug(f"available load generator {server}")
            return True
        if line == "busy":
            logging.debug(f"busy load generator {server}")
            return False

    raise Exception(
        f'could not determine if loadgen {server} was busy!? check command must have failed to return "available" or "busy". Maybe try it manually: {check_command}'
    )


def cleanup(server_list):
    logging.debug("cleanup started")
    procs = psutil.Process().children()
    for p in procs:
        logging.debug(f"killing subprocess {p}")
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            pass
    psutil.wait_procs(procs, timeout=3)
    check_output_multiple(
        f"ssh -q {server} 'pkill -9 -u $USER -f \"locust --worker\"' 2>&1 | grep -v 'No such process' || true"
        for server in server_list
    )
    logging.debug("cleanup complete")


def upload(server):
    files = args.extra_files.copy()
    if args.upload_plugins:
        try:
            files.append(os.path.dirname(svs_locust.__file__))
        except NameError:
            pass

        try:
            import locust_plugins

            files.append(os.path.dirname(locust_plugins.__file__))
        except ModuleNotFoundError:
            logging.error("locust-plugins wasnt installed")
            sys.exit(1)

    if not files:
        return

    if len(files) > 1:
        filestr = "{" + ",".join(files) + "}"
    else:
        filestr = files[0]

    if args.loglevel and args.loglevel.upper() == "DEBUG":
        check_output(f"shopt -s failglob; rsync -vvrtl --exclude __pycache__ --exclude .mypy_cache {filestr} {server}:")
    else:
        check_output(f"rsync -qrtl --exclude __pycache__ --exclude .mypy_cache {filestr} {server}:")


def start_worker_process(server, port):
    upload(server)

    if args.selenium:
        check_output(f"ssh -q {server} 'rm -rf /tmp/.com.google.Chrome.*' || true")
        selenium_cmd = f"ssh -q {server} 'pkill -f \"^java -jar selenium-server-4.\"; java -jar selenium-server-4.0.0.jar standalone > selenium.log 2>&1' &"
        logging.info(selenium_cmd)
        subprocess.Popen(
            selenium_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        time.sleep(0.2)
        check_output(
            f"ssh -q {server} 'pgrep -f \"^java -jar selenium-server-4.\"' # check to see selenium actually launched"
        )
        time.sleep(1)

    if args.playwright:
        check_output(f"ssh -q {server} 'rm -rf tmp/* && pkill playwright.sh || true'")

    if args.remote_master:
        port_forwarding_parameters = []
        ensure_remote_kill = []
        nohup = ["sudo", "-E", "nohup"]
        master_parameters = ["--master-host " + args.remote_master]

    else:
        port_forwarding_parameters = [
            "-R",
            f"{port}:localhost:{port}",
            "-R",
            f"{port + 1}:localhost:{port + 1}",
        ]
        ensure_remote_kill = ["& read; kill -9 $!"]
        nohup = []
        master_parameters = []

    if args.loglevel:
        master_parameters.append("-L")
        master_parameters.append(args.loglevel)

    procs = []
    extra_env = ["PYTHONUNBUFFERED=1"]

    if args.playwright:
        extra_env.append("LOCUST_PLAYWRIGHT=1")
    if args.test_env:
        extra_env.append("LOCUST_TEST_ENV=" + args.test_env)

    timescale_args = []
    if args.timescale:
        timescale_args = [
            "--timescale",
        ]

    cmd = " ".join([
        "ssh",
        "-q",
        *port_forwarding_parameters,
        server,
        "'",
        *extra_env,
        *nohup,
        "locust",
        "--worker",
        "--processes",
        str(args.processes),
        "--master-port",
        str(port),
        *master_parameters,
        *timescale_args,
        "--headless",
        "--expect-workers-max-wait",
        "30",
        "-f",
        "-",
        *ensure_remote_kill,
        "'",
    ])

    logging.info("workers started " + cmd)
    procs.append(
        subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # dont forward CTRL-C, let locust quit the workers instead
        )
    )
    return procs


# ensure atexit handler gets called even if we get a signal (typically when terminating the debugger)
def sig_handler(_signo, _frame):
    sys.exit(0)


def main():
    global master_proc
    if args.loglevel:
        logging.getLogger().setLevel(args.loglevel.upper())

    locustfile = args.locustfile or "locustfile.py"

    port = int(args.port)
    if args.processes_per_loadgen:
        parser.error(
            f"--processes-per-loadgen has been removed in favour of locusts native --processes parameter (you had it set to {args.processes_per_loadgen})"
        )
    if args.skip_plugins:
        parser.error(
            "--skip-plugins has been removed, the default is now NOT to upload plugins (but you can enable it with --upload-plugins)"
        )
    loadgen_list = args.loadgen_list.split(",")
    if args.loadgens < 0:
        args.loadgens = len(loadgen_list)
    worker_process_count = args.processes * args.loadgens

    try:
        subprocess.check_output(
            f"ssh -o LogLevel=error -o BatchMode=yes {loadgen_list[0]} true 2>&1",
            shell=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as e:
        if "Host key verification failed." in str(e.stdout):
            # add all loadgens to known hosts
            for loadgen in loadgen_list:
                subprocess.check_output(
                    f"ssh -o LogLevel=error -o BatchMode=yes -o StrictHostKeyChecking=accept-new {loadgen} true",
                    shell=True,
                )
        else:
            logging.error(
                f"Error ssh:ing to loadgen ({loadgen_list[0]}). Maybe you dont have permission to log on to them? Or your ssh key requires a password? (in that case, use ssh-agent)"
            )
            raise

    signal.signal(signal.SIGTERM, sig_handler)

    while is_port_in_use(port):
        port += 2

    def get_available_servers_and_lock_them():
        attempts = 0
        check_interval = 25
        while True:
            available_servers = []
            for server in loadgen_list:
                if check_and_lock_server(server):
                    available_servers.append(server)
                if len(available_servers) == args.loadgens:
                    return available_servers
            logging.info(
                f"Only found {len(available_servers)} available servers, wanted {args.loadgens}. Will try again in {check_interval} seconds..."
            )
            available_servers = []
            time.sleep(check_interval)
            attempts += 1
            if attempts > 5:
                raise Exception("Never found enough servers :(")

    server_list = get_available_servers_and_lock_them()

    worker_procs = []
    extra_env = []
    start_time = datetime.now(timezone.utc)
    atexit.register(cleanup, server_list)

    if args.remote_master:
        logging.info("Some argument passing will not work with remote master (broken since 2.0)")
        env_vars = ["PYTHONUNBUFFERED=1"]
        if args.test_env:
            env_vars.append("LOCUST_TEST_ENV=" + args.test_env)
        ssh_command = ["ssh", "-q", args.remote_master, "'", *env_vars, "sudo", "-E", "nohup"]
        bind_only_localhost = []
        ssh_command_end = ["'"]
        check_output(f"ssh -q {args.remote_master} 'pkill -9 -u $USER locust' || true")
        upload(args.remote_master)
    else:
        # avoid firewall popups by only binding localhost if running local master (ssh port forwarding):
        bind_only_localhost = ["--master-bind-host=127.0.0.1"]
        ssh_command = []
        ssh_command_end = []

    run_time_arg = ["--run-time=" + args.run_time] if args.run_time else []

    if args.iterations:
        unrecognized_args.append("-i")
        unrecognized_args.append(str(int(args.iterations / worker_process_count)))
        if args.iterations % worker_process_count:
            logging.warning(
                f"Iteration limit was not evenly divisible between workers, so you will end up with {args.iterations % worker_process_count} fewer iterations than requested"
            )

    if args.loglevel:
        unrecognized_args.append("-L")
        unrecognized_args.append(args.loglevel)

    if args.playwright:
        extra_env.append("LOCUST_PLAYWRIGHT=1")

    timescale_args = []
    if args.timescale:
        timescale_args = [
            "--timescale",
        ]

    master_command = [
        *ssh_command,
        *extra_env,
        "locust",
        "--master",
        "--master-bind-port",
        str(port),
        *bind_only_localhost,
        "--expect-workers",
        str(worker_process_count),
        "--expect-workers-max-wait",
        "60",
        *timescale_args,
        "--headless",
        "-f",
        locustfile,
        *run_time_arg,
        "--exit-code-on-error",
        "0",  # return zero even if there were failed samples (locust default is to return 1)
        *unrecognized_args,
        *ssh_command_end,
    ]

    logging.info(f"launching master: {' '.join(master_command)}")
    master_proc = subprocess.Popen(" ".join(master_command), shell=True)

    for server in server_list:
        # fail early if master has already terminated
        check_proc_running(master_proc)
        worker_procs.extend(start_worker_process(server, port))

    # check that worker procs didnt immediately terminate for some reason (like invalid parameters)
    try:
        time.sleep(5)
    except KeyboardInterrupt:  # dont give strange callstack if interrupted
        sys.exit(1)

    for proc in worker_procs:
        check_proc_running(proc)

    logging.debug("all workers seem to have launched fine")

    start_time = time.time()
    max_run_time = locust.util.timespan.parse_timespan(args.run_time) if args.run_time else float("inf")

    # wait for test to complete
    while True:
        try:
            code = master_proc.wait(timeout=10)
            break
        except subprocess.TimeoutExpired:
            if max_run_time + args.exit_timeout < time.time() - start_time:
                logging.error(
                    f"Locust exceeded the run time specified ({max_run_time}) by more than 30 seconds, giving up"
                )
                master_proc.send_signal(1)
        except KeyboardInterrupt:
            pass
        # ensure worker procs didnt die before master
        for proc in worker_procs:
            try:
                check_proc_running(proc)
            except subprocess.CalledProcessError as e:
                try:
                    code = master_proc.wait(timeout=10)
                    break
                except subprocess.TimeoutExpired:
                    logging.error(
                        f"worker proc finished unexpectedly with ret code {e.returncode} (and master was still running)"
                    )
                    raise

    logging.info(f"Load gen master process finished (return code {code})")
    sys.exit(code)
