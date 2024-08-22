# How To Run GPT Mission Planner
## GPT Token
Create a file at `~/.gpt/token.env` and add your token in environment variable structure:
```bash
OPENAI_API_TOKEN=<my_token_here>
```

## Docker
NOTE: if running on Mac, ensure you have network mode enabled for this to work. This capability is only available on version 4.29+ of Docker Desktop.
If working in Linux, will work on any version.

```bash
$ make build-image
```

```bash
$ make bash
```

The above two commands will start the build and bash process of the Docker environment to execute your GPT Mission Planner.
From within the Docker container, execute `make run` to request your first mission plan.

## Current Process
Currently, this doesn't connect to a robot to feed in the mission plan that comes out of GPT.
```bash
$ make server
nc -l 0.0.0.0 12345
...
```
Make sure to run this **first** before running the mission planner (`make run`). 

## Example Execution:
On the host machine running a listening server. Make sure the IP/port matches the YAML config file IP/port:
```bash
$ make server
nc -l 0.0.0.0 12345
...
```

```bash
$ make build-image
docker build . -t gpt-mission-planner --target local
...    
...

$ make bash
docker run -it --rm \
        -v ./Makefile:/gpt-mission-planner/Makefile:Z \
        -v ./app/:/gpt-mission-planner/app:Z \
        --env-file ~/.gpt/token.env \
        --net=host \
        gpt-mission-planner \
        /bin/bash
root@linuxkit-965cbccc7c1e:/gpt-mission-planner#

root@linuxkit-965cbccc7c1e:/gpt-mission-planner# make run
python3 ./app/mission_planner.py
Enter the specifications for your mission plan: Take a thermal picture of every other tree on the farm.
File sent successfully.
```