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
make build
```

```bash
make bash
```

The above two commands will start the build and bash process of the Docker environment to execute your GPT Mission Planner.
From within the Docker container, execute `make run` to request your first mission plan.

## Current Process
Currently, this doesn't connect to a robot to feed in the mission plan that comes out of GPT.
To access the mission plan, simply install `netcat` on your host running this Docker container to view the XML plan.
```bash
make server
```
Make sure to run this **first** before running the mission planner (`make run`). 

This will kick off a `netcat` server to receive the mission plan intended to be sent to the robot.

## Example Execution:
```bash
$ make build
docker build . -t gpt-mission-planner --target local
[+] Building 14.2s (11/11) FINISHED                                                                                                                            docker:desktop-linux
 => [internal] load build definition from Dockerfile                                                                                                                           0.0s
 => => transferring dockerfile: 1.47kB                                                                                                                                         0.0s
 => [internal] load .dockerignore         
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

On the host machine running the listening server:
```bash
$ make server
nc -l 0.0.0.0 12345
<?xml version="1.0" encoding="UTF-8"?>
<TaskTemplate xmlns="https://robotics.ucmerced.edu/task"
...
```