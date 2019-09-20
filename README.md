# Swarm

Swarm is a tool for running [locust](https://github.com/locustio/locust) in a distributed fashion on a set of load generator slaves. It also has basic support for jmeter.

Swarm supports [locust-plugins](https://github.com/SvenskaSpel/locust-plugins), allowing you to do things like RPS limiting in a distributed setting.

## Installation

On the master:

```
pip install locust-swarm
```

On the loadgens:

```
pip install locustio
```

Swarm uses SSH to launch remote processes and SSH tunnels for communication, so you should ensure you can access the slaves over ssh.

## Detailed help

```
swarm -h
```

## Configuration

Any env vars starting with LOCUST_ will be forwarded to the load gen slaves. You can use this to parametrize your locust scripts.

## Example run

This assumes you have env vars like LOADGEN_LIST etc set. Just try running it and you'll get feedback on what is missing.

```
~/git/locust-swarm > swarm -t 10 -c 10  --loadgens 1 --processes-per-loadgen 2 -f examples/locustfile.py -H https://example.com
[2019-09-20 13:46:09,726] lafp-mac-JG5J/INFO/root: Follow test run here: https://grafana/d/qjIIww4Zz/locust?orgId=1&var-testplan=example&from=1568979968805&to=now
[2019-09-20 13:46:09,885] lafp-mac-JG5J/INFO/root: Waiting for slaves to be ready, 0 of 2 connected
[2019-09-20 13:46:10,889] lafp-mac-JG5J/INFO/root: Waiting for slaves to be ready, 0 of 2 connected
[2019-09-20 13:46:11,891] lafp-mac-JG5J/INFO/root: Waiting for slaves to be ready, 0 of 2 connected
[2019-09-20 13:46:12,195] perftest03/INFO/locust.main: Starting Locust 0.11.1
[2019-09-20 13:46:12,195] perftest03/INFO/locust.main: Starting Locust 0.11.1
[2019-09-20 13:46:12,322] lafp-mac-JG5J/INFO/locust.runners: Client 'perftest03_5ac395b244f3497796a6928e218da7ea' reported as ready. Currently 1 clients ready to swarm.
[2019-09-20 13:46:12,323] lafp-mac-JG5J/INFO/locust.runners: Client 'perftest03_09770e3ada2c47138ffabc5b7af1a25f' reported as ready. Currently 2 clients ready to swarm.
[2019-09-20 13:46:12,896] lafp-mac-JG5J/INFO/locust.runners: Sending hatch jobs to 2 ready clients
[2019-09-20 13:46:12,897] lafp-mac-JG5J/INFO/locust.main: Run time limit set to 10 seconds
[2019-09-20 13:46:12,897] lafp-mac-JG5J/INFO/locust.main: Starting Locust 0.11.1
 Name                                                          # reqs      # fails     Avg     Min     Max  |  Median   req/s
--------------------------------------------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------------------------------------------
 Total                                                              0     0(0.00%)                                       0.00

[2019-09-20 13:46:12,916] perftest03/INFO/locust.runners: Hatching and swarming 5 clients at the rate 0.5 clients/s...
[2019-09-20 13:46:12,916] perftest03/INFO/locust.runners: Hatching and swarming 5 clients at the rate 0.5 clients/s...
 Name                                                          # reqs      # fails     Avg     Min     Max  |  Median   req/s
--------------------------------------------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------------------------------------------
 Total                                                              0     0(0.00%)                                       0.00

 Name                                                          # reqs      # fails     Avg     Min     Max  |  Median   req/s
--------------------------------------------------------------------------------------------------------------------------------------------
 POST /authentication/1.0/getResults                                4     0(0.00%)      69      65      76  |      65    0.00
--------------------------------------------------------------------------------------------------------------------------------------------
 Total                                                              4     0(0.00%)                                       0.00

...

[2019-09-20 13:46:22,901] lafp-mac-JG5J/INFO/locust.main: Time limit reached. Stopping Locust.
 Name                                                          # reqs      # fails     Avg     Min     Max  |  Median   req/s
--------------------------------------------------------------------------------------------------------------------------------------------
 POST /authentication/1.0/getResults                               16     0(0.00%)      67      65      76  |      66    1.60
--------------------------------------------------------------------------------------------------------------------------------------------
 Total                                                             16     0(0.00%)                                       1.60

[2019-09-20 13:46:22,919] perftest03/INFO/locust.runners: All locusts hatched: WebsiteUser: 5
[2019-09-20 13:46:22,919] perftest03/INFO/locust.runners: Got quit message from master, shutting down...
[2019-09-20 13:46:22,919] perftest03/INFO/locust.runners: Got quit message from master, shutting down...
[2019-09-20 13:46:22,920] perftest03/INFO/locust.main: Shutting down (exit code 0), bye.
[2019-09-20 13:46:22,920] perftest03/INFO/locust.main: Shutting down (exit code 0), bye.
[2019-09-20 13:46:22,920] perftest03/INFO/locust.main: Cleaning up runner...
[2019-09-20 13:46:22,921] perftest03/INFO/locust.main: Running teardowns...
[2019-09-20 13:46:22,920] perftest03/INFO/locust.main: Cleaning up runner...
[2019-09-20 13:46:22,920] perftest03/INFO/locust.main: Running teardowns...
[2019-09-20 13:46:22,955] lafp-mac-JG5J/INFO/locust.runners: Client 'perftest03_5ac395b244f3497796a6928e218da7ea' quit. Currently 0 clients connected.
[2019-09-20 13:46:22,955] lafp-mac-JG5J/INFO/locust.runners: Client 'perftest03_09770e3ada2c47138ffabc5b7af1a25f' quit. Currently 0 clients connected.

...

[2019-09-20 13:46:23,406] lafp-mac-JG5J/INFO/locust.main: Shutting down (exit code 0), bye.
[2019-09-20 13:46:23,407] lafp-mac-JG5J/INFO/locust.main: Cleaning up runner...
[2019-09-20 13:46:23,911] lafp-mac-JG5J/INFO/locust.main: Running teardowns...
[2019-09-20 13:46:25,093] lafp-mac-JG5J/INFO/root: Report: https://grafana/d/qjIIww4Zz/locust?orgId=1&var-testplan=example&from=1568979968805&to=1568979985806

 Name                                                          # reqs      # fails     Avg     Min     Max  |  Median   req/s
--------------------------------------------------------------------------------------------------------------------------------------------
 POST /authentication/1.0/getResults                               20     0(0.00%)      67      65      76  |      66    1.71
--------------------------------------------------------------------------------------------------------------------------------------------
 Total                                                             20     0(0.00%)                                       1.71

Percentage of the requests completed within given times
 Name                                                           # reqs    50%    66%    75%    80%    90%    95%    98%    99%   100%
--------------------------------------------------------------------------------------------------------------------------------------------
 POST /authentication/1.0/getResults                                20     66     67     68     68     70     76     76     76     76
--------------------------------------------------------------------------------------------------------------------------------------------
 Total                                                              20     66     67     68     68     70     76     76     76     76

2019-09-20:13:46:25,184 INFO [swarm:201] Load gen master process finished (return code 0)
```

As you can tell, the output is a bit chatty. The best way to see your results is using the TimescaleListener and grafana dashboard (see [listeners.py](https://github.com/SvenskaSpel/locust-plugins/blob/master/locust_plugins/listeners.py)). If you do that, then links will automatically be added to the output as seen above.

## Contributions

Contributions are very welcome! 😁

For guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md)

## License

Copyright 2019 AB SvenskaSpel

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.