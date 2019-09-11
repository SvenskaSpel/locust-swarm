# Swarm

Swarm is a tool for running locust in a distributed fashion on a set of load generator slaves. It also has basic support for jmeter.

Swarm supports [locust-extensions](https://github.com/SvenskaSpel/locust-extensions), allowing you to do things like RPS limiting in a distributed setting.

## Installation

Install from package repository

```
pip install locust-swarm
```

Install from source

```
git clone <this repo>
pip install -e locust-swarm/
```

Swarm uses SSH to launch remote processes and SSH tunnels for communication, so your first step should be to ensure you can access the slaves over ssh.

## Detailed help

```
swarm -h
```

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