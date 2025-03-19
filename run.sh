#!/bin/bash

HOST="0.0.0.0"
PORT="8000"

while getopts h:p: flag
do
    case "${flag}" in
        h) HOST=${OPTARG};;
        p) PORT=${OPTARG};;
    esac
done

echo "Running FastAPI on host $HOST and port $PORT"
uvicorn app:app --host $HOST --port $PORT --reload
