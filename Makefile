CONTAINER_NAME := gpt-mission-planner
REPO_NAME := gpt-mission-planner

build: 
	docker build . -t ${CONTAINER_NAME} --target local

build-train: 
	docker build . -t ${CONTAINER_NAME}-train --target train

bash:
	docker run -it --rm \
	-v ./Makefile:/${REPO_NAME}/Makefile:Z \
	-v ./app/:/${REPO_NAME}/app:Z \
	--env-file ~/.gpt/token.env \
	--net=host \
	${CONTAINER_NAME} \
	/bin/bash

run:
	python3 ./app/mission_planner.py

server:
	nc -l 0.0.0.0 12345